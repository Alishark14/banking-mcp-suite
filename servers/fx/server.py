"""
FX Rate MCP Server

Exposes live foreign exchange rates sourced from frankfurter.app,
which publishes daily ECB reference rates. No API key required.

Run standalone:
    python -m servers.fx.server

Or via FastMCP dev mode:
    fastmcp dev servers/fx/server.py
"""

from __future__ import annotations

from typing import Annotated

import httpx
from fastmcp import FastMCP
from pydantic import Field

BASE_URL = "https://api.frankfurter.app"

SUPPORTED_CURRENCIES = {
    "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR",
    "GBP", "HKD", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW",
    "MXN", "MYR", "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD",
    "THB", "TRY", "USD", "ZAR",
}

mcp = FastMCP(
    name="banking-fx",
    instructions=(
        "Provides live ECB foreign exchange rates via frankfurter.app. "
        "Rates are published on European business days. "
        "Always state the rate date when quoting an exchange rate. "
        "Do not use these rates for legally binding transactions."
    ),
)


# ── Internal HTTP helper ──────────────────────────────────────────────────────


async def _fetch(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{BASE_URL}{path}", params=params)
        response.raise_for_status()
        return response.json()


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
async def get_fx_rate(
    base: Annotated[str, Field(description="Base currency ISO code, e.g. EUR")],
    quote: Annotated[str, Field(description="Quote currency ISO code, e.g. USD")],
) -> dict:
    """
    Return the latest ECB reference exchange rate between two currencies.

    Example: base=EUR, quote=USD returns how many USD per 1 EUR.
    """
    base = base.upper()
    quote = quote.upper()

    for code in (base, quote):
        if code not in SUPPORTED_CURRENCIES:
            return {
                "error": f"Unsupported currency '{code}'.",
                "supported": sorted(SUPPORTED_CURRENCIES),
            }

    if base == quote:
        return {"base": base, "quote": quote, "rate": 1.0, "date": "n/a", "note": "Same currency"}

    try:
        data = await _fetch("/latest", params={"from": base, "to": quote})
    except httpx.HTTPError as exc:
        return {"error": f"FX API unavailable: {exc}"}

    rate = data["rates"].get(quote)
    if rate is None:
        return {"error": f"Rate for {quote} not found in response."}

    return {
        "base": base,
        "quote": quote,
        "rate": rate,
        "date": data.get("date"),
        "source": "ECB via frankfurter.app",
    }


@mcp.tool()
async def convert_amount(
    amount: Annotated[float, Field(gt=0, description="Amount to convert")],
    from_currency: Annotated[str, Field(description="Source currency ISO code, e.g. GBP")],
    to_currency: Annotated[str, Field(description="Target currency ISO code, e.g. EUR")],
) -> dict:
    """
    Convert a monetary amount from one currency to another using live ECB rates.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    for code in (from_currency, to_currency):
        if code not in SUPPORTED_CURRENCIES:
            return {"error": f"Unsupported currency '{code}'."}

    if from_currency == to_currency:
        return {
            "original_amount": amount,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "converted_amount": amount,
            "rate": 1.0,
            "date": "n/a",
        }

    try:
        data = await _fetch("/latest", params={"amount": amount, "from": from_currency, "to": to_currency})
    except httpx.HTTPError as exc:
        return {"error": f"FX API unavailable: {exc}"}

    converted = data["rates"].get(to_currency)
    if converted is None:
        return {"error": "Conversion result not found in API response."}

    return {
        "original_amount": amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "converted_amount": round(converted, 4),
        "rate": round(converted / amount, 6),
        "date": data.get("date"),
        "source": "ECB via frankfurter.app",
    }


@mcp.tool()
async def get_fx_rates_bulk(
    base: Annotated[str, Field(description="Base currency ISO code, e.g. EUR")],
    quotes: Annotated[
        list[str],
        Field(description="List of quote currency ISO codes, e.g. ['USD', 'GBP', 'JPY']"),
    ],
) -> dict:
    """
    Return live ECB rates from a base currency to multiple quote currencies in one call.
    Useful for multi-currency portfolio valuation or risk exposure snapshots.
    """
    base = base.upper()
    quotes = [q.upper() for q in quotes]

    invalid = [q for q in quotes if q not in SUPPORTED_CURRENCIES and q != base]
    if base not in SUPPORTED_CURRENCIES:
        return {"error": f"Unsupported base currency '{base}'."}
    if invalid:
        return {"error": f"Unsupported quote currencies: {invalid}"}

    target_currencies = [q for q in quotes if q != base]
    if not target_currencies:
        return {"base": base, "rates": {base: 1.0}, "date": "n/a"}

    try:
        data = await _fetch("/latest", params={"from": base, "to": ",".join(target_currencies)})
    except httpx.HTTPError as exc:
        return {"error": f"FX API unavailable: {exc}"}

    rates = data.get("rates", {})
    if base in quotes:
        rates[base] = 1.0

    return {
        "base": base,
        "rates": rates,
        "date": data.get("date"),
        "source": "ECB via frankfurter.app",
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
