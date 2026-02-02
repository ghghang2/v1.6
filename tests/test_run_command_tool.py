import json
import os
import sys
from pathlib import Path

# Ensure the repository root is on sys.path for imports
sys.path.append(os.path.abspath("."))

from app.tools.run_command import func as run_command


def test_run_command_basic():
    """Verify that a simple command returns stdout, stderr and exit code."""
    result_json = run_command("echo hello")
    result = json.loads(result_json)
    assert "stdout" in result and "stderr" in result and "exit_code" in result
    assert result["stdout"].strip() == "hello"
    assert result["stderr"].strip() == ""
    assert result["exit_code"] == 0


def test_run_command_in_repo_root():
    """Verify that the command always runs in the repository root.

    The :mod:`app.tools.run_command` implementation no longer accepts a
    ``cwd`` argument – it always executes in the repository root.  This
    test checks that the working directory reported by ``pwd`` matches the
    repository root path.
    """
    repo_root = Path(__file__).resolve().parents[1]
    result_json = run_command("pwd")
    result = json.loads(result_json)
    assert result["exit_code"] == 0
    assert result["stdout"].strip() == str(repo_root)


def test_run_command_error():
    """Verify that a non-existent command returns a non-zero exit code."""
    result_json = run_command("this-command-does-not-exist")
    result = json.loads(result_json)
    assert "stdout" in result
    assert "stderr" in result
    assert "exit_code" in result
    assert result["exit_code"] != 0

