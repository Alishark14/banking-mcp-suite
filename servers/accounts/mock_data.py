"""
Mock banking data store.

Simulates a core banking system with customers, accounts, and transactions.
In production this would be replaced by authenticated calls to the bank's
internal APIs or database layer.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

# ── Customer registry ─────────────────────────────────────────────────────────

CUSTOMERS: dict[str, dict[str, Any]] = {
    "CUST-001": {
        "customer_id": "CUST-001",
        "name": "Isabelle Fontaine",
        "email": "i.fontaine@example.com",
        "kyc_status": "verified",
        "risk_rating": "low",
        "country": "FR",
        "date_onboarded": "2019-03-14",
    },
    "CUST-002": {
        "customer_id": "CUST-002",
        "name": "Marco Visconti",
        "email": "m.visconti@example.com",
        "kyc_status": "verified",
        "risk_rating": "medium",
        "country": "IT",
        "date_onboarded": "2021-07-22",
    },
    "CUST-003": {
        "customer_id": "CUST-003",
        "name": "Lukas Brenner",
        "email": "l.brenner@example.com",
        "kyc_status": "pending",
        "risk_rating": "high",
        "country": "DE",
        "date_onboarded": "2024-01-10",
    },
}

# ── Account registry ──────────────────────────────────────────────────────────

ACCOUNTS: dict[str, dict[str, Any]] = {
    "ACC-1001": {
        "account_id": "ACC-1001",
        "customer_id": "CUST-001",
        "account_type": "current",
        "currency": "EUR",
        "balance": Decimal("24_750.82"),
        "available_balance": Decimal("24_250.82"),
        "status": "active",
        "iban": "FR76 3000 6000 0112 3456 7890 189",
        "opened_date": "2019-03-14",
    },
    "ACC-1002": {
        "account_id": "ACC-1002",
        "customer_id": "CUST-001",
        "account_type": "savings",
        "currency": "EUR",
        "balance": Decimal("102_300.00"),
        "available_balance": Decimal("102_300.00"),
        "status": "active",
        "iban": "FR76 3000 6000 0112 3456 7890 200",
        "opened_date": "2020-06-01",
    },
    "ACC-2001": {
        "account_id": "ACC-2001",
        "customer_id": "CUST-002",
        "account_type": "current",
        "currency": "EUR",
        "balance": Decimal("3_412.55"),
        "available_balance": Decimal("3_412.55"),
        "status": "active",
        "iban": "IT60 X054 2811 1010 0000 0123 456",
        "opened_date": "2021-07-22",
    },
    "ACC-3001": {
        "account_id": "ACC-3001",
        "customer_id": "CUST-003",
        "account_type": "current",
        "currency": "EUR",
        "balance": Decimal("890.10"),
        "available_balance": Decimal("890.10"),
        "status": "restricted",
        "iban": "DE89 3704 0044 0532 0130 00",
        "opened_date": "2024-01-10",
    },
}

# ── Transaction generators ────────────────────────────────────────────────────

_TX_TEMPLATES: list[dict[str, Any]] = [
    {"description": "Salary payment",         "amount": Decimal("4_500.00"),  "type": "credit",  "category": "income"},
    {"description": "Rent – Hausmann & Co",   "amount": Decimal("-1_200.00"), "type": "debit",   "category": "housing"},
    {"description": "Supermarché BIO",        "amount": Decimal("-87.34"),    "type": "debit",   "category": "groceries"},
    {"description": "Netflix subscription",   "amount": Decimal("-17.99"),    "type": "debit",   "category": "subscriptions"},
    {"description": "Freelance invoice #42",  "amount": Decimal("1_800.00"),  "type": "credit",  "category": "income"},
    {"description": "SNCF train ticket",      "amount": Decimal("-54.00"),    "type": "debit",   "category": "transport"},
    {"description": "ATM withdrawal",         "amount": Decimal("-200.00"),   "type": "debit",   "category": "cash"},
    {"description": "Restaurant Le Marais",   "amount": Decimal("-67.50"),    "type": "debit",   "category": "dining"},
    {"description": "Amazon.fr",              "amount": Decimal("-43.99"),    "type": "debit",   "category": "shopping"},
    {"description": "Electricity – EDF",      "amount": Decimal("-95.20"),    "type": "debit",   "category": "utilities"},
    {"description": "Dividend – ETF World",   "amount": Decimal("312.80"),    "type": "credit",  "category": "investment"},
    {"description": "FX transfer USD/EUR",    "amount": Decimal("5_000.00"),  "type": "credit",  "category": "transfer"},
    {"description": "International wire",     "amount": Decimal("-9_800.00"), "type": "debit",   "category": "transfer"},
]


def generate_transactions(
    account_id: str,
    days: int = 30,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Generate a deterministic list of mock transactions for an account."""
    rng = random.Random(seed or hash(account_id))
    today = datetime.utcnow().date()
    txs: list[dict[str, Any]] = []

    for i in range(rng.randint(8, min(days * 2, 60))):
        template = rng.choice(_TX_TEMPLATES)
        tx_date = today - timedelta(days=rng.randint(0, days - 1))
        amount = template["amount"] * Decimal(str(round(rng.uniform(0.85, 1.15), 4)))
        txs.append(
            {
                "transaction_id": f"TXN-{account_id}-{i:04d}",
                "account_id": account_id,
                "date": tx_date.isoformat(),
                "description": template["description"],
                "amount": float(round(amount, 2)),
                "currency": ACCOUNTS.get(account_id, {}).get("currency", "EUR"),
                "type": template["type"],
                "category": template["category"],
                "balance_after": None,  # simplified
                "reference": f"REF{rng.randint(100_000, 999_999)}",
            }
        )

    return sorted(txs, key=lambda t: t["date"], reverse=True)
