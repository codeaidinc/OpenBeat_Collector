#!/usr/bin/env python3
"""RWT — no-code web UI (for non-developers).

The whole flow is: "pick a country / theme / sources -> press Collect ->
browse what was gathered -> export JSON". After installation, run it with
`python app.py`; a browser opens automatically and the user never touches code.

The UI is English by default. Set OPENBEAT_LANG=ja for a Japanese UI.
"""
from __future__ import annotations

import os
import sys
import threading
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
# PyInstaller onefile unpacks resources into sys._MEIPASS; otherwise use the
# script location.
BASE = getattr(sys, "_MEIPASS", HERE)
sys.path.insert(0, BASE)
sys.path.insert(0, HERE)

from urllib.parse import quote as _urlquote
from flask import (Flask, render_template, request, redirect,
                   url_for, Response, flash, session)

GITHUB_REPO = "https://github.com/codeaidinc/OpenBeat_Collector"


# Where source requests should be sent. Point this at a spam-protected form
# (Google Forms, Tally, etc.). If the URL contains {site} / {detail}, they are
# substituted (URL-encoded) so the form opens pre-filled.
# Resolution order (so packaged builds work without environment variables):
#   1) OPENBEAT_SUPPORT_URL environment variable (dev / power users)
#   2) a 'support_url.txt' file next to the executable (editable after install)
#      or bundled with the build
#   3) default = the project's GitHub Issues page
def _read_support_template():
    v = os.environ.get("OPENBEAT_SUPPORT_URL")
    if v and v.strip():
        return v.strip()
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else HERE
    for d in (exe_dir, BASE):
        try:
            with open(os.path.join(d, "support_url.txt"), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
        except OSError:
            pass
    return f"{GITHUB_REPO}/issues"


SUPPORT_URL_TEMPLATE = _read_support_template()


def _support_url(site, detail=""):
    u = SUPPORT_URL_TEMPLATE
    if "{site}" in u or "{detail}" in u:
        u = u.replace("{site}", _urlquote(site, safe="")).replace(
            "{detail}", _urlquote(detail, safe=""))
    return u


def _request_text(site, detail=""):
    """Account-free support request the user can copy and send anywhere.

    Localized to the active UI language (OPENBEAT_LANG)."""
    return strings()["req_text"].format(site=site, detail=detail)

from openbeat_collector.registry import (load_registry, by_country, by_id, countries,
                          save_sources, validate_registry,
                          VALID_SOURCE_TYPES, VALID_FETCH_METHODS, VALID_TRUST)
from openbeat_collector.schema import Source
from openbeat_collector.collector import (collect_source, collect_manual, verify_source,
                           discover_feed)
from openbeat_collector.storage import Store
from openbeat_collector.export import corpus_to_json_str
from openbeat_collector.themes import load_themes, theme_keywords
from openbeat_collector.i18n import strings, get_lang
from openbeat_collector.packs import PackStore
from openbeat_collector.store_routes import init_store

# Read-only resources (overridable via env; bundled data is used when packaged).
SOURCES_DIR = os.environ.get("OPENBEAT_SOURCES_DIR") or os.path.join(BASE, "sources")
THEMES_DIR = os.environ.get("OPENBEAT_THEMES_DIR") or os.path.join(BASE, "themes")
PACKS_DIR = os.environ.get("OPENBEAT_PACKS_DIR") or os.path.join(BASE, "packs")
TEMPLATES_DIR = os.path.join(BASE, "templates")
TESTS_DIR = os.path.join(BASE, "tests")


def _default_db_path():
    # The DB must live in a writable location. When frozen (.exe/.app), put it
    # in a data/ folder next to the executable.
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else HERE
    return os.path.join(base, "data", "rwt.sqlite")


DB_PATH = os.environ.get("OPENBEAT_DB_PATH") or _default_db_path()
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

app = Flask(__name__, template_folder=TEMPLATES_DIR)
# The app binds to 127.0.0.1 only (localhost; see app.run() at the bottom), so
# the session cookie never leaves the machine and the localhost-only default
# secret is acceptable. Operators who want a unique key can still override it
# via the OPENBEAT_SECRET environment variable.
app.secret_key = os.environ.get("OPENBEAT_SECRET") or "rwt-local-only"

# Sources edited from the web UI are saved to a writable overlay (next to the DB),
# so editing works even when the app is packaged (the bundled sources/ is read-only).
# Once this file exists it is the active registry; delete it to restore defaults.
USER_SOURCES_DIR = os.environ.get("OPENBEAT_USER_SOURCES_DIR") or os.path.join(
    os.path.dirname(DB_PATH), "user_sources")
USER_SOURCES_FILE = os.path.join(USER_SOURCES_DIR, "sources.yaml")


# ---- Pack store (remote beat-pack marketplace; bundled fallback) ---------
# The store index URL is configurable so packs can be served from the JASTJ
# server. Resolution: OPENBEAT_PACK_INDEX_URL env -> pack_url.txt next to the exe/
# bundle -> none (use the bundled catalog only, no network).
def _read_pack_index_url():
    v = os.environ.get("OPENBEAT_PACK_INDEX_URL")
    if v and v.strip():
        return v.strip()
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else HERE
    for d in (exe_dir, BASE):
        try:
            with open(os.path.join(d, "pack_url.txt"), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
        except OSError:
            pass
    return None


PACK_INDEX_URL = _read_pack_index_url()
from openbeat_collector.collector import http_get as _pack_http_get
# When no server URL is configured, pass http_get=None so the store reads the
# bundled catalog directly (no network attempt to the placeholder domain).
pack_store = PackStore(
    bundled_dir=PACKS_DIR,
    data_dir=os.path.dirname(DB_PATH),
    index_url=PACK_INDEX_URL,
    http_get=(_pack_http_get if PACK_INDEX_URL else None),
)
init_store(app, pack_store)


def _using_user_registry():
    return os.path.exists(USER_SOURCES_FILE)


def _base_registry():
    if _using_user_registry():
        return load_registry(USER_SOURCES_DIR)
    return load_registry(SOURCES_DIR)


def get_registry():
    """Base registry (bundled or user overlay) plus any active beat packs."""
    base = _base_registry()
    active = load_registry(pack_store.active_sources_dir)
    seen = {s.id for s in base}
    return base + [s for s in active if s.id not in seen]


def _save_user_registry(sources):
    """Persist the full active registry to the writable overlay file."""
    save_sources(sources, USER_SOURCES_FILE)


def get_store():
    store = Store(DB_PATH)
    store.sync_registry(get_registry())
    return store


def _merged_themes():
    """Bundled themes plus the themes of any active beat packs."""
    d = dict(load_themes(THEMES_DIR))
    d.update(load_themes(pack_store.active_themes_dir))
    return d


def _theme_kws(theme):
    if not theme:
        return None
    return _merged_themes().get(theme) or None


def _filter_items_by_theme(items, theme):
    kws = _theme_kws(theme)
    if not kws:
        return items
    ks = [k.strip().lower() for k in kws if k.strip()]
    def _t(r):
        return (f"{r.get('title','')} {r.get('summary_excerpt','')} "
                f"{r.get('body_raw','')}").lower()
    return [r for r in items if any(k in _t(r) for k in ks)]


@app.route("/")
def index():
    reg = get_registry()
    store = get_store()
    sel_country = request.args.get("country") or (countries(reg)[0] if reg else "")
    sel_theme = request.args.get("theme", "")
    sel_full = request.args.get("full") == "1"   # remember the "fetch full text" choice across collects
    sources = by_country(reg, sel_country) if sel_country else reg
    items = store.items(country=sel_country, limit=1000)
    counts = {c: store.count(c) for c in countries(reg)}
    store.close()
    items = _filter_items_by_theme(items, sel_theme)   # also filter the view by theme
    return render_template(
        "index.html",
        t=strings(), lang=get_lang(),
        countries=countries(reg),
        sel_country=sel_country,
        sel_theme=sel_theme,
        sel_full=sel_full,
        sources=sources,
        items=items,
        shown=len(items),
        counts=counts,
        total=sum(counts.values()),
        themes=list(_merged_themes().keys()),
    )


@app.route("/collect", methods=["POST"])
def collect():
    t = strings()
    country = request.form.get("country", "")
    full = request.form.get("full") == "on"
    theme = request.form.get("theme", "")
    selected = request.form.getlist("source_ids")
    reg = get_registry()
    store = get_store()
    targets = [s for s in reg if s.id in selected] if selected else by_country(reg, country)
    keywords = _merged_themes().get(theme) if theme else None

    new_total, upd_total, dup_total, msgs, notes = 0, 0, 0, [], []
    for s in targets:
        res = collect_source(s, is_duplicate=store.is_duplicate,
                             max_items=30, fetch_full_text=full, keywords=keywords)
        c = store.add_or_update_items(res.items, overwrite_by_url=full)
        new_total += c["added"]
        upd_total += c["updated"]
        dup_total += c["skipped"] if full else res.skipped_duplicates
        if res.errors:
            msgs.append(f"⚠ {s.name}: {res.errors[0][:80]}")
        for n in res.notes:
            notes.append(n[:120])
    store.close()
    tnote = t["theme_paren"].format(theme=theme) if theme else ""
    msg = t["collect_done"].format(theme=tnote, new=new_total, dup=dup_total)
    if full and upd_total:
        msg += t["collect_refreshed"].format(upd=upd_total)
    if msgs:
        msg += "  " + " ".join(msgs[:4])
    flash(msg)
    # Surface why some sources could not be fully fetched (e.g. bot-blocked / JS
    # pages fell back to summary) so the user understands what happened.
    if notes:
        flash(t["notes_label"] + ": " + " / ".join(notes[:6]))
    return redirect(url_for("index", country=country, theme=theme,
                            full="1" if full else None))


@app.route("/manual", methods=["POST"])
def manual():
    """Manual paste fallback (robots-disallowed, paywalled, or unfetchable)."""
    t = strings()
    sid = request.form.get("source_id", "")
    url = request.form.get("url", "").strip()
    title = request.form.get("title", "").strip()
    text = request.form.get("text", "").strip()
    country = request.form.get("country", "")
    reg = get_registry()
    s = by_id(reg, sid)
    if not s or not text:
        flash(t["manual_required"])
        return redirect(url_for("index", country=country))
    store = get_store()
    item = collect_manual(s, url or s.site, title or t["untitled"], text)
    added = store.add_item(item)
    store.close()
    theme = request.form.get("theme", "")
    flash(t["manual_added"] if added else t["manual_dup"])
    return redirect(url_for("index", country=country, theme=theme))


def _source_from_form(f):
    return Source(
        id=(f.get("id") or "").strip(),
        country=(f.get("country") or "").strip(),
        source_type=(f.get("source_type") or "media").strip(),
        name=(f.get("name") or "").strip(),
        url=(f.get("url") or "").strip(),
        site=(f.get("site") or "").strip(),
        lang=(f.get("lang") or "").strip(),
        fetch_method=(f.get("fetch_method") or "rss").strip(),
        license_note=(f.get("license_note") or "").strip(),
        trust=(f.get("trust") or "medium").strip(),
        update_freq=(f.get("update_freq") or "").strip(),
        url_rewrite=(f.get("url_rewrite") or "").strip(),
        dataset_spec=(f.get("dataset_spec") or "").strip(),
    )


@app.route("/sources")
def sources_page():
    """No-code source manager: add / edit / delete / test sources on screen."""
    reg = get_registry()
    edit_id = request.args.get("edit", "")
    edit_src = by_id(reg, edit_id) if edit_id else None
    # Result of the "auto-detect feed" helper (stashed in the session), used to
    # pre-fill the add form and to offer candidate feeds / a support-request link.
    disc = session.pop("disc", None)
    if disc:
        _site = disc.get("site") or disc.get("url", "")
        disc["request_text"] = _request_text(_site, disc.get("detail", ""))
        disc["support_url"] = _support_url(_site, disc.get("detail", ""))
    return render_template(
        "sources.html",
        t=strings(), lang=get_lang(),
        sources=reg,
        edit_src=edit_src,
        disc=disc,
        using_user=_using_user_registry(),
        known_countries=countries(load_registry(SOURCES_DIR)),
        valid_types=sorted(VALID_SOURCE_TYPES),
        valid_methods=sorted(VALID_FETCH_METHODS),
        valid_trust=["high", "medium", "low"],
    )


@app.route("/sources/save", methods=["POST"])
def sources_save():
    """Add a new source or update an existing one (id may change on edit)."""
    t = strings()
    orig_id = (request.form.get("orig_id") or "").strip()
    s = _source_from_form(request.form)
    reg = get_registry()
    # Everything except the row being edited (orig_id). The new id must not
    # collide with any of these — note we keep rows whose id == s.id here so the
    # duplicate check below can actually see a clash.
    others = [x for x in reg if x.id != orig_id]
    # Hard validation (license_note 'recommended' is a soft warning, not blocking).
    issues = [i for i in validate_registry([s]) if "recommended" not in i]
    if any(x.id == s.id for x in others):
        issues.append(t["src_dup_id"].format(id=s.id))
    if issues:
        flash(t["src_save_err"].format(msg="; ".join(issues[:4])))
        return redirect(url_for("sources_page", edit=orig_id or s.id))
    # Persist: drop any stale row with the same id, then append the new/edited one.
    _save_user_registry([x for x in others if x.id != s.id] + [s])
    flash(t["src_saved"].format(id=s.id))
    return redirect(url_for("sources_page"))


@app.route("/sources/delete", methods=["POST"])
def sources_delete():
    t = strings()
    sid = (request.form.get("id") or "").strip()
    reg = get_registry()
    _save_user_registry([x for x in reg if x.id != sid])
    # GDPR Art.17 / APPI-style erasure: when a source is removed, also delete the
    # raw items collected from it so no orphaned personal data lingers locally.
    store = get_store()
    try:
        store.delete_by_source(sid)
    finally:
        store.close()
    flash(t["src_deleted"].format(id=sid))
    return redirect(url_for("sources_page"))


@app.route("/data/delete_all", methods=["POST"])
def data_delete_all():
    """Erase ALL locally collected items (GDPR Art.17 / APPI-style full wipe).
    Source definitions are kept; only the stored corpus is removed."""
    t = strings()
    store = get_store()
    try:
        n = store.delete_all_items()
    finally:
        store.close()
    # Use a localized message if available, else a clear bilingual fallback.
    msg = t.get("data_wiped")
    if msg:
        flash(msg.format(n=n))
    else:
        flash(f"Deleted all {n} collected items. / 収集済みデータ {n} 件をすべて削除しました。")
    return redirect(url_for("index"))


@app.route("/sources/verify", methods=["POST"])
def sources_verify():
    """Live connection test for one source (so users can fix URLs on screen)."""
    t = strings()
    sid = (request.form.get("id") or "").strip()
    s = by_id(get_registry(), sid)
    if not s:
        flash(t["src_not_found"].format(id=sid))
        return redirect(url_for("sources_page"))
    r = verify_source(s)
    msg = t["src_verify_result"].format(id=s.id, status=r["status"], detail=r["detail"])
    if r.get("action"):
        msg += "  -> " + r["action"]
    flash(msg)
    return redirect(url_for("sources_page", edit=sid))


@app.route("/sources/reset", methods=["POST"])
def sources_reset():
    """Restore the bundled default sources (removes the user overlay file)."""
    t = strings()
    try:
        os.remove(USER_SOURCES_FILE)
    except FileNotFoundError:
        pass
    flash(t["src_reset_done"])
    return redirect(url_for("sources_page"))


@app.route("/sources/discover", methods=["POST"])
def sources_discover():
    """Paste a normal site URL -> auto-detect the feed and pre-fill the add form,
    so non-technical users never have to know what 'RSS' or 'fetch_method' means."""
    t = strings()
    page = (request.form.get("page_url") or "").strip()
    if not page:
        flash(t["src_discover_need_url"])
        return redirect(url_for("sources_page"))
    r = discover_feed(page)
    key = {"rss": "src_discover_rss", "html": "src_discover_html",
           "manual": "src_discover_manual"}.get(r["status"], "src_discover_error")
    flash(t[key].format(detail=r["detail"]))
    session["disc"] = {"url": r["url"], "method": r["method"], "site": page,
                       "status": r["status"], "detail": r["detail"],
                       "candidates": r.get("candidates", [])}
    return redirect(url_for("sources_page"))


def _load_demo(store, country):
    """Load the bundled samples (no internet) so first-time users see results."""
    t = strings()
    from openbeat_collector.schema import Source
    from pathlib import Path
    # Replace any old demo rows so stale, non-existent URLs from past versions
    # never linger (rebuild them every time).
    for _sid in ("demo-feed", "demo-stats"):
        try:
            store.delete_by_source(_sid)
        except Exception:
            pass
    added = 0
    feed = os.path.join(TESTS_DIR, "sample_feed.xml")
    if os.path.exists(feed):
        src = Source(id="demo-feed", country=country, source_type="media",
                     name=t["demo_feed_name"], url=Path(feed).as_uri(),
                     lang="en", fetch_method="rss",
                     license_note=t["demo_license"], trust="medium")
        res = collect_source(src, is_duplicate=store.is_duplicate, max_items=30)
        for it in res.items:
            it.url = "/sample/" + it.id      # local sample view, not a fake source URL
        added += store.add_items(res.items)
    stats = os.path.join(TESTS_DIR, "sample_stats.csv")
    if os.path.exists(stats):
        src2 = Source(id="demo-stats", country=country, source_type="statistics",
                      name=t["demo_stats_name"], url=Path(stats).as_uri(),
                      lang="en", fetch_method="dataset",
                      license_note=t["demo_license"], trust="high",
                      dataset_spec=("format=csv;label=" + t["demo_stats_label"] +
                                    ";period=month;value=index_yoy;unit=%;"
                                    "delta=mom;max=6"))
        res2 = collect_source(src2, is_duplicate=store.is_duplicate, max_items=10)
        for it in res2.items:
            it.url = "/sample/" + it.id
        added += store.add_items(res2.items)
    return added


@app.route("/demo", methods=["POST"])
def demo():
    t = strings()
    reg = get_registry()
    country = request.form.get("country") or (countries(reg)[0] if reg else "Japan")
    store = get_store()
    try:
        added = _load_demo(store, country)
    finally:
        store.close()
    flash(t["demo_loaded"].format(n=added))
    return redirect(url_for("index", country=country))


@app.route("/sample/<item_id>")
def sample_view(item_id):
    """Offline view of a demo sample article (clearly not a real page)."""
    store = get_store()
    try:
        rows = store.items(limit=1000)
    finally:
        store.close()
    it = next((r for r in rows if r.get("id") == item_id), None)
    if not it:
        return Response("Not found", status=404)
    return render_template("sample.html", it=it, t=strings(), lang=get_lang())


@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Quit the tool from the UI (so it can be stopped even without a console)."""
    t = strings()
    import time
    def _stop():
        time.sleep(0.6)
        os._exit(0)
    threading.Thread(target=_stop, daemon=True).start()
    return ("<!doctype html><meta charset='utf-8'>"
            "<body style='font-family:system-ui,sans-serif;padding:48px;color:#1e293b'>"
            f"<h2>{t['shutdown_h2']}</h2>"
            f"<p>{t['shutdown_p']}</p>"
            "</body>")


@app.route("/export.json")
def export_json():
    country = request.args.get("country") or None
    theme = request.args.get("theme", "")
    store = get_store()
    payload = corpus_to_json_str(store, country=country, keywords=_theme_kws(theme))
    store.close()
    fname = f"rwt_corpus_{country or 'all'}{('_' + theme) if theme else ''}.json"
    return Response(
        payload, mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


def _open_browser(port):
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    t = strings()
    port = int(os.environ.get("OPENBEAT_PORT", "5000"))
    # During development, OPENBEAT_DEBUG=1 enables auto-reload (edits apply instantly).
    # When distributed, it is unset = safe production mode.
    debug = os.environ.get("OPENBEAT_DEBUG") == "1"
    # With auto-reload, avoid opening the browser twice (skip it in the reloader
    # parent process).
    if os.environ.get("OPENBEAT_NO_BROWSER") != "1" and not (debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true"):
        threading.Timer(1.2, _open_browser, args=(port,)).start()
    print("\n  " + t["startup_running"] + (t["startup_debug"] if debug else ""))
    print(t["startup_open"] + f"http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=debug)
