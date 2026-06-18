"""Regression tests for the `cli.py pack ...` subcommands (rwt/packcli.py).

Offline and deterministic: uses the bundled packs/ catalog and an isolated temp
data dir, so no network and no pollution of the repo's data/.
"""
import os
import sys
from argparse import Namespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PACKS = os.path.join(REPO, "packs")
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from openbeat_collector import packcli  # noqa: E402


def _run(cmd, here, **kw):
    return packcli.cmd_pack(Namespace(pack_cmd=cmd, **kw), here)


def test_validate_bundled_packs_ok():
    # The shipped packs (4 beats + crisis-response) must all be valid.
    issues = packcli.validate_packs(PACKS)
    assert issues == [], issues


def test_validate_catches_bad_pack(tmp_path):
    bad = tmp_path / "packs" / "broken"
    bad.mkdir(parents=True)
    (bad / "manifest.yaml").write_text(
        "schema: rwt.pack\nid: broken\n", encoding="utf-8")  # missing required fields
    issues = packcli.validate_packs(str(tmp_path / "packs"))
    assert any("required field" in m for m in issues)


def test_list_and_validate_via_cmd(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENBEAT_PACKS_DIR", PACKS)
    assert _run("list", str(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "crisis-response" in out and "EMERGENCY" in out
    assert _run("validate", str(tmp_path), dir=None) == 0


def test_free_tier_single_active_and_paid_gating(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBEAT_PACKS_DIR", PACKS)
    here = str(tmp_path)
    # free pack installs + activates
    assert _run("install", here, id="science-tech") == 0
    assert _run("activate", here, id="science-tech") == 0
    # paid pack blocked without a license
    assert _run("activate", here, id="crisis-response") == 1
    # license unlocks it (free tier); activating replaces the previous one
    assert _run("license", here, key="DEMO-CRISIS-2026", clear=False) == 0
    assert _run("activate", here, id="crisis-response") == 0
    ps = packcli.build_pack_store(here)
    assert ps.activated() == ["crisis-response"]
    # active dirs were rebuilt to exactly the active pack
    asrc = os.path.join(here, "data", "active_sources")
    assert sorted(os.listdir(asrc)) == ["crisis-response.yaml"]


def test_pro_tier_multiple_active(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBEAT_PACKS_DIR", PACKS)
    here = str(tmp_path)
    assert _run("license", here, key="DEMO-ALL-2026", clear=False) == 0
    for pid in ("science-tech", "food-agriculture", "crisis-response"):
        assert _run("activate", here, id=pid) == 0
    ps = packcli.build_pack_store(here)
    assert set(ps.activated()) == {"science-tech", "food-agriculture", "crisis-response"}
    assert ps.active_limit() is None


def test_unknown_pack_and_bad_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBEAT_PACKS_DIR", PACKS)
    here = str(tmp_path)
    assert _run("install", here, id="nope") == 1
    assert _run("activate", here, id="nope") == 1
    assert _run("license", here, key="NOT-A-KEY", clear=False) == 1


def test_update_refreshes_active_pack(tmp_path, monkeypatch):
    # `pack update` must re-copy bundled content and rebuild the active dirs,
    # so a stale active copy (e.g. an old source URL) gets replaced.
    monkeypatch.setenv("OPENBEAT_PACKS_DIR", PACKS)
    here = str(tmp_path)
    assert _run("install", here, id="science-tech") == 0
    assert _run("activate", here, id="science-tech") == 0
    active = os.path.join(here, "data", "active_sources", "science-tech.yaml")
    installed = os.path.join(here, "data", "packs_installed", "science-tech", "sources.yaml")
    # simulate a stale / hand-edited active copy
    with open(active, "w", encoding="utf-8") as f:
        f.write("country: STALE\nsources: []\n")
    assert _run("update", here, id="science-tech") == 0
    # active dir is rebuilt to match the (re-installed) bundled content
    assert open(active, encoding="utf-8").read() == open(installed, encoding="utf-8").read()
    assert "STALE" not in open(active, encoding="utf-8").read()


def test_update_unknown_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENBEAT_PACKS_DIR", PACKS)
    assert _run("update", str(tmp_path), id="nope") == 1
