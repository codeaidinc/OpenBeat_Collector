"""Cross-cutting / module-level scenarios (C1..C7 from tests/SCENARIOS.md).

These complement the route-level E2E tests by covering branches that are awkward
to drive through the HTTP layer (discover_feed branches, verify_source statuses,
registry/storage internals, the support-URL resolver, and i18n parity).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from openbeat_collector import collector
from openbeat_collector.collector import discover_feed, verify_source, collect_source
from openbeat_collector.registry import (load_registry, save_sources, validate_registry, by_id)
from openbeat_collector.schema import Source, RawItem
from openbeat_collector.storage import Store
from openbeat_collector.i18n import strings

HERE = os.path.dirname(os.path.abspath(__file__))
FEED_XML = open(os.path.join(HERE, "sample_feed.xml"), encoding="utf-8").read()
STATS_URI = Path(os.path.join(HERE, "sample_stats.csv")).as_uri()
FEED_URI = Path(os.path.join(HERE, "sample_feed.xml")).as_uri()


# --------------------------------------------------------------------------
# C1 — i18n parity (no missing translations; en != ja for real strings)
# --------------------------------------------------------------------------
def test_c1_i18n_key_parity():
    en, ja = strings("en"), strings("ja")
    assert set(en.keys()) == set(ja.keys())          # every key translated both ways
    assert en["collect_btn"] != ja["collect_btn"]
    assert en["html_lang"] == "en" and ja["html_lang"] == "ja"


# --------------------------------------------------------------------------
# C2 — discover_feed branches (fetch injected = offline)
# --------------------------------------------------------------------------
def test_c2_discover_self_feed():
    r = discover_feed("https://x.test/feed", fetch=lambda u: FEED_XML)
    assert r["status"] == "rss"
    assert "already a feed" in r["detail"]


def test_c2_discover_declared_link():
    page = "https://x.test/"

    def fetch(u):
        if u == "https://x.test/feed.xml":
            return FEED_XML
        if u == page:
            return ('<link rel="alternate" type="application/rss+xml" '
                    'href="/feed.xml">')
        raise OSError("404")

    r = discover_feed(page, fetch=fetch)
    assert r["status"] == "rss"
    assert r["url"] == "https://x.test/feed.xml"


def test_c2_discover_common_path():
    page = "https://y.test/"

    def fetch(u):
        if u == "https://y.test/feed":
            return FEED_XML
        if u == page:
            return "<html><body>no feeds declared here</body></html>"
        raise OSError("404")

    r = discover_feed(page, fetch=fetch)
    assert r["status"] == "rss"
    assert r["url"] == "https://y.test/feed"


def test_c2_discover_html_fallback():
    page = "https://z.test/"
    long_html = "<html><body>" + ("article word " * 100) + "</body></html>"

    def fetch(u):
        if u == page:
            return long_html
        raise OSError("404")

    r = discover_feed(page, fetch=fetch)
    assert r["status"] == "html"


def test_c2_discover_manual():
    page = "https://s.test/"

    def fetch(u):
        if u == page:
            return "<html><body>hi</body></html>"
        raise OSError("404")

    r = discover_feed(page, fetch=fetch)
    assert r["status"] == "manual"


def test_c2_discover_error_exposes_candidates():
    def fetch(u):
        raise OSError("blocked")

    r = discover_feed("https://e.test/news", fetch=fetch)
    assert r["status"] == "error"
    assert r["candidates"]                            # common-path candidates surfaced


# --------------------------------------------------------------------------
# C4 — verify_source statuses (offline)
# --------------------------------------------------------------------------
def _src(**kw):
    base = dict(id="v", country="Testland", source_type="government", name="V",
                url="", lang="en", fetch_method="rss", license_note="x", trust="high")
    base.update(kw)
    return Source(**base)


def test_c4_verify_rss_ok():
    r = verify_source(_src(url=FEED_URI))
    assert r["status"] == "ok" and r["entries"] == 3


def test_c4_verify_empty(tmp_path):
    p = tmp_path / "empty.xml"
    p.write_text('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
                 '<title>e</title></feed>', encoding="utf-8")
    r = verify_source(_src(url=p.as_uri()))
    assert r["status"] == "empty"


def test_c4_verify_parse_error():
    # RSS method pointed at a CSV -> not a feed
    r = verify_source(_src(url=STATS_URI))
    assert r["status"] == "parse_error"


def test_c4_verify_fetch_error(tmp_path):
    missing = (tmp_path / "nope.xml").as_uri()
    r = verify_source(_src(url=missing))
    assert r["status"] == "fetch_error"


def test_c4_verify_robots_blocked(monkeypatch):
    collector._robots_cache.clear()

    def fake_get(url, timeout=None):
        if url.endswith("/robots.txt"):
            return "User-agent: *\nDisallow: /\n"
        raise OSError("should not fetch")

    monkeypatch.setattr(collector, "http_get", fake_get)
    r = verify_source(_src(url="https://blocked.test/feed"))
    assert r["status"] == "robots_blocked"
    collector._robots_cache.clear()


def test_c4_verify_manual():
    r = verify_source(_src(fetch_method="manual"))
    assert r["status"] == "manual"


def test_c4_verify_dataset_ok():
    r = verify_source(_src(
        fetch_method="dataset", url=STATS_URI,
        dataset_spec="format=csv;label=Idx;period=month;value=index_yoy;unit=%"))
    assert r["status"] == "ok" and r["entries"] == 6


# --------------------------------------------------------------------------
# C3 — collect_source (keyword filter + dataset adapter)
# --------------------------------------------------------------------------
def test_c3_collect_keyword_filter():
    res = collect_source(_src(url=FEED_URI), keywords=["Middle East"])
    assert len(res.items) == 1                        # only the ME entry


def test_c3_collect_dataset_unique_period_urls():
    res = collect_source(_src(
        fetch_method="dataset", url=STATS_URI,
        dataset_spec="format=csv;label=Idx;period=month;value=index_yoy;unit=%;max=6"))
    assert len(res.items) == 6
    assert all("#" in it.url for it in res.items)     # per-period unique URL
    assert any("4.2" in it.title for it in res.items) # newest value ingested


# --------------------------------------------------------------------------
# C5 — registry: per-source country, save round-trip, validation
# --------------------------------------------------------------------------
def test_c5_per_source_country(tmp_path):
    (tmp_path / "r.yaml").write_text(
        "country: Testland\nsources:\n"
        "  - id: a\n    name: A\n    url: https://a.test/f\n    fetch_method: rss\n"
        "    source_type: media\n    license_note: x\n    trust: medium\n"
        "  - id: b\n    name: B\n    country: UK\n    url: https://b.test/f\n"
        "    fetch_method: rss\n    source_type: media\n    license_note: x\n    trust: medium\n",
        encoding="utf-8")
    reg = load_registry(str(tmp_path))
    assert by_id(reg, "a").country == "Testland"      # inherits file country
    assert by_id(reg, "b").country == "UK"             # overrides it


def test_c5_save_round_trip(tmp_path):
    srcs = [_src(id="a", url="https://a.test/f", country="UK"),
            _src(id="b", url="https://b.test/f", country="France")]
    path = str(tmp_path / "out.yaml")
    save_sources(srcs, path)
    reg = load_registry(str(tmp_path))
    assert {s.id for s in reg} == {"a", "b"}
    assert by_id(reg, "a").country == "UK"
    assert by_id(reg, "b").url == "https://b.test/f"


def test_c5_validation():
    assert validate_registry([_src(url="https://a.test/f")]) == []      # clean
    dup = validate_registry([_src(id="x", url="https://a/f"),
                             _src(id="x", url="https://b/f")])
    assert any("duplicate id" in i for i in dup)
    miss = validate_registry([_src(id="", name="", url="https://a/f")])
    assert miss                                                          # id/name missing
    scheme = validate_registry([_src(url="ftp://a/f")])
    assert any("scheme" in i for i in scheme)


# --------------------------------------------------------------------------
# C6 — storage: upsert / dedup / full-text refresh
# --------------------------------------------------------------------------
def test_c6_upsert_dedup_and_refresh(tmp_path):
    store = Store(str(tmp_path / "s.sqlite"))
    src = _src(id="ft", fetch_method="rss", url="https://ex.test/feed")
    url = "https://ex.test/article/1"
    summary = RawItem.make(src, url, "Head", "short.", summary_excerpt="short.")
    assert store.upsert_item(summary, overwrite_by_url=True) == "added"
    full = RawItem.make(src, url, "Head", "Full body. " * 40, summary_excerpt="short.")
    assert store.upsert_item(full, overwrite_by_url=True) == "updated"   # refreshed in place
    assert len(store.items(country="Testland")) == 1                     # URL dedup kept
    assert store.upsert_item(full, overwrite_by_url=True) == "skipped"   # idempotent
    assert store.upsert_item(summary, overwrite_by_url=False) == "skipped"  # legacy dedup
    store.close()


# --------------------------------------------------------------------------
# C7 — support-URL resolution (env > support_url.txt > GitHub) + substitution
# --------------------------------------------------------------------------
def test_c7_support_url_env_and_substitution(make_client):
    client, ctx = make_client(support_url="https://form.test/?u={site}&d={detail}")
    app = ctx["app"]
    assert app.SUPPORT_URL_TEMPLATE == "https://form.test/?u={site}&d={detail}"
    u = app._support_url("https://a.test/b c", "hi")
    assert "https%3A%2F%2Fa.test%2Fb%20c" in u        # {site} URL-encoded
    assert u.endswith("d=hi")


def test_c7_support_url_falls_back_to_bundled_file(make_client):
    client, ctx = make_client(support_url=None)        # no env -> bundled support_url.txt
    assert ctx["app"].SUPPORT_URL_TEMPLATE == "https://forms.gle/isMmNXiMyto6th4m9"
