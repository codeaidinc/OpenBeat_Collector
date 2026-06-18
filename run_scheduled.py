#!/usr/bin/env python3
"""Scheduled run (periodic job) — collect all sources and write the raw corpus JSON.

Intended to run periodically from cron / Windows Task Scheduler.
Logs are appended to data/collect.log. Output JSON is saved to exports/ with a
timestamp.

Usage:
  python run_scheduled.py                        # all sources, all countries
  python run_scheduled.py --country Japan
  python run_scheduled.py --theme example         # crawl narrowed to a theme

Schedule examples:
  Linux/macOS (daily at 6am):
    0 6 * * *  cd /path/to/repo && /usr/bin/python3 run_scheduled.py >> data/cron.out 2>&1
  Windows Task Scheduler:
    Program: python   Arguments: run_scheduled.py   Start in: the repository folder
"""
from __future__ import annotations

import argparse
import os
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from openbeat_collector.registry import load_registry, by_country
from openbeat_collector.collector import collect_source
from openbeat_collector.storage import Store
from openbeat_collector.export import export_corpus_json
from openbeat_collector.themes import theme_keywords

SOURCES_DIR = os.path.join(HERE, "sources")
THEMES_DIR = os.path.join(HERE, "themes")
DB_PATH = os.path.join(HERE, "data", "rwt.sqlite")
LOG_PATH = os.path.join(HERE, "data", "collect.log")
EXPORT_DIR = os.path.join(HERE, "exports")


def log(msg: str):
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    ap = argparse.ArgumentParser(description="RWT scheduled crawl job")
    ap.add_argument("--country")
    ap.add_argument("--theme")
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--no-export", action="store_true", help="skip writing JSON")
    args = ap.parse_args()

    reg = load_registry(SOURCES_DIR)
    targets = by_country(reg, args.country) if args.country else reg
    keywords = theme_keywords(THEMES_DIR, args.theme) if args.theme else None

    store = Store(DB_PATH)
    store.sync_registry(reg)

    log(f"crawl start: {len(targets)} sources"
        + (f" / country={args.country}" if args.country else "")
        + (f" / theme={args.theme}({len(keywords or [])}kw)" if args.theme else ""))

    new_total, upd_total, dup_total, err_total = 0, 0, 0, 0
    for s in targets:
        try:
            res = collect_source(s, is_duplicate=store.is_duplicate,
                                 max_items=args.max, fetch_full_text=args.full,
                                 keywords=keywords)
            c = store.add_or_update_items(res.items, overwrite_by_url=args.full)
            new, upd = c["added"], c["updated"]
            dup = c["skipped"] if args.full else res.skipped_duplicates
            new_total += new
            upd_total += upd
            dup_total += dup
            err_total += len(res.errors)
            if res.errors:
                log(f"  ERR {s.id}: {res.errors[0]}")
            else:
                upd_str = f" / upd {upd}" if args.full else ""
                log(f"  OK  {s.id}: new {new}{upd_str} / dup {dup}")
        except Exception as e:
            err_total += 1
            log(f"  EXC {s.id}: {type(e).__name__}: {e}")

    upd_done = f" / refreshed {upd_total}" if args.full else ""
    log(f"crawl done: new {new_total}{upd_done} / dup {dup_total} / errors {err_total} / total {store.count()}")

    if not args.no_export:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        cc = (args.country or "all").replace(" ", "")
        out = os.path.join(EXPORT_DIR, f"corpus_{cc}_{stamp}.json")
        export_corpus_json(store, out, country=args.country)
        log(f"wrote raw corpus JSON: {out}")

    store.close()


if __name__ == "__main__":
    main()
