# Contribution Guide (adding / fixing sources)

**English** · [日本語](CONTRIBUTING.ja.md)

The OpenBeat Collector's **source registry is a community asset.** Anyone
can add sources for their own country or theme. You can contribute without
writing code — just add one YAML block.

## The easiest contribution: add one source

1. Open the file for the relevant country in `sources/` (e.g. `japan.yaml`). For
   a new country, create `<country>.yaml`.
2. Add one block under `sources:`:

   ```yaml
   - id: jp-example-org              # unique ID (a country prefix is recommended: jp- / uk- / fr-)
     name: Example Support Org — News
     source_type: support_org       # government|ministry|media|sme_media|support_org|statistics
     url: https://example.org/news.rss
     site: https://example.org/news # the human-facing top page
     lang: ja
     fetch_method: rss              # rss|html|api|manual|dataset
     update_freq: weekly
     license_note: "Comply with terms of use; summary + source link only"
     trust: medium                  # high|medium|low
   ```

3. Validate (no internet):

   ```
   python cli.py validate
   ```

   If you see `OK: no problems`, the schema is fine.

4. Check that it actually fetches (internet required):

   ```
   python cli.py verify --source jp-example-org
   ```

   If you see `[ok]`, it can be fetched and parsed. For `[fetch_error]`/`[empty]`,
   follow the displayed "fix" to update the URL, or change `fetch_method` to
   `html` / `manual`.

5. Send a pull request (just the YAML file you changed is fine).

## Acceptance criteria (what reviewers check)

- **Public information only.** Login-required, paywalled, or robots.txt-disallowed targets are not allowed.
- `python cli.py validate` passes (required fields, enums, ID uniqueness).
- `license_note` states the usage terms (attribution + summary-only use is the principle).
- Unfetchable sources are set to `fetch_method: manual` (manual paste).
- Balance with public bodies, statistics and multiple media rather than a single politically biased source (neutrality).

## Choosing fetch_method

- `rss` … there is an RSS/Atom feed (preferred, most stable).
- `html` … no feed; you want to extract the body of a single page.
- `manual` … robots-disallowed, paywalled, or dynamically generated so it can't be auto-fetched (a person pastes a summary/quote).
- `api` … there is a public API (currently treated the same as html; dedicated connectors are planned as plugins).
- `dataset` … a statistics/industry CSV or JSON release; each row becomes one item (requires a `dataset_spec`; see the README "dataset" section). On scheduled runs only new periods are ingested.

## Add your own source, step by step (worked example)

Say you want to add a new outlet for your beat. End to end:

1. **Find the feed URL.** On the outlet's site, look for an RSS/feed icon or a
   "RSS / Feeds" link. If there isn't an obvious one, try common paths
   (`/rss`, `/feed`, `/index.xml`, a section URL ending in `.xml` or `.atom`),
   or open the page source and search for `application/rss+xml` — the `href`
   next to it is the feed. No feed at all? You can still use `fetch_method: html`
   on a single article/list page, or `manual`.
2. **Add one block** to the right country file in `sources/` (e.g. `japan.yaml`),
   following the template above. Give it a unique `id` (e.g. `jp-myoutlet-news`).
3. **Validate the definition** (no internet): `python cli.py validate`. Fix any
   reported field/enum/id-uniqueness problems until you see `OK: no problems`.
4. **Check it actually fetches** (internet): `python cli.py verify --source jp-myoutlet-news`.
   - `[ok]` → great, go to step 5.
   - `[empty]` or `[parse_error]` → the URL is a web page, not a feed. Find the
     real feed URL, or change `fetch_method` to `html`.
   - `[fetch_error]` → the URL is wrong/moved/blocked. Re-check it in a browser;
     update `url`, or switch to `html`/`manual`.
   - `[robots_blocked]` → set `fetch_method: manual` and paste summaries by hand.
   - (Full status table: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).)
5. **Collect and confirm articles arrive:**
   ```
   python cli.py collect --source jp-myoutlet-news
   python cli.py list --country Japan
   ```
   You should see your outlet's items with their source URLs. In the web UI, the
   same source now appears under its country tab.

The same loop applies when you **edit or remove** a source: change the YAML, run
`validate`, then `verify` to confirm the source still fetches before you rely on it.

## Add a theme

Create `themes/<name>.yaml` and list multilingual keywords under `keywords:`.
At collection time, narrow with `--theme <name>` (CLI) or the theme selector in
the UI (this is a simple search, not classification).

## Quality gate (for maintainers)

These run automatically on every push / PR via `.github/workflows/tests.yml`.
To run them locally:

```
python cli.py validate     # static validation (required; can be automated in CI)
python selftest.py         # pipeline self-test (no internet)
python -m pytest tests/    # E2E / scenario tests (offline, deterministic)
python cli.py verify       # live feed diagnosis (internet required; run locally)
```

`pytest` is a dev-only dependency: `pip install -r requirements.txt -r requirements-dev.txt`.
The E2E tests drive the web UI (Flask `test_client`) and the collector across both
languages (en/ja) with the network stubbed out; see [tests/SCENARIOS.md](tests/SCENARIOS.md)
for the full screen / event / API coverage map.

## Code of conduct

Given that this collects public information, please respect copyright, each
site's terms of use, and personal-data protection. Do not reproduce full text;
keep to summary + source link.
