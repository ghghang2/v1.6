"""Test that all public modules in the repository can be imported.

The repository is expected to expose a number of top‑level modules under
``app``.  Importing each module ensures that the package structure is
correct and that dependencies are installed.  The test simply imports
the modules and checks that the objects are present.
"""

import importlib
import pkgutil
import sys

import pytest


def get_public_modules(package_name: str):
    """Yield names of public modules inside *package_name*.

    Public modules are those that are not prefixed with an underscore.
    """
    package = importlib.import_module(package_name)
    for _, name, ispkg in pkgutil.iter_modules(package.__path__):
        if not name.startswith("_") and not ispkg:
            yield f"{package_name}.{name}"


def test_all_public_modules_importable():
    """Ensure that all public modules can be imported without error."""
    for mod_name in get_public_modules("app"):
        try:
            importlib.import_module(mod_name)
        except Exception as exc:  # pragma: no cover - import errors are critical
            pytest.fail(f"Failed to import {mod_name}: {exc}")
