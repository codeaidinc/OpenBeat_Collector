"""Theme definitions loader (keyword sets for narrowing collection).

Reads themes/*.yaml and returns theme name -> list of multilingual keywords.
Note: this is NOT classification (closed side, section 4.4); it is a simple
keyword search to "narrow collection to a specific theme".
"""
from __future__ import annotations

import os
import glob
from typing import Dict, List

try:
    import yaml
    _HAVE_YAML = True
except Exception:
    _HAVE_YAML = False


def _read(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if _HAVE_YAML:
        return yaml.safe_load(text) or {}
    return _mini(text)


def _mini(text: str) -> dict:
    """Minimal parser for when PyYAML is absent (only name: and a keywords: string list)."""
    out: Dict = {"keywords": []}
    in_kw = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        s = line.strip()
        if s.startswith("keywords:"):
            in_kw = True
            continue
        if in_kw and s.startswith("- "):
            v = s[2:].strip().strip('"').strip("'")
            if v:
                out["keywords"].append(v)
            continue
        if ":" in s and not s.startswith("- "):
            in_kw = False
            k, v = s.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_themes(themes_dir: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for path in sorted(glob.glob(os.path.join(themes_dir, "*.yaml")) +
                       glob.glob(os.path.join(themes_dir, "*.yml"))):
        data = _read(path)
        name = data.get("id") or os.path.splitext(os.path.basename(path))[0]
        kws = data.get("keywords") or []
        out[name] = [str(k) for k in kws if str(k).strip()]
    return out


def theme_keywords(themes_dir: str, name: str) -> List[str]:
    return load_themes(themes_dir).get(name, [])
