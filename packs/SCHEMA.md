# Beat Pack format (`schema: rwt.pack` v1.0)

A **pack** bundles one journalist beat (specialty) into a single, shareable,
installable unit. It extends the existing community assets (`themes/*.yaml`,
`sources/*.yaml`) — nothing here is new conceptually; a pack just groups them
together with metadata so they can be distributed and curated as one thing.

> 日本語は本文中に併記しています。

## Directory layout

```
packs/<id>/
├─ manifest.yaml   # pack metadata (this spec)
├─ theme.yaml      # collection-side theme keywords (same format as themes/*.yaml) — OPEN
├─ sources.yaml    # source registry for this beat (same format as sources/*.yaml) — OPEN
└─ tags.yaml       # OPTIONAL classification dictionary — CLOSED (paid add-on), usually absent here
```

**Open/closed boundary:** the collection part (`theme.yaml` + `sources.yaml`) is
open (Apache-2.0 code, CC-BY source lists). The fine-grained classification
dictionary / analysis prompts (`tags.yaml`, prompts) are the closed (paid) layer
and are normally NOT shipped in the open pack. This preserves the open-core line.

## `manifest.yaml` fields

| Field | Req | Meaning |
|---|---|---|
| `schema` | yes | always `rwt.pack` |
| `spec_version` | yes | manifest spec version (`1.0`) |
| `id` | yes | unique pack id, kebab-case (e.g. `science-tech`) |
| `type` | no | `beat` (default) or `emergency` (rapid-response pack distributed worldwide during a crisis; sold at member / general prices) |
| `name` | yes | English display name |
| `name_ja` | no | Japanese display name |
| `domain` | yes | the beat this pack serves |
| `description` / `description_ja` | yes/no | one-paragraph summary |
| `version` | yes | pack content version (semver, e.g. `1.0.0`) |
| `languages` | yes | list of source/keyword languages (e.g. `[ja, en]`) |
| `license` | yes | license for the source list (e.g. `CC-BY-4.0`) |
| `trust_tier` | yes | `community` (anyone), `verified` (curated by an association), or `federation-certified` (reviewed under the WFSJ federation / expert supervision — the trust tier behind emergency packs) |
| `maintainer` | yes | who keeps this pack healthy (name/handle/email) |
| `created` / `updated` | yes | ISO dates |
| `provides` | yes | which files this pack ships (`theme`, `sources`, optional `tags`) |
| `source_count` | no | number of sources (for the index) |
| `notes` | no | caveats, e.g. feeds to re-verify |

`trust_tier: verified` packs are the curation/monetization point: an organization
(e.g. JASTJ) reviews the source list for quality and neutrality and stands behind
it. `community` packs are user-contributed via PR (same model as `CONTRIBUTING.md`).

## Theme & source file formats

- `theme.yaml` — identical to a bundled theme (e.g. `themes/example.yaml`): `id`, `name`, multilingual `keywords[]`.
- `sources.yaml` — identical to `sources/japan.yaml`: top-level `country` /
  `language_default`, then `sources[]`. Each source may override `country`
  (e.g. `International`) and uses the standard fields:
  `id, name, source_type, url, site, lang, fetch_method, update_freq, license_note, trust`
  (+ optional `url_rewrite`, `dataset_spec`). See `CONTRIBUTING.md`.

`fetch_method`: `rss | html | api | manual | dataset`.
`source_type`: `government | ministry | media | sme_media | support_org | statistics`.

## Installing a pack (`cli.py pack`)

The `pack` subcommand automates installation and activation (offline-capable;
it resolves from a live store URL when configured, otherwise from the bundled
`packs/`):

```
python cli.py pack list                 # catalog + this install's state
python cli.py pack install <id>         # fetch pack content (store or bundled)
python cli.py pack activate <id>        # turn it on (free = 1 active, Pro = many)
python cli.py pack deactivate <id>      # turn it off
python cli.py pack license <KEY>        # unlock paid packs / the Pro tier
python cli.py pack validate             # statically validate pack folders (offline)
python cli.py pack status               # tier + active packs
```

Activating a pack writes its `theme.yaml` / `sources.yaml` into
`data/active_themes/` and `data/active_sources/`, which the collector already
reads — so the pack's sources appear in `cli.py sources` / `collect` right away.
After installing, run `cli.py verify` to check live feed health (URL drift is
expected) and fix any `[fetch_error]` / `[empty]` per the printed hint.

The same flow is available without the command line in the app's Pack Store
screen.

## Health / trust

Feeds rot. Each pack has a `maintainer` and should be re-checked with `verify`
periodically; the marketplace surfaces a freshness/health badge from that.
