"""
Compliance & AML MCP Server

Exposes regulatory compliance tools for AML threshold checking,
sanctions screening, and jurisdiction-specific rule lookups.

Run standalone:
    python -m servers.compliance.server
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from servers.compliance.rules import (
    AML_THRESHOLDS,
    HIGH_RISK_JURISDICTIONS,
    REGULATORY_LIMITS,
    SANCTIONED_ENTITIES,
    AlertLevel,
    check_pep_indicators,
)

mcp = FastMCP(
    name="banking-compliance",
    instructions=(
        "Provides AML threshold checking, sanctions screening, and regulatory limit lookups. "
        "All outputs are advisory. Compliance decisions must be reviewed by a qualified MLRO. "
        "This system does not substitute for a licensed watchlist screening service. "
        "Always record the rationale for any compliance decision in the case management system."
    ),
)


@mcp.tool()
def check_aml_threshold(
    amount: Annotated[float, Field(gt=0, description="Transaction amount in the specified currency")],
    currency: Annotated[str, Field(description="ISO currency code, e.g. EUR")],
    transaction_type: Annotated[
        str,
        Field(
            description=(
                "Type of transaction. One of: cash_deposit, cash_withdrawal, "
                "wire_transfer, international_wire, fx_conversion, crypto_exchange, general"
            )
        ),
    ],
    counterparty_jurisdiction: Annotated[
        str | None,
        Field(description="ISO 3166-1 alpha-2 country code of counterparty, e.g. DE, US, AF"),
    ] = None,
) -> dict:
    """
    Check whether a transaction triggers AML reporting obligations or alerts.

    Applies EU 6AMLD / FATF thresholds based on transaction type.
    Also checks for high-risk jurisdiction exposure.

    Returns alert level, applicable thresholds, required actions, and regulatory reference.
    """
    tx_type = transaction_type.lower().replace(" ", "_")
    rules = AML_THRESHOLDS.get(tx_type, AML_THRESHOLDS["general"])

    flags: list[str] = []
    required_actions: list[str] = []
    alert_level = AlertLevel.CLEAR

    # Threshold checks
    if amount >= rules["report_threshold"]:
        alert_level = AlertLevel.HIGH
        flags.append(f"Amount {currency} {amount:,.2f} meets or exceeds CTR threshold ({rules['report_threshold']:,.0f}).")
        required_actions.append("File Currency Transaction Report (CTR) with FIU within 15 days.")
        required_actions.append("Apply enhanced due diligence — obtain source of funds documentation.")
    elif amount >= rules["alert_threshold"]:
        alert_level = AlertLevel.MEDIUM
        flags.append(f"Amount {currency} {amount:,.2f} is in the SAR consideration zone (threshold: {rules['alert_threshold']:,.0f}).")
        required_actions.append("Assess for suspicious activity. Consider filing a Suspicious Activity Report (SAR).")
        required_actions.append("Document rationale for decision either way in case management system.")
    else:
        alert_level = AlertLevel.CLEAR
        flags.append(f"Amount {currency} {amount:,.2f} is below alert threshold.")

    # Jurisdiction risk check
    jurisdiction_risk = "standard"
    if counterparty_jurisdiction:
        cj = counterparty_jurisdiction.upper()
        if cj in HIGH_RISK_JURISDICTIONS:
            jurisdiction_risk = "high"
            if alert_level == AlertLevel.CLEAR:
                alert_level = AlertLevel.LOW
            elif alert_level == AlertLevel.MEDIUM:
                alert_level = AlertLevel.HIGH
            flags.append(f"Counterparty jurisdiction '{cj}' is on FATF high-risk/grey list.")
            required_actions.append("Apply enhanced due diligence (EDD) for high-risk jurisdiction exposure.")
            required_actions.append("Obtain senior management approval before processing.")

    # Structuring note
    structuring_note = (
        f"Review transaction history for structuring patterns within "
        f"{rules['structuring_window_days']}-day window (transactions just below "
        f"{currency} {rules['report_threshold']:,.0f} may indicate smurfing)."
    )

    return {
        "alert_level": alert_level.value,
        "transaction_type": tx_type,
        "amount": amount,
        "currency": currency,
        "counterparty_jurisdiction": counterparty_jurisdiction,
        "jurisdiction_risk": jurisdiction_risk,
        "flags": flags,
        "required_actions": required_actions if required_actions else ["No immediate action required. Retain records per standard retention policy."],
        "structuring_check_note": structuring_note,
        "applicable_thresholds": {
            "report_threshold": rules["report_threshold"],
            "alert_threshold": rules["alert_threshold"],
        },
        "regulatory_reference": rules["regulation"],
    }


@mcp.tool()
def check_sanctions(
    entity_name: Annotated[str, Field(description="Full legal name of the entity or individual to screen")],
    country: Annotated[str | None, Field(description="ISO 3166-1 alpha-2 country code, e.g. IR, SY")] = None,
) -> dict:
    """
    Perform a basic sanctions and PEP (Politically Exposed Person) screen.

    Checks against an illustrative restricted entity list and FATF high-risk jurisdictions.

    IMPORTANT: This is a demo implementation. Production systems must use
    a licensed watchlist provider (e.g. Refinitiv World-Check, Dow Jones Risk & Compliance).
    """
    name_upper = entity_name.upper().strip()
    flags: list[str] = []
    alert_level = AlertLevel.CLEAR
    required_actions: list[str] = []

    # Sanctions name match (exact — real systems use fuzzy matching + alias lists)
    if name_upper in SANCTIONED_ENTITIES:
        alert_level = AlertLevel.BLOCKED
        flags.append(f"'{entity_name}' matches a sanctioned entity on the restricted list.")
        required_actions.append("BLOCK transaction immediately.")
        required_actions.append("File a Suspicious Activity Report (SAR).")
        required_actions.append("Do not tip off the subject. Contact MLRO immediately.")

    # Jurisdiction check
    if country:
        cc = country.upper()
        if cc in HIGH_RISK_JURISDICTIONS:
            if alert_level == AlertLevel.CLEAR:
                alert_level = AlertLevel.MEDIUM
            flags.append(f"Country of operation '{cc}' is on the FATF high-risk/grey list.")
            required_actions.append("Apply Enhanced Due Diligence (EDD).")
            required_actions.append("Obtain source of funds and wealth documentation.")

    # PEP indicator check
    is_pep_indicator = check_pep_indicators(entity_name)
    if is_pep_indicator:
        if alert_level in (AlertLevel.CLEAR, AlertLevel.LOW):
            alert_level = AlertLevel.MEDIUM
        flags.append(f"Name '{entity_name}' contains PEP keyword indicators.")
        required_actions.append("Conduct PEP screening against licensed watchlist.")
        required_actions.append("If confirmed PEP, apply enhanced monitoring and senior approval.")

    if not flags:
        flags.append("No matches found in illustrative restricted list.")
        required_actions.append(
            "Continue standard CDD. Note: this screen is illustrative only — "
            "always run production screening via licensed watchlist provider."
        )

    return {
        "entity_name": entity_name,
        "country": country,
        "alert_level": alert_level.value,
        "sanctions_match": name_upper in SANCTIONED_ENTITIES,
        "pep_indicators_found": is_pep_indicator,
        "high_risk_jurisdiction": country.upper() in HIGH_RISK_JURISDICTIONS if country else False,
        "flags": flags,
        "required_actions": required_actions,
        "disclaimer": (
            "This is an illustrative demo screen. "
            "Production use requires a licensed watchlist screening service."
        ),
    }


@mcp.tool()
def get_regulatory_limits(
    jurisdiction: Annotated[
        str,
        Field(description="Jurisdiction code: EU, UK, US, CH, SG"),
    ],
    transaction_type: Annotated[
        str | None,
        Field(description="Optional: cash_deposit, wire_transfer, etc. Returns all limits if omitted."),
    ] = None,
) -> dict:
    """
    Return the applicable regulatory reporting limits and requirements for a given jurisdiction.

    Covers CTR thresholds, SAR thresholds, cash transaction limits, and wire transfer info requirements.
    Useful for compliance officers assessing cross-border transaction obligations.
    """
    jurisdiction = jurisdiction.upper()

    if jurisdiction not in REGULATORY_LIMITS:
        return {
            "error": f"Jurisdiction '{jurisdiction}' not in registry.",
            "available": list(REGULATORY_LIMITS.keys()),
        }

    limits = REGULATORY_LIMITS[jurisdiction]

    # Enrich with AML thresholds for the transaction type if specified
    aml_context = None
    if transaction_type:
        tx_key = transaction_type.lower().replace(" ", "_")
        aml_context = AML_THRESHOLDS.get(tx_key, AML_THRESHOLDS["general"])

    result: dict = {
        "jurisdiction": jurisdiction,
        "currency": limits["currency"],
        "ctr_threshold": limits["ctr_threshold"],
        "sar_discretionary_threshold": limits["sar_discretionary_threshold"],
        "cash_transaction_limit": limits["cash_transaction_limit"],
        "wire_transfer_info_threshold": limits["wire_transfer_info_threshold"],
        "regulation": limits["regulation"],
        "notes": limits["notes"],
    }

    if aml_context:
        result["aml_thresholds_for_transaction_type"] = {
            "transaction_type": transaction_type,
            "report_threshold": aml_context["report_threshold"],
            "alert_threshold": aml_context["alert_threshold"],
            "regulation": aml_context["regulation"],
        }

    return result


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
