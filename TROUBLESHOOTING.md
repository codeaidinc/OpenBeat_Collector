# Troubleshooting & FAQ

**English** · [日本語](TROUBLESHOOTING.ja.md)

A practical guide for when collection fails, returns nothing, or returns messy
text. Most problems are a stale or moved feed URL, a site that blocks bots, or
the app needing a restart — all fixable in a minute.

> First step for almost any collection problem: run the health check.
> ```
> python cli.py verify              # all sources
> python cli.py verify --source <id>   # just one
> ```
> It connects to each feed, prints a status, and writes `verify_report.txt`.

---

## Reading the `verify` status

| status | meaning | what to do |
|---|---|---|
| `ok` | fetched and parsed fine | nothing — it works |
| `empty` | connected, but 0 items/rows | the URL responds but isn't a live feed anymore; find the current RSS URL, or switch to `html` |
| `robots_blocked` | robots.txt disallows fetching | switch the source to `fetch_method: manual` (paste by hand), or find another feed |
| `fetch_error` | could not connect (404, timeout, DNS, 403) | the feed URL moved or is down — open the site, find the new RSS URL, or switch to `html`/`manual` |
| `parse_error` | response isn't valid RSS/Atom (often an HTML page) | you pointed at a web page, not a feed — use the real feed URL, or set `fetch_method: html` |
| `manual` | a manual-paste source (not auto-fetched) | normal — add items via the "paste by hand" box |

---

## Common problems

| symptom | likely cause | fix |
|---|---|---|
| **Nothing is collected (0 new)** | everything is already stored (deduplicated), or a theme filter is hiding it | this is normal on re-runs; remove the theme filter to see all, or check a different country tab |
| **A source shows `fetch_error`** | the feed URL changed or the site is down | run `verify`, open the site, update `url` in `sources/*.yaml` to the current RSS, or switch to `html`/`manual` |
| **A source shows `empty` / `parse_error`** | the URL is a normal web page, not a feed | find the page's RSS link (see the walkthrough in `CONTRIBUTING.md`), or set `fetch_method: html` to extract the page body |
| **A source is `robots_blocked`** | the site disallows bots in robots.txt | set `fetch_method: manual` and paste a summary/quote by hand (within fair use) |
| **"Fetch full article text" still shows only the summary** | the article page blocks bots or is rendered by JavaScript, so the body could not be fetched | this is the safe fallback; the reason is shown in the CLI output and in the web UI under "Fetch notes". Installing `trafilatura` (`pip install trafilatura`) improves extraction |
| **The body text is full of cookie-banner / menu text** | the page has no clean article container, so extraction grabbed boilerplate | use the summary instead of `--full` for that source, or switch it to `manual`; extraction quality varies by site |
| **The app opens an old screen / your edits don't show** | an older `python app.py` (or an installed copy) is still holding port 5000, or Flask isn't auto-reloading | stop the old process, then restart from source; for live reload during editing run with `OPENBEAT_DEBUG=1` |
| **"Port 5000 is already in use"** | another process (or a previous run) holds the port | close the old window, or set a different port: `OPENBEAT_PORT=5050 python app.py` |
| **Theme filter returns nothing** | the keywords don't match the collected articles' language/wording | themes are a simple text search; edit `themes/<name>.yaml` to add keywords (include the source languages, e.g. Japanese/French) |
| **The UI is in English and I want Japanese** | language is controlled by an environment variable | set `OPENBEAT_LANG=ja` before launching (PowerShell: `$env:OPENBEAT_LANG="ja"`; Mac/Linux: `export OPENBEAT_LANG=ja`) |
| **macOS: "cannot verify the developer / free of malware"** | the app is unsigned (notarization is planned) | right-click the app → **Open**, or System Settings → Privacy & Security → **Open anyway**; or `xattr -dr com.apple.quarantine <app>` |
| **Windows SmartScreen warning** | the installer is unsigned | click **More info → Run anyway** (code signing is planned) |
| **Want to start over with a clean database** | old/test items are cluttering the list | stop the app and delete `data/rwt.sqlite`, then collect again |

---

## FAQ

**Does it use my data, or send anything to a cloud AI?**
No. The collector runs entirely on your computer. It only fetches public
RSS/HTML/CSV and stores them in a local SQLite file. Nothing is sent to any AI
service, and no account or API key is required. (AI-based classification and
analysis are a separate, paid closed layer that is not part of this tool.)

**Where is my collected data stored?**
In a local SQLite file, `data/rwt.sqlite`, next to the app. Exports are written
to `exports/` (and the JSON you save via "Export raw corpus JSON").

**I edited a source URL — how do I confirm it works?**
Run `python cli.py verify --source <id>`. `ok` means it fetches and parses; for
`fetch_error`/`empty`/`parse_error`, follow the table above. There is a full
worked example in `CONTRIBUTING.md` ("Add your own source, step by step").

**Why is some text only a summary, not the full article?**
By default the collector stores the feed's headline + summary (lightweight and
polite). Turn on "Fetch full article text" (or `--full`) to fetch the article
body where the site allows it; bot-blocked or JavaScript-rendered pages fall
back to the summary.

**How do I keep collecting automatically?**
Use `run_scheduled.py` with cron (Linux/macOS) or Task Scheduler (Windows). See
"Scheduled crawling" in `README.md`.

**Can I add my own country, outlet or topic?**
Yes — edit `sources/*.yaml` (sources) or `themes/*.yaml` (topics). No code
needed. See the step-by-step walkthrough in `CONTRIBUTING.md`.

**Is collecting this information legal?**
The tool collects only public information, respects robots.txt and each site's
terms, attaches a source link to every item, and stores summaries — not
full-text reproductions. Respecting each site's terms of use remains the user's
responsibility; the intended use is summary/quotation with attribution.

**It still doesn't work / I found a bug.**
Open an issue on GitHub with the `verify_report.txt` output and the exact
command or screen, and we'll help fix the source or the tool.
