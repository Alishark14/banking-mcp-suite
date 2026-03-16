"""
Banking MCP Suite — Agent Demo

Demonstrates a Claude agent using all four MCP servers to answer
a complex, multi-step banking query.

Usage:
    python demo/agent_demo.py
    python demo/agent_demo.py --scenario loan       # Credit risk only
    python demo/agent_demo.py --scenario aml        # AML check only
    python demo/agent_demo.py --scenario full       # All servers (default)
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import sys
from pathlib import Path
from typing import Callable

# Add project root to path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from dotenv import load_dotenv
from rich.console import Console

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

console = Console()


# ── Demo scenarios ────────────────────────────────────────────────────────────

SCENARIOS = {
    "full": {
        "title": "Full customer assessment",
        "prompt": (
            "I need a comprehensive assessment of customer CUST-001 (Isabelle Fontaine). "
            "Please do the following:\n\n"
            "1. Pull her account balances and summarise her financial position.\n"
            "2. She holds EUR but wants her total wealth expressed in USD and GBP — "
            "use live FX rates to calculate this.\n"
            "3. She's applying for a €35,000 personal loan over 48 months. "
            "Run a credit risk assessment and tell me whether to proceed.\n"
            "4. She also wants to wire €12,000 to a counterparty in the UAE. "
            "Check this transfer for AML compliance and tell me what actions are required.\n\n"
            "Summarise your findings with a clear recommendation for each item."
        ),
        "servers": ["accounts", "fx", "credit", "compliance"],
    },
    "loan": {
        "title": "Credit risk assessment",
        "prompt": (
            "Customer CUST-002 (Marco Visconti) is applying for a €20,000 loan over 36 months. "
            "Pull his accounts to understand his financial position, run a credit risk assessment, "
            "and give me a clear approve/decline recommendation with reasoning."
        ),
        "servers": ["accounts", "credit"],
    },
    "aml": {
        "title": "AML compliance check",
        "prompt": (
            "We have an incoming international wire of €9,500 from an entity called "
            "'MOCK RESTRICTED ENTITY LTD' based in Iran (IR). "
            "Run all relevant compliance checks and tell me exactly what actions the compliance "
            "team must take before this transaction can be processed."
        ),
        "servers": ["compliance"],
    },
}


# ── Tool registry ─────────────────────────────────────────────────────────────

def _build_tool_registry(server_names: list[str]) -> tuple[list[dict], dict[str, Callable]]:
    """
    Import tool functions directly from server modules.
    Returns (tools_for_claude_api, tool_name → callable).
    """
    from servers.accounts.server import (
        get_account_balance,
        get_transaction_history,
        get_customer_accounts,
    )
    from servers.fx.server import (
        get_fx_rate,
        convert_amount,
        get_fx_rates_bulk,
    )
    from servers.credit.server import (
        score_credit_risk,
        get_risk_factors,
    )
    from servers.compliance.server import (
        check_aml_threshold,
        check_sanctions,
        get_regulatory_limits,
    )

    all_tools: dict[str, tuple[Callable, dict]] = {
        "get_account_balance": (get_account_balance, {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Account identifier, e.g. ACC-1001"},
            },
            "required": ["account_id"],
        }),
        "get_transaction_history": (get_transaction_history, {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Account identifier"},
                "days": {"type": "integer", "description": "Number of days to look back (1-365)"},
                "category_filter": {"type": "string", "description": "Optional category filter"},
            },
            "required": ["account_id"],
        }),
        "get_customer_accounts": (get_customer_accounts, {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer identifier, e.g. CUST-001"},
            },
            "required": ["customer_id"],
        }),
        "get_fx_rate": (get_fx_rate, {
            "type": "object",
            "properties": {
                "base": {"type": "string", "description": "Base currency ISO code, e.g. EUR"},
                "quote": {"type": "string", "description": "Quote currency ISO code, e.g. USD"},
            },
            "required": ["base", "quote"],
        }),
        "convert_amount": (convert_amount, {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Amount to convert"},
                "from_currency": {"type": "string", "description": "Source currency ISO code"},
                "to_currency": {"type": "string", "description": "Target currency ISO code"},
            },
            "required": ["amount", "from_currency", "to_currency"],
        }),
        "get_fx_rates_bulk": (get_fx_rates_bulk, {
            "type": "object",
            "properties": {
                "base": {"type": "string", "description": "Base currency ISO code"},
                "quotes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of quote currency codes",
                },
            },
            "required": ["base", "quotes"],
        }),
        "score_credit_risk": (score_credit_risk, {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer identifier"},
                "loan_amount": {"type": "number", "description": "Requested loan amount in EUR"},
                "loan_term_months": {"type": "integer", "description": "Loan term in months (6-360)"},
            },
            "required": ["customer_id", "loan_amount", "loan_term_months"],
        }),
        "get_risk_factors": (get_risk_factors, {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer identifier"},
            },
            "required": ["customer_id"],
        }),
        "check_aml_threshold": (check_aml_threshold, {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Transaction amount"},
                "currency": {"type": "string", "description": "ISO currency code, e.g. EUR"},
                "transaction_type": {
                    "type": "string",
                    "description": "One of: cash_deposit, cash_withdrawal, wire_transfer, international_wire, fx_conversion, crypto_exchange, general",
                },
                "counterparty_jurisdiction": {
                    "type": "string",
                    "description": "ISO 3166-1 alpha-2 country code of counterparty, e.g. IR",
                },
            },
            "required": ["amount", "currency", "transaction_type"],
        }),
        "check_sanctions": (check_sanctions, {
            "type": "object",
            "properties": {
                "entity_name": {"type": "string", "description": "Full legal name to screen"},
                "country": {"type": "string", "description": "ISO country code"},
            },
            "required": ["entity_name"],
        }),
        "get_regulatory_limits": (get_regulatory_limits, {
            "type": "object",
            "properties": {
                "jurisdiction": {"type": "string", "description": "Jurisdiction code: EU, UK, US, CH, SG"},
                "transaction_type": {"type": "string", "description": "Optional transaction type"},
            },
            "required": ["jurisdiction"],
        }),
    }

    server_tool_map = {
        "accounts":   ["get_account_balance", "get_transaction_history", "get_customer_accounts"],
        "fx":         ["get_fx_rate", "convert_amount", "get_fx_rates_bulk"],
        "credit":     ["score_credit_risk", "get_risk_factors"],
        "compliance": ["check_aml_threshold", "check_sanctions", "get_regulatory_limits"],
    }

    active_names: list[str] = []
    for server in server_names:
        active_names.extend(server_tool_map.get(server, []))

    tools_for_api: list[dict] = []
    callable_map: dict[str, Callable] = {}

    for name in active_names:
        fn, schema = all_tools[name]
        description = (inspect.getdoc(fn) or name).split("\n\n")[0].strip()
        tools_for_api.append({
            "name": name,
            "description": description,
            "input_schema": schema,
        })
        callable_map[name] = fn

    return tools_for_api, callable_map


async def call_tool(fn: Callable, tool_input: dict) -> str:
    """Call a tool function — handles both sync and async functions."""
    if inspect.iscoroutinefunction(fn):
        result = await fn(**tool_input)
    else:
        result = fn(**tool_input)
    return json.dumps(result, default=str)


# ── Agent loop ────────────────────────────────────────────────────────────────


async def run_agent(scenario_key: str = "full") -> None:
    scenario = SCENARIOS[scenario_key]

    console.print(Rule(f"[bold]Banking MCP Agent — {scenario['title']}[/bold]"))
    console.print()
    console.print(Panel(scenario["prompt"], title="User query", border_style="blue"))
    console.print()

    console.print("[dim]Loading tools...[/dim]")
    tools, callable_map = _build_tool_registry(scenario["servers"])
    console.print(f"[dim]Loaded {len(tools)} tools from {len(scenario['servers'])} server(s).[/dim]")
    console.print()

    client = anthropic.Anthropic()

    messages: list[dict] = [{"role": "user", "content": scenario["prompt"]}]

    system_prompt = (
        "You are a senior banking AI assistant with access to live banking tools. "
        "You must always call the appropriate tools to get accurate data — never guess figures. "
        "When presenting financial data, always include currency codes. "
        "When making recommendations, clearly state the evidence from tool results. "
        "Compliance findings must list concrete required actions."
    )

    iteration = 0
    max_iterations = 10

    while iteration < max_iterations:
        iteration += 1
        console.print(f"[dim]Agent iteration {iteration}...[/dim]")

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        text_blocks     = [b for b in response.content if b.type == "text"]
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        for block in text_blocks:
            if block.text.strip():
                console.print(Markdown(block.text))

        if tool_use_blocks:
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_use_blocks:
                console.print(f"\n[cyan]→ Tool:[/cyan] [bold]{block.name}[/bold]")
                preview = json.dumps(block.input)
                console.print(f"  [dim]{preview[:200]}{'...' if len(preview) > 200 else ''}[/dim]")

                fn = callable_map.get(block.name)
                if fn is None:
                    result_text = json.dumps({"error": f"Unknown tool: {block.name}"})
                else:
                    try:
                        result_text = await call_tool(fn, block.input)
                    except Exception as exc:
                        result_text = json.dumps({"error": str(exc)})

                console.print(f"  [green]✓ {len(result_text)} chars returned[/green]")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

            messages.append({"role": "user", "content": tool_results})

        if response.stop_reason == "end_turn":
            console.print()
            console.print(Rule("[green]Agent completed[/green]"))
            break
        elif response.stop_reason != "tool_use":
            console.print(f"[yellow]Unexpected stop reason: {response.stop_reason}[/yellow]")
            break

    if iteration >= max_iterations:
        console.print("[red]Max iterations reached.[/red]")


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Banking MCP Agent Demo")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="full",
        help="Which demo scenario to run (default: full)",
    )
    args = parser.parse_args()
    asyncio.run(run_agent(args.scenario))


if __name__ == "__main__":
    main()