"""Pytest fixtures for the RWT open-side E2E / scenario tests.

Everything here is offline and deterministic (the same policy as selftest.py):
 * Sources point at bundled file:// fixtures (sample_feed.xml / sample_stats.csv),
   which urllib can read without a network connection.
 * Any real HTTP (full-text fetch, feed auto-detect, robots.txt, verify of an
   http(s) source) is routed through a fake `http_get` / `http_get_bytes` that
   returns canned responses, so nothing ever touches the network.
 * Each test gets its own temporary DB, user-sources overlay and source registry
   (OPENBEAT_DB_PATH / OPENBEAT_USER_SOURCES_DIR / OPENBEAT_SOURCES_DIR), so tests do not leak
   state into one another.
 * The UI language (OPENBEAT_LANG) is switched per request; app strings() reads it
   live, so no reload is needed to flip en/ja.

`app.py` reads several paths at import time (DB_PATH, SOURCES_DIR, USER_SOURCES_DIR,
SUPPORT_URL_TEMPLATE), so the `client` factory sets the environment first and then
imports / reloads the app module.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

SAMPLE_FEED = os.path.join(TESTS_DIR, "sample_feed.xml")
SAMPLE_STATS = os.path.join(TESTS_DIR, "sample_stats.csv")
THEMES_DIR = os.path.join(REPO_ROOT, "themes")


def _file_uri(path: str) -> str:
    return Path(path).as_uri()


# --------------------------------------------------------------------------
# A small, deterministic source registry written to a temp dir per test.
# (Three sources, all in the 'Testland' country, all offline via file://.)
# --------------------------------------------------------------------------
def write_fixture_registry(sources_dir: str) -> None:
    os.makedirs(sources_dir, exist_ok=True)
    feed_uri = _file_uri(SAMPLE_FEED)
    stats_uri = _file_uri(SAMPLE_STATS)
    text = f"""country: Testland
language_default: en
sources:
  - id: t-rss
    name: Test RSS Feed
    source_type: government
    url: "{feed_uri}"
    site: https://example.test/
    lang: en
    fetch_method: rss
    license_note: "Headline + summary + link only."
    trust: high
  - id: t-stats
    name: Test Statistics
    source_type: statistics
    url: "{stats_uri}"
    lang: en
    fetch_method: dataset
    license_note: "Public statistics (sample)."
    trust: high
    dataset_spec: "format=csv;label=Test Price Index;period=month;value=index_yoy;unit=%;delta=mom;max=6"
  - id: t-manual
    name: Test Manual Source
    source_type: media
    url: ""
    lang: en
    fetch_method: manual
    license_note: "Manual paste only."
    trust: medium
