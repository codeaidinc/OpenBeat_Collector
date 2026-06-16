"""Screen B — the no-code source manager (GET /sources and its events / APIs).

Covers scenarios B1..B15 from tests/SCENARIOS.md. Offline / deterministic.
"""
from __future__ import annotations

import os


def _text(resp):
    return resp.get_data(as_text=True)


def _reg(ctx):
    return ctx["app"].get_registry()


def _ids(ctx):
    return {s.id for s in _reg(ctx)}


VALID_NEW = {
    "id": "new-src", "name": "My New Source", "country": "Testland",
    "source_type": "media", "fetch_method": "rss",
    "url": "https://example.test/feed.xml", "lang": "en", "trust": "medium",
    "license_note": "Headline + link only.", "orig_id": "",
}


# --------------------------------------------------------------------------
# B1..B2 — rendering
# --------------------------------------------------------------------------
def test_b1_sources_list(make_client):
    client, ctx = make_client(lang="en")
    body = _text(client.get("/sources"))
    assert "Manage sources" in body
    assert "3 sources" in body                      # the fixture registry
    assert "Easy add" in body                       # auto-detect box
    assert "bundled default sources" in body        # using_bundled pill
    assert "t-rss" in body


def test_b2_edit_prefill(make_client):
    client, ctx = make_client(lang="en")
    body = _text(client.get("/sources?edit=t-rss"))
    assert "Edit source" in body
    assert 'value="t-rss"' in body
    assert 'value="Test RSS Feed"' in body


