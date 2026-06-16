"""Tests for the beat-pack store (rwt.packs.PackStore).

Offline and deterministic: uses the bundled packs/ catalog and demo licenses,
with http_get=None (no network) plus a fake http_get for the remote path.
Run: python -m pytest tests/test_store.py
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openbeat_collector.packs import PackStore  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED = os.path.join(REPO, "packs")


def _store(tmp_path, http_get=None, index_url=None):
    return PackStore(bundled_dir=BUNDLED, data_dir=str(tmp_path),
                     index_url=index_url, http_get=http_get)


def test_index_loads_from_bundled(tmp_path):
    ps = _store(tmp_path)
    ids = [p["id"] for p in ps.packs_meta()]
    assert ids == ["middle-east-impact", "science-tech", "food-agriculture",
                   "health-publichealth", "climate-energy", "crisis-response"]
    assert ps.store_info().get("pro")


def test_free_pack_entitled_paid_locked(tmp_path):
    ps = _store(tmp_path)
    assert ps.is_entitled(ps.pack_meta("science-tech")) is True
    assert ps.is_entitled(ps.pack_meta("food-agriculture")) is False


def test_activate_free_pack_single(tmp_path):
    ps = _store(tmp_path)
    r = ps.activate("science-tech")
    assert r["ok"] and ps.activated() == ["science-tech"]
    assert os.path.exists(os.path.join(tmp_path, "active_sources", "science-tech.yaml"))
    assert os.path.exists(os.path.join(tmp_path, "active_themes", "science-tech.yaml"))


def test_paid_pack_blocked_without_license(tmp_path):
    ps = _store(tmp_path)
    r = ps.activate("food-agriculture")
    assert not r["ok"] and r["error"] == "not_entitled"


def test_demo_license_unlocks_pack(tmp_path):
    ps = _store(tmp_path)
    r = ps.activate_license("DEMO-FOOD-2026")
    assert r["ok"] and r["tier"] == "free" and "food-agriculture" in r["packs"]
    assert ps.is_entitled(ps.pack_meta("food-agriculture"))


def test_free_tier_replaces_active(tmp_path):
    ps = _store(tmp_path)
    ps.activate_license("DEMO-FOOD-2026")
    ps.activate("science-tech")
    ps.activate("food-agriculture")          # free tier: replaces
    assert ps.activated() == ["food-agriculture"]
    files = sorted(os.path.basename(p) for p in
                   os.listdir(os.path.join(tmp_path, "active_sources")))
    assert files == ["food-agriculture.yaml"]


def test_pro_tier_multiple_active(tmp_path):
    ps = _store(tmp_path)
    ps.activate_license("DEMO-PRO-2026")
    assert ps.tier() == "pro" and ps.active_limit() is None
    ps.activate("food-agriculture")
    ps.activate("health-publichealth")
    ps.activate("climate-energy")
    assert set(ps.activated()) == {"food-agriculture", "health-publichealth", "climate-energy"}
    assert len(os.listdir(os.path.join(tmp_path, "active_sources"))) == 3


def test_deactivate(tmp_path):
    ps = _store(tmp_path)
    ps.activate_license("DEMO-PRO-2026")
    ps.activate("food-agriculture")
    ps.activate("health-publichealth")
    ps.deactivate("food-agriculture")
    assert ps.activated() == ["health-publichealth"]


def test_clear_license_back_to_free(tmp_path):
    ps = _store(tmp_path)
    ps.activate_license("DEMO-PRO-2026")
    assert ps.tier() == "pro"
    ps.clear_license()
    assert ps.tier() == "free"


def test_active_sources_parse_as_registry(tmp_path):
    from openbeat_collector.registry import load_registry
    from openbeat_collector.themes import load_themes
    ps = _store(tmp_path)
    ps.activate_license("DEMO-PRO-2026")
    ps.activate("food-agriculture")
    ps.activate("health-publichealth")
    srcs = load_registry(os.path.join(tmp_path, "active_sources"))
    assert len(srcs) == 12
    themes = load_themes(os.path.join(tmp_path, "active_themes"))
    assert set(themes.keys()) == {"food-agriculture", "health-publichealth"}


def test_catalog_state(tmp_path):
    ps = _store(tmp_path)
    ps.activate("science-tech")
    cat = {c["id"]: c for c in ps.catalog()}
    assert cat["science-tech"]["active"] is True
    assert cat["science-tech"]["entitled"] is True
    assert cat["food-agriculture"]["entitled"] is False


def test_remote_index_and_license(tmp_path):
    INDEX = {
        "schema": "rwt.pack_index",
        "store": {"license_endpoint": "https://srv/api/license"},
        "packs": [
            {"id": "science-tech", "paid": False, "files_base": "https://srv/p/science-tech/"},
            {"id": "food-agriculture", "paid": True, "files_base": "https://srv/p/food/"},
        ],
    }

    def fake_http(url):
        if url == "https://srv/index":
            return json.dumps(INDEX)
        if "/api/license" in url and "key=SRV-PRO" in url:
            return json.dumps({"valid": True, "tier": "pro", "packs": ["food-agriculture"]})
        if "/api/license" in url:
            return json.dumps({"valid": False})
        if url.startswith("https://srv/p/food/"):
            fn = url.split("/")[-1].split("?")[0]
            with open(os.path.join(BUNDLED, "food-agriculture", fn), encoding="utf-8") as f:
                return f.read()
        raise RuntimeError("no route " + url)

    ps = _store(tmp_path, http_get=fake_http, index_url="https://srv/index")
    assert [p["id"] for p in ps.packs_meta()] == ["science-tech", "food-agriculture"]
    r = ps.activate_license("SRV-PRO")
    assert r["ok"] and r["tier"] == "pro" and r["source"] == "server"
    assert not ps.activate_license("BOGUS")["ok"]
    r2 = ps.activate("food-agriculture")
    assert r2["ok"] and ps.is_installed("food-agriculture")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