"""
    with open(os.path.join(sources_dir, "testland.yaml"), "w", encoding="utf-8") as f:
        f.write(text)


# --------------------------------------------------------------------------
# Fake HTTP layer (no network). file:// is delegated to the real getter.
# --------------------------------------------------------------------------
ARTICLE_HTML = (
    "<html><head><title>Full Article Title</title></head><body><article>"
    + ("This is the full article body text with plenty of words. " * 60)
    + "</article></body></html>"
)
SHORT_HTML = "<html><head><title>Tiny</title></head><body><p>hi</p></body></html>"


def _read_feed_xml() -> str:
    with open(SAMPLE_FEED, encoding="utf-8") as f:
        return f.read()


class FakeNet:
    """Configurable fake for collector.http_get / http_get_bytes.

    Routes:
      *file://*          -> delegate to the original getter (real fixture read)
      *robots.txt        -> "allow all" (so robots never blocks, unless overridden)
      a page in `pages`  -> the mapped HTML / feed text
      anything else       -> ARTICLE_HTML (so RSS full-text fetch returns a long body)
    """

    def __init__(self, orig_get, orig_get_bytes):
        self._orig_get = orig_get
        self._orig_get_bytes = orig_get_bytes
        self.pages: dict[str, str] = {}
        self.robots_disallow_all = False
        self.raise_for: set[str] = set()
        self.raise_substr: list[str] = []     # raise if any of these appears in the URL
        self.calls: list[str] = []

    def _blocked(self, url):
        return url in self.raise_for or any(s in url for s in self.raise_substr)

    def get(self, url, timeout=None):
        self.calls.append(url)
        if url.startswith("file://"):
            return self._orig_get(url)
        if url.endswith("/robots.txt"):
            # robots.txt itself stays reachable so the blocklist below only models
            # the *page* being bot-blocked, not the robots policy.
            return "User-agent: *\nDisallow: /\n" if self.robots_disallow_all else "User-agent: *\nDisallow:\n"
        if self._blocked(url):
            raise OSError(f"blocked: {url}")
        if url in self.pages:
            return self.pages[url]
        return ARTICLE_HTML

    def get_bytes(self, url, timeout=None):
        if url.startswith("file://"):
            return self._orig_get_bytes(url)
        if self._blocked(url):
            raise OSError(f"blocked: {url}")
        if url in self.pages:
            return self.pages[url].encode("utf-8")
        return ARTICLE_HTML.encode("utf-8")


@pytest.fixture
def fixtures():
    """Expose fixture paths / helpers to tests."""
    return {
        "feed": SAMPLE_FEED,
        "stats": SAMPLE_STATS,
        "feed_uri": _file_uri(SAMPLE_FEED),
        "stats_uri": _file_uri(SAMPLE_STATS),
        "feed_xml": _read_feed_xml(),
        "article_html": ARTICLE_HTML,
        "short_html": SHORT_HTML,
    }


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    """Factory: build an isolated Flask test client.

    Usage:  client, ctx = make_client(lang="en")
    `ctx` carries handles the test may need: the (re)loaded app module, the fake
    net, and key paths.
    """
    created = {}

    def _factory(lang="en", support_url=None, write_registry=True):
        sources_dir = tmp_path / "sources"
        user_dir = tmp_path / "data" / "user_sources"
        db_path = tmp_path / "data" / "rwt.sqlite"
        os.makedirs(user_dir, exist_ok=True)
        if write_registry:
            write_fixture_registry(str(sources_dir))

        monkeypatch.setenv("OPENBEAT_LANG", lang)
        monkeypatch.setenv("OPENBEAT_SOURCES_DIR", str(sources_dir))
        monkeypatch.setenv("OPENBEAT_THEMES_DIR", THEMES_DIR)
        monkeypatch.setenv("OPENBEAT_USER_SOURCES_DIR", str(user_dir))
        monkeypatch.setenv("OPENBEAT_DB_PATH", str(db_path))
        monkeypatch.setenv("OPENBEAT_NO_BROWSER", "1")
        if support_url is not None:
            monkeypatch.setenv("OPENBEAT_SUPPORT_URL", support_url)
        else:
            monkeypatch.delenv("OPENBEAT_SUPPORT_URL", raising=False)

        # Import / reload the app with the env in place.
        import openbeat_collector.collector as collector
        if "app" in sys.modules:
            app_mod = importlib.reload(sys.modules["app"])
        else:
            app_mod = importlib.import_module("app")

        # Route all real HTTP through the offline fake (file:// still works).
        fake = FakeNet(collector.http_get, collector.http_get_bytes)
        monkeypatch.setattr(collector, "http_get", fake.get)
        monkeypatch.setattr(collector, "http_get_bytes", fake.get_bytes)
        collector._robots_cache.clear()  # avoid robots leaking between tests

        # /shutdown spawns a thread that calls os._exit(0); neuter it so the test
        # process survives while still exercising the route.
        monkeypatch.setattr(app_mod.threading, "Thread", _NoopThread)

        app_mod.app.config["TESTING"] = True
        client = app_mod.app.test_client()
        ctx = {
            "app": app_mod, "collector": collector, "fake": fake,
            "sources_dir": str(sources_dir), "user_dir": str(user_dir),
            "user_file": os.path.join(str(user_dir), "sources.yaml"),
            "db_path": str(db_path), "tmp": tmp_path,
        }
        created["ctx"] = ctx
        return client, ctx

    return _factory


class _NoopThread:
    """Stand-in for threading.Thread used only by /shutdown in tests."""

    def __init__(self, *a, **k):
        pass

    def start(self):
        pass


def set_lang(ctx, lang):
    """Flip the UI language at runtime (strings() reads OPENBEAT_LANG live)."""
    os.environ["OPENBEAT_LANG"] = lang
