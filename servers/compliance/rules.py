"""
AML and regulatory rule definitions.

Rules reflect simplified versions of real frameworks:
- FATF 40 Recommendations
- EU 6AMLD (Sixth Anti-Money Laundering Directive)
- EBA Guidelines on ML/TF Risk Factors

These are illustrative — not legal compliance advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AlertLevel(str, Enum):
    CLEAR = "clear"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


@dataclass
class AMLRule:
    rule_id: str
    name: str
    description: str
    regulation: str


# ── AML threshold rules by transaction type ──────────────────────────────────

# EUR thresholds — adapted from EU AMLD requirements
AML_THRESHOLDS: dict[str, dict] = {
    "cash_deposit": {
        "report_threshold": 10_000.0,      # CTR required above this (most EU jurisdictions)
        "alert_threshold": 7_500.0,        # SAR consideration zone
        "structuring_window_days": 5,      # Look-back window for structuring detection
        "regulation": "EU 6AMLD Art. 33 / FATF Rec. 20",
    },
    "cash_withdrawal": {
        "report_threshold": 10_000.0,
        "alert_threshold": 7_500.0,
        "structuring_window_days": 5,
        "regulation": "EU 6AMLD Art. 33",
    },
    "wire_transfer": {
        "report_threshold": 15_000.0,      # EBA cross-border wire reporting threshold
        "alert_threshold": 10_000.0,
        "structuring_window_days": 3,
        "regulation": "EU Funds Transfer Regulation 2015/847",
    },
    "international_wire": {
        "report_threshold": 10_000.0,
        "alert_threshold": 5_000.0,
        "structuring_window_days": 3,
        "regulation": "FATF Rec. 16 / EU FTR",
    },
    "fx_conversion": {
        "report_threshold": 15_000.0,
        "alert_threshold": 10_000.0,
        "structuring_window_days": 5,
        "regulation": "EU 5AMLD Art. 13",
    },
    "crypto_exchange": {
        "report_threshold": 1_000.0,       # Lower threshold due to anonymity risk
        "alert_threshold": 500.0,
        "structuring_window_days": 1,
        "regulation": "EU MiCA / 6AMLD",
    },
    "general": {
        "report_threshold": 15_000.0,
        "alert_threshold": 10_000.0,
        "structuring_window_days": 5,
        "regulation": "FATF Rec. 20",
    },
}

# ── High-risk jurisdictions (FATF grey/black list excerpt, illustrative) ──────

HIGH_RISK_JURISDICTIONS: set[str] = {
    "AF", "IR", "KP", "MM", "SY", "YE",   # FATF black list (illustrative)
    "AL", "BB", "BF", "KH", "KY", "HT",   # FATF grey list excerpt
    "JM", "ML", "MZ", "PA", "PH", "SN",
    "SS", "TN", "TT", "UG", "AE", "VU",
}

# ── Mock sanctions list (illustrative names only) ─────────────────────────────

SANCTIONED_ENTITIES: set[str] = {
    "EXAMPLE SANCTIONED CORP",
    "MOCK RESTRICTED ENTITY LTD",
    "ILLUSTRATIVE BLOCKED PERSON",
}

# ── PEP indicators (simplified — in production this is a licensed data feed) ──

PEP_KEYWORDS = frozenset({
    "minister", "senator", "governor", "ambassador", "general",
    "president", "chancellor", "mp", "councillor",
})


def check_pep_indicators(name: str) -> bool:
    """Very simplified PEP name screen — real systems use licensed watchlist feeds."""
    return any(kw in name.lower() for kw in PEP_KEYWORDS)


# ── Regulatory limit lookups ──────────────────────────────────────────────────

REGULATORY_LIMITS: dict[str, dict] = {
    "EU": {
        "cash_transaction_limit": 10_000.0,
        "currency": "EUR",
        "ctr_threshold": 10_000.0,
        "sar_discretionary_threshold": 5_000.0,
        "wire_transfer_info_threshold": 1_000.0,
        "regulation": "EU 6AMLD / Regulation 2015/847",
        "notes": "Cash payment limit of €10k from Jan 2027 under proposed EU regulation.",
    },
    "UK": {
        "cash_transaction_limit": None,    # No statutory limit currently
        "currency": "GBP",
        "ctr_threshold": None,             # Suspicious Activity Reports (SARs) are discretionary
        "sar_discretionary_threshold": None,
        "wire_transfer_info_threshold": 1_000.0,
        "regulation": "Proceeds of Crime Act 2002 / MLR 2017",
        "notes": "UK uses a suspicion-based SAR model rather than fixed thresholds.",
    },
    "US": {
        "cash_transaction_limit": None,
        "currency": "USD",
        "ctr_threshold": 10_000.0,
        "sar_discretionary_threshold": 5_000.0,
        "wire_transfer_info_threshold": 3_000.0,
        "regulation": "Bank Secrecy Act / FinCEN",
        "notes": "CTRs required for cash transactions ≥ $10k. SARs for suspicious activity ≥ $5k.",
    },
    "CH": {
        "cash_transaction_limit": 100_000.0,
        "currency": "CHF",
        "ctr_threshold": 25_000.0,
        "sar_discretionary_threshold": 25_000.0,
        "wire_transfer_info_threshold": 1_000.0,
        "regulation": "AMLA (Anti-Money Laundering Act) / FINMA",
        "notes": "Switzerland requires enhanced due diligence for cash transactions ≥ CHF 100k.",
    },
    "SG": {
        "cash_transaction_limit": None,
        "currency": "SGD",
        "ctr_threshold": 20_000.0,
        "sar_discretionary_threshold": None,
        "wire_transfer_info_threshold": 1_500.0,
        "regulation": "MAS Notice 626 / CDSA",
        "notes": "MAS applies a risk-based approach; CTR threshold SGD 20k.",
    },
}
