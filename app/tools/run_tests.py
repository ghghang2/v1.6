# app/tools/run_tests.py
"""Run the repository's pytest suite and return a JSON summary.

The function returns a stringified JSON object that contains:
  * passed   – number of tests that passed
  * failed   – number of tests that failed
  * errors   – number of errored tests
  * output   – the raw stdout from pytest

If anything goes wrong, the JSON payload contains an `error` key.
"""

import json, subprocess
from pathlib import Path
from typing import Dict


def _run_tests() -> str:
    """Execute `pytest -q` in the repository root and return JSON."""
    try:
        proc = subprocess.run(
            ["pytest", "-q"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[2],  # repo root
        )

        # Parse the final line: "X passed, Y failed, Z errors"
        stats_line = proc.stdout.splitlines()[-1]
        passed = int(stats_line.split()[1].split(":")[0])
        failed = int(stats_line.split()[2].split(":")[0])
        errors = int(stats_line.split()[3].split(":")[0])

        result: Dict = {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "output": proc.stdout,
        }
        return json.dumps(result)

    except Exception as exc:
        return json.dumps({"error": str(exc)})

# Public attributes for the discovery logic
func = _run_tests
name = "run_tests"
description = "Run the repository's pytest suite and return the results."
__all__ = ["func", "name", "description"]
