"""Screen A — the collect page (GET / and its events / APIs).

Covers scenarios A1..A17 from tests/SCENARIOS.md. Everything is offline:
sources are file:// fixtures and any real HTTP is faked in conftest.
"""
from __future__ import annotations

from openbeat_collector.storage import Store


def _text(resp):
    return resp.get_data(as_text=True)


def _db_count(ctx, country=None):
    s = Store(ctx["db_path"])
    try:
        return s.count(country)
    finally:
        s.close()


# --------------------------------------------------------------------------
# A1..A4 — rendering the collect page
# --------------------------------------------------------------------------
def test_a1_index_renders(make_client):
    client, ctx = make_client(lang="en")
    r = client.get("/")
    body = _text(r)
    assert r.status_code == 200
    assert "OpenBeat Collector" in body
    assert "Testland" in body                 # country tab
    assert "Manage sources" in body           # link to screen B
    assert "Saved total" in body
    assert 'name="source_ids"' in body        # source checklist
    assert "Collect" in body                  # collect button


def test_a2_country_selection(make_client):
    client, ctx = make_client(lang="en")
    r = client.get("/?country=Testland")
    assert r.status_code == 200
    # all three fixture sources belong to Testland
    for name in ("Test RSS Feed", "Test Statistics", "Test Manual Source"):
        assert name in _text(r)


def test_a3_theme_filter_view(make_client):
    client, ctx = make_client(lang="en")
    # collect first so there is something to filter
    client.post("/collect", data={"country": "Testland", "source_ids": ["t-rss"]},
                follow_redirects=True)
    r = client.get("/?country=Testland&theme=example")
    body = _text(r)
    assert r.status_code == 200
    assert "Showing theme" in body
    assert "example" in body
    # export link carries the theme
    assert "theme=example" in body


def test_a4_full_text_checkbox_preserved(make_client):
    client, ctx = make_client(lang="en")
    r = client.get("/?country=Testland&full=1")
    # the "fetch full text" checkbox must come back checked (v1.0.3 fix)
    body = _text(r)
    assert 'name="full"' in body
    assert "checked" in body.split('name="full"')[1][:40]


# --------------------------------------------------------------------------
# A5..A9 — collecting
# --------------------------------------------------------------------------
def test_a5_collect_basic(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/collect",
                    data={"country": "Testland", "source_ids": ["t-rss", "t-stats"]},
                    follow_redirects=True)
    body = _text(r)
    assert r.status_code == 200
    assert "Collection complete" in body
    assert "9 new" in body                     # 3 RSS entries + 6 dataset rows
    assert _db_count(ctx, "Testland") == 9


def test_a6_collect_dedup(make_client):
    client, ctx = make_client(lang="en")
    data = {"country": "Testland", "source_ids": ["t-rss", "t-stats"]}
    client.post("/collect", data=data, follow_redirects=True)
    r = client.post("/collect", data=data, follow_redirects=True)
    body = _text(r)
    assert "0 new" in body
    assert "9 duplicates" in body
    assert _db_count(ctx, "Testland") == 9     # no growth


def test_a7_collect_full_text_overwrite(make_client):
    client, ctx = make_client(lang="en")
    # 1) collect summaries only
    client.post("/collect", data={"country": "Testland", "source_ids": ["t-rss"]},
                follow_redirects=True)
    s = Store(ctx["db_path"])
    before = len(s.items(country="Testland")[0]["body_raw"])
    s.close()
    # 2) re-collect with full text on -> rows are refreshed in place
    r = client.post("/collect",
                    data={"country": "Testland", "source_ids": ["t-rss"], "full": "on"},
                    follow_redirects=False)
    assert r.status_code == 302
    assert "full=1" in r.headers["Location"]   # the choice round-trips
    r2 = client.post("/collect",
                     data={"country": "Testland", "source_ids": ["t-rss"], "full": "on"},
                     follow_redirects=True)
    # second full run finds the same URLs already present and refreshes them
    s = Store(ctx["db_path"])
    rows = s.items(country="Testland")
    after = len(rows[0]["body_raw"])
    s.close()
    assert len(rows) == 3                       # URL dedup kept (no duplicate rows)
    assert after > before                       # body grew to full text
    assert "refreshed" in _text(r2)


def test_a8_collect_with_theme(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/collect",
                    data={"country": "Testland", "source_ids": ["t-rss"],
                          "theme": "example"},
                    follow_redirects=True)
    body = _text(r)
    assert "theme: example" in body
    assert "1 new" in body                      # only the energy entry matches
    assert _db_count(ctx, "Testland") == 1


def test_a9_collect_subset(make_client):
    client, ctx = make_client(lang="en")
    client.post("/collect", data={"country": "Testland", "source_ids": ["t-rss"]},
                follow_redirects=True)
    assert _db_count(ctx, "Testland") == 3      # only the RSS source, not the stats


