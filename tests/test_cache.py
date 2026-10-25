from radar import cache

DAY = 24 * 3600


def test_roundtrip_key_normalisation(tmp_path):
    db = tmp_path / "c.sqlite"
    cache.put("Semaglutide ", 6, {"markdown": "# hi"}, path=db, now=1000)
    entry = cache.get("  semaglutide", 6, path=db, now=1000 + 60)
    assert entry.payload == {"markdown": "# hi"} and not entry.stale
    assert cache.get("semaglutide", 12, path=db, now=1000) is None


def test_expiry_and_stale_read(tmp_path):
    db = tmp_path / "c.sqlite"
    cache.put("pcsk9", 6, {"v": 1}, path=db, now=0)
    assert cache.get("pcsk9", 6, path=db, now=DAY + 1) is None
    stale = cache.get("pcsk9", 6, path=db, now=DAY + 1, allow_stale=True)
    assert stale.stale and stale.payload == {"v": 1}


def test_pinned_never_expires_and_survives_refresh(tmp_path):
    db = tmp_path / "c.sqlite"
    cache.put("denosumab", 6, {"v": 1}, path=db, now=0)
    assert cache.pin("denosumab", 6, path=db)
    assert not cache.pin("missing", 6, path=db)
    assert cache.get("denosumab", 6, path=db, now=30 * DAY).payload == {"v": 1}
    cache.put("denosumab", 6, {"v": 2}, path=db, now=31 * DAY)
    entry = cache.get("denosumab", 6, path=db, now=31 * DAY)
    assert entry.pinned and entry.payload == {"v": 2}
    assert cache.entries(path=db) == [("denosumab", 6, 31 * DAY, True)]
