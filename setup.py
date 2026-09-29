"""Compatibility shim for legacy tooling.

All build and distribution metadata lives in ``pyproject.toml``. Hatchling is the
authoritative build backend; keeping this file intentionally metadata-free prevents
the two packaging configurations drifting apart.
"""

from setuptools import setup


setup()
