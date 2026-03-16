# Banking MCP Server Suite

A production-grade suite of [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers exposing banking-relevant AI tools. Built to demonstrate how agentic AI systems can connect to live financial data through standardised, auditable interfaces.

## What this is

Four standalone FastMCP servers, each wrapping a distinct banking domain:

| Server | Tools | Data source |
|---|---|---|
| **Accounts** | `get_account_balance`, `get_transaction_history`, `get_customer_accounts` | Mock core banking DB |
| **FX Rates** | `get_fx_rate`, `convert_amount`, `get_fx_rates_bulk` | Live ECB rates via [frankfurter.app](https://www.frankfurter.app) |
| **Credit Risk** | `score_credit_risk`, `get_risk_factors` | Rule-based Basel-inspired engine |
| **Compliance** | `check_aml_threshold`, `check_sanctions`, `get_regulatory_limits` | EU 6AMLD / FATF rules |

An agent demo (`demo/agent_demo.py`) wires all four servers to Claude, showing a multi-step banking assessment: account lookup → FX conversion → credit scoring → AML compliance check.

---

## Why MCP vs RAG

Traditional RAG retrieves from a static document index. For banking:

- A balance query needs **live data** — a RAG index is stale the moment it's built.
- A compliance check needs **structured rule evaluation** — not semantic search over regulation PDFs.
- A credit risk score needs to **call deterministic logic** — not approximate it with embeddings.

MCP exposes these as typed, callable tools with defined input/output schemas. The AI model reasons about *which* tool to call and *when* — the tools do the deterministic work.

---

## Architecture

```
Claude agent (demo/agent_demo.py)
        │
        │  MCP tool calls (stdio transport)
        ├──────────────────────┬──────────────────────┬──────────────────────┐
        ▼                      ▼                      ▼                      ▼
 Accounts server          FX server            Credit server        Compliance server
 (mock bank DB)      (frankfurter.app)       (rule engine)         (AML/FATF rules)
```

Each server runs as an independent process over stdio transport. In production, swap stdio for SSE or HTTP to deploy behind an authenticated API gateway.

---

## Getting started

**Prerequisites:** Python 3.11+, `uv` (recommended) or `pip`

```bash
git clone https://github.com/your-username/banking-mcp-suite
cd banking-mcp-suite

# Install dependencies
uv pip install -e requirements.txt

# Set your Anthropic API key (only needed for the agent demo)
export ANTHROPIC_API_KEY=sk-...
```

### Run an individual server (FastMCP dev mode)

```bash
fastmcp dev servers/accounts/server.py
fastmcp dev servers/fx/server.py
fastmcp dev servers/credit/server.py
fastmcp dev servers/compliance/server.py
```

The FastMCP dev UI lets you call tools interactively in a browser.

### Run the agent demo

```bash
# Full multi-server scenario (default)
python demo/agent_demo.py

# Credit risk only
python demo/agent_demo.py --scenario loan

# AML compliance only
python demo/agent_demo.py --scenario aml
```

### Run tests

```bash
pytest tests/ -v
```

---

## Server reference

### Accounts server

```python
get_account_balance(account_id: str) → dict
get_transaction_history(account_id: str, days: int = 30, category_filter: str | None = None) → dict
get_customer_accounts(customer_id: str) → dict
```

Mock customers: `CUST-001` (low risk), `CUST-002` (medium risk), `CUST-003` (high risk / restricted)  
Mock accounts: `ACC-1001`, `ACC-1002` (CUST-001), `ACC-2001` (CUST-002), `ACC-3001` (CUST-003)

### FX server

```python
get_fx_rate(base: str, quote: str) → dict
convert_amount(amount: float, from_currency: str, to_currency: str) → dict
get_fx_rates_bulk(base: str, quotes: list[str]) → dict
```

Rates sourced from [frankfurter.app](https://www.frankfurter.app) (ECB reference rates, no API key required, updates daily on business days).

### Credit risk server

```python
score_credit_risk(customer_id: str, loan_amount: float, loan_term_months: int) → dict
get_risk_factors(customer_id: str) → dict
```

Scoring model weighs five factors:

| Factor | Weight | Basis |
|---|---|---|
| KYC status | 25% | Verified / pending / failed |
| Existing risk rating | 20% | Internal CRM classification |
| Debt-to-income ratio | 25% | Estimated from 90-day transaction history |
| Account behaviour | 15% | Balance level, restricted status |
| Loan-to-assets ratio | 15% | Loan vs total assets at bank |

Risk tiers: **Low** (≤25) → **Medium** (≤50) → **High** (≤70) → **Very High** (>70)

### Compliance server

```python
check_aml_threshold(amount: float, currency: str, transaction_type: str, counterparty_jurisdiction: str | None) → dict
check_sanctions(entity_name: str, country: str | None) → dict
get_regulatory_limits(jurisdiction: str, transaction_type: str | None) → dict
```

Regulatory coverage:
- **Thresholds:** EU 6AMLD, FATF Recommendation 20, EU Funds Transfer Regulation 2015/847
- **Jurisdictions:** EU, UK, US, CH, SG
- **Transaction types:** cash_deposit, cash_withdrawal, wire_transfer, international_wire, fx_conversion, crypto_exchange
- **Sanctions screen:** Illustrative demo list — production systems require a licensed watchlist provider (Refinitiv, Dow Jones, etc.)

> ⚠️ **Disclaimer:** Compliance tools are illustrative. They do not constitute legal or regulatory advice. Production deployments require integration with licensed watchlist providers and review by a qualified MLRO.

---

## Extending to production

To adapt this for a real banking environment:

1. **Replace mock data** — swap `servers/accounts/mock_data.py` with authenticated calls to your core banking API (Temenos, Thought Machine, FIS, etc.)
2. **Add authentication** — implement OAuth2 client credentials at the MCP gateway level; never pass credentials through tool schemas
3. **Switch transport** — replace `stdio` with `sse` or `streamable-http` for multi-client deployments
4. **Add observability** — wrap each tool call with OpenTelemetry spans; log token count, latency, and tool input/output per request
5. **Integrate licensed watchlists** — replace the illustrative sanctions list with Refinitiv World-Check or Dow Jones Risk & Compliance API
6. **Connect the credit engine** — replace rule-based scoring with calls to your credit bureau integration (Experian Connect, Equifax Interconnect, etc.)

---

## Project structure

```
banking-mcp-suite/
├── servers/
│   ├── accounts/
│   │   ├── server.py        # MCP server entry point
│   │   └── mock_data.py     # Mock customer/account/transaction data
│   ├── fx/
│   │   └── server.py        # Live FX rate server (frankfurter.app)
│   ├── credit/
│   │   ├── server.py        # MCP server entry point
│   │   └── engine.py        # Rule-based scoring engine
│   └── compliance/
│       ├── server.py        # MCP server entry point
│       └── rules.py         # AML rules, thresholds, jurisdiction data
├── demo/
│   └── agent_demo.py        # Claude agent orchestrating all four servers
├── tests/
│   └── test_servers.py      # Unit tests for all servers
└── pyproject.toml
```

---

## Tech stack

- **[FastMCP](https://github.com/jlowin/fastmcp)** — Python MCP server framework
- **[Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)** — Claude API client for agent loop
- **[httpx](https://www.python-httpx.org/)** — Async HTTP client for FX API
- **[Pydantic v2](https://docs.pydantic.dev/)** — Schema validation and type safety
- **[Rich](https://rich.readthedocs.io/)** — Terminal output for the agent demo
- **[pytest](https://pytest.org/) + pytest-asyncio** — Test suite

---

## Regulatory references

- [FATF 40 Recommendations](https://www.fatf-gafi.org/en/topics/fatf-recommendations.html)
- [EU 6AMLD (Directive 2018/1673)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32018L1673)
- [EU Funds Transfer Regulation 2015/847](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015R0847)
- [Model Context Protocol specification](https://spec.modelcontextprotocol.io)
