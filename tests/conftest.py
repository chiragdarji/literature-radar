from pathlib import Path

import pytest

from radar import http as rhttp

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def no_network_delays(monkeypatch):
    """Tests use saved responses; skip rate-limit sleeps and keep keys out."""
    monkeypatch.setattr(rhttp, "throttle", lambda host, interval: None)
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda s: None)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.setenv("NCBI_EMAIL", "test@example.com")