# --------------------------------------------------------------------------
# A10..A12 — manual paste
# --------------------------------------------------------------------------
def test_a10_manual_add(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/manual",
                    data={"country": "Testland", "source_id": "t-manual",
                          "url": "https://example.test/a", "title": "Hand pasted",
                          "text": "Some pasted body text within fair use."},
                    follow_redirects=True)
    body = _text(r)
    assert "Manual item added" in body
    assert _db_count(ctx, "Testland") == 1


def test_a11_manual_requires_body(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/manual",
                    data={"country": "Testland", "source_id": "t-manual",
                          "url": "https://example.test/a", "title": "x", "text": "   "},
                    follow_redirects=True)
    assert "required" in _text(r)
    assert _db_count(ctx, "Testland") == 0


def test_a12_manual_duplicate(make_client):
    client, ctx = make_client(lang="en")
    data = {"country": "Testland", "source_id": "t-manual",
            "url": "https://example.test/a", "title": "x",
            "text": "identical body text"}
    client.post("/manual", data=data, follow_redirects=True)
    r = client.post("/manual", data=data, follow_redirects=True)
    assert "duplicate" in _text(r).lower()
    assert _db_count(ctx, "Testland") == 1


# --------------------------------------------------------------------------
# A13 — export.json
# --------------------------------------------------------------------------
def test_a13_export_json(make_client):
    import json
    client, ctx = make_client(lang="en")
    client.post("/collect", data={"country": "Testland", "source_ids": ["t-rss"]},
                follow_redirects=True)
    r = client.get("/export.json?country=Testland")
    assert r.status_code == 200
    assert r.mimetype == "application/json"
    assert 'filename="rwt_corpus_Testland.json"' in r.headers["Content-Disposition"]
    payload = json.loads(_text(r))
    assert payload["schema"] == "rwt.raw_corpus"
    assert payload["schema_version"] == "1.0"
    assert payload["item_count"] == 3
    assert payload["filter"]["country"] == "Testland"


def test_a13_export_json_theme(make_client):
    import json
    client, ctx = make_client(lang="en")
    client.post("/collect", data={"country": "Testland", "source_ids": ["t-rss"]},
                follow_redirects=True)
    r = client.get("/export.json?country=Testland&theme=example")
    assert 'filename="rwt_corpus_Testland_example.json"' in r.headers["Content-Disposition"]
    payload = json.loads(_text(r))
    assert payload["filter"]["keywords"]            # theme keywords recorded
    assert payload["item_count"] == 1               # filtered to the energy item


# --------------------------------------------------------------------------
# A14..A15 — demo + sample view
# --------------------------------------------------------------------------
def test_a14_demo_loads_and_is_idempotent(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/demo", data={"country": "Testland"}, follow_redirects=True)
    body = _text(r)
    assert "Demo data loaded" in body
    assert "/sample/" in body                       # demo rows link to the local viewer
    n1 = _db_count(ctx, "Testland")
    assert n1 > 0
    # re-running demo replaces, never duplicates
    client.post("/demo", data={"country": "Testland"}, follow_redirects=True)
    assert _db_count(ctx, "Testland") == n1


def test_a15_sample_view(make_client):
    client, ctx = make_client(lang="en")
    client.post("/demo", data={"country": "Testland"}, follow_redirects=True)
    s = Store(ctx["db_path"])
    item_id = s.items(country="Testland")[0]["id"]
    s.close()
    r = client.get(f"/sample/{item_id}")
    assert r.status_code == 200
    assert "demo sample" in _text(r).lower()        # the offline-view banner
    r404 = client.get("/sample/does-not-exist")
    assert r404.status_code == 404


# --------------------------------------------------------------------------
# A16 — shutdown (thread is neutered in conftest so the test process survives)
# --------------------------------------------------------------------------
def test_a16_shutdown(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/shutdown")
    assert r.status_code == 200
    assert "stopped" in _text(r).lower()


# --------------------------------------------------------------------------
# A17 — i18n (Japanese UI + localized flash); English shows no Japanese
# --------------------------------------------------------------------------
def test_a17_japanese_ui_and_flash(make_client):
    client, ctx = make_client(lang="ja")
    body = _text(client.get("/"))
    assert "収集する" in body
    r = client.post("/collect",
                    data={"country": "Testland", "source_ids": ["t-rss"]},
                    follow_redirects=True)
    assert "収集完了" in _text(r)


def test_a17_english_ui_has_no_japanese(make_client):
    client, ctx = make_client(lang="en")
    body = _text(client.get("/"))
    assert "収集" not in body
    assert "Collect" in body
