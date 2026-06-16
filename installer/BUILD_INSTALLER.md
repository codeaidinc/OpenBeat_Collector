# Building a single installer (.exe / .app)

**English** · [日本語](BUILD_INSTALLER_ja.md)

Steps to turn the OpenBeat Collector (collector UI) into a **single
executable** that can be distributed without installing Python.

> Important: **build on the same OS you want to distribute to** (PyInstaller
> cannot cross-build). Build the Windows `.exe` on Windows and the macOS `.app`
> on macOS.
> If you just want people to "use it now" without a build, the **one-click
> launchers** (`start_windows.bat` / `start_mac.command`) are enough (recommended).

## 0. Common setup (from the repository root)
```
python -m venv .venv
# Windows: .venv\Scripts\activate    /    macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
```

## 1. Windows (build the .exe)
```
pyinstaller installer\rwt.spec
```
- Output: `dist\OpenBeat_Collector.exe` (single file).
- Distribution: just hand over this exe. Double-clicking launches the UI and opens a browser.
- Data (collection results `data\rwt.sqlite`) is created in a `data\` folder **next to the exe** (put it somewhere writable).
- Note: a SmartScreen warning may appear. For internal distribution, "More info -> Run anyway." For official distribution, signing with a **code-signing certificate** reduces the warnings.

## 2. macOS (build the .app)
```
pyinstaller installer/rwt.spec
```
- Output: `dist/OpenBeat_Collector.app`.
- Distribution: zip the `.app`, or make a `.dmg` (`hdiutil create -volname RWT -srcfolder dist/OpenBeat_Collector.app -ov RWT.dmg`).
- First launch: if Gatekeeper warns, **right-click -> Open** (or "System Settings -> Privacy & Security -> Open Anyway").
- For official distribution, **Apple Developer signing + notarization** lets it open without warnings.

## 3. Icons (optional)
- Windows: provide `installer/app.ico`; in the spec, `icon='installer/app.ico'`.
- macOS: provide `installer/app.icns`; `icon='installer/app.icns'`.

## 4. Troubleshooting
- `feedparser` etc. raise "ModuleNotFoundError": add them to the spec's `hiddenimports`.
- It launches but no screen appears: build with `console=True` and check the printed logs.
- Want high-accuracy main-text extraction: install `trafilatura` from `requirements.txt` and add `'trafilatura'` to the spec's `hiddenimports` (the size will grow).
- Port conflict: change it with the `OPENBEAT_PORT` environment variable (e.g. `set OPENBEAT_PORT=5050`).

## 5. How paths are resolved (reference)
`app.py` resolves paths as follows (works even when built):
- Read-only resources (templates/sources/themes/tests): read from `sys._MEIPASS` (the onefile unpack location).
- Writable DB: `OPENBEAT_DB_PATH` env var, or `data/rwt.sqlite` next to the exe/app if unset.
- Swapping sources or themes: specify external folders via `OPENBEAT_SOURCES_DIR` / `OPENBEAT_THEMES_DIR`.

---

## 6. Automatic build & distribution with GitHub Actions (recommended, zero manual work)

`.github/workflows/build.yml` is included. **Just push a version tag** to
automatically build Windows (exe + Inno Setup installer) and macOS (.app + .dmg)
and **attach them to GitHub Releases**.

```bash
# e.g. cut and push the v1.0.0 tag
git tag v1.0.0
git push origin v1.0.0
```

- Watch the run in GitHub's "Actions" tab. When it finishes, each OS's files appear under "Releases."
- To try without a tag: Actions tab -> "Build installers" -> **Run workflow** (manual run). This produces only Artifacts; no Release is created.
- Icons `installer/app.ico` (Windows) / `installer/app.icns` (macOS) are bundled and applied automatically (replaceable).
- Distributables:
  - `OpenBeat_Collector-Setup-<version>.exe` (Windows installer; Start menu entry, uninstall support)
  - `OpenBeat_Collector-Windows-portable.zip` (standalone exe, no install)
  - `OpenBeat_Collector-macOS.dmg` (Apple Silicon; to ship for Intel Macs, add a job with `build-macos` `runs-on: macos-13`)

### About signing / notarization
- It runs unsigned, but Windows shows SmartScreen and macOS shows Gatekeeper warnings.
- For official distribution, ideally add Windows code-signing and macOS Apple Developer signing + notarization to Actions (store the certificates in repo Secrets).

## 7. Auto-reload during development (optional)

To apply edits instantly, start with the `OPENBEAT_DEBUG=1` environment variable (auto-reload). Don't set it for distribution (production mode).

```powershell
# Windows
$env:OPENBEAT_DEBUG = "1"; python app.py
```
```bash
# macOS / Linux
OPENBEAT_DEBUG=1 python3 app.py
```
