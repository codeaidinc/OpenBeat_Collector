"""Collector — the core of the open side.

Responsibilities: ingest RSS/Atom, HTML (within allowed bounds) and manual
pastes -> extract main text -> detect language -> deduplicate -> attach
provenance. It respects robots.txt and terms of use; unfetchable sources fall
back to manual paste. Output = provenance-tagged RawItems (the raw corpus).
This is the boundary of the open-source scope.
"""
from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from urllib.parse import urlparse, urljoin

from .schema import Source, RawItem

USER_AGENT = "Mozilla/5.0 (compatible; OpenBeat_Collector/1.0; +https://github.com/codeaidinc/OpenBeat_Collector)"
DEFAULT_TIMEOUT = 10
ROBOTS_TIMEOUT = 6
POLITE_DELAY = 1.0  # delay between consecutive fetches to the same host (seconds)

# ---- Optional dependencies (a fallback keeps things working without them) ----
try:
    import httpx
    _HAVE_HTTPX = True
except Exception:
    _HAVE_HTTPX = False

try:
    import feedparser
    _HAVE_FEEDPARSER = True
except Exception:
    _HAVE_FEEDPARSER = False

try:
    import trafilatura
    _HAVE_TRAFILATURA = True
except Exception:
    _HAVE_TRAFILATURA = False


@dataclass
class CollectResult:
    items: List[RawItem] = field(default_factory=list)
    skipped_duplicates: int = 0
    errors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# HTTP fetch (uses httpx if available, otherwise urllib)
# --------------------------------------------------------------------------
def http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "*"}
    if _HAVE_HTTPX and not url.startswith("file://"):
        r = httpx.get(url, headers=headers, timeout=timeout,
                      follow_redirects=True)
        r.raise_for_status()
        return r.text
    import urllib.request
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, "replace")


