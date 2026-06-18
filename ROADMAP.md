# OpenBeat Collector — Roadmap

**English** · [日本語](ROADMAP.ja.md)

The roadmap for an open-core product that **collects → classifies → analyzes →
turns into per-country reports → diagnoses individual companies** using public
information about SMEs against geopolitical shocks.

- **Open side (free, OSS) = collection only:** `OpenBeat_Collector`
- **Closed side (paid) = everything after collection:** `rwt-closed`
- **Boundary:** right after the Collector. The handoff artifact is the raw
  corpus JSON (`schema: rwt.raw_corpus` v1.0).

The open side aims to be widely used as a community asset (the source registry
and a robust collector), while the core value (classification, analysis,
cross-country comparison, diagnosis, primary data) is offered on the closed side.

## Design principles (shared across all layers)

- **Source traceability:** every claim/judgment is tied to a source (URL).
  Claims that can't be tied are not emitted (anti-hallucination).
- **Human-in-the-loop:** generated output is always `status: draft`. A human
  edits and approves before publication/distribution.
- **Reproducibility:** sources, tag dictionaries and prompts are managed in the repo.
- **Privacy first:** primary data is anonymized by default; accumulation is
  opt-in; no personal data.
- **Neutrality:** given the geopolitical theme, avoid assertions and focus on
  presenting sources.

## Implementation status

Legend: ✅ implemented (verified by offline self-test) · 🔜 upcoming

### Open side (collection, OSS)

- ✅ Source registry (UK / France / Japan, 20 sources: government, ministries,
  media, support organizations, **official statistics, industry associations**)
- ✅ Collector (RSS/Atom, HTML, **statistics data CSV/JSON (`fetch_method: dataset`)**, manual paste)
- ✅ Main-text extraction, language detection, deduplication, provenance
- ✅ robots.txt respect (timeout, lenient policy) / url_rewrite (source URL normalization)
- ✅ Theme filtering (`themes/*.yaml`, `--theme`)
- ✅ Registry static validation (`validate`) / feed health check (`verify`)
- ✅ Scheduled crawl (`run_scheduled.py`) + deduplication = a **continuous primary-data pipeline**
- ✅ Raw corpus JSON export (the boundary handoff artifact)
- ✅ English-first UI with a Japanese toggle (`OPENBEAT_LANG=ja`)
- 🔜 Multi-country expansion (Germany, Italy, Spain, Southeast Asia, etc.) and community PR operations
- 🔜 Expanding real statistics endpoints (connectors for e-Stat / INSEE / ONS, etc.)
- 🔜 **Beat-pack marketplace** (each journalist's specialty = theme + sources packaged as a shareable, installable "pack"; see below)

### Beat-pack marketplace (a community moat on the open side)

Turn "theme fit" into templates so that **each journalist's beat (specialty) can be shared and installed as a single "pack."**
Collection assets (theme + sources) stay open; fine-grained classification dictionaries and analysis prompts stay in the closed (paid) layer, preserving the open-core boundary.

- **Pack unit:** `manifest.yaml` (id / domain / author / language / version / license / trust notes) + `theme.yaml` (multilingual keywords) + `sources.yaml` (curated sources) + (optional, closed) `tags.yaml` (classification dictionary).
- **Built on existing assets:** extends `themes/*.yaml` and `sources/*.yaml` (community asset), the app's `OPENBEAT_SOURCES_DIR` / `OPENBEAT_THEMES_DIR` / `OPENBEAT_USER_SOURCES_DIR` (user overlay), the in-UI source manager, and the `CONTRIBUTING` PR model.
- **Status:** ✅ pack manifest format (`packs/SCHEMA.md`); ✅ `cli.py pack list / install / activate / deactivate / license / validate` and the in-app Pack Store; 🔜 a community-packs repository for one-click contribution.
- **Trust tiers:** separate "community packs" from "verified packs" (curated by editorial/professional bodies). `verify` powers a pack health badge (detecting feed rot).
- **Examples:** medical/public health, climate/energy, semiconductors/supply chain, research integrity.
- **Network effect:** more journalists → more packs → more value → more journalists. Pairs with the primary-data moat on the closed side.

### Closed side (everything after collection, paid)

- ✅ Ingest (raw corpus JSON) → classification (rules + optional LLM, shared tag schema)
- ✅ Analysis (summary / implications / early signals, **sources required**)
- ✅ Per-country cards + cross-country digest (**international comparison**:
  differences in each country's response to the same shock, deduplicated)
- ✅ Editing dashboard (ingest → edit → approve draft/reviewed/published → timeline)
- ✅ English op-ed draft generation for overseas contributions (sources required)
- ✅ SME training menu generation (cases + questions + actions, sources required)
- ✅ **AI diagnostician** (company-specific business-continuity risk diagnosis,
  evidence-driven scoring, sources required)
- ✅ Distribution tools (email / newsletter HTML / teaser, draft-distribution guard)
- ✅ **Primary-data platform + industry benchmark** (anonymized accumulation of
  diagnostic intake → per-industry aggregation → individual-company comparison)
- 🔜 More LLM providers (local / OSS model support)
- 🔜 Multilingual UI and broader English/other-language report output

### Product & business

- 🔜 SaaS (multi-tenant, billing, permissions)
- 🔜 Partnerships with industry associations / financial institutions (continuous
  primary-data supply, joint reports)
- 🔜 Scaling primary data (accumulating diagnoses/surveys = the deepest moat)

## Milestones (approximate)

| Phase | Goal | Main content |
|---|---|---|
| M0 (done) | End-to-end proof | collect → analyze → per-country report → diagnose → primary data, end to end (offline / real API) |
| M1 | Pilot | Pilot with a few SMEs and 1–2 support organizations. Validate real endpoints. **Implement the pack manifest format and `pack` subcommand** |
| M2 | Commercial beta | Routine operation including editing/distribution. Introduce billing. Multi-country expansion. **Publish the community-packs repo and start curating verified packs** |
| M3 | Scale | SaaS, broader partnerships, scaling primary data (deepening the moat). **Bring the pack marketplace network effect to scale** |

> This roadmap is updated as circumstances change. For how to use each feature,
> see each repository's README.
