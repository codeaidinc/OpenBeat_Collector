#!/usr/bin/env python3
"""Offline self-test — verifies the main pipeline and Step 1 features without a network connection."""
from __future__ import annotations

import os
import sys
import json
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from openbeat_collector.schema import Source
from openbeat_collector.collector import collect_source, verify_source
from openbeat_collector.storage import Store
from openbeat_collector.export import build_corpus
from openbeat_collector.registry import load_registry, validate_registry
from openbeat_collector.themes import load_themes


def main():
    feed_path = os.path.join(HERE, "tests", "sample_feed.xml")
    assert os.path.exists(feed_path), f"sample feed missing: {feed_path}"
    feed_url = Path(feed_path).as_uri()  # file:/// URI that works on Windows and Linux

    src = Source(
        id="test-sample", country="Testland", source_type="government",
        name="Sample Gov Feed", url=feed_url, lang="en",
        fetch_method="rss", license_note="test", trust="high",
    )

    tmpdb = os.path.join(tempfile.gettempdir(), "rwt_selftest.sqlite")
    if os.path.exists(tmpdb):
        os.remove(tmpdb)
    store = Store(tmpdb)
    store.sync_registry([src])

    res = collect_source(src, is_duplicate=store.is_duplicate)
    n1 = store.add_items(res.items)
    assert not res.errors, f"collection error: {res.errors}"
    assert n1 >= 2, f"no items collected: {n1}"
    print(f"[1] collection OK: {n1} items stored (0 errors)")

    res2 = collect_source(src, is_duplicate=store.is_duplicate)
    n2 = store.add_items(res2.items)
    assert n2 == 0, f"deduplication not working: {n2} items re-added"
    assert res2.skipped_duplicates >= n1
    print(f"[2] deduplication OK: re-collect gave {n2} new / {res2.skipped_duplicates} skipped")

    items = store.items(country="Testland")
    it = items[0]
    for key in ("url", "fetched_at", "source_name", "country", "license_note", "hash"):
        assert it.get(key), f"missing provenance field: {key}"
    print("[3] provenance OK: URL/fetched_at/source/country/license/hash all present")

    corpus = build_corpus(store, country="Testland")
    assert corpus["schema"] == "rwt.raw_corpus"
    assert corpus["item_count"] == len(items)
    assert "rwt.raw_corpus" in json.dumps(corpus, ensure_ascii=False)
    print(f"[4] raw corpus JSON OK: schema={corpus['schema']} v{corpus['schema_version']} / {corpus['item_count']} items")

    store.close()
    os.remove(tmpdb)

    # ---- Step 1 added features ----
    tmpdb2 = os.path.join(tempfile.gettempdir(), "rwt_selftest2.sqlite")
    if os.path.exists(tmpdb2):
        os.remove(tmpdb2)
    store2 = Store(tmpdb2)
    res_kw = collect_source(src, is_duplicate=store2.is_duplicate,
                            keywords=["energy", "supply-chain", "supply chain"])
    n_kw = store2.add_items(res_kw.items)
    assert 1 <= n_kw < n1, f"theme filter not working: {n_kw} of {n1}"
    print(f"[5] theme filter OK: collected only {n_kw} keyword matches out of {n1}")
    store2.close(); os.remove(tmpdb2)

    vr = verify_source(src)
    assert vr["status"] == "ok", f"verify failed: {vr}"
    assert vr["entries"] >= 2
    print(f"[6] feed health check OK: status={vr['status']} entries={vr['entries']}")

    reg = load_registry(os.path.join(HERE, "sources"))
    assert len(reg) >= 12, f"too few registry entries: {len(reg)}"
    issues = validate_registry(reg)
    assert not issues, f"bundled registry has validation errors: {issues}"
    print(f"[7] registry validation OK: all {len(reg)} sources pass (0 problems)")

    bad = Source(id="", country="", source_type="bogus", name="",
                 url="ftp://x", lang="en", fetch_method="weird", trust="???")
    assert validate_registry([bad]), "failed to detect invalid definition"
    print("[8] validation negative control OK: invalid definition correctly detected")

    themes = load_themes(os.path.join(HERE, "themes"))
    assert "example" in themes and len(themes["example"]) >= 10
    print(f"[9] theme load OK: example ({len(themes['example'])} keywords)")

    from openbeat_collector.collector import _rewrite_url
    nhk = next(x for x in reg if x.id == "jp-nhk-business")
    assert nhk.url_rewrite, "NHK has no url_rewrite"
    fixed = _rewrite_url(nhk, "https://news.web.nhk/newsweb/na/na-k10015146761000")
    assert fixed == "https://www3.nhk.or.jp/news/html/k10015146761000.html", fixed
    print("[10] source URL rewrite OK: NHK app URL -> web article URL")

    # [11] statistics dataset adapter (fetch_method=dataset, CSV -> items, continuous ingest)
    # Note: a non-ASCII (Japanese) label is used on purpose to verify that
    # labels in any language flow through unchanged into item titles.
    stats_path = os.path.join(HERE, "tests", "sample_stats.csv")
    assert os.path.exists(stats_path), f"sample stats CSV missing: {stats_path}"
    stats_url = Path(stats_path).as_uri()
    dsrc = Source(
        id="test-stats", country="Testland", source_type="statistics",
        name="Sample Stats", url=stats_url, lang="ja", fetch_method="dataset",
        license_note="test", trust="high",
        dataset_spec="format=csv;label=企業物価指数(前年比);period=month;value=index_yoy;unit=%;delta=mom;max=4",
    )
    tmpdb3 = os.path.join(tempfile.gettempdir(), "rwt_selftest3.sqlite")
    if os.path.exists(tmpdb3):
        os.remove(tmpdb3)
    store3 = Store(tmpdb3)
    r = collect_source(dsrc, is_duplicate=store3.is_duplicate)
    n = store3.add_items(r.items)
    assert not r.errors, f"dataset collection error: {r.errors}"
    assert n == 4, f"expected max=4 but got {n}"
    rows = store3.items(country="Testland")
    assert all("企業物価指数" in it["title"] for it in rows), "label missing from title"
    assert any("4.2" in it["title"] for it in rows), "latest value (2026-06=4.2) not ingested"
    assert all("#" in it["url"] for it in rows), "missing per-period unique URL (#period)"
    print(f"[11] stats adapter OK: CSV -> {n} items (latest max, per-period unique URL, faithful to values)")

    # [12] continuous ingest: a re-run adds 0 (dedup) — only new releases grow
    r2 = collect_source(dsrc, is_duplicate=store3.is_duplicate)
    n2 = store3.add_items(r2.items)
    assert n2 == 0 and r2.skipped_duplicates >= 4, f"dataset dedup failed: new={n2}"
    print(f"[12] dataset continuous ingest OK: re-run gave {n2} new / {r2.skipped_duplicates} skipped (only new periods grow)")

    # [13] dataset verify and keyword filtering
    vd = verify_source(dsrc)
    assert vd["status"] == "ok" and vd["entries"] == 6, f"dataset verify failed: {vd}"
    tmpdb4 = os.path.join(tempfile.gettempdir(), "rwt_selftest4.sqlite")
    if os.path.exists(tmpdb4):
        os.remove(tmpdb4)
    store4 = Store(tmpdb4)
    r3 = collect_source(dsrc, is_duplicate=store4.is_duplicate, keywords=["企業物価"])
    assert store4.add_items(r3.items) == 4, "matching keyword did not collect"
    store4.close(); os.remove(tmpdb4)
    store5 = Store(tmpdb4)
    r4 = collect_source(dsrc, is_duplicate=store5.is_duplicate, keywords=["nonexistent-term-XYZ"])
    assert store5.add_items(r4.items) == 0, "non-matching keyword still collected"
    store5.close(); os.remove(tmpdb4)
    store3.close(); os.remove(tmpdb3)
    print(f"[13] dataset verify + filter OK: verify entries={vd['entries']} / match 4, non-match 0")

    # [14] full-text refresh overwrites a summary-only row in place (URL dedup kept)
    from openbeat_collector.schema import RawItem
    tmpdb6 = os.path.join(tempfile.gettempdir(), "rwt_selftest6.sqlite")
    if os.path.exists(tmpdb6):
        os.remove(tmpdb6)
    store6 = Store(tmpdb6)
    fsrc = Source(id="ft", country="Testland", source_type="media",
                  name="FT source", url="http://example.test/feed", lang="en",
                  fetch_method="rss", license_note="test", trust="medium")
    art_url = "http://example.test/article/1"
    summary_item = RawItem.make(fsrc, art_url, "Headline", "short summary.",
                                summary_excerpt="short summary.")
    assert store6.upsert_item(summary_item, overwrite_by_url=True) == "added"
    full_body = "Full article body. " * 40
    full_item = RawItem.make(fsrc, art_url, "Headline", full_body,
                             summary_excerpt="short summary.")
    assert store6.upsert_item(full_item, overwrite_by_url=True) == "updated", "full text did not overwrite"
    rows = store6.items(country="Testland")
    assert len(rows) == 1, f"URL dedup broken: {len(rows)} rows"
    assert len(rows[0]["body_raw"]) > 100, "body was not refreshed to full text"
    # re-applying identical full text is a no-op
    assert store6.upsert_item(full_item, overwrite_by_url=True) == "skipped"
    # without overwrite, the same URL is treated as a duplicate (legacy behavior)
    assert store6.upsert_item(summary_item, overwrite_by_url=False) == "skipped"
    store6.close(); os.remove(tmpdb6)
    print("[14] full-text refresh OK: summary row overwritten in place (1 row kept, identical = no-op)")

    print("\nOK all tests passed: collect -> extract -> deduplicate -> provenance -> boundary JSON, plus theme filtering, full-text refresh, health check and validation.")


if __name__ == "__main__":
    main()
