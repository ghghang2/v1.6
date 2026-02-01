# app/tools/get_stock_price.py
"""Utility tool that returns a mock stock price.

This module is discovered by :mod:`app.tools.__init__`.  The discovery
mechanism looks for a ``func`` attribute (or the first callable) and
uses the optional ``name`` and ``description`` attributes to build the
OpenAI function‑calling schema.  The public API therefore consists of

* ``func`` – the callable that implements the tool.
* ``name`` – the name the model will use to refer to the tool.
* ``description`` – a short human‑readable description.

The function returns a **JSON string**.  On success the JSON contains a
``ticker`` and ``price`` key; on failure it contains an ``error`` key.
This format matches the expectations of the OpenAI function‑calling
workflow used in :mod:`app.chat`.
"""

from __future__ import annotations

import json
from typing import Dict

# ---------------------------------------------------------------------------
#  Data & helpers
# ---------------------------------------------------------------------------
# Sample data – in a real world tool this would call a finance API.
_SAMPLE_PRICES: Dict[str, float] = {
    "AAPL": 170.23,
    "GOOGL": 2819.35,
    "MSFT": 299.79,
    "AMZN": 3459.88,
    "NVDA": 568.42,
}

# ---------------------------------------------------------------------------
#  The tool implementation
# ---------------------------------------------------------------------------

def _get_stock_price(ticker: str) -> str:
    """Return the current stock price for *ticker*.

    Parameters
    ----------
    ticker:
        Stock symbol (e.g. ``"AAPL"``).  The lookup is case‑insensitive.

    Returns
    -------
    str
        JSON string containing ``ticker`` and ``price`` keys.  If the
        ticker is unknown, ``price`` is set to ``"unknown"``.
    """
    price = _SAMPLE_PRICES.get(ticker.upper(), "unknown")
    result = {"ticker": ticker.upper(), "price": price}
    return json.dumps(result)

# ---------------------------------------------------------------------------
#  Public attributes for auto‑discovery
# ---------------------------------------------------------------------------
# ``tools/__init__`` expects the module to expose a ``func`` attribute.
func = _get_stock_price
name = "get_stock_price"
description = "Return the current price for a given stock ticker."

# Keep the public surface minimal.
__all__ = ["func", "name", "description"]
