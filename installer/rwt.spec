# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — single-executable build of OpenBeat Collector (collector UI).
# Important: build on the OS you want to distribute to (.exe on Windows / .app on macOS). No cross-build.
# Usage (from the repository root):
#   pip install pyinstaller
#   pyinstaller installer/rwt.spec
# Output: dist/OpenBeat_Collector(.exe)  or  dist/OpenBeat_Collector.app
import os, sys

# Resolve the repository root relative to the spec's location (installer/), not cwd.
# SPECPATH is the "directory containing the spec file" that PyInstaller injects at spec time.
ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

# App icon (bundled in installer/). Used if present.
_ICO = os.path.join(SPECPATH, 'app.ico')
_ICNS = os.path.join(SPECPATH, 'app.icns')
_WIN_ICON = _ICO if os.path.exists(_ICO) else None
_MAC_ICON = _ICNS if os.path.exists(_ICNS) else None

# Read-only resources to bundle (app.py reads them from sys._MEIPASS). Absolute paths.
datas = [
    (os.path.join(ROOT, 'templates'), 'templates'),
    (os.path.join(ROOT, 'sources'), 'sources'),
    (os.path.join(ROOT, 'themes'), 'themes'),
    (os.path.join(ROOT, 'tests'), 'tests'),
]
# Optional: bundle support_url.txt (the source-request form URL) if present, so the
# packaged build opens the request form without any environment variable.
_support_txt = os.path.join(ROOT, 'support_url.txt')
if os.path.exists(_support_txt):
    datas.append((_support_txt, '.'))
# Explicitly list packages that may be imported dynamically
hiddenimports = ['feedparser', 'httpx', 'yaml']

# trafilatura has heavy dependencies and is optional (main-text extraction still
# works via the built-in simple fallback without it). Excluded by default to keep
# the first build light and reliable. To bundle high-accuracy extraction, remove
# 'trafilatura' from excludes (you may then need to bundle justext/lxml/babel data).
excludes = ['trafilatura']

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

# Single-file (onefile) configuration
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='OpenBeat_Collector',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    runtime_tmpdir=None,
    console=False,       # distributed build shows no console window (quit via the UI's "Quit tool" button)
    disable_windowed_traceback=False,
    icon=_WIN_ICON,      # Windows: app.ico (None if absent)
)

# On macOS, also produce a .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='OpenBeat_Collector.app',
        icon=_MAC_ICON,
        bundle_identifier='jp.codeaid.openbeatcollector',
        info_plist={'CFBundleDisplayName': 'OpenBeat Collector',
                    'NSHighResolutionCapable': True},
    )
