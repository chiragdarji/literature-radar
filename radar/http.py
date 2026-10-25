"""Shared HTTP client with retries and a per-host rate limiter."""

from __future__ import annotations

import threading
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from radar import history
from radar.config import settings

RETRY_STATUSES = {429, 500, 502, 503, 504}
PRIVATE_PARAMS = {"api_key", "email", "tool"}  # never part of a cache key

_client: httpx.Client | None = None
_lock = threading.Lock()
_last_call: dict[str, float] = {}


def client() -> httpx.Client:
    """Return the process-wide client, creating it on first use."""
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=settings()["fetch"]["timeout_s"],
            headers={"User-Agent": "literature-radar/0.1"},
            follow_redirects=True,
        )
    return _client


def throttle(host: str, min_interval_s: float) -> None:
    """Block until at least min_interval_s has passed since the last call to host."""
    with _lock:
        wait = _last_call.get(host, 0.0) + min_interval_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRY_STATUSES
    return isinstance(exc, httpx.TransportError)


def cache_key(url: str, params: dict[str, Any]) -> str:
    """URL plus sorted parameters, leaving out credentials and contact details."""
    kept = sorted((k, str(v)) for k, v in params.items() if k not in PRIVATE_PARAMS)
    return f"{url}?{urlencode(kept)}"


def get(
    url: str,
    params: dict[str, Any],
    *,
    min_interval_s: float = 0.0,
    http: httpx.Client | None = None,
    cache: bool = False,
) -> httpx.Response:
    """GET with throttling and exponential-backoff retries on timeouts, 429 and 5xx.

    With cache=True, a successful response is kept for api_cache_hours in data/radar.db
    and served from there on repeat calls (F11).
    """
    if cache:
        key = cache_key(url, params)
        if (hit := history.api_cache_get(key)) is not None:
            return httpx.Response(200, text=hit, request=httpx.Request("GET", url))
        response = get(url, params, min_interval_s=min_interval_s, http=http)
        history.api_cache_put(key, response.text)
        return response

    http = http or client()
    host = urlsplit(url).netloc

    @retry(
        retry=retry_if_exception(_retryable),
        stop=stop_after_attempt(settings()["fetch"]["max_retries"]),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    def _do() -> httpx.Response:
        throttle(host, min_interval_s)
        response = http.get(url, params=params)
        response.raise_for_status()
        return response

    return _do()
