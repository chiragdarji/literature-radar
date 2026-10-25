from pathlib import Path

import pytest

from radar import http as rhttp

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def no_network_delays(monkeypatch, tmp_path):
    """Tests use saved responses; skip rate-limit sleeps, keep keys out, use a fresh database."""
    from radar.config import settings

    monkeypatch.setitem(settings()["history"], "path", str(tmp_path / "radar.db"))
    monkeypatch.setattr(rhttp, "throttle", lambda host, interval: None)
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda s: None)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.setenv("NCBI_EMAIL", "test@example.com")


class FakeAPI:
    """Stands in for anthropic.Anthropic: records calls, answers via a responder function.

    responder(kwargs) returns a dict (sent back as JSON text) or a full response object.
    """

    def __init__(self, responder):
        import json
        from types import SimpleNamespace

        self.calls = []

        def create(**kwargs):
            self.calls.append(kwargs)
            out = responder(kwargs)
            if isinstance(out, dict):
                return SimpleNamespace(
                    model=kwargs["model"],
                    stop_reason="end_turn",
                    stop_details=None,
                    content=[SimpleNamespace(type="thinking", thinking=""),
                             SimpleNamespace(type="text", text=json.dumps(out))],
                    usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
                )
            return out

        self.messages = SimpleNamespace(create=create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=create))


@pytest.fixture
def fake_api():
    return FakeAPI
