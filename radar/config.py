"""Load config.toml and .env settings."""

from __future__ import annotations

import os
import tomllib
from functools import cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.toml"


@cache
def settings() -> dict[str, Any]:
    """Return config.toml as a dict, loading .env into the environment once."""
    load_dotenv(ROOT / ".env")
    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)


def env(name: str) -> str | None:
    """Return a non-empty environment variable, or None."""
    settings()  # ensure .env is loaded
    value = os.environ.get(name, "").strip()
    return value or None
