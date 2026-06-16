"""Data model (the two entities the open side handles: Source / RawItem).

Of design-doc section 6, the collection (open) scope only owns Source and
RawItem. Everything from NormalizedItem onward is produced by the closed layer
from the raw corpus JSON.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def content_hash(*parts: str) -> str:
    """Body/URL hash (for deduplication)."""
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").strip().encode("utf-8", "ignore"))
        h.update(b"\x1f")
    return h.hexdigest()


@dataclass
class Source:
    id: str
    country: str
    source_type: str            # government | ministry | media | sme_media | support_org | statistics
    name: str
    url: str                    # fetch target (feed/page)
    lang: str
    fetch_method: str           # rss | html | api | manual
    site: str = ""              # human-facing top URL
    license_note: str = ""
    trust: str = "medium"       # high | medium | low
    update_freq: str = ""
    url_rewrite: str = ""        # optional: 'regex => replacement' to normalize article URLs (e.g. NHK app URL -> web URL)
    dataset_spec: str = ""       # optional: transform spec for fetch_method=dataset ('key=value;...')

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RawItem:
    """A provenance-tagged raw item. This is the open side's final output."""
    id: str                     # = hash(URL + title)
    source_id: str
    url: str                    # article source URL
    title: str
    body_raw: str               # body (extracted, ads/nav removed). For manual, the pasted text.
    lang: str
    hash: str                   # body hash (deduplication)
    fetched_at: str             # fetch time (ISO 8601 UTC)
    published_at: Optional[str] = None
    summary_excerpt: str = ""   # feed-provided summary (if any)
    # ---- provenance ----
    source_name: str = ""
    source_type: str = ""
    country: str = ""
    license_note: str = ""
    fetch_method: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def make(source: "Source", url: str, title: str, body_raw: str,
             lang: str = "", published_at: Optional[str] = None,
             summary_excerpt: str = "") -> "RawItem":
        lang = lang or source.lang
        body = (body_raw or "").strip()
        h = content_hash(url, body[:2000])
        item_id = content_hash(source.id, url, title)[:16]
        return RawItem(
            id=item_id,
            source_id=source.id,
            url=url,
            title=(title or "").strip(),
            body_raw=body,
            lang=lang,
            hash=h,
            fetched_at=utcnow_iso(),
            published_at=published_at,
            summary_excerpt=(summary_excerpt or "").strip(),
            source_name=source.name,
            source_type=source.source_type,
            country=source.country,
            license_note=source.license_note,
            fetch_method=source.fetch_method,
        )
