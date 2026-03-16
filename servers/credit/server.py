"""
Credit Risk MCP Server

Exposes a rule-based credit risk scoring engine as MCP tools.
Implements a simplified Basel-inspired model covering KYC, DTI,
account behaviour, and loan-to-asset ratio.

Run standalone:
    python -m servers.credit.server
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from servers.accounts.mock_data import CUSTOMERS
from servers.credit.engine import score_customer

mcp = FastMCP(
    name="banking-credit",
    instructions=(
        "Provides credit risk scoring for loan applications. "
        "All scores are model-generated and must be reviewed by a human credit officer "
        "before any lending decision is made. "
        "Never present a model recommendation as a final decision."
    ),
)


@mcp.tool()
def score_credit_risk(
    customer_id: Annotated[str, Field(description="Customer identifier, e.g. CUST-001")],
    loan_amount: Annotated[float, Field(gt=0, description="Requested loan amount in EUR")],
    loan_term_months: Annotated[
        int, Field(ge=6, le=360, description="Loan term in months (6–360)")
    ],
) -> dict:
    """
    Run a full credit risk assessment for a loan application.

    Returns a risk score (0–100), risk tier, approval recommendation,
    estimated monthly payment, and a breakdown of contributing risk factors.

    This is a rule-based model — not an ML prediction.
    The result is advisory; a human credit officer makes the final call.
    """
    if customer_id not in CUSTOMERS:
        return {
            "error": f"Customer '{customer_id}' not found.",
            "available_ids": list(CUSTOMERS.keys()),
        }

    try:
        result = score_customer(customer_id, loan_amount, loan_term_months)
        return result.to_dict()
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_risk_factors(
    customer_id: Annotated[str, Field(description="Customer identifier, e.g. CUST-001")],
) -> dict:
    """
    Return the individual risk factor breakdown for a customer without a specific loan scenario.

    Uses a benchmark loan of €25,000 over 60 months to compute factor scores.
    Useful for understanding a customer's credit profile before they apply.
    """
    if customer_id not in CUSTOMERS:
        return {
            "error": f"Customer '{customer_id}' not found.",
            "available_ids": list(CUSTOMERS.keys()),
        }

    try:
        result = score_customer(customer_id, loan_amount=25_000.0, loan_term_months=60)
        return {
            "customer_id": customer_id,
            "benchmark_loan_amount": 25_000.0,
            "benchmark_term_months": 60,
            "overall_risk_score": round(result.weighted_score, 1),
            "risk_tier": result.risk_tier,
            "risk_factors": [
                {
                    "factor": f.name,
                    "score": round(f.score, 1),
                    "weight": f.weight,
                    "contribution": round(f.score * f.weight, 2),
                    "detail": f.detail,
                }
                for f in result.risk_factors
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
