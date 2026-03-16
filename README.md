# Banking MCP Server Suite

A suite of MCP servers that give an AI agent live access to core banking capabilities — account data, FX rates, credit scoring, and AML compliance checks. Built with [Model Context Protocol](https://modelcontextprotocol.io), FastMCP, and Claude.

---

## Problem

AI has enormous potential in banking, but most deployments hit the same wall: **the model is cut off from live data**.

The dominant approach today is RAG — index documents into a vector store, retrieve at query time. It works for policy FAQs and document search. It breaks completely for anything operational:

- A customer asks for their current balance. The RAG index was built last night. The answer is wrong.
- A loan officer wants a credit decision. The model needs live transaction history and deterministic rule evaluation — not semantic similarity over PDFs.
- A compliance officer needs to know if a wire transfer triggers AML reporting. The answer depends on real jurisdiction rules and real transaction amounts — not an LLM approximating from training data.

The consequence is that AI in banking either gets confined to low-stakes use cases, or it gets deployed on stale data and produces outputs that compliance teams can't trust or sign off on.

---

## Solution

This project uses **Model Context Protocol (MCP)** to connect an AI agent directly to live banking systems through standardised, typed tool interfaces.

Instead of retrieving from a static index, the agent calls tools in real time. The model decides *which* tool to call and *when* — the tools execute the deterministic logic against live data and return structured results. Every output is grounded, traceable, and auditable.

Four MCP servers were built, each owning a distinct banking domain:

**Accounts server** — account balances, transaction history, and customer profiles. Backed by a realistic mock core banking store with customers across low, medium, and high risk profiles. In production, swap the mock for authenticated calls to Temenos, Thought Machine, or FIS.

**FX server** — live ECB reference rates via [frankfurter.app](https://www.frankfurter.app). Supports single rate lookups, currency conversion, and bulk multi-currency valuation. No API key needed — rates update every European business day directly from the ECB.

**Credit risk server** — a rule-based scoring engine modelled on Basel framework principles. Evaluates five weighted factors: KYC status, debt-to-income ratio derived from transaction history, existing internal risk rating, account behaviour, and loan-to-assets ratio. Returns a risk tier (Low / Medium / High / Very High), approval recommendation, estimated monthly payment, and a full per-factor breakdown.

**Compliance server** — AML threshold checking, sanctions screening, and jurisdiction-specific regulatory limits. Implements EU 6AMLD, FATF Recommendation 20, and the EU Funds Transfer Regulation across five jurisdictions: EU, UK, US, Switzerland, and Singapore.

A Claude agent demo wires all four servers together. A single natural language query triggers the agent to decide which tools to call, execute them in sequence, and synthesise the results into a structured report with evidence and recommendations.

---

## Example — Full Customer Assessment

```
Input:
"Assess customer CUST-001. Summarise her financial position,
express her wealth in USD and GBP, run a credit check for a
€35k loan, and check a €12k wire to the UAE for AML compliance."

Agent calls:
→ get_customer_accounts(CUST-001)
→ get_fx_rates_bulk(EUR, [USD, GBP])
→ score_credit_risk(CUST-001, 35000, 48)
→ check_aml_threshold(12000, EUR, international_wire, AE)
→ check_sanctions(counterparty_name, AE)

Output:
Structured report with financial summary, FX-converted wealth,
credit decision with reasoning, and compliance actions required.
```

---

## Why This Matters for Production AI in Banking

| Concern | How this addresses it |
|---|---|
| **Live data** | Tools call live sources — no stale RAG index |
| **Determinism** | Credit scoring and AML checks are rule-based, not LLM guesses |
| **Auditability** | Every tool call has typed inputs/outputs — fully traceable |
| **Modularity** | Each server is independently deployable and testable |
| **Compliance** | Regulatory logic is isolated in the compliance server, not embedded in prompts |

---

## Getting Started

**Prerequisites:** Python 3.11+, Miniconda or venv

```bash
git clone https://github.com/YOUR_USERNAME/banking-mcp-suite
cd banking-mcp-suite

conda create -n banking-mcp python=3.11 -y
conda activate banking-mcp

pip install -r requirements.txt

cp .env.example .env
# Add your Anthropic API key to .env
```

**Run the tests** (no API key needed):
```bash
pytest tests/ -v
```

**Run the agent demo:**
```bash
python demo/agent_demo.py --scenario aml    # AML compliance check
python demo/agent_demo.py --scenario loan   # Credit risk assessment
python demo/agent_demo.py                   # Full multi-server scenario
```

---

## Project Structure

```
banking-mcp-suite/
├── servers/
│   ├── accounts/
│   │   ├── server.py        # MCP server — balance & transaction tools
│   │   └── mock_data.py     # Mock customers, accounts, transactions
│   ├── fx/
│   │   └── server.py        # MCP server — live ECB FX rates
│   ├── credit/
│   │   ├── server.py        # MCP server — credit risk tools
│   │   └── engine.py        # Rule-based Basel-inspired scoring engine
│   └── compliance/
│       ├── server.py        # MCP server — AML & regulatory tools
│       └── rules.py         # EU 6AMLD / FATF thresholds & jurisdiction data
├── demo/
│   └── agent_demo.py        # Claude agent orchestrating all four servers
├── tests/
│   └── test_servers.py      # Unit tests (~25) for all servers
├── requirements.txt
└── .env.example
```

---

## Server Reference

### Accounts
| Tool | Description |
|---|---|
| `get_account_balance` | Current balance, available balance, account status |
| `get_transaction_history` | Transactions over N days, filterable by category |
| `get_customer_accounts` | All accounts for a customer with total balance |

Mock customers: `CUST-001` (low risk), `CUST-002` (medium risk), `CUST-003` (high risk / restricted)

### FX Rates
| Tool | Description |
|---|---|
| `get_fx_rate` | Latest ECB rate between two currencies |
| `convert_amount` | Convert an amount between currencies |
| `get_fx_rates_bulk` | Rates from one base to multiple quotes |

### Credit Risk
| Tool | Description |
|---|---|
| `score_credit_risk` | Full assessment for a loan application |
| `get_risk_factors` | Factor breakdown for a customer profile |

Scoring model: KYC (25%) · Existing risk rating (20%) · Debt-to-income (25%) · Account behaviour (15%) · Loan-to-assets (15%)

Risk tiers: **Low** ≤25 · **Medium** ≤50 · **High** ≤70 · **Very High** >70

### Compliance
| Tool | Description |
|---|---|
| `check_aml_threshold` | AML alert level for a transaction + jurisdiction |
| `check_sanctions` | Sanctions + PEP screen for an entity |
| `get_regulatory_limits` | CTR/SAR thresholds by jurisdiction |

Jurisdictions: EU · UK · US · CH · SG

> ⚠️ Compliance tools are illustrative. Production systems require a licensed watchlist provider and qualified MLRO oversight.

---

## Regulatory References

- [FATF 40 Recommendations](https://www.fatf-gafi.org/en/topics/fatf-recommendations.html)
- [EU Sixth Anti-Money Laundering Directive (6AMLD)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32018L1673)
- [EU Funds Transfer Regulation 2015/847](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015R0847)
- [Model Context Protocol specification](https://spec.modelcontextprotocol.io)

---

## Tech Stack

[FastMCP](https://github.com/jlowin/fastmcp) · [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) · [httpx](https://www.python-httpx.org/) · [Pydantic v2](https://docs.pydantic.dev/) · [Rich](https://rich.readthedocs.io/) · [pytest](https://pytest.org/)