# --------------------------------------------------------------------------
# B3..B7 — save (add / edit / rename / dup / validation)
# --------------------------------------------------------------------------
def test_b3_add_source_creates_overlay(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/sources/save", data=VALID_NEW, follow_redirects=True)
    body = _text(r)
    # NB: the flash text is HTML-escaped by Jinja ("'" -> "&#39;"), so match the
    # id and the verb separately rather than the raw "Saved source 'new-src'".
    assert "Saved source" in body and "new-src" in body
    assert os.path.exists(ctx["user_file"])         # writable overlay created
    assert "new-src" in _ids(ctx)
    assert len(_reg(ctx)) == 4
    assert "your own edited source list" in body     # using_user pill flipped


def test_b3_add_preserves_per_source_country(make_client):
    client, ctx = make_client(lang="en")
    data = dict(VALID_NEW, id="uk-x", country="UK")
    client.post("/sources/save", data=data, follow_redirects=True)
    got = {s.id: s.country for s in _reg(ctx)}
    assert got["uk-x"] == "UK"                       # not coerced to Testland


def test_b4_edit_overwrites(make_client):
    client, ctx = make_client(lang="en")
    data = {"id": "t-rss", "orig_id": "t-rss", "name": "Test RSS Feed",
            "country": "Testland", "source_type": "government",
            "fetch_method": "rss", "url": "https://changed.test/feed.xml",
            "lang": "en", "trust": "low", "license_note": "x"}
    client.post("/sources/save", data=data, follow_redirects=True)
    src = next(s for s in _reg(ctx) if s.id == "t-rss")
    assert src.url == "https://changed.test/feed.xml"
    assert src.trust == "low"
    assert len(_reg(ctx)) == 3                       # still 3, edited in place


def test_b5_rename_id(make_client):
    client, ctx = make_client(lang="en")
    data = dict(VALID_NEW, id="t-rss-2", orig_id="t-rss",
                source_type="government", url="https://example.test/feed.xml")
    client.post("/sources/save", data=data, follow_redirects=True)
    ids = _ids(ctx)
    assert "t-rss-2" in ids and "t-rss" not in ids
    assert len(_reg(ctx)) == 3


def test_b6_duplicate_id_rejected(make_client):
    client, ctx = make_client(lang="en")
    # try to ADD a new source whose id clashes with the existing t-rss
    data = dict(VALID_NEW, id="t-rss", name="Dup Attempt")
    r = client.post("/sources/save", data=data, follow_redirects=True)
    body = _text(r)
    assert "duplicate id" in body                    # rejected with the dup message
    # the original t-rss must be untouched (not overwritten by "Dup Attempt")
    src = next(s for s in _reg(ctx) if s.id == "t-rss")
    assert src.name == "Test RSS Feed"


def test_b7_missing_required_rejected(make_client):
    client, ctx = make_client(lang="en")
    data = dict(VALID_NEW, id="bad-1", name="")      # no name
    r = client.post("/sources/save", data=data, follow_redirects=True)
    assert "Could not save" in _text(r)
    assert "bad-1" not in _ids(ctx)


def test_b7_missing_url_rejected_for_non_manual(make_client):
    client, ctx = make_client(lang="en")
    data = dict(VALID_NEW, id="bad-2", url="", fetch_method="rss")
    r = client.post("/sources/save", data=data, follow_redirects=True)
    assert "Could not save" in _text(r)
    assert "bad-2" not in _ids(ctx)


def test_b7_missing_license_is_warning_only(make_client):
    client, ctx = make_client(lang="en")
    data = dict(VALID_NEW, id="ok-3", license_note="")   # only a soft warning
    r = client.post("/sources/save", data=data, follow_redirects=True)
    body = _text(r)
    assert "Saved source" in body and "ok-3" in body
    assert "ok-3" in _ids(ctx)


# --------------------------------------------------------------------------
# B8..B9 — delete + reset
# --------------------------------------------------------------------------
def test_b8_delete(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/sources/delete", data={"id": "t-stats"}, follow_redirects=True)
    body = _text(r)
    assert "Deleted source" in body and "t-stats" in body
    assert "t-stats" not in _ids(ctx)


def test_b9_reset_restores_defaults(make_client):
    client, ctx = make_client(lang="en")
    client.post("/sources/save", data=VALID_NEW, follow_redirects=True)
    assert os.path.exists(ctx["user_file"])
    r = client.post("/sources/reset", data={}, follow_redirects=True)
    assert "Restored the bundled default sources" in _text(r)
    assert not os.path.exists(ctx["user_file"])
    assert _ids(ctx) == {"t-rss", "t-stats", "t-manual"}     # back to the 3 defaults


# --------------------------------------------------------------------------
# B10..B11 — verify (live connection test, must never 500 offline)
# --------------------------------------------------------------------------
def test_b10_verify_rss_ok(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/sources/verify", data={"id": "t-rss"}, follow_redirects=True)
    body = _text(r)
    assert r.status_code == 200                       # i.e. the 302 redirect resolved
    assert "[ok]" in body


def test_b10_verify_manual(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/sources/verify", data={"id": "t-manual"}, follow_redirects=True)
    assert "[manual]" in _text(r)


def test_b10_verify_does_not_crash_on_blocked(make_client):
    client, ctx = make_client(lang="en")
    # point a source at an http(s) URL that the fake net blocks -> must still 302
    data = dict(VALID_NEW, id="blk", url="https://blocked.test/x")
    client.post("/sources/save", data=data, follow_redirects=True)
    ctx["fake"].raise_substr = ["blocked.test"]
    r = client.post("/sources/verify", data={"id": "blk"}, follow_redirects=False)
    assert r.status_code == 302                       # graceful, no 500


def test_b11_verify_unknown_id(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/sources/verify", data={"id": "nope"}, follow_redirects=True)
    assert "not found" in _text(r).lower()


# --------------------------------------------------------------------------
# B12..B14 — auto-detect feed (discover)
# --------------------------------------------------------------------------
def test_b12_discover_rss(make_client, fixtures):
    client, ctx = make_client(lang="en")
    page = "https://news.test/"
    ctx["fake"].pages[page] = (
        '<html><head><link rel="alternate" type="application/rss+xml" '
        'href="/feed.xml"></head><body>news</body></html>')
    ctx["fake"].pages["https://news.test/feed.xml"] = fixtures["feed_xml"]
    r = client.post("/sources/discover", data={"page_url": page}, follow_redirects=True)
    body = _text(r)
    assert "Found it" in body                          # rss success flash
    assert "https://news.test/feed.xml" in body        # feed URL pre-filled into the form


def test_b13_discover_blocked_offers_request(make_client):
    client, ctx = make_client(lang="en",
                              support_url="https://form.test/?site={site}")
    ctx["fake"].raise_substr = ["blocked.test"]
    r = client.post("/sources/discover",
                    data={"page_url": "https://blocked.test/news"},
                    follow_redirects=True)
    body = _text(r)
    assert "Open the request page" in body             # support-request UI shown
    assert "source support request" in body            # copyable request text
    assert "form.test" in body                          # support_url resolved
    assert "blocked.test" in body                       # {site} substituted (encoded)


def test_b14_discover_requires_url(make_client):
    client, ctx = make_client(lang="en")
    r = client.post("/sources/discover", data={"page_url": ""}, follow_redirects=True)
    assert "paste a website address" in _text(r)


# --------------------------------------------------------------------------
# B15 — i18n
# --------------------------------------------------------------------------
def test_b15_japanese_sources_and_request(make_client):
    client, ctx = make_client(lang="ja")
    assert "情報源を管理" in _text(client.get("/sources"))
    ctx["fake"].raise_substr = ["blocked.test"]
    r = client.post("/sources/discover",
                    data={"page_url": "https://blocked.test/news"},
                    follow_redirects=True)
    body = _text(r)
    assert "自動検出できませんでした" in body
    assert "情報源の対応依頼" in body                  # localized request text
