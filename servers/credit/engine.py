"""
Rule-based credit risk scoring engine.

Implements a simplified Basel-inspired risk scoring model.
Each rule contributes a weighted score from 0–100.
Final tier mapping: Low / Medium / High / Very High.

In production this would call the bank's internal credit bureau
integration and may incorporate ML model scores alongside rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from servers.accounts.mock_data import ACCOUNTS, CUSTOMERS, generate_transactions


@dataclass
class RiskFactor:
    name: str
    score: float          # 0 (good) → 100 (bad)
    weight: float         # relative weight
    detail: str


@dataclass
class CreditRiskResult:
    customer_id: str
    loan_amount: float
    loan_term_months: int
    weighted_score: float           # 0–100
    risk_tier: str                  # Low / Medium / High / Very High
    recommendation: str
    approved: bool
    max_loan_amount: float
    monthly_payment_estimate: float
    risk_factors: list[RiskFactor] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "loan_amount_requested": self.loan_amount,
            "loan_term_months": self.loan_term_months,
            "risk_score": round(self.weighted_score, 1),
            "risk_tier": self.risk_tier,
            "recommendation": self.recommendation,
            "approved": self.approved,
            "max_loan_amount_eur": self.max_loan_amount,
            "estimated_monthly_payment_eur": round(self.monthly_payment_estimate, 2),
            "risk_factors": [
                {
                    "factor": f.name,
                    "score": round(f.score, 1),
                    "weight": f.weight,
                    "detail": f.detail,
                }
                for f in self.risk_factors
            ],
        }


# ── Scoring rules ─────────────────────────────────────────────────────────────


def _score_kyc(customer: dict) -> RiskFactor:
    status = customer.get("kyc_status", "unknown")
    score_map = {"verified": 0.0, "pending": 50.0, "failed": 100.0, "unknown": 80.0}
    return RiskFactor(
        name="KYC status",
        score=score_map.get(status, 80.0),
        weight=0.25,
        detail=f"KYC status is '{status}'.",
    )


def _score_existing_risk_rating(customer: dict) -> RiskFactor:
    rating = customer.get("risk_rating", "unknown")
    score_map = {"low": 10.0, "medium": 40.0, "high": 80.0, "unknown": 70.0}
    return RiskFactor(
        name="Existing risk rating",
        score=score_map.get(rating, 70.0),
        weight=0.20,
        detail=f"Customer's internal risk rating is '{rating}'.",
    )


def _score_debt_to_income(customer_id: str, loan_amount: float, loan_term_months: int) -> RiskFactor:
    """Estimate monthly income from transaction history and compute DTI."""
    accounts = [acc for acc in ACCOUNTS.values() if acc["customer_id"] == customer_id]
    total_monthly_income = 0.0

    for acc in accounts:
        txs = generate_transactions(acc["account_id"], days=90)
        income = sum(t["amount"] for t in txs if t["category"] == "income")
        total_monthly_income += income / 3  # 90 days → monthly average

    if total_monthly_income <= 0:
        return RiskFactor(
            name="Debt-to-income ratio",
            score=90.0,
            weight=0.25,
            detail="No verifiable income found in transaction history.",
        )

    # Simple annuity estimate: monthly payment
    monthly_rate = 0.05 / 12  # assume 5% APR
    if monthly_rate > 0 and loan_term_months > 0:
        monthly_payment = (
            loan_amount
            * monthly_rate
            * (1 + monthly_rate) ** loan_term_months
            / ((1 + monthly_rate) ** loan_term_months - 1)
        )
    else:
        monthly_payment = loan_amount / max(loan_term_months, 1)

    dti = monthly_payment / total_monthly_income

    if dti < 0.20:
        score, detail = 10.0, f"DTI {dti:.0%} — well within limits."
    elif dti < 0.35:
        score, detail = 35.0, f"DTI {dti:.0%} — acceptable range."
    elif dti < 0.50:
        score, detail = 65.0, f"DTI {dti:.0%} — elevated, approaching limit."
    else:
        score, detail = 90.0, f"DTI {dti:.0%} — exceeds 50% threshold."

    return RiskFactor(name="Debt-to-income ratio", score=score, weight=0.25, detail=detail)


def _score_account_behaviour(customer_id: str) -> RiskFactor:
    """Assess account health: overdrafts, irregularity, balance trend."""
    accounts = [acc for acc in ACCOUNTS.values() if acc["customer_id"] == customer_id]

    if not accounts:
        return RiskFactor(
            name="Account behaviour",
            score=70.0,
            weight=0.15,
            detail="No accounts found to assess behaviour.",
        )

    total_balance = sum(float(acc["balance"]) for acc in accounts)
    restricted = any(acc["status"] == "restricted" for acc in accounts)

    if restricted:
        return RiskFactor(
            name="Account behaviour",
            score=85.0,
            weight=0.15,
            detail="One or more accounts are in restricted status.",
        )
    elif total_balance > 50_000:
        score, detail = 10.0, f"Strong total balance (€{total_balance:,.0f})."
    elif total_balance > 10_000:
        score, detail = 30.0, f"Healthy total balance (€{total_balance:,.0f})."
    elif total_balance > 1_000:
        score, detail = 55.0, f"Moderate total balance (€{total_balance:,.0f})."
    else:
        score, detail = 80.0, f"Low total balance (€{total_balance:,.0f})."

    return RiskFactor(name="Account behaviour", score=score, weight=0.15, detail=detail)


def _score_loan_size(customer_id: str, loan_amount: float) -> RiskFactor:
    """Compare loan size to total assets held at the bank."""
    accounts = [acc for acc in ACCOUNTS.values() if acc["customer_id"] == customer_id]
    total_balance = sum(float(acc["balance"]) for acc in accounts)

    if total_balance <= 0:
        return RiskFactor(
            name="Loan-to-assets ratio",
            score=80.0,
            weight=0.15,
            detail="No assets to compare against loan amount.",
        )

    lta = loan_amount / total_balance

    if lta < 0.25:
        score, detail = 10.0, f"Loan is {lta:.0%} of assets — low exposure."
    elif lta < 0.75:
        score, detail = 35.0, f"Loan is {lta:.0%} of assets — moderate exposure."
    elif lta < 1.5:
        score, detail = 65.0, f"Loan is {lta:.0%} of assets — high exposure."
    else:
        score, detail = 90.0, f"Loan is {lta:.0%} of assets — very high exposure."

    return RiskFactor(name="Loan-to-assets ratio", score=score, weight=0.15, detail=detail)


# ── Public API ────────────────────────────────────────────────────────────────

TIER_THRESHOLDS = [
    (25.0, "Low",       True,  "Approved. Standard terms apply."),
    (50.0, "Medium",    True,  "Conditionally approved. Enhanced monitoring required."),
    (70.0, "High",      False, "Declined. Risk exceeds appetite. Consider a smaller loan or improved financial standing."),
    (float("inf"), "Very High", False, "Declined. Significant risk indicators present."),
]

TIER_MAX_LOAN = {"Low": 100_000.0, "Medium": 50_000.0, "High": 25_000.0, "Very High": 0.0}


def score_customer(customer_id: str, loan_amount: float, loan_term_months: int) -> CreditRiskResult:
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        raise ValueError(f"Customer '{customer_id}' not found.")

    factors = [
        _score_kyc(customer),
        _score_existing_risk_rating(customer),
        _score_debt_to_income(customer_id, loan_amount, loan_term_months),
        _score_account_behaviour(customer_id),
        _score_loan_size(customer_id, loan_amount),
    ]

    weighted_score = sum(f.score * f.weight for f in factors)

    tier, approved, recommendation = "Very High", False, ""
    for threshold, t, a, rec in TIER_THRESHOLDS:
        if weighted_score <= threshold:
            tier, approved, recommendation = t, a, rec
            break

    max_loan = TIER_MAX_LOAN[tier]

    # Monthly payment estimate (5% APR annuity)
    monthly_rate = 0.05 / 12
    if loan_term_months > 0 and loan_amount > 0:
        monthly_payment = (
            loan_amount
            * monthly_rate
            * (1 + monthly_rate) ** loan_term_months
            / ((1 + monthly_rate) ** loan_term_months - 1)
        )
    else:
        monthly_payment = 0.0

    return CreditRiskResult(
        customer_id=customer_id,
        loan_amount=loan_amount,
        loan_term_months=loan_term_months,
        weighted_score=weighted_score,
        risk_tier=tier,
        recommendation=recommendation,
        approved=approved,
        max_loan_amount=max_loan,
        monthly_payment_estimate=monthly_payment,
        risk_factors=factors,
    )
