"""The only module that talks to the Anthropic SDK: one JSON-schema call with usage tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import anthropic

from radar.config import settings

FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client: anthropic.Anthropic | None = None


class ModelError(RuntimeError):
    """The model call finished without usable JSON."""


class ModelRefusal(ModelError):
    def __init__(self, category: str | None):
        super().__init__(f"model declined the request (category: {category or 'unknown'})")
        self.category = category


@dataclass(frozen=True)
class Usage:
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def cost_usd(self) -> float | None:
        price = settings()["prices_per_mtok"].get(self.model)
        if price is None:
            return None
        return (self.input_tokens * price["input"] + self.output_tokens * price["output"]) / 1e6


def client() -> anthropic.Anthropic:
    """Process-wide client; reads ANTHROPIC_API_KEY (loaded from .env by settings())."""
    global _client
    if _client is None:
        settings()
        _client = anthropic.Anthropic()
    return _client


def call_json(
    *,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    effort: str,
    max_tokens: int,
    fallback: bool = False,
    api: Any = None,
) -> tuple[dict[str, Any], Usage]:
    """One request constrained to `schema`; returns the parsed JSON and token usage."""
    api = api or client()
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    }
    if fallback:
        # On a refusal the API re-runs the request on a fallback model in the same call.
        response = api.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
    else:
        response = api.messages.create(**kwargs)

    usage = Usage(
        model=getattr(response, "model", model) or model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        raise ModelRefusal(getattr(details, "category", None))
    if response.stop_reason == "max_tokens":
        raise ModelError(f"{model} hit max_tokens ({max_tokens}) before finishing")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise ModelError(f"{model} returned no text block")
    try:
        return json.loads(text), usage
    except json.JSONDecodeError as exc:
        raise ModelError(f"{model} returned invalid JSON: {exc}") from exc
