"""
Test suite for all four Banking MCP servers.

Tests are designed to be fast and self-contained — no live API calls
(FX tests mock httpx). Each server's tools are tested for:
- Happy path correctness
- Input validation / error handling
- Edge cases specific to banking domain

Run with:
    pytest tests/ -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio


# ── Accounts server tests ─────────────────────────────────────────────────────


class TestAccountsServer:
    def test_get_balance_valid_account(self):
        from servers.accounts.server import get_account_balance

        result = get_account_balance("ACC-1001")
        assert result["account_id"] == "ACC-1001"
        assert result["currency"] == "EUR"
        assert result["balance"] > 0
        assert result["status"] == "active"
        assert len(result["iban_last4"]) == 4  # Masked

    def test_get_balance_unknown_account(self):
        from servers.accounts.server import get_account_balance

        result = get_account_balance("ACC-9999")
        assert "error" in result
        assert "available_ids" in result

    def test_get_transactions_returns_sorted_desc(self):
        from servers.accounts.server import get_transaction_history

        result = get_transaction_history("ACC-1001", days=30)
        assert result["transaction_count"] > 0
        dates = [t["date"] for t in result["transactions"]]
        assert dates == sorted(dates, reverse=True)

    def test_get_transactions_category_filter(self):
        from servers.accounts.server import get_transaction_history

        result = get_transaction_history("ACC-1001", days=90, category_filter="income")
        for tx in result["transactions"]:
            assert tx["category"] == "income"

    def test_get_transactions_net_flow_correct(self):
        from servers.accounts.server import get_transaction_history

        result = get_transaction_history("ACC-1001", days=60)
        expected_net = round(result["total_credits"] + result["total_debits"], 2)
        assert abs(result["net_flow"] - expected_net) < 0.01

    def test_get_customer_accounts(self):
        from servers.accounts.server import get_customer_accounts

        result = get_customer_accounts("CUST-001")
        assert result["account_count"] == 2  # CUST-001 has ACC-1001 + ACC-1002
        assert result["total_balance_eur"] > 0
        assert all(a["currency"] == "EUR" for a in result["accounts"])

    def test_get_customer_accounts_unknown(self):
        from servers.accounts.server import get_customer_accounts

        result = get_customer_accounts("CUST-999")
        assert "error" in result


# ── FX server tests ───────────────────────────────────────────────────────────


class TestFXServer:
    @pytest.mark.asyncio
    async def test_same_currency_returns_rate_one(self):
        from servers.fx.server import get_fx_rate

        result = await get_fx_rate("EUR", "EUR")
        assert result["rate"] == 1.0

    @pytest.mark.asyncio
    async def test_unsupported_currency_returns_error(self):
        from servers.fx.server import get_fx_rate

        result = await get_fx_rate("EUR", "XYZ")
        assert "error" in result
        assert "supported" in result

    @pytest.mark.asyncio
    async def test_same_currency_convert_is_identity(self):
        from servers.fx.server import convert_amount

        result = await convert_amount(1000.0, "USD", "USD")
        assert result["converted_amount"] == 1000.0
        assert result["rate"] == 1.0

    @pytest.mark.asyncio
    async def test_bulk_rates_includes_all_requested(self, httpx_mock):
        """Mock the FX API to avoid network calls in unit tests."""
        from servers.fx.server import get_fx_rates_bulk

        httpx_mock.add_response(
            json={"base": "EUR", "date": "2025-01-01", "rates": {"USD": 1.09, "GBP": 0.86}}
        )

        result = await get_fx_rates_bulk("EUR", ["USD", "GBP"])
        assert "USD" in result["rates"]
        assert "GBP" in result["rates"]
        assert result["base"] == "EUR"

    @pytest.mark.asyncio
    async def test_bulk_includes_self_as_one(self):
        from servers.fx.server import get_fx_rates_bulk

        result = await get_fx_rates_bulk("EUR", ["EUR"])
        assert result["rates"].get("EUR") == 1.0


# ── Credit server tests ───────────────────────────────────────────────────────


class TestCreditServer:
    def test_low_risk_customer_approved(self):
        """CUST-001 has high balances, verified KYC, low risk rating → should approve."""
        from servers.credit.server import score_credit_risk

        result = score_credit_risk("CUST-001", loan_amount=10_000.0, loan_term_months=24)
        assert "error" not in result
        assert result["approved"] is True
        assert result["risk_tier"] in ("Low", "Medium")

    def test_restricted_account_customer_declined(self):
        """CUST-003 has a restricted account and pending KYC → should flag high risk."""
        from servers.credit.server import score_credit_risk

        result = score_credit_risk("CUST-003", loan_amount=50_000.0, loan_term_months=60)
        assert "error" not in result
        assert result["risk_tier"] in ("High", "Very High")

    def test_very_large_loan_increases_risk(self):
        """Even a good customer should score worse for an outsized loan."""
        from servers.credit.server import score_credit_risk

        small = score_credit_risk("CUST-001", loan_amount=5_000.0, loan_term_months=12)
        large = score_credit_risk("CUST-001", loan_amount=500_000.0, loan_term_months=12)
        assert large["risk_score"] >= small["risk_score"]

    def test_result_has_required_fields(self):
        from servers.credit.server import score_credit_risk

        result = score_credit_risk("CUST-001", loan_amount=20_000.0, loan_term_months=36)
        for field in ("risk_score", "risk_tier", "approved", "recommendation", "risk_factors"):
            assert field in result, f"Missing field: {field}"

    def test_unknown_customer_returns_error(self):
        from servers.credit.server import score_credit_risk

        result = score_credit_risk("CUST-999", loan_amount=10_000.0, loan_term_months=12)
        assert "error" in result

    def test_risk_factors_include_all_categories(self):
        from servers.credit.server import get_risk_factors

        result = get_risk_factors("CUST-001")
        factor_names = {f["factor"] for f in result["risk_factors"]}
        assert "KYC status" in factor_names
        assert "Debt-to-income ratio" in factor_names
        assert "Account behaviour" in factor_names


# ── Compliance server tests ───────────────────────────────────────────────────


class TestComplianceServer:
    def test_amount_below_threshold_is_clear(self):
        from servers.compliance.server import check_aml_threshold

        result = check_aml_threshold(
            amount=1_000.0, currency="EUR", transaction_type="wire_transfer"
        )
        assert result["alert_level"] == "clear"

    def test_amount_above_report_threshold_is_high(self):
        from servers.compliance.server import check_aml_threshold

        result = check_aml_threshold(
            amount=15_001.0, currency="EUR", transaction_type="wire_transfer"
        )
        assert result["alert_level"] == "high"
        assert any("CTR" in action for action in result["required_actions"])

    def test_high_risk_jurisdiction_elevates_alert(self):
        from servers.compliance.server import check_aml_threshold

        # Amount below threshold but high-risk jurisdiction
        result = check_aml_threshold(
            amount=500.0,
            currency="EUR",
            transaction_type="international_wire",
            counterparty_jurisdiction="KP",  # North Korea — FATF black list
        )
        assert result["alert_level"] != "clear"
        assert result["jurisdiction_risk"] == "high"

    def test_sanctions_match_blocks_transaction(self):
        from servers.compliance.server import check_sanctions

        result = check_sanctions("MOCK RESTRICTED ENTITY LTD")
        assert result["alert_level"] == "blocked"
        assert result["sanctions_match"] is True
        assert any("BLOCK" in action for action in result["required_actions"])

    def test_clean_entity_returns_clear(self):
        from servers.compliance.server import check_sanctions

        result = check_sanctions("Acme Pharmaceuticals GmbH", country="DE")
        assert result["alert_level"] == "clear"
        assert result["sanctions_match"] is False

    def test_pep_keyword_triggers_medium_alert(self):
        from servers.compliance.server import check_sanctions

        result = check_sanctions("Ambassador John Smith", country="US")
        assert result["pep_indicators_found"] is True
        assert result["alert_level"] in ("medium", "high")

    def test_regulatory_limits_eu(self):
        from servers.compliance.server import get_regulatory_limits

        result = get_regulatory_limits("EU")
        assert result["ctr_threshold"] == 10_000.0
        assert result["currency"] == "EUR"

    def test_regulatory_limits_unknown_jurisdiction(self):
        from servers.compliance.server import get_regulatory_limits

        result = get_regulatory_limits("ZZ")
        assert "error" in result
        assert "available" in result

    def test_regulatory_limits_with_tx_type(self):
        from servers.compliance.server import get_regulatory_limits

        result = get_regulatory_limits("US", transaction_type="cash_deposit")
        assert "aml_thresholds_for_transaction_type" in result
        assert result["aml_thresholds_for_transaction_type"]["transaction_type"] == "cash_deposit"
