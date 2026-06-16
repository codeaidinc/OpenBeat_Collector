"""Flask blueprint for the pack store UI.

Kept separate from app.py so it can be registered with one call and tested with
a minimal shim app. All state lives in a PackStore instance (rwt.packs).
"""
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash

from .store_text import store_strings, get_lang

store_bp = Blueprint("store", __name__)

_CTX = {"store": None}


def init_store(app, pack_store):
    """Attach a PackStore and register the blueprint on the app."""
    _CTX["store"] = pack_store
    app.register_blueprint(store_bp)
    return store_bp


def _store():
    return _CTX["store"]


def _name(meta):
    if not meta:
        return ""
    return (meta.get("name_ja") if get_lang() == "ja" else None) or meta.get("name") or meta.get("id")


@store_bp.route("/store")
def store_page():
    ps = _store()
    return render_template(
        "store.html",
        s=store_strings(), lang=get_lang(),
        catalog=ps.catalog(),
        summary=ps.summary(),
        store=ps.store_info(),
    )


@store_bp.route("/store/license", methods=["POST"])
def store_license():
    ps = _store()
    s = store_strings()
    key = (request.form.get("key") or "").strip()
    r = ps.activate_license(key)
    if r.get("ok"):
        packs = ", ".join(r.get("packs", [])) or "-"
        flash(s["f_license_ok"].format(tier=r.get("tier", "free"), packs=packs))
    elif r.get("error") == "empty":
        flash(s["f_license_empty"])
    else:
        flash(s["f_license_bad"])
    return redirect(url_for("store.store_page"))


@store_bp.route("/store/license/clear", methods=["POST"])
def store_license_clear():
    ps = _store()
    ps.clear_license()
    flash(store_strings()["f_license_cleared"])
    return redirect(url_for("store.store_page"))


@store_bp.route("/store/activate", methods=["POST"])
def store_activate():
    ps = _store()
    s = store_strings()
    pid = (request.form.get("id") or "").strip()
    meta = ps.pack_meta(pid)
    was_free_single = ps.tier() != "pro" and len(ps.activated()) >= 1 and not ps.is_active(pid)
    r = ps.activate(pid)
    if r.get("ok"):
        flash(s["f_activated"].format(name=_name(meta)))
        if was_free_single:
            flash(s["f_need_pro"])
    elif r.get("error") == "not_entitled":
        flash(s["f_not_entitled"])
    else:
        flash(s["f_install_failed"].format(err=r.get("error", "")))
    return redirect(url_for("store.store_page"))


@store_bp.route("/store/deactivate", methods=["POST"])
def store_deactivate():
    ps = _store()
    s = store_strings()
    pid = (request.form.get("id") or "").strip()
    meta = ps.pack_meta(pid)
    ps.deactivate(pid)
    flash(s["f_deactivated"].format(name=_name(meta)))
    return redirect(url_for("store.store_page"))


@store_bp.route("/store/refresh", methods=["POST"])
def store_refresh():
    ps = _store()
    ps.load_index(refresh=True)
    flash(store_strings()["f_index_refreshed"])
    return redirect(url_for("store.store_page"))