def http_get_bytes(url: str, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if _HAVE_HTTPX and not url.startswith("file://"):
        r = httpx.get(url, headers=headers, timeout=timeout,
                      follow_redirects=True)
        r.raise_for_status()
        return r.content
    import urllib.request
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# --------------------------------------------------------------------------
# Respect robots.txt (with a timeout and a lenient policy)
#   Important: Python's stdlib RobotFileParser.read() (a) has no timeout and can
#   hang forever on an unresponsive server, and (b) treats a 403/401 on
#   robots.txt as "disallow everything". Many CDNs return 403 on robots.txt for
#   bot user agents, which would block even genuinely public RSS feeds. So we
#   fetch robots.txt ourselves with a timeout and fall back to "no restriction
#   (allowed)" when it cannot be retrieved. We only disallow on an explicit
#   Disallow rule.
# --------------------------------------------------------------------------
from urllib.robotparser import RobotFileParser  # noqa: E402

_robots_cache: dict = {}


def _get_robots(base: str, timeout: int):
    if base in _robots_cache:
        return _robots_cache[base]
    rp = None
    try:
        txt = http_get(base + "/robots.txt", timeout=timeout)  # own UA, with timeout
        rp = RobotFileParser()
        rp.parse(txt.splitlines())
    except Exception:
        rp = None  # unfetchable (404/403/timeout, etc.) -> treat as no restriction
    _robots_cache[base] = rp
    return rp


def robots_allows(url: str, timeout: int = ROBOTS_TIMEOUT) -> bool:
    """Whether robots.txt allows fetching this URL.

    On a fetch failure/error, allow (True). Returns False only when there is an
    explicit Disallow rule.
    """
    try:
        parts = urlparse(url)
        if parts.scheme not in ("http", "https"):
            return True  # file:// and the like are out of scope
        base = f"{parts.scheme}://{parts.netloc}"
        rp = _get_robots(base, timeout)
        if rp is None:
            return True
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:
            return True
    except Exception:
        return True


# --------------------------------------------------------------------------
# Language detection (lightweight, no dependencies)
# --------------------------------------------------------------------------
def detect_lang(text: str, fallback: str = "") -> str:
    if not text:
        return fallback
    sample = text[:1500]
    jp = sum(1 for c in sample if "぀" <= c <= "ヿ" or "一" <= c <= "鿿")
    if jp >= 8:
        return "ja"
    fr_markers = ("é", "è", "à", "ç", "ê", " le ", " la ", " des ", " est ", " une ")
    fr = sum(sample.lower().count(m) for m in fr_markers)
    en_markers = (" the ", " and ", " of ", " to ", " is ", " for ")
    en = sum(sample.lower().count(m) for m in en_markers)
    if fr > en and fr >= 3:
        return "fr"
    if en >= 2:
        return "en"
    return fallback


# --------------------------------------------------------------------------
# Main-text extraction (strips ads and navigation)
# --------------------------------------------------------------------------
def extract_main_text(html: str, url: str = "") -> str:
    if _HAVE_TRAFILATURA and html:
        try:
            txt = trafilatura.extract(
                html, url=url or None,
                include_comments=False, include_tables=False,
                favor_precision=True,
            )
            if txt:
                return txt.strip()
        except Exception:
            pass
    return _strip_html(html)


def _strip_html(html: str) -> str:
    """Simple fallback when trafilatura is absent (drop script/style + tags)."""
    import re
    if not html:
        return ""
    html = re.sub(r"(?is)<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    import html as _h
    text = _h.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text



def _rewrite_url(source, url: str) -> str:
    r"""Normalize an article URL using the source YAML's url_rewrite ('regex => replacement').

    Converts in-app/internal URLs into a real, openable web article URL to
    preserve source traceability.
    Example (NHK): r'https://news\.web\.nhk/newsweb/na/na-(k\d+) => https://www3.nhk.or.jp/news/html/\1.html'
    """
    import re as _re
    rw = (getattr(source, "url_rewrite", "") or "").strip()
    if not rw or "=>" not in rw or not url:
        return url
    pat, _, rep = rw.partition("=>")
    try:
        return _re.sub(pat.strip(), rep.strip(), url)
    except _re.error:
        return url

def _matches_keywords(keywords: Optional[List[str]], *texts: str) -> bool:
    """Simple case-insensitive text match for theme filtering.

    Note: this is NOT classification (closed side, section 4.4); it is a search
    used to narrow collection to a specific theme. If keywords is None/empty,
    always returns True (no filtering).
    """
    if not keywords:
        return True
    hay = " ".join(t for t in texts if t).lower()
    return any(k.strip().lower() in hay for k in keywords if k.strip())


# --------------------------------------------------------------------------
# Collection core
# --------------------------------------------------------------------------
def collect_source(source: Source,
                   is_duplicate: Optional[Callable[[str, str], bool]] = None,
                   max_items: int = 30,
                   fetch_full_text: bool = False,
                   keywords: Optional[List[str]] = None,
                   overwrite: Optional[bool] = None) -> CollectResult:
    """Collect a single source.

    is_duplicate(url, body_hash) -> bool : if True, the item is treated as
        existing and excluded (used to query storage).
    fetch_full_text : whether to fetch each RSS entry's full article page
        (default False = feed summary only; lightweight and polite).
    keywords : if given, only collect items whose title/summary contains one of
        them (theme filtering, not classification).
    overwrite : when True, items that already exist (same URL) are still emitted
        so the caller can refresh them in place (combine with
        Store.add_or_update_items(..., overwrite_by_url=True)). Defaults to the
        value of fetch_full_text, so turning "fetch full text" on also refreshes
        previously summary-only rows with the newly fetched full text, while
        URL-level deduplication is preserved downstream.
    """
    if overwrite is None:
        overwrite = fetch_full_text
    res = CollectResult()
    is_dup = is_duplicate or (lambda u, h: False)
    method = source.fetch_method

    if method == "manual":
        res.notes.append(f"[{source.id}] manual: manual-paste source. Use collect_manual().")
        return res

    if not source.url:
        res.errors.append(f"[{source.id}] URL is not set.")
        return res

    if not robots_allows(source.url):
        res.notes.append(f"[{source.id}] disallowed by robots.txt -> use the manual-paste fallback.")
        return res

    if method == "rss":
        _collect_rss(source, res, is_dup, max_items, fetch_full_text, keywords, overwrite)
    elif method in ("html", "api"):
        _collect_html(source, res, is_dup, keywords, overwrite)
    elif method == "dataset":
        _collect_dataset(source, res, is_dup, max_items, keywords, overwrite)
    else:
        res.errors.append(f"[{source.id}] unknown fetch_method: {method}")
    return res


def _collect_rss(source, res, is_dup, max_items, fetch_full_text, keywords=None, overwrite=False):
    try:
        raw = http_get_bytes(source.url)
    except Exception as e:
        res.errors.append(f"[{source.id}] feed fetch failed: {type(e).__name__}: {e}")
        return
    if not _HAVE_FEEDPARSER:
        res.errors.append(f"[{source.id}] feedparser not installed. Run: pip install feedparser")
        return
    feed = feedparser.parse(raw)
    entries = feed.entries[:max_items]
    if not entries:
        res.notes.append(f"[{source.id}] feed has no entries (check the URL/format).")
    last_host_fetch = 0.0
    for e in entries:
        link = _rewrite_url(source, getattr(e, "link", "") or "")
        title = getattr(e, "title", "") or ""
        summary = getattr(e, "summary", "") or ""
        published = getattr(e, "published", None) or getattr(e, "updated", None)
        summary_clean = _strip_html(summary)
        body = summary_clean

        if not _matches_keywords(keywords, title, summary_clean):
            continue  # excluded by theme filter

        if fetch_full_text and link and robots_allows(link):
            wait = POLITE_DELAY - (time.time() - last_host_fetch)
            if wait > 0:
                time.sleep(wait)
            try:
                html = http_get(link)
                full = extract_main_text(html, link)
                if full and len(full) > len(body):
                    body = full
            except Exception as ex:
                res.notes.append(f"[{source.id}] skipped full text {link}: {type(ex).__name__}")
            last_host_fetch = time.time()

        lang = detect_lang(body or title, source.lang)
        item = RawItem.make(source, link, title, body, lang=lang,
                            published_at=published, summary_excerpt=summary_clean)
        # In refresh mode, emit even existing items so the caller can overwrite
        # them in place (e.g. replace a summary-only row with the full text).
        if not overwrite and is_dup(item.url, item.hash):
            res.skipped_duplicates += 1
            continue
        res.items.append(item)


def _collect_html(source, res, is_dup, keywords=None, overwrite=False):
    """Extract one HTML page as a single item (no full crawl of list pages = lean)."""
    try:
        html = http_get(source.url)
    except Exception as e:
        res.errors.append(f"[{source.id}] page fetch failed: {type(e).__name__}: {e} -> manual-paste fallback recommended.")
        return
    body = extract_main_text(html, source.url)
    if not body:
        res.notes.append(f"[{source.id}] could not extract main text -> use manual paste.")
        return
    import re
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    title = _strip_html(m.group(1)) if m else source.name
    if not _matches_keywords(keywords, title, body):
        res.notes.append(f"[{source.id}] did not match the theme filter (HTML body).")
        return
    lang = detect_lang(body, source.lang)
    item = RawItem.make(source, _rewrite_url(source, source.url), title, body, lang=lang,
                        summary_excerpt=body[:280])
    if not overwrite and is_dup(item.url, item.hash):
        res.skipped_duplicates += 1
        return
    res.items.append(item)


# --------------------------------------------------------------------------
# Statistics dataset adapter (fetch_method: dataset) — continuous primary data
#   from official statistics / industry associations.
#   Converts a CSV/JSON "data release" into 1 row = 1 item and feeds it into the
#   raw corpus. On re-runs, deduplication (is_dup) means only new periods
#   (releases) are ingested = combined with scheduled runs it becomes a
#   "continuous primary-data pipeline".
#
#   dataset_spec ('key=value;...') main keys:
#     format   : csv | json            (default csv)
#     label    : indicator name (fixed string, e.g. "Corporate Goods Price Index (YoY)")
#     period   : column/key name for the period
#     value    : column/key name for the value
#     unit     : unit (fixed string, e.g. "%"); optional
#     delta    : column/key name for change vs. previous period (optional)
#     max      : number of latest rows to ingest (default 6)
#     records  : for JSON, dotted path to the array (optional; default = root is the array)
#     template : sentence template ({label}{period}{value}{unit}{delta}); optional
# --------------------------------------------------------------------------
def _parse_dataset_spec(spec: str) -> dict:
    out = {}
    for part in (spec or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _dataset_rows_csv(text: str):
    import csv, io
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader]


def _dataset_rows_json(text: str, records_path: str):
    import json as _json
    data = _json.loads(text)
    if records_path:
        for key in records_path.split("."):
            if isinstance(data, dict):
                data = data.get(key, [])
            else:
                data = []
                break
    if isinstance(data, dict):
        # dict of records → values
        data = list(data.values())
    return [r for r in (data or []) if isinstance(r, dict)]


def _render_dataset_title(spec: dict, row: dict) -> str:
    label = spec.get("label", "indicator")
    period = str(row.get(spec.get("period", ""), "")).strip()
    value = str(row.get(spec.get("value", ""), "")).strip()
    unit = spec.get("unit", "")
    delta_field = spec.get("delta", "")
    delta = str(row.get(delta_field, "")).strip() if delta_field else ""
    tmpl = spec.get("template", "")
    if tmpl:
        try:
            return tmpl.format(label=label, period=period, value=value,
                               unit=unit, delta=delta).strip()
        except Exception:
            pass
    title = f"{label}: {period} = {value}{unit}"
    if delta:
        title += f" (MoM {delta}{unit})"
    return title.strip()


def _collect_dataset(source, res, is_dup, max_items=6, keywords=None, overwrite=False):
    spec = _parse_dataset_spec(getattr(source, "dataset_spec", ""))
    if not spec:
        res.errors.append(f"[{source.id}] dataset_spec is not set (fetch_method=dataset).")
        return
    try:
        text = http_get(source.url)
    except Exception as e:
        res.errors.append(f"[{source.id}] data fetch failed: {type(e).__name__}: {e} -> manual fallback recommended.")
        return
    fmt = (spec.get("format") or "csv").lower()
    try:
        if fmt == "json":
            rows = _dataset_rows_json(text, spec.get("records", ""))
        else:
            rows = _dataset_rows_csv(text)
    except Exception as e:
        res.errors.append(f"[{source.id}] data parse failed (format={fmt}): {type(e).__name__}: {e}")
        return
    if not rows:
        res.notes.append(f"[{source.id}] 0 data rows (check the URL/format/records).")
        return
    try:
        limit = int(spec.get("max", max_items))
    except Exception:
        limit = max_items
    period_key = spec.get("period", "")
    value_key = spec.get("value", "")
    if not value_key:
        res.errors.append(f"[{source.id}] dataset_spec needs a 'value' column.")
        return
    # latest `limit` rows (assume the tail is newest), newest first
    recent = list(reversed(rows[-limit:])) if limit > 0 else list(reversed(rows))
    for row in recent:
        title = _render_dataset_title(spec, row)
        period = str(row.get(period_key, "")).strip() if period_key else ""
        body = (f"{title}. Source: statistical data from {source.name} "
                f"({source.country}). This is an automatic summary of public "
                f"statistics; the figures are faithful to the source data.")
        if not _matches_keywords(keywords, title, body, spec.get("label", "")):
            continue
        # unique source URL per period (for traceability + deduplication)
        item_url = source.url + (f"#{period}" if period else "")
        item_url = _rewrite_url(source, item_url)
        item = RawItem.make(source, item_url, title, body,
                            lang=source.lang, published_at=period or None,
                            summary_excerpt=title)
        if not overwrite and is_dup(item.url, item.hash):
            res.skipped_duplicates += 1
            continue
        res.items.append(item)


def collect_manual(source: Source, url: str, title: str, text: str) -> RawItem:
    """Manual-paste fallback. For unfetchable, paywalled or robots-disallowed
    sources, a person pastes the body text.

    Note: respecting the terms of use is the user's responsibility. The intended
    use is summary/quotation, not full-text reproduction.
    """
    lang = detect_lang(text, source.lang)
    return RawItem.make(source, url, title, text, lang=lang,
                        summary_excerpt=text[:280])


# --------------------------------------------------------------------------
# Feed auto-discovery — so non-technical users can just paste a site URL and let
# the tool figure out the RSS/Atom feed and the right fetch_method for them.
# --------------------------------------------------------------------------
COMMON_FEED_PATHS = ("/feed", "/feed/", "/rss", "/rss.xml", "/feed.xml",
                     "/atom.xml", "/index.xml", "/feeds/posts/default", "/en/rss.xml")


def _find_feed_links(html: str, base_url: str) -> List[str]:
    """Find declared RSS/Atom feeds in a page's <link rel="alternate"> tags."""
    import re
    out: List[str] = []
    for m in re.finditer(r"(?is)<link\b[^>]*>", html or ""):
        tag = m.group(0)
        tl = tag.lower()
        if "alternate" not in tl:
            continue
        if "application/rss+xml" in tl or "application/atom+xml" in tl:
            href = re.search(r"""(?is)href\s*=\s*["']([^"']+)["']""", tag)
            if href:
                out.append(urljoin(base_url, href.group(1).strip()))
    return out


def discover_feed(page_url: str, fetch=None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Given a normal website URL, work out how to collect from it.

    Returns {status, method, url, detail} where:
      status 'rss'    -> a real feed was found (method='rss', url=feed URL)
      status 'html'   -> no feed, but the page has readable text (method='html')
      status 'manual' -> nothing usable found (method='manual')
      status 'error'  -> the page could not be fetched (method='manual')
    `fetch` is injectable for testing (defaults to the real HTTP getter).
    """
    fetch = fetch or (lambda u: http_get(u, timeout=timeout))
    res = {"status": "error", "method": "manual", "url": page_url,
           "detail": "", "candidates": []}
    if not page_url:
        res["detail"] = "No URL given."
        return res
    if not (page_url.startswith("http://") or page_url.startswith("https://")
            or page_url.startswith("file://")):
        page_url = "https://" + page_url
        res["url"] = page_url
    # Try to open the page, but DON'T give up if it is blocked: a feed endpoint
    # may still be reachable even when the homepage refuses bots (403, etc.).
    html, page_err = None, ""
    try:
        html = fetch(page_url)
    except Exception as e:
        page_err = type(e).__name__

    # If the URL the user pasted is itself a feed, use it as-is.
    if html and _HAVE_FEEDPARSER:
        f0 = feedparser.parse(html)
        if getattr(f0, "entries", None):
            res.update(status="rss", method="rss", url=page_url,
                       detail=f"This address is already a feed ({len(f0.entries)} items).")
            return res

    # Candidate feeds: declared <link> feeds first, then common conventional paths.
    candidates = list(_find_feed_links(html or "", page_url))
    parts = urlparse(page_url)
    if parts.scheme in ("http", "https"):
        base = f"{parts.scheme}://{parts.netloc}"
        candidates += [base + p for p in COMMON_FEED_PATHS]
    seen, ordered = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    # Expose the candidate feed addresses so the UI can let the user test/pick
    # one when we cannot confirm a single feed automatically.
    res["candidates"] = [c for c in ordered if c != page_url][:6]

    if _HAVE_FEEDPARSER:
        for cand in ordered:
            try:
                ftext = fetch(cand)
            except Exception:
                continue
            feed = feedparser.parse(ftext)
            if getattr(feed, "entries", None):
                res.update(status="rss", method="rss", url=cand,
                           detail=f"Found a news feed ({len(feed.entries)} items).")
                return res

    if html:
        body = extract_main_text(html, page_url)
        if body and len(body) > 200:
            res.update(status="html", method="html", url=page_url,
                       detail="No feed found; the page text will be read directly (html).")
            return res
        res.update(status="manual", method="manual", url=page_url,
                   detail="No feed found on this page.")
        return res

    # The page itself could not be opened and no feed path worked. This is
    # usually bot protection (the site works in a browser but blocks tools).
    res.update(status="error", method="manual", url=page_url,
               detail=f"the site blocked the automatic check ({page_err or 'no response'})")
    return res


# --------------------------------------------------------------------------
# Feed health check (live) — helps fix URLs
# --------------------------------------------------------------------------
def verify_source(source: Source, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Connect to a single source live and diagnose whether it can be fetched
    and parsed.

    Returns: {id, name, status, detail, entries, action}
      status = ok | empty | robots_blocked | fetch_error | parse_error | manual
    Note: requires a network connection. Use it to find and fix sources whose
    bundled URLs are stale or have changed.
    """
    base = {"id": source.id, "name": source.name, "country": source.country,
            "fetch_method": source.fetch_method, "url": source.url,
            "entries": 0, "detail": "", "action": ""}

    if source.fetch_method == "manual":
        return {**base, "status": "manual", "detail": "Manual-paste source (no connection check)."}
    if not source.url:
        return {**base, "status": "fetch_error", "detail": "URL is not set.",
                "action": "Set 'url' in sources/*.yaml."}
    if not robots_allows(source.url, timeout=min(timeout, ROBOTS_TIMEOUT)):
        return {**base, "status": "robots_blocked",
                "detail": "robots.txt does not allow fetching.",
                "action": "Switch to manual paste (fetch_method: manual) or find another feed."}

    if source.fetch_method == "dataset":
        spec = _parse_dataset_spec(getattr(source, "dataset_spec", ""))
        if not spec:
            return {**base, "status": "parse_error", "detail": "dataset_spec is not set.",
                    "action": "Set 'dataset_spec' in sources/*.yaml."}
        try:
            text = http_get(source.url, timeout=timeout)
        except Exception as e:
            return {**base, "status": "fetch_error", "detail": f"{type(e).__name__}: {e}",
                    "action": "Check the data URL / switch to manual."}
        try:
            rows = (_dataset_rows_json(text, spec.get("records", ""))
                    if (spec.get("format") or "csv").lower() == "json"
                    else _dataset_rows_csv(text))
        except Exception as e:
            return {**base, "status": "parse_error", "detail": f"parse failed: {type(e).__name__}: {e}",
                    "action": "Check that format/records match the actual data shape."}
        if not rows:
            return {**base, "status": "empty", "detail": "0 data rows.",
                    "action": "Check the URL/format/records."}
        return {**base, "status": "ok", "entries": len(rows),
                "detail": f"OK ({len(rows)} rows). e.g. {_render_dataset_title(spec, rows[-1])[:60]}"}

    if source.fetch_method == "rss":
        try:
            raw = http_get_bytes(source.url, timeout=timeout)
        except Exception as e:
            return {**base, "status": "fetch_error",
                    "detail": f"{type(e).__name__}: {e}",
                    "action": "Open the site and update to the latest RSS URL / switch to html or manual."}
        if not _HAVE_FEEDPARSER:
            return {**base, "status": "parse_error",
                    "detail": "feedparser is not installed.",
                    "action": "pip install feedparser"}
        feed = feedparser.parse(raw)
        n = len(feed.entries)
        if getattr(feed, "bozo", 0) and n == 0:
            return {**base, "status": "parse_error",
                    "detail": f"feed parse error: {getattr(feed,'bozo_exception','')}",
                    "action": "Check that the URL returns RSS/Atom (not HTML)."}
        if n == 0:
            return {**base, "status": "empty", "detail": "0 entries.",
                    "action": "Check that the feed URL is correct and still updating."}
        return {**base, "status": "ok", "entries": n,
                "detail": f"OK ({n} entries). First: {feed.entries[0].get('title','')[:60]}"}

    try:
        html = http_get(source.url, timeout=timeout)
    except Exception as e:
        return {**base, "status": "fetch_error",
                "detail": f"{type(e).__name__}: {e}",
                "action": "Check the URL / switch to manual."}
    body = extract_main_text(html, source.url)
    if not body:
        return {**base, "status": "empty", "detail": "Could not extract main text.",
                "action": "Point at another page or switch to manual paste."}
    return {**base, "status": "ok", "entries": 1,
            "detail": f"OK (extracted {len(body)} characters of body text)."}


def verify_sources(sources: List[Source]) -> List[dict]:
    return [verify_source(s) for s in sources]
