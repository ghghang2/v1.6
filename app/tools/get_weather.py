# app/tools/weather.py
"""
Get the current weather for a city using the public wttr.in service.

No API key or external dependencies are required – the tool uses the
built‑in urllib module, which ships with every Python installation.
"""

import json
import urllib.request
from typing import Dict

def _get_weather(city: str) -> str:
    """
    Return a short weather description for *city*.

    Parameters
    ----------
    city : str
        The name of the city to query (e.g. "Taipei").

    Returns
    -------
    str
        JSON string. On success:

            {"city":"Taipei","weather":"☀️  +61°F"}

        On error:

            {"error":"<error message>"}
    """
    try:
        # wttr.in gives a plain‑text summary; we ask for the
        # “format=1” variant which is a single line.
        url = f"https://wttr.in/{urllib.parse.quote_plus(city)}?format=1"
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode().strip()

        # The response is already a nice one‑line string
        result: Dict[str, str] = {"city": city, "weather": body}
        return json.dumps(result)
    except Exception as exc:      # pragma: no cover
        return json.dumps({"error": str(exc)})

# Public attributes used by the tool loader
func = _get_weather
name = "get_weather"
description = (
    "Return a concise, human‑readable weather summary for a city using wttr.in. "
    "No API key or external packages are required."
)

__all__ = ["func", "name", "description"]