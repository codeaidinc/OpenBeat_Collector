"""Storage (SQLite) — local persistence of the provenance-tagged raw corpus.

The open side's responsibility ends at "local storage of collected data"
(design doc section 4.8 note). Distribution and archiving of deliverables
belong to the closed layer.
"""
from __future__ import annotations

import sqlite3
import os
from typing import List, Optional

from .schema import Source, RawItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS source (
    id          TEXT PRIMARY KEY,
    country     TEXT,
    source_type TEXT,
    name        TEXT,
    url         TEXT,
    site        TEXT,
    lang        TEXT,
    fetch_method TEXT,
    license_note TEXT,
    trust       TEXT,
    update_freq TEXT
);
CREATE TABLE IF NOT EXISTS raw_item (
    id          TEXT PRIMARY KEY,
    source_id   TEXT,
    url         TEXT,
    title       TEXT,
    body_raw    TEXT,
    lang        TEXT,
    hash        TEXT,
    fetched_at  TEXT,
    published_at TEXT,
    summary_excerpt TEXT,
    source_name TEXT,
    source_type TEXT,
    country     TEXT,
    license_note TEXT,
    fetch_method TEXT
);
CREATE INDEX IF NOT EXISTS idx_item_hash ON raw_item(hash);
CREATE INDEX IF NOT EXISTS idx_item_url ON raw_item(url);
CREATE INDEX IF NOT EXISTS idx_item_country ON raw_item(country);
CREATE INDEX IF NOT EXISTS idx_item_source ON raw_item(source_id);
"""


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        d = os.path.dirname(os.path.abspath(db_path))
        if d:
            os.makedirs(d, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ---- Source ----
    def upsert_source(self, s: Source):
        self.conn.execute(
            """INSERT INTO source (id,country,source_type,name,url,site,lang,
                 fetch_method,license_note,trust,update_freq)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 country=excluded.country, source_type=excluded.source_type,
                 name=excluded.name, url=excluded.url, site=excluded.site,
                 lang=excluded.lang, fetch_method=excluded.fetch_method,
                 license_note=excluded.license_note, trust=excluded.trust,
                 update_freq=excluded.update_freq""",
            (s.id, s.country, s.source_type, s.name, s.url, s.site, s.lang,
             s.fetch_method, s.license_note, s.trust, s.update_freq),
        )
        self.conn.commit()

    def sync_registry(self, sources: List[Source]):
        for s in sources:
            self.upsert_source(s)

    # ---- duplicate check ----
    def is_duplicate(self, url: str, body_hash: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM raw_item WHERE hash=? OR (url=? AND url<>'') LIMIT 1",
            (body_hash, url),
        )
        return cur.fetchone() is not None

    # ---- RawItem ----
    def add_item(self, it: RawItem) -> bool:
        if self.is_duplicate(it.url, it.hash):
            return False
        d = it.to_dict()
        self.conn.execute(
            """INSERT OR IGNORE INTO raw_item
               (id,source_id,url,title,body_raw,lang,hash,fetched_at,published_at,
                summary_excerpt,source_name,source_type,country,license_note,fetch_method)
               VALUES (:id,:source_id,:url,:title,:body_raw,:lang,:hash,:fetched_at,
                :published_at,:summary_excerpt,:source_name,:source_type,:country,
                :license_note,:fetch_method)""",
            d,
        )
        self.conn.commit()
        return True

    def add_items(self, items: List[RawItem]) -> int:
        n = 0
        for it in items:
            if self.add_item(it):
                n += 1
        return n

    # ---- insert / refresh-in-place (used when re-fetching full article text) ----
    def upsert_item(self, it: RawItem, overwrite_by_url: bool = False) -> str:
        """Insert, refresh-in-place, or skip a single item.

        Returns one of: 'added' | 'updated' | 'skipped'.

        Normal mode (overwrite_by_url=False) behaves like add_item: a hash- or
        URL-level duplicate is skipped.

        Refresh mode (overwrite_by_url=True, used when "fetch full text" is on)
        keeps URL-level deduplication but lets fresh full text overwrite an
        existing summary-only row for the same article:
          - identical content already stored (same body hash)  -> 'skipped'
          - same article already stored (same id or URL)        -> overwrite -> 'updated'
          - otherwise                                           -> insert    -> 'added'
        """
        # Identical content already stored anywhere -> nothing to do.
        if self.conn.execute(
            "SELECT 1 FROM raw_item WHERE hash=? LIMIT 1", (it.hash,)
        ).fetchone() is not None:
            return "skipped"

        if overwrite_by_url:
            exists = self.conn.execute(
                "SELECT 1 FROM raw_item WHERE id=? OR (url=? AND url<>'') LIMIT 1",
                (it.id, it.url),
            ).fetchone() is not None
            if exists:
                # Replace the stale (e.g. summary-only) row(s) for this article
                # with the freshly fetched full text. URL-level dedup is preserved
                # because we keep exactly one row per id/URL.
                self.conn.execute(
                    "DELETE FROM raw_item WHERE id=? OR (url=? AND url<>'')",
                    (it.id, it.url),
                )
                self.conn.execute(
                    """INSERT INTO raw_item
                       (id,source_id,url,title,body_raw,lang,hash,fetched_at,published_at,
                        summary_excerpt,source_name,source_type,country,license_note,fetch_method)
                       VALUES (:id,:source_id,:url,:title,:body_raw,:lang,:hash,:fetched_at,
                        :published_at,:summary_excerpt,:source_name,:source_type,:country,
                        :license_note,:fetch_method)""",
                    it.to_dict(),
                )
                self.conn.commit()
                return "updated"

        # Fall back to normal insert with hash/URL deduplication.
        return "added" if self.add_item(it) else "skipped"

    def add_or_update_items(self, items: List[RawItem],
                            overwrite_by_url: bool = False) -> dict:
        """Bulk upsert. Returns counts {'added', 'updated', 'skipped'}."""
        counts = {"added": 0, "updated": 0, "skipped": 0}
        for it in items:
            counts[self.upsert_item(it, overwrite_by_url)] += 1
        return counts

    def delete_by_source(self, source_id: str) -> int:
        """Erase all collected raw_item rows belonging to one source (cascade on
        source deletion). Implements GDPR Art.17 / APPI-style erasure for a
        single source's data."""
        cur = self.conn.execute("DELETE FROM raw_item WHERE source_id=?", (source_id,))
        self.conn.commit()
        return cur.rowcount

    def delete_all_items(self) -> int:
        """Erase ALL collected raw_item rows (full local data wipe). Source
        definitions in the registry are left intact; only the collected corpus
        is removed. Implements GDPR Art.17 / APPI-style erasure of all stored
        personal data that may appear in collected body text."""
        cur = self.conn.execute("DELETE FROM raw_item")
        self.conn.commit()
        return cur.rowcount

    def items(self, country: Optional[str] = None, source_id: Optional[str] = None,
              limit: int = 200) -> List[dict]:
        q = "SELECT * FROM raw_item"
        cond, args = [], []
        if country:
            cond.append("country=?"); args.append(country)
        if source_id:
            cond.append("source_id=?"); args.append(source_id)
        if cond:
            q += " WHERE " + " AND ".join(cond)
        q += " ORDER BY fetched_at DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.conn.execute(q, args).fetchall()]

    def count(self, country: Optional[str] = None) -> int:
        if country:
            r = self.conn.execute("SELECT COUNT(*) c FROM raw_item WHERE country=?", (country,))
        else:
            r = self.conn.execute("SELECT COUNT(*) c FROM raw_item")
        return r.fetchone()["c"]
