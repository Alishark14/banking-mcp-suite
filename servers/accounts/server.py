"""
Accounts MCP Server

Exposes tools for querying account balances and transaction history.
In a real deployment this connects to the bank's core banking API
behind an authenticated service account.

Run standalone:
    python -m servers.accounts.server

Or via FastMCP dev mode:
    fastmcp dev servers/accounts/server.py
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from servers.accounts.mock_data import ACCOUNTS, CUSTOMERS, generate_transactions

mcp = FastMCP(
    name="banking-accounts",
    instructions=(
        "Provides read-only access to bank account balances and transaction history. "
        "Always present monetary amounts with their currency. "
        "Never expose full IBAN numbers — truncate to last 4 digits."
    ),
)


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_account_balance(
    account_id: Annotated[str, Field(description="Account identifier, e.g. ACC-1001")],
) -> dict:
    """
    Return the current balance and account metadata for a given account.

    Returns balance, available balance, currency, account type, and status.
    IBAN is masked to last 4 digits for security.
    """
    account = ACCOUNTS.get(account_id)
    if account is None:
        return {"error": f"Account '{account_id}' not found.", "available_ids": list(ACCOUNTS.keys())}

    customer = CUSTOMERS.get(account["customer_id"], {})

    return {
        "account_id": account["account_id"],
        "account_type": account["account_type"],
        "status": account["status"],
        "currency": account["currency"],
        "balance": float(account["balance"]),
        "available_balance": float(account["available_balance"]),
        "iban_last4": account["iban"][-4:],
        "customer_name": customer.get("name", "Unknown"),
        "customer_id": account["customer_id"],
    }


@mcp.tool()
def get_transaction_history(
    account_id: Annotated[str, Field(description="Account identifier, e.g. ACC-1001")],
    days: Annotated[int, Field(ge=1, le=365, description="Number of days to look back (1–365)")] = 30,
    category_filter: Annotated[
        str | None,
        Field(description="Optional category filter: income, housing, groceries, transport, etc."),
    ] = None,
) -> dict:
    """
    Return transaction history for an account over the specified period.

    Results are sorted newest-first. Optionally filter by spending category.
    """
    if account_id not in ACCOUNTS:
        return {"error": f"Account '{account_id}' not found.", "available_ids": list(ACCOUNTS.keys())}

    transactions = generate_transactions(account_id, days=days)

    if category_filter:
        transactions = [t for t in transactions if t["category"] == category_filter]

    total_credits = sum(t["amount"] for t in transactions if t["amount"] > 0)
    total_debits = sum(t["amount"] for t in transactions if t["amount"] < 0)

    return {
        "account_id": account_id,
        "period_days": days,
        "transaction_count": len(transactions),
        "total_credits": round(total_credits, 2),
        "total_debits": round(total_debits, 2),
        "net_flow": round(total_credits + total_debits, 2),
        "category_filter": category_filter,
        "transactions": transactions,
    }


@mcp.tool()
def get_customer_accounts(
    customer_id: Annotated[str, Field(description="Customer identifier, e.g. CUST-001")],
) -> dict:
    """
    Return all accounts belonging to a customer, with balances.
    Useful for getting a full financial picture of a customer.
    """
    if customer_id not in CUSTOMERS:
        return {"error": f"Customer '{customer_id}' not found.", "available_ids": list(CUSTOMERS.keys())}

    customer = CUSTOMERS[customer_id]
    accounts = [acc for acc in ACCOUNTS.values() if acc["customer_id"] == customer_id]

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "kyc_status": customer["kyc_status"],
        "risk_rating": customer["risk_rating"],
        "account_count": len(accounts),
        "accounts": [
            {
                "account_id": acc["account_id"],
                "account_type": acc["account_type"],
                "currency": acc["currency"],
                "balance": float(acc["balance"]),
                "status": acc["status"],
            }
            for acc in accounts
        ],
        "total_balance_eur": float(sum(acc["balance"] for acc in accounts)),
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
