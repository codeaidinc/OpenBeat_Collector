"""Source registry.

Reads sources/*.yaml and returns a list of Source objects. A minimal YAML
parser fallback is built in so it still works in environments without PyYAML.
"""
from __future__ import annotations

import os
import glob
from typing import List, Dict

from .schema import Source

try:
    import yaml  # PyYAML
    _HAVE_YAML = True
except Exception:
    _HAVE_YAML = False


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if _HAVE_YAML:
        return yaml.safe_load(text) or {}
    return _mini_yaml(text)


def _mini_yaml(text: str) -> dict:
    """Minimal parser for when PyYAML is not installed.

    It only understands this registry's format (country / language_default /
    a list of sources with key: value). It does not handle general YAML
    (installing PyYAML is recommended).
    """
    root: Dict = {}
    sources: List[Dict] = []
    cur = None
    in_sources = False

    def conv(v: str):
        v = v.strip()
        if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
            return v[1:-1]
        return v

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if indent == 0 and s.endswith(":") and s[:-1] == "sources":
            in_sources = True
            continue
        if indent == 0 and ":" in s and not s.endswith(":"):
            k, v = s.split(":", 1)
            root[k.strip()] = conv(v)
            in_sources = False
            continue
        if in_sources and s.startswith("- "):
            cur = {}
            sources.append(cur)
            s = s[2:].strip()
            if ":" in s:
                k, v = s.split(":", 1)
                cur[k.strip()] = conv(v)
            continue
        if in_sources and cur is not None and ":" in s:
            k, v = s.split(":", 1)
            cur[k.strip()] = conv(v)
    root["sources"] = sources
    return root


def load_registry(sources_dir: str) -> List[Source]:
    """Read every *.yaml in sources_dir and return the list of Sources."""
    out: List[Source] = []
    files = sorted(glob.glob(os.path.join(sources_dir, "*.yaml")) +
                   glob.glob(os.path.join(sources_dir, "*.yml")))
    seen = set()
    for path in files:
        data = _load_yaml(path)
        if not data:
            continue
        country = data.get("country", "Unknown")
        default_lang = data.get("language_default", "")
        for s in data.get("sources", []) or []:
            sid = s.get("id")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            out.append(Source(
                id=sid,
                country=s.get("country") or country,   # a source may override the file's country
                source_type=s.get("source_type", "media"),
                name=s.get("name", sid),
                url=s.get("url", ""),
                site=s.get("site", ""),
                lang=s.get("lang", default_lang),
                fetch_method=s.get("fetch_method", "rss"),
                license_note=s.get("license_note", ""),
                trust=s.get("trust", "medium"),
                update_freq=s.get("update_freq", ""),
                url_rewrite=s.get("url_rewrite", ""),
                dataset_spec=s.get("dataset_spec", ""),
            ))
    return out


def _source_to_block(s: Source) -> dict:
    d = {
        "id": s.id, "country": s.country, "source_type": s.source_type,
        "name": s.name, "url": s.url, "site": s.site, "lang": s.lang,
        "fetch_method": s.fetch_method, "update_freq": s.update_freq,
        "license_note": s.license_note, "trust": s.trust,
    }
    if getattr(s, "url_rewrite", ""):
        d["url_rewrite"] = s.url_rewrite
    if getattr(s, "dataset_spec", ""):
        d["dataset_spec"] = s.dataset_spec
    return d


def _emit_sources_yaml(blocks: List[dict]) -> str:
    """Manual YAML emitter (used only when PyYAML is unavailable)."""
    import json
    lines = ["# OpenBeat Collector - user source registry (edited from the web UI).",
             "# Delete this file to restore the bundled defaults.",
             "sources:"]
    for b in blocks:
        first = True
        for k, v in b.items():
            val = json.dumps(v, ensure_ascii=False)
            lines.append(("  - " if first else "    ") + f"{k}: {val}")
            first = False
    return "\n".join(lines) + "\n"


def save_sources(sources: List[Source], path: str) -> str:
    """Write a list of Source objects to a single writable YAML file.

    This is the user-editable registry the web UI saves to (each source carries
    its own `country`). Deleting the file restores the bundled defaults.
    """
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    blocks = [_source_to_block(s) for s in sources]
    if _HAVE_YAML:
        text = ("# OpenBeat Collector - user source registry (edited from the web UI).\n"
                "# Delete this file to restore the bundled defaults.\n"
                + yaml.safe_dump({"sources": blocks}, allow_unicode=True,
                                 sort_keys=False, default_flow_style=False))
    else:
        text = _emit_sources_yaml(blocks)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return path


def countries(sources: List[Source]) -> List[str]:
    seen, out = set(), []
    for s in sources:
        if s.country not in seen:
            seen.add(s.country)
            out.append(s.country)
    return out


def by_country(sources: List[Source], country: str) -> List[Source]:
    return [s for s in sources if s.country == country]


def by_id(sources: List[Source], sid: str):
    for s in sources:
        if s.id == sid:
            return s
    return None


# --------------------------------------------------------------------------
# Registry validation (offline — for PR intake / quality gate)
# --------------------------------------------------------------------------
VALID_SOURCE_TYPES = {
    "government", "ministry", "media", "sme_media", "support_org", "statistics",
}
VALID_FETCH_METHODS = {"rss", "html", "api", "manual", "dataset"}
VALID_TRUST = {"high", "medium", "low"}


def validate_registry(sources: List[Source]) -> List[str]:
    """Static validation of source definitions. Returns a list of problem
    messages (empty = pass).

    No network needed. Used by CI, PR review, and `cli.py validate`.
    """
    issues: List[str] = []
    seen_ids: Dict[str, int] = {}
    for i, s in enumerate(sources):
        loc = f"[{s.id or '(no id)'}]"
        if not s.id:
            issues.append(f"{loc} id is not set (item #{i+1}).")
        else:
            seen_ids[s.id] = seen_ids.get(s.id, 0) + 1
        if not s.name:
            issues.append(f"{loc} name is not set.")
        if not s.country:
            issues.append(f"{loc} country is not set.")
        if s.source_type not in VALID_SOURCE_TYPES:
            issues.append(f"{loc} invalid source_type: '{s.source_type}'")
        if s.fetch_method not in VALID_FETCH_METHODS:
            issues.append(f"{loc} invalid fetch_method: '{s.fetch_method}'")
        if s.trust not in VALID_TRUST:
            issues.append(f"{loc} invalid trust: '{s.trust}'")
        if s.fetch_method != "manual" and not s.url:
            issues.append(f"{loc} url is not set (required unless manual).")
        if s.fetch_method == "dataset" and not getattr(s, "dataset_spec", ""):
            issues.append(f"{loc} fetch_method=dataset requires dataset_spec.")
        if s.url and not (s.url.startswith("http://") or s.url.startswith("https://")):
            issues.append(f"{loc} invalid url scheme: '{s.url}'")
        if not s.license_note:
            issues.append(f"{loc} license_note is not set (recommended for legal / source attribution).")
    for sid, n in seen_ids.items():
        if n > 1:
            issues.append(f"[{sid}] duplicate id ({n} times). ids must be unique.")
    return issues
