"""`cli.py pack ...` subcommands — beat-pack management for the collection CLI.

This wires the pure-Python :class:`rwt.packs.PackStore` (store index, licensing,
install, tier-gated activation) into the command line so a journalist can do, end
to end and offline:

    python cli.py pack list                 # catalog + this install's state
    python cli.py pack install <id>         # fetch pack content (remote or bundled)
    python cli.py pack activate <id>        # turn a pack on (free=1 at a time, pro=many)
    python cli.py pack deactivate <id>      # turn it off
    python cli.py pack license <KEY>        # unlock paid packs / Pro tier
    python cli.py pack license --clear      # forget the license
    python cli.py pack validate [--dir D]   # statically validate pack folders (offline)
    python cli.py pack status               # tier / active packs summary

Activating a pack writes its theme/sources into ``data/active_themes`` /
``data/active_sources``; the collector already reads those, so a freshly
activated pack's sources show up in ``cli.py sources`` / ``collect``.

Kept in its own module (not inline in cli.py) so the bulk of the logic lives in a
clean importable file. Network is only touched when a store URL is configured;
otherwise everything resolves from the bundled ``packs/`` directory.
"""
from __future__ import annotations

import os
from typing import List, Optional

from .packs import PackStore, DEFAULT_INDEX_URL


