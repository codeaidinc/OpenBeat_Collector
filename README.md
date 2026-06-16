# OpenBeat Collector (open side)

**English** · [日本語](README.ja.md)

> 📍 For the full product roadmap and implementation status, see [ROADMAP.md](ROADMAP.md).

> 🛟 Something not working (a source fails, nothing is collected, or the text looks messy)? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

> ⬇ **Use it now (install):** [**Download the latest release**](https://github.com/codeaidinc/OpenBeat_Collector/releases/latest) → on Windows, `OpenBeat_Collector-Setup-x.y.z.exe` (installer) or `...-Windows-portable.zip`; on macOS, `OpenBeat_Collector-macOS.dmg`. **No Python required** — just download and run.

An open-source tool that **routinely collects** the open information local businesses in each country normally see (government, ministries, general media, SME media, support organizations, statistics) and turns it into a **provenance-tagged raw corpus JSON**.

> **Boundary:** this repository implements only the **open side (collection)** of the design.
> Translation, classification, analysis, the editing dashboard, deliverable generation and distribution are the **closed layer** (offered separately).
> The handoff artifact = the **raw corpus JSON** (`schema: rwt.raw_corpus` v1.0).

People who don't write code (businesses, freelancers, journalists, support organizations) can use it by simply **picking a country, theme and sources, and pressing "Collect."**

> **Language:** the UI is English by default. Set the environment variable `OPENBEAT_LANG=ja` to switch the web UI and CLI messages to Japanese.

> **No API key or cloud AI required.** The collector runs entirely on your own computer: it only fetches public RSS/HTML/CSV feeds and stores them in a local SQLite file. **Nothing is ever sent to any AI service, and no account, key or sign-up is needed.** (AI-based classification and analysis belong to the separate, paid closed layer, which is not part of this tool — so there is no API-key onboarding here by design.)

---

## What it does (collection only)

- Ingests from a source registry (country × source type) via **RSS/Atom, HTML, statistics data (CSV/JSON), and manual paste**
- Respects robots.txt and terms of use (unfetchable sources fall back to manual paste)
- Main-text extraction (ads/nav removed), language detection, **deduplication** (URL/body hash)
- Attaches **provenance** to everything (source URL, fetch time, source, country, language, license note, hash)
- **Theme filtering** (e.g. the Middle East) — a simple search that narrows collection to a theme (not classification)
- **Feed health check** (`verify`) and **static definition validation** (`validate`)
- **Scheduled crawling** (periodic job) to automate routine monitoring
- Local storage in **SQLite**, and export of the **raw corpus JSON**

What it does not do: translation, classification, analysis, deliverable generation, distribution (= the closed layer); full-text reproduction; personal data; anything behind a login or paywall.

---

## Download (pre-built, no Python)

The easiest path is to use the pre-built executables. Get the one for your OS from the **▶ [Releases page (latest)](https://github.com/codeaidinc/OpenBeat_Collector/releases/latest)**.

- Windows: `OpenBeat_Collector-Setup-<version>.exe` (installer) or `...-Windows-portable.zip` (standalone exe)
- macOS: `OpenBeat_Collector-macOS.dmg`

For maintainers: `git tag vX.Y.Z && git push origin vX.Y.Z` triggers GitHub Actions to build Windows/macOS automatically and attach them to Releases (see `installer/BUILD_INSTALLER.md`).

### If macOS says "cannot verify the developer / could not verify it is free of malware"

This app is currently a free build without Apple signing/notarization, so macOS blocks it on first launch (nothing is wrong with the app). Open it in one of these ways:

1. **Allow from Settings (recommended):** drag `OpenBeat_Collector.app` from the `.dmg` into Applications → double-click it once (the block dialog is expected) → **Apple menu → System Settings → Privacy & Security** → near the bottom, next to "'OpenBeat_Collector' was blocked," click **Open Anyway** → authenticate → open it again → "Open."
2. **Clear the quarantine attribute in Terminal** (most reliable, after moving the app):
   ```bash
   xattr -dr com.apple.quarantine "/Applications/OpenBeat_Collector.app"
   open "/Applications/OpenBeat_Collector.app"
   ```
3. **Signing-free alternative:** the source-based one-click launcher (`start_mac.command`) is far less affected by this warning and works right away (requires Python 3.10+).

> To remove the warning entirely for distribution, Apple Developer ID signing + notarization is required (planned for the future).

> During development, start with `OPENBEAT_DEBUG=1` to apply edits instantly (auto-reload; don't set it for distribution).

## Easy setup (Windows / Mac, double-click to launch)

If you don't write code, this is all you need to get started.

1. Install **Python 3.10 or later** ([python.org](https://www.python.org/downloads/); on Windows, check "Add python.exe to PATH" during install).
2. **Double-click** the launcher in this folder:
   - **Windows:** `start_windows.bat`
   - **Mac:** `start_mac.command` (on first run, if a warning appears, **right-click → Open**)
3. The first time, it automatically prepares the runtime (creates a dedicated `.venv` and installs the needed parts), and **a browser opens automatically** (http://127.0.0.1:5000).
4. Press **"🧪 Try it now with samples (no internet needed)"** to load the bundled samples and see **results immediately**.
5. For real use: **pick a country → (optional) theme → "▶ Collect" → "⬇ Export raw corpus JSON."**

> To build a Python-free **single executable (.exe / .app)** for distribution, see `installer/BUILD_INSTALLER.md` (build on each OS).

## Simplest way to use it (no-code web UI / manual launch)

1. Install Python 3.10+
2. In this folder, install dependencies: `pip install -r requirements.txt`
3. Launch: `python app.py` (a browser opens automatically)
4. In the UI, **pick a country → (optional) theme → check sources → "▶ Collect"** (first time? try **"🧪 Try it now with samples"**)
5. Save the boundary handoff artifact (JSON) with **"⬇ Export raw corpus JSON."**

For sources you can't fetch (robots-disallowed, paywalled, etc.), use **"paste by hand"** on the right to add body text within the bounds of summary/quotation.

---

## After you collect — using it as a journalist

You have a sourced corpus. Here is what to do with it.

- **Read on screen.** Use the country tabs and the theme filter to narrow the list. Each row shows the type, title, source, language and fetch time. Expand **"Full text" / "Summary"** to read, and click the source **"↗"** link to open the original article so you can verify and quote it with attribution.
- **Focus on one story.** Pick a theme (or add your own keywords in `themes/*.yaml`) to zero in on a single shock — e.g. the Middle East, energy prices, supply chains — across all your sources and countries at once.
- **Take it into your own tools.** **"⬇ Export raw corpus JSON"** saves one file containing every item plus its **provenance** (source URL, fetch time, source name, country, language, license note, content hash). Open it in any JSON-aware tool, a spreadsheet, or your notes app to triage leads, build a timeline, or keep an audit trail of exactly where each fact came from. The provenance is the point: every item keeps its original link and fetch time, so your reporting stays verifiable and citable.
- **Keep it fresh.** Schedule `run_scheduled.py` (see below) so new releases and articles arrive automatically. Re-collect with **"Fetch full article text"** to pull article bodies where the site allows it.
- **Going deeper (optional).** Translation, classification, per-country analysis and draft generation are the separate **closed layer**. The open tool's job is to give you a clean, fully sourced corpus you can trust.

> Collection not behaving as expected (a source fails, returns nothing, or the body looks messy)? See **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — symptom → cause → fix, plus a short FAQ.

---

## CLI (for power users / automation)

```
python cli.py sources                        # list sources
python cli.py validate                       # statically validate definitions (offline, PR quality gate)
python cli.py verify --country Japan          # connect to each feed and diagnose (helps fix URLs)
python cli.py collect --country Japan         # collect all sources for Japan
python cli.py collect --theme middle-east      # collect narrowed to the Middle East theme
python cli.py collect --source jp-meti --full # one source, fetch full article page (polite/slower)
python cli.py list --country France
python cli.py export corpus.json --country Japan
```

With `--full` (or the "Fetch full article text" checkbox in the web UI), items that
were previously stored summary-only are re-fetched and **refreshed in place** with
the full article text. URL-level deduplication is preserved (one row per article),
and items whose content is unchanged are skipped, so re-running is safe and idempotent.
When a source cannot be fully fetched (bot-blocked or JavaScript-rendered pages), it
falls back to the summary and the reason is shown in the CLI output and the web UI.

### Scheduled crawling (periodic job)

```
python run_scheduled.py --country Japan --theme middle-east
```

- Linux/macOS (daily at 6am): `0 6 * * * cd /path/to/repo && python3 run_scheduled.py >> data/cron.out 2>&1`
- Windows Task Scheduler: Program `python` / Arguments `run_scheduled.py` / Start in = the repository folder

Crawl logs go to `data/collect.log`, and output JSON is saved to `exports/` with a timestamp. If one source fails, the whole run does not stop.

---

## Verify it works (no internet)

```
python selftest.py                 # pipeline self-test
python -m pytest tests/            # E2E / scenario tests (dev deps)
```

`selftest.py` uses the bundled samples to verify collect → main-text extraction → deduplication → provenance → boundary JSON, plus theme filtering, the health check and registry validation. If you see `OK all tests passed`, it's working.

The `pytest` suite additionally drives the whole web UI (collect / sources manager / export / demo) and the collector across both languages (en/ja), with the network stubbed out so it stays offline and deterministic. Install the dev dependency first: `pip install -r requirements.txt -r requirements-dev.txt`. The full screen / event / API coverage map is in [tests/SCENARIOS.md](tests/SCENARIOS.md). Both run automatically in CI (`.github/workflows/tests.yml`).

---

## Add / fix sources

Just edit `sources/*.yaml` (the community can extend it via PRs). For the format and steps, see `CONTRIBUTING.md`. Bundled by default: representative sources for **UK / France / Japan** (20 sources, including official statistics and industry associations).

> Note: the bundled URLs are representative public feeds, but each site's feed URL can change.
> Use `python cli.py verify` to find unfetchable sources and update the `url` to the latest RSS, or switch to `html`/`manual`.

---

## Themes (narrowing collection)

Define multilingual keywords in `themes/*.yaml`. Bundled by default: `middle-east`.
With `--theme middle-east` or the theme selector in the UI, only articles matching the keywords are collected.
Note: this is not a classification tag (closed side, section 4.4) but a simple text search on the collection side. Fine-grained classification is handled by the closed layer.

---

## Layout

```
OpenBeat_Collector/
├─ app.py            # no-code web UI (for non-developers; the entry point)
├─ cli.py            # CLI (sources/validate/verify/collect/list/export)
├─ run_scheduled.py  # scheduled crawl (periodic job)
├─ selftest.py       # offline self-test
├─ requirements.txt
├─ README.md  CONTRIBUTING.md  ROADMAP.md  TROUBLESHOOTING.md   # docs (+ *.ja.md = Japanese)
├─ sources/          # source registry (YAML, a community asset)
│   └─ uk.yaml  france.yaml  japan.yaml
├─ themes/           # theme definitions (keywords for narrowing collection)
│   └─ middle-east.yaml
├─ templates/index.html
├─ tests/sample_feed.xml
├─ data/             # SQLite & logs (auto-created on first run, gitignored)
├─ exports/          # JSON output from the crawl job (gitignored)
└─ rwt/              # collection engine (internals; users don't touch this)
    ├─ schema.py registry.py collector.py storage.py export.py themes.py i18n.py
```

Dependencies (feedparser/trafilatura/httpx/PyYAML/Flask) each **fall back** gracefully if missing, but installing `requirements.txt` gives you full operation.

---

## Legal & ethics

Summary + source link only (no full-text reproduction) / respects robots.txt and terms of use / attaches a source to every item / handles no personal data (company, institution and statistics level) / stays neutral given the geopolitical theme and focuses on presenting sources.

## License

Apache-2.0 (to maximize adoption and distribute capability). See `LICENSE` for details.


## Continuous collection of official statistics / industry associations (fetch_method: dataset)

Beyond articles, you can **continuously ingest data releases (CSV/JSON) from official statistics and industry associations as primary data.** Each row (= one period's release) is converted into one item and flows into the raw corpus with provenance. Combined with scheduled runs (`run_scheduled.py`) and deduplication, **only new periods** are added automatically.

In `sources/*.yaml`, set `fetch_method: dataset` and a `dataset_spec` (a `key=value;...` string):

```yaml
- id: example-stats-csv
  name: Example Statistics — Monthly Index
  source_type: statistics
  url: https://www.example.go.jp/stats/index.csv
  lang: en
  fetch_method: dataset
  dataset_spec: "format=csv;label=Monthly Index (YoY);period=month;value=index_yoy;unit=%;delta=mom;max=6"
  license_note: "Official statistics; figures faithful to the source"
  trust: high
```

The adapter expects a **long-format** CSV/JSON (1 row = 1 period, with a period column and a value column), UTF-8, single header row. Some official series are published only as ZIP archives, in a non-UTF-8 encoding, or in wide format (periods as columns); for those, collect the release page with `fetch_method: html` instead (this is what the bundled `jp-boj-cgpi` source does for the Bank of Japan CGPI). The bundled demo (`tests/sample_stats.csv`, loaded via the UI's sample button) shows the `dataset` adapter working end to end.

`dataset_spec` keys:

| key | meaning |
|---|---|
| `format` | `csv` or `json` (default `csv`) |
| `label` | indicator name (fixed string, e.g. `Corporate Goods Price Index (YoY)`) |
| `period` | column/key name for the period |
| `value` | column/key name for the value (required) |
| `unit` | unit (fixed string, e.g. `%`); optional |
| `delta` | column/key name for change vs. previous period; optional |
| `max` | number of latest rows to ingest (default 6) |
| `records` | for JSON, dotted path to the array; optional (default: the root is the array) |
| `template` | sentence template using `{label}{period}{value}{unit}{delta}`; optional |

Each period gets a unique source URL (e.g. `...index.csv#2026-06`) for traceability and deduplication, and the figures stay faithful to the source data. Use `python cli.py verify --source <id>` to confirm the endpoint and parsing.
