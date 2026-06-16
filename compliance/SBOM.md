> 本書はリーガルチェック前のドラフト（標準構成）です。弁護士確認のうえ確定してください。
>
> (This document is a pre-legal-review draft / standard configuration. Confirm with counsel before finalizing.)

# SBOM — Software Bill of Materials (OpenBeat Collector)

Last updated: 2026-06-16
Component: OpenBeat Collector (open side; collection only). License: Apache-2.0.

This SBOM lists the direct runtime dependencies declared in `requirements.txt`.
Each dependency has a graceful fallback in the code, so the tool still runs (with
reduced capability) if a package is absent. License identifiers are best-effort
(SPDX) and should be confirmed against the installed package versions.

## Runtime dependencies (requirements.txt)

| Package      | Version spec | Purpose                                                                 | License (typical SPDX) |
|--------------|--------------|-------------------------------------------------------------------------|------------------------|
| flask        | >=3.0        | Local web UI server (binds to 127.0.0.1 only)                           | BSD-3-Clause           |
| feedparser   | >=6.0        | RSS/Atom feed parsing (core of collection)                              | BSD-2-Clause           |
| trafilatura  | >=1.6        | Main-text extraction (strips ads/nav); falls back to simple HTML strip  | Apache-2.0             |
| httpx        | >=0.27       | HTTP fetching; falls back to stdlib urllib if absent                    | BSD-3-Clause           |
| PyYAML       | >=6.0        | Source-registry (YAML) loading; falls back to a built-in mini parser    | MIT                    |

## Notes

- Dev/test-only dependencies (see `requirements-dev.txt`, e.g. pytest) are not
  distributed with the runtime and are excluded from this SBOM. Update this table
  if they are ever bundled.
- Transitive dependencies are not enumerated here. For a full, machine-readable
  SBOM (e.g. CycloneDX/SPDX), generate one from the resolved environment, e.g.:
  `pip install cyclonedx-bom && cyclonedx-py environment`.
- License column lists the license most commonly published by each project at the
  time of writing; verify the exact license shipped with the version you install.
- See the repository root `NOTICE` file for attribution.
