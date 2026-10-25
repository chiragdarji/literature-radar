"""Append one JSON line per brief to logs/runs.jsonl (AD-13): counts, tokens, cost, latency."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from radar.config import ROOT, settings


def append(entry: dict[str, Any], path: Path | None = None) -> Path:
    path = path or ROOT / settings()["log"]["runs_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return path
