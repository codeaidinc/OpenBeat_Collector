"""OpenBeat Collector — open side (collection only).

Boundary = right after the Collector. Output = a provenance-tagged raw corpus
JSON. This package handles "collection only" (translation, classification,
analysis, editing and deliverable generation belong to the closed layer).
"""

__version__ = "1.0.2"

# ブランド移行: 旧 RWT_* 環境変数を OPENBEAT_* として後方互換で受理
import os as _os
for _k in list(_os.environ):
    if _k.startswith("RWT_"):
        _os.environ.setdefault("OPENBEAT_" + _k[4:], _os.environ[_k])
