"""Raw corpus JSON output — the handoff artifact at the open<->closed boundary
(the standard format).

Design doc section 7: the boundary is right after the Collector; the raw corpus
JSON is the handoff artifact. The closed layer (translation, classification,
analysis) runs on this JSON as input.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from . import __version__
from .storage import Store


def _match_keywords(item: dict, kws) -> bool:
    if not kws:
        return True
    text = (f"{item.get('title','')} {item.get('summary_excerpt','')} "
            f"{item.get('body_raw','')}").lower()
    return any(k in text for k in kws)


def build_corpus(store: Store, country: Optional[str] = None,
                 limit: int = 100000, keywords: Optional[List[str]] = None) -> dict:
    items = store.items(country=country, limit=limit)
    ks = [k.strip().lower() for k in (keywords or []) if k.strip()]
    if ks:
        items = [it for it in items if _match_keywords(it, ks)]
    return {
        "schema": "rwt.raw_corpus",
        "schema_version": "1.0",
        "generator": f"OpenBeat_Collector/{__version__}",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "boundary_note": "The open side's final output. Translation, classification, analysis, editing and deliverable generation are handled by the closed layer.",
        "privacy_note": (
            "Collected body text is taken from public articles and may contain "
            "personal data (names, affiliations, quotes, etc.). Downstream use, "
            "storage, sharing and publication must respect applicable data "
            "protection law (EU/UK GDPR, Japan APPI) and the source's terms of "
            "use. The recipient is responsible for lawful processing of any "
            "personal data contained herein. / "
            "本文は公開記事に由来し、個人データ（氏名・所属・発言等）を含む場合が"
            "あります。以降の利用・保存・共有・公表にあたっては、適用される"
            "データ保護法（EU/英国GDPR、日本の個人情報保護法）および各情報源の"
            "利用規約を遵守してください。含まれる個人データの適法な取扱い責任は"
            "受領者にあります。"
        ),
        "filter": {"country": country, "keywords": keywords or []},
        "item_count": len(items),
        "items": items,
    }


def export_corpus_json(store: Store, path: str, country: Optional[str] = None,
                       indent: int = 2, keywords: Optional[List[str]] = None) -> str:
    corpus = build_corpus(store, country=country, keywords=keywords)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=indent)
    return path


def corpus_to_json_str(store: Store, country: Optional[str] = None,
                       keywords: Optional[List[str]] = None) -> str:
    return json.dumps(build_corpus(store, country=country, keywords=keywords),
                      ensure_ascii=False, indent=2)
