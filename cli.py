#!/usr/bin/env python3
"""RWT CLI — for power users / automation (non-developers use the app.py web UI).

Examples:
  python cli.py sources                        # list sources
  python cli.py validate                       # statically validate the registry (offline)
  python cli.py verify --country Japan          # connect to each feed and diagnose (helps fix URLs)
  python cli.py collect --country Japan         # collect all sources for Japan
  python cli.py collect --theme example          # collect narrowed to a theme (themes/*.yaml)
  python cli.py list --country France --limit 20
  python cli.py export corpus.json --country Japan
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from openbeat_collector.registry import (load_registry, by_country, by_id, countries,
                          validate_registry)
from openbeat_collector.collector import collect_source, verify_source
from openbeat_collector.storage import Store
from openbeat_collector.export import export_corpus_json
from openbeat_collector.themes import theme_keywords, load_themes
from openbeat_collector.packcli import add_pack_parser, cmd_pack, build_pack_store

SOURCES_DIR = os.path.join(HERE, "sources")
THEMES_DIR = os.path.join(HERE, "themes")
DB_PATH = os.path.join(HERE, "data", "rwt.sqlite")


def _registry():
    """Bundled sources plus any active beat packs (matches the web app)."""
    base = load_registry(SOURCES_DIR)
    try:
        active = load_registry(build_pack_store(HERE).active_sources_dir)
    except Exception:
        active = []
    seen = {s.id for s in base}
    return base + [s for s in active if s.id not in seen]


def _theme_dirs():
    """Bundled themes plus any active beat-pack themes (matches the web app).

    Activating a pack writes its theme to data/active_themes/<id>.yaml, so a
    pack theme (e.g. a pack's own theme) is resolvable by `collect --theme`.
    """
    dirs = [THEMES_DIR]
    try:
        d = build_pack_store(HERE).active_themes_dir
        if d and d not in dirs:
            dirs.append(d)
    except Exception:
        pass
    return dirs


def _resolve_keywords(args):
    kws = []
    if getattr(args, "theme", None):
        for d in _theme_dirs():
            kws += theme_keywords(d, args.theme)
        if not kws:
            avail = []
            for d in _theme_dirs():
                avail += load_themes(d)
            print(f"warn: theme '{args.theme}' not found or has no keywords."
                  f" Available: {', '.join(sorted(set(avail))) or '(none)'}")
    if getattr(args, "keywords", None):
        kws += [k.strip() for k in args.keywords.split(",") if k.strip()]
    return kws or None


def cmd_sources(args):
    reg = _registry()
    if args.country:
        reg = by_country(reg, args.country)
    print(f"{'ID':22} {'COUNTRY':8} {'TYPE':12} {'METHOD':7} NAME")
    for s in reg:
        print(f"{s.id:22} {s.country:8} {s.source_type:12} {s.fetch_method:7} {s.name}")
    print(f"\n{len(reg)} sources / countries: {', '.join(countries(_registry()))}")


def cmd_collect(args):
    reg = _registry()
    store = Store(DB_PATH)
    store.sync_registry(reg)
    if args.source:
        targets = [s for s in reg if s.id == args.source]
    elif args.country:
        targets = by_country(reg, args.country)
    else:
        targets = reg
    if not targets:
        print("No matching sources found."); return
    keywords = _resolve_keywords(args)
    if keywords:
        print(f"Theme filter: {len(keywords)} keywords (collect matches only)")
    total_new, total_upd, total_dup, total_err = 0, 0, 0, 0
    for s in targets:
        res = collect_source(s, is_duplicate=store.is_duplicate,
                             max_items=args.max, fetch_full_text=args.full,
                             keywords=keywords)
        c = store.add_or_update_items(res.items, overwrite_by_url=args.full)
        new, upd = c["added"], c["updated"]
        # In refresh mode the collector emits existing items, so report storage's
        # skip count; otherwise the collector's own duplicate count is correct.
        dup = c["skipped"] if args.full else res.skipped_duplicates
        total_new += new; total_upd += upd; total_dup += dup
        total_err += len(res.errors)
        status = "OK" if not res.errors else "ERR"
        upd_str = f" / upd {upd:3}" if args.full else ""
        print(f"[{status}] {s.id:22} new {new:3}{upd_str} / dup {dup:3}")
        for e in res.errors:
            print(f"      ! {e}")
        for n in res.notes:
            print(f"      - {n}")
    upd_total_str = f" / refreshed {total_upd}" if args.full else ""
    print(f"\nTotal: new {total_new}{upd_total_str} / duplicates skipped {total_dup} / errors {total_err}")
    print(f"DB: {DB_PATH} (total items {store.count()})")
    store.close()


def cmd_list(args):
    store = Store(DB_PATH)
    rows = store.items(country=args.country, source_id=args.source, limit=args.limit)
    for r in rows:
        print(f"- [{r['country']}/{r['source_type']}] {r['title'][:80]}")
        print(f"    {r['url']}")
        print(f"    fetched:{r['fetched_at']} lang:{r['lang']} source:{r['source_name']}")
    print(f"\n{len(rows)} items")
    store.close()


def cmd_export(args):
    store = Store(DB_PATH)
    path = export_corpus_json(store, args.path, country=args.country)
    print(f"Wrote raw corpus JSON: {path}")
    print("-> This is the open<->closed handoff artifact (schema: rwt.raw_corpus 1.0).")
    store.close()


def cmd_purge(args):
    """Erase locally collected items (GDPR Art.17 / APPI-style erasure).

    --source <id>  erase only that source's items (cascade).
    (no flag)      erase ALL collected items; requires --yes to confirm.
    Source definitions in the registry are never touched.
    """
    store = Store(DB_PATH)
    try:
        if args.source:
            n = store.delete_by_source(args.source)
            print(f"Deleted {n} item(s) collected from source '{args.source}'.")
        else:
            if not args.yes:
                print("Refusing to delete ALL collected items without --yes.")
                print("Re-run: python cli.py purge --yes")
                return
            n = store.delete_all_items()
            print(f"Deleted ALL {n} collected item(s). Source definitions kept.")
        print(f"DB: {DB_PATH} (remaining items {store.count()})")
    finally:
        store.close()


def cmd_validate(args):
    """Offline: static validation of registry definitions (no network; PR quality gate)."""
    reg = _registry()
    issues = validate_registry(reg)
    print(f"Validating {len(reg)} sources...")
    if not issues:
        print("OK: no problems (schema, required fields, id uniqueness).")
        return
    print(f"FAIL: {len(issues)} problem(s):")
    for m in issues:
        print(f"  - {m}")
    sys.exit(1)


def cmd_verify(args):
    """Live: connect to each feed and diagnose whether it can be fetched/parsed
    (helps fix URLs).

    Each source is cut off by a timeout so it never stalls. Progress is printed
    as it goes, and the results are also saved to verify_report.txt (useful to
    share or to drive fixes later).
    """
    from openbeat_collector.collector import verify_source as _vs
    reg = _registry()
    if args.country:
        reg = by_country(reg, args.country)
    if args.source:
        reg = [s for s in reg if s.id == args.source]
    timeout = args.timeout
    print(f"Connecting to {len(reg)} sources to diagnose (cut off at {timeout}s each)...\n", flush=True)
    ok = bad = 0
    lines = []
    for idx, s in enumerate(reg, 1):
        print(f"  ({idx}/{len(reg)}) checking: {s.id} ...", end="", flush=True)
        r = _vs(s, timeout=timeout)
        st = r["status"]
        if st == "ok":
            ok += 1
        elif st != "manual":
            bad += 1
        print(f"\r[{st:14}] {s.id:22} {r['detail']}        ", flush=True)
        if r.get("action"):
            print(f"      -> fix: {r['action']}", flush=True)
        lines.append(f"[{st}] {s.id} ({s.fetch_method}) {s.url}")
        lines.append(f"    {r['detail']}")
        if r.get("action"):
            lines.append(f"    fix: {r['action']}")
    summary = f"Result: OK {ok} / needs attention {bad} / total {len(reg)}"
    print(f"\n{summary}", flush=True)
    report = os.path.join(HERE, "verify_report.txt")
    with open(report, "w", encoding="utf-8") as f:
        f.write(summary + "\n\n" + "\n".join(lines) + "\n")
    print(f"Saved report: {report}", flush=True)
    if bad:
        print("Note: for sources needing attention, update the url in sources/*.yaml to the latest RSS, or switch to html/manual.", flush=True)


def main():
    p = argparse.ArgumentParser(description="OpenBeat Collector — collection CLI (open side)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("sources", help="show the source registry")
    s1.add_argument("--country")
    s1.set_defaults(func=cmd_sources)

    s2 = sub.add_parser("collect", help="run collection")
    s2.add_argument("--country")
    s2.add_argument("--source")
    s2.add_argument("--max", type=int, default=30, help="max items per source")
    s2.add_argument("--full", action="store_true", help="also fetch the full article page (polite/slower)")
    s2.add_argument("--theme", help="filter by theme (e.g. example)")
    s2.add_argument("--keywords", help="filter by comma-separated keywords")
    s2.set_defaults(func=cmd_collect)

    s3 = sub.add_parser("list", help="show stored items")
    s3.add_argument("--country")
    s3.add_argument("--source")
    s3.add_argument("--limit", type=int, default=50)
    s3.set_defaults(func=cmd_list)

    s4 = sub.add_parser("export", help="write the raw corpus JSON")
    s4.add_argument("path")
    s4.add_argument("--country")
    s4.set_defaults(func=cmd_export)

    s5 = sub.add_parser("validate", help="statically validate the registry (offline)")
    s5.set_defaults(func=cmd_validate)

    s7 = sub.add_parser("purge", help="erase collected items (GDPR Art.17-style erasure)")
    s7.add_argument("--source", help="erase only this source's items; omit to erase ALL")
    s7.add_argument("--yes", action="store_true", help="confirm erasing ALL items")
    s7.set_defaults(func=cmd_purge)

    s6 = sub.add_parser("verify", help="connect to each feed and diagnose (helps fix URLs)")
    s6.add_argument("--country")
    s6.add_argument("--source")
    s6.add_argument("--timeout", type=int, default=8, help="cutoff seconds per source")
    s6.set_defaults(func=cmd_verify)

    add_pack_parser(sub)

    args = p.parse_args()
    if getattr(args, "_is_pack", False):
        sys.exit(cmd_pack(args, HERE))
    args.func(args)


if __name__ == "__main__":
    main()