# --------------------------------------------------------------- index URL ----
def read_pack_index_url(here: str) -> Optional[str]:
    """Resolve the store index URL: env > pack_url.txt > None (bundled only).

    Mirrors app.py so the CLI and the web UI use the same store. Returning None
    means "no live store configured" — the bundled packs/packs.json is used and
    no network call is attempted.
    """
    env = os.environ.get("OPENBEAT_PACK_INDEX_URL")
    if env and env.strip():
        return env.strip()
    txt = os.path.join(here, "pack_url.txt")
    try:
        with open(txt, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except OSError:
        pass
    return None


def _http_get(url: str) -> str:
    """Minimal GET used only when a real store URL is configured."""
    from urllib.request import urlopen, Request
    req = Request(url, headers={"User-Agent": "openbeat-collector/1.0"})
    with urlopen(req, timeout=15) as resp:  # noqa: S310 (configured store URL)
        return resp.read().decode("utf-8")


def build_pack_store(here: str) -> PackStore:
    """Construct a PackStore rooted at this repo (bundled packs/ + data/)."""
    bundled = os.environ.get("OPENBEAT_PACKS_DIR") or os.path.join(here, "packs")
    data_dir = os.path.join(here, "data")
    index_url = read_pack_index_url(here)
    http = _http_get if index_url else None
    return PackStore(bundled_dir=bundled, data_dir=data_dir,
                     index_url=index_url, http_get=http)


# --------------------------------------------------------------- validate ----
_MANIFEST_REQUIRED = ("schema", "spec_version", "id", "name", "version",
                      "languages", "license", "trust_tier", "maintainer",
                      "created", "updated", "provides")
_TRUST_TIERS = ("community", "verified", "federation-certified")
_PACK_TYPES = ("beat", "emergency")


def validate_packs(packs_dir: str) -> List[str]:
    """Statically validate every pack folder under ``packs_dir`` (offline).

    Checks manifest required fields, trust_tier/type enums, that the files named
    in ``provides`` exist, pack-id uniqueness, and that each pack's sources.yaml
    parses and passes the registry validator. Returns a list of problems (empty
    = OK).
    """
    from .registry import load_registry, validate_registry
    try:
        import yaml  # PyYAML
        def _load(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f.read()) or {}
    except Exception:  # pragma: no cover - PyYAML expected in this repo
        from .registry import _load_yaml as _load  # type: ignore

    issues: List[str] = []
    seen_ids = set()
    if not os.path.isdir(packs_dir):
        return [f"packs dir not found: {packs_dir}"]

    pack_dirs = sorted(
        d for d in os.listdir(packs_dir)
        if os.path.isfile(os.path.join(packs_dir, d, "manifest.yaml"))
    )
    if not pack_dirs:
        return [f"no packs found under {packs_dir} (a pack needs manifest.yaml)"]

    for pid_dir in pack_dirs:
        pdir = os.path.join(packs_dir, pid_dir)
        mpath = os.path.join(pdir, "manifest.yaml")
        try:
            man = _load(mpath)
        except Exception as e:  # noqa: BLE001
            issues.append(f"{pid_dir}: cannot parse manifest.yaml ({e})")
            continue

        for field in _MANIFEST_REQUIRED:
            if not man.get(field):
                issues.append(f"{pid_dir}: manifest missing required field '{field}'")
        if man.get("schema") and man.get("schema") != "rwt.pack":
            issues.append(f"{pid_dir}: schema must be 'rwt.pack' (got {man.get('schema')!r})")
        if man.get("trust_tier") and man["trust_tier"] not in _TRUST_TIERS:
            issues.append(f"{pid_dir}: trust_tier must be one of {_TRUST_TIERS}")
        if man.get("type") and man["type"] not in _PACK_TYPES:
            issues.append(f"{pid_dir}: type must be one of {_PACK_TYPES}")

        mid = man.get("id")
        if mid:
            if mid != pid_dir:
                issues.append(f"{pid_dir}: manifest id '{mid}' != folder name")
            if mid in seen_ids:
                issues.append(f"{pid_dir}: duplicate pack id '{mid}'")
            seen_ids.add(mid)

        # provides files must exist
        provides = man.get("provides") or {}
        if isinstance(provides, dict):
            for key in ("theme", "sources"):
                fn = provides.get(key)
                if not fn:
                    issues.append(f"{pid_dir}: provides.{key} not declared")
                elif not os.path.isfile(os.path.join(pdir, fn)):
                    issues.append(f"{pid_dir}: provides.{key} file missing: {fn}")

        # validate the sources list (load_registry only reads keys named 'sources',
        # so manifest.yaml / theme.yaml in the same dir contribute nothing)
        if os.path.isfile(os.path.join(pdir, "sources.yaml")):
            try:
                sources = load_registry(pdir)
                if not sources:
                    issues.append(f"{pid_dir}: sources.yaml has no usable sources")
                for m in validate_registry(sources):
                    issues.append(f"{pid_dir}: {m}")
            except Exception as e:  # noqa: BLE001
                issues.append(f"{pid_dir}: cannot load sources.yaml ({e})")
    return issues


# --------------------------------------------------------------- printing ----
def _fmt_price(p: dict) -> str:
    if not p.get("paid"):
        return "free"
    cur = p.get("currency", "JPY")
    parts = [f"{p.get('price', 0):,} {cur}"]
    if p.get("price_member") is not None:
        parts.append(f"member {p['price_member']:,}")
    per = p.get("period")
    s = " / ".join(parts)
    return s + (f" /{per}" if per else "")


def _state_flags(p: dict) -> str:
    flags = []
    if p.get("type") == "emergency":
        flags.append("EMERGENCY")
    flags.append("entitled" if p.get("entitled") else "locked")
    if p.get("installed"):
        flags.append("installed")
    if p.get("active"):
        flags.append("ACTIVE")
    return ",".join(flags)


# --------------------------------------------------------------- commands ----
def cmd_pack(args, here: str) -> int:
    ps = build_pack_store(here)
    action = args.pack_cmd

    if action == "list":
        info = ps.store_info()
        store_name = info.get("name_en") or info.get("name_ja") or "(bundled, no live store)"
        url = ps.index_url if read_pack_index_url(here) else "(bundled packs/packs.json)"
        print(f"Store: {store_name}")
        print(f"Index: {url}")
        s = ps.summary()
        lim = "unlimited" if s["active_limit"] is None else s["active_limit"]
        print(f"Tier:  {s['tier']}  (active packs allowed: {lim})  "
              f"active now: {', '.join(s['active']) or '(none)'}\n")
        print(f"{'ID':22} {'PRICE':24} {'TRUST':20} STATE")
        for p in ps.catalog():
            print(f"{p.get('id',''):22} {_fmt_price(p):24} "
                  f"{p.get('trust_tier',''):20} {_state_flags(p)}")
        print("\nUse: pack install <id> / pack activate <id> / pack license <KEY>")
        return 0

    if action == "status":
        s = ps.summary()
        print(f"Tier: {s['tier']}  license: {'yes' if s['has_license'] else 'no'}"
              f" ({s['license_source'] or 'n/a'})")
        lim = "unlimited" if s["active_limit"] is None else s["active_limit"]
        print(f"Active packs ({len(s['active'])}/{lim}): {', '.join(s['active']) or '(none)'}")
        return 0

    if action == "validate":
        packs_dir = args.dir or (os.environ.get("OPENBEAT_PACKS_DIR") or os.path.join(here, "packs"))
        issues = validate_packs(packs_dir)
        n = len([d for d in os.listdir(packs_dir)
                 if os.path.isfile(os.path.join(packs_dir, d, "manifest.yaml"))]) \
            if os.path.isdir(packs_dir) else 0
        print(f"Validating {n} pack(s) under {packs_dir} ...")
        if not issues:
            print("OK: all packs valid (manifest, provides files, source registry).")
            return 0
        print(f"FAIL: {len(issues)} problem(s):")
        for m in issues:
            print(f"  - {m}")
        return 1

    if action == "license":
        if args.clear:
            ps.clear_license()
            print("License cleared. Tier reset to free.")
            return 0
        if not args.key:
            print("Provide a license key, e.g. pack license DEMO-PRO-2026 (or --clear).")
            return 1
        r = ps.activate_license(args.key)
        if not r.get("ok"):
            print(f"License not accepted: {r.get('error')}")
            return 1
        print(f"License OK ({r.get('source')}). Tier: {r.get('tier')}. "
              f"Entitled packs: {', '.join(r.get('packs', [])) or '(none)'}")
        return 0

    if action == "install":
        meta = ps.pack_meta(args.id)
        if not meta:
            print(f"Unknown pack: {args.id}. See 'pack list'.")
            return 1
        r = ps.install(args.id)
        if not r.get("ok"):
            print(f"Install failed: {r.get('error')}")
            return 1
        gated = " (paid — activation needs a license)" if (meta.get("paid") and not ps.is_entitled(meta)) else ""
        print(f"Installed: {args.id}{gated}. Activate with: pack activate {args.id}")
        return 0

    if action == "update":
        meta = ps.pack_meta(args.id)
        if not meta:
            print(f"Unknown pack: {args.id}. See 'pack list'.")
            return 1
        # Re-fetch content (store, else bundled) over the installed copy, so a
        # newer pack version / fixed source URLs replace the cached files.
        r = ps.install(args.id)
        if not r.get("ok"):
            print(f"Update failed: {r.get('error')}")
            return 1
        if ps.is_active(args.id):
            ps.activate(args.id)   # already-active path now rebuilds active dirs
            print(f"Updated '{args.id}' and refreshed its active sources/theme.")
            print("Re-run 'cli.py verify' to re-check this pack's feeds.")
        else:
            print(f"Updated '{args.id}'. Activate with: pack activate {args.id}")
        return 0

    if action == "activate":
        r = ps.activate(args.id)
        if not r.get("ok"):
            err = r.get("error")
            if err == "not_entitled":
                print(f"'{args.id}' is a paid pack. Buy it and run: pack license <KEY>")
            elif err == "unknown_pack":
                print(f"Unknown pack: {args.id}. See 'pack list'.")
            else:
                print(f"Activate failed: {err}")
            return 1
        if r.get("already"):
            print(f"'{args.id}' was already active.")
        elif ps.tier() != "pro":
            print(f"Activated '{args.id}' (free tier = one pack at a time; others were turned off).")
        else:
            print(f"Activated '{args.id}'.")
        print(f"Active now: {', '.join(ps.activated())}")
        print("Its sources are now part of 'cli.py sources' / 'collect'.")
        return 0

    if action == "deactivate":
        ps.deactivate(args.id)
        print(f"Deactivated '{args.id}'. Active now: {', '.join(ps.activated()) or '(none)'}")
        return 0

    print("Unknown pack action. Try: list, install, activate, deactivate, license, validate, status.")
    return 1


def add_pack_parser(sub) -> None:
    """Register the `pack` subcommand tree on an argparse subparsers object."""
    p = sub.add_parser("pack", help="install / manage beat packs from the store")
    psub = p.add_subparsers(dest="pack_cmd", required=True)

    psub.add_parser("list", help="show the pack catalog and this install's state")
    psub.add_parser("status", help="show tier and active packs")

    pi = psub.add_parser("install", help="fetch pack content (store or bundled)")
    pi.add_argument("id")

    pa = psub.add_parser("activate", help="turn a pack on (free=1, pro=many)")
    pa.add_argument("id")

    pd = psub.add_parser("deactivate", help="turn a pack off")
    pd.add_argument("id")

    pup = psub.add_parser("update", help="re-fetch a pack's content; refresh if active")
    pup.add_argument("id")

    pl = psub.add_parser("license", help="unlock paid packs / Pro with a key")
    pl.add_argument("key", nargs="?", help="license key (omit with --clear)")
    pl.add_argument("--clear", action="store_true", help="forget the stored license")

    pv = psub.add_parser("validate", help="statically validate pack folders (offline)")
    pv.add_argument("--dir", help="packs dir to validate (default: bundled packs/)")

    # func is dispatched by cli.py (needs `here`); store the marker
    p.set_defaults(_is_pack=True)
