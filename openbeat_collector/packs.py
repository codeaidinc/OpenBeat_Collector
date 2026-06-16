"""Beat-pack store / marketplace (open-core paid-pack model).

The open-source core stays free. Beat packs (a theme + a curated source list for
one journalist specialty) are distributed from a store server (e.g. JASTJ's), and
some packs are paid — the WordPress model: free core, a marketplace of free and
paid add-ons.

Design:
  - The store index (``packs.json``) is fetched from a configurable URL
    (``OPENBEAT_PACK_INDEX_URL`` / ``pack_url.txt`` / a placeholder default). It is
    metadata only (names, descriptions, prices, buy links). If the server cannot
    be reached, a bundled copy under ``packs/packs.json`` is used so the store
    still works offline / before the server exists.
  - Paid packs are unlocked with a LICENSE KEY (bought on the store site). The
    key is verified against the store's ``license_endpoint`` and the resulting
    entitlements are cached locally. An offline demo fallback
    (``packs/licenses.demo.json``) lets the flow be tested without a live server.
  - Tier gating: the FREE tier can have ONE active pack at a time (activating a
    new one replaces the current). The PRO tier (a paid upgrade) can have many
    packs active at once — like the sections of a newspaper.

This module is pure-Python (no Flask) so it is independently testable. Pack
content (theme.yaml / sources.yaml) is written into ``data/active_*`` dirs that
the app already knows how to load via ``rwt.registry`` / ``rwt.themes``.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
from typing import Dict, List, Optional
from urllib.parse import quote

PACK_FILES = ("manifest.yaml", "theme.yaml", "sources.yaml")
DEFAULT_INDEX_URL = "https://packs.jastj.example/packs.json"


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _write_json(path: str, obj) -> None:
    _write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))


def _read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


class PackStore:
    """Stateful store: index, licensing, install, activation (tier-gated)."""

    def __init__(self, *, bundled_dir: str, data_dir: str,
                 index_url: Optional[str] = None, http_get=None):
        self.bundled_dir = bundled_dir          # repo packs/ (read-only: packs.json + <id>/ + licenses.demo.json)
        self.data_dir = data_dir                # writable
        self.installed_dir = os.path.join(data_dir, "packs_installed")
        self.active_sources_dir = os.path.join(data_dir, "active_sources")
        self.active_themes_dir = os.path.join(data_dir, "active_themes")
        self.license_file = os.path.join(data_dir, "license.json")
        self.state_file = os.path.join(data_dir, "packs_state.json")
        self.index_url = index_url or DEFAULT_INDEX_URL
        self._http_get = http_get
        self._index_cache: Optional[dict] = None
        for d in (self.installed_dir, self.active_sources_dir, self.active_themes_dir):
            os.makedirs(d, exist_ok=True)

    # -------------------------------------------------------------- index ----
    def load_index(self, refresh: bool = False) -> dict:
        if self._index_cache is not None and not refresh:
            return self._index_cache
        data = None
        if refresh or self._index_cache is None:
            data = self._fetch_remote_index()
        if data is None:
            data = self._bundled_index()
        if data is None:
            data = {"schema": "rwt.pack_index", "version": "1.0", "store": {}, "packs": []}
        self._index_cache = data
        return data

    def _fetch_remote_index(self) -> Optional[dict]:
        if not (self.index_url and self._http_get):
            return None
        try:
            return json.loads(self._http_get(self.index_url))
        except Exception:
            return None

    def _bundled_index(self) -> Optional[dict]:
        return _read_json(os.path.join(self.bundled_dir, "packs.json"))

    def store_info(self) -> dict:
        return self.load_index().get("store", {}) or {}

    def packs_meta(self) -> List[dict]:
        return self.load_index().get("packs", []) or []

    def pack_meta(self, pack_id: str) -> Optional[dict]:
        for p in self.packs_meta():
            if p.get("id") == pack_id:
                return p
        return None

    # ---------------------------------------------------------- licensing ----
    def load_license(self) -> dict:
        lic = _read_json(self.license_file)
        if not isinstance(lic, dict):
            return {"key": "", "tier": "free", "packs": []}
        lic.setdefault("tier", "free")
        lic.setdefault("packs", [])
        lic.setdefault("key", "")
        return lic

    def tier(self) -> str:
        return self.load_license().get("tier", "free") or "free"

    def entitled_packs(self) -> List[str]:
        return list(self.load_license().get("packs", []) or [])

    def is_entitled(self, pack: dict) -> bool:
        if not pack.get("paid"):
            return True
        return pack.get("id") in self.entitled_packs()

    def activate_license(self, key: str) -> dict:
        key = (key or "").strip()
        if not key:
            return {"ok": False, "error": "empty"}
        ent = self._verify_remote(key)
        source = "server"
        if ent is None:
            ent = self._verify_demo(key)
            source = "demo"
        if ent is None:
            return {"ok": False, "error": "invalid"}
        lic = {"key": key, "tier": ent.get("tier", "free"),
               "packs": list(ent.get("packs", [])), "source": source}
        _write_json(self.license_file, lic)
        return {"ok": True, **lic}

    def _verify_remote(self, key: str) -> Optional[dict]:
        endpoint = self.store_info().get("license_endpoint")
        if not (endpoint and self._http_get):
            return None
        try:
            sep = "&" if "?" in endpoint else "?"
            resp = json.loads(self._http_get(endpoint + sep + "key=" + quote(key)))
            if resp.get("valid"):
                return {"tier": resp.get("tier", "free"), "packs": resp.get("packs", [])}
        except Exception:
            return None
        return None

    def _verify_demo(self, key: str) -> Optional[dict]:
        m = _read_json(os.path.join(self.bundled_dir, "licenses.demo.json"))
        if not isinstance(m, dict):
            return None
        e = m.get(key)
        if not isinstance(e, dict):
            return None
        return {"tier": e.get("tier", "free"), "packs": e.get("packs", [])}

    def clear_license(self) -> None:
        try:
            os.remove(self.license_file)
        except OSError:
            pass

    # ------------------------------------------------------------ install ----
    def is_installed(self, pack_id: str) -> bool:
        return os.path.exists(os.path.join(self.installed_dir, pack_id, "sources.yaml"))

    def install(self, pack_id: str) -> dict:
        """Download pack content (remote files_base, else bundled fallback)."""
        meta = self.pack_meta(pack_id)
        if not meta:
            return {"ok": False, "error": "unknown_pack"}
        dest = os.path.join(self.installed_dir, pack_id)
        os.makedirs(dest, exist_ok=True)
        if self._download_remote(meta, dest) or self._copy_bundled(pack_id, dest):
            return {"ok": True}
        return {"ok": False, "error": "content_unavailable"}

    def _download_remote(self, meta: dict, dest: str) -> bool:
        files_base = meta.get("files_base")
        if not (files_base and self._http_get):
            return False
        key = self.load_license().get("key", "") if meta.get("paid") else ""
        try:
            for fn in PACK_FILES:
                url = files_base.rstrip("/") + "/" + fn
                if key:
                    url += ("&" if "?" in url else "?") + "key=" + quote(key)
                _write_text(os.path.join(dest, fn), self._http_get(url))
            return True
        except Exception:
            return False

    def _copy_bundled(self, pack_id: str, dest: str) -> bool:
        src = os.path.join(self.bundled_dir, pack_id)
        ok = False
        for fn in PACK_FILES:
            sp = os.path.join(src, fn)
            if os.path.exists(sp):
                shutil.copyfile(sp, os.path.join(dest, fn))
                ok = True
        return ok

    # --------------------------------------------------------- activation ----
    def activated(self) -> List[str]:
        st = _read_json(self.state_file)
        if isinstance(st, dict):
            return list(st.get("activated", []))
        return []

    def is_active(self, pack_id: str) -> bool:
        return pack_id in self.activated()

    def active_limit(self) -> Optional[int]:
        """Max simultaneously-active packs. None = unlimited (Pro)."""
        return None if self.tier() == "pro" else 1

    def can_activate_more(self) -> bool:
        lim = self.active_limit()
        return lim is None or len(self.activated()) < lim

    def activate(self, pack_id: str) -> dict:
        meta = self.pack_meta(pack_id)
        if not meta:
            return {"ok": False, "error": "unknown_pack"}
        if not self.is_entitled(meta):
            return {"ok": False, "error": "not_entitled"}
        if not self.is_installed(pack_id):
            r = self.install(pack_id)
            if not r["ok"]:
                return r
        ids = self.activated()
        if pack_id in ids:
            # Already active — rebuild active dirs in case the installed content
            # was refreshed (e.g. by `pack update`) so edits propagate.
            self._rebuild_active_dirs(ids)
            return {"ok": True, "already": True, "activated": ids}
        if self.tier() == "pro":
            ids = ids + [pack_id]
        else:
            ids = [pack_id]            # free tier: single active pack (replace)
        self._set_activated(ids)
        return {"ok": True, "activated": ids}

    def deactivate(self, pack_id: str) -> dict:
        ids = [i for i in self.activated() if i != pack_id]
        self._set_activated(ids)
        return {"ok": True, "activated": ids}

    def _set_activated(self, ids: List[str]) -> None:
        _write_json(self.state_file, {"activated": ids})
        self._rebuild_active_dirs(ids)

    def _rebuild_active_dirs(self, ids: List[str]) -> None:
        """Rewrite active_sources/ and active_themes/ to exactly these packs."""
        for d in (self.active_sources_dir, self.active_themes_dir):
            for f in glob.glob(os.path.join(d, "*.yaml")) + glob.glob(os.path.join(d, "*.yml")):
                try:
                    os.remove(f)
                except OSError:
                    pass
        for pid in ids:
            s = os.path.join(self.installed_dir, pid, "sources.yaml")
            t = os.path.join(self.installed_dir, pid, "theme.yaml")
            if os.path.exists(s):
                shutil.copyfile(s, os.path.join(self.active_sources_dir, pid + ".yaml"))
            if os.path.exists(t):
                shutil.copyfile(t, os.path.join(self.active_themes_dir, pid + ".yaml"))

    # --------------------------------------------------------------- view ----
    def catalog(self) -> List[dict]:
        """Index packs enriched with this install's state (for the UI)."""
        out = []
        active = set(self.activated())
        ent = set(self.entitled_packs())
        for p in self.packs_meta():
            pid = p.get("id")
            d = dict(p)
            d["entitled"] = (not p.get("paid")) or (pid in ent)
            d["installed"] = self.is_installed(pid)
            d["active"] = pid in active
            out.append(d)
        return out

    def summary(self) -> dict:
        lic = self.load_license()
        return {
            "tier": lic.get("tier", "free"),
            "has_license": bool(lic.get("key")),
            "license_source": lic.get("source", ""),
            "active": self.activated(),
            "active_limit": self.active_limit(),
            "can_activate_more": self.can_activate_more(),
            "store": self.store_info(),
        }
