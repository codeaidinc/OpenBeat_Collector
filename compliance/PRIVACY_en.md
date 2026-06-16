> 本書はリーガルチェック前のドラフト（標準構成）です。弁護士確認のうえ確定してください。
>
> (This document is a pre-legal-review draft / standard configuration. Confirm with counsel before finalizing.)

# Privacy Notice (OpenBeat Collector)

Last updated: 2026-06-16

## 1. Nature of the tool

OpenBeat Collector ("the tool") is a collection-only desktop tool that runs on the user's local machine (Python / Flask / SQLite, Apache-2.0). The tool **binds to 127.0.0.1 (localhost) only**, so its web UI is reachable solely from the user's own machine.

- The tool itself **does not transmit collected data to any external server** (not to the operator's servers, not to us, not to third parties).
- No AI processing, authentication, or payment functionality is included in this repository.
- Outbound fetch requests to the information sources (RSS / site pages) occur only to the extent necessary to perform collection.

## 2. Information collected

The tool collects only from **public information sources** that the user has registered or selected (public RSS feeds, public article pages, etc.).
Collected body text **may contain personal data that appears in public articles** (names, affiliations, quotes, contact details, etc.).

Collected data is stored in a **local SQLite database file** on the user's machine.

## 3. Storage and retention

- Data is stored on the local machine only (by default `data/rwt.sqlite` next to the executable).
- **Retention is user-controlled.** The tool does not delete data automatically.

## 4. Deletion (erasure)

In line with GDPR Article 17 and Japan's APPI, the tool provides:

- **Per-source cascade deletion**: deleting a source also deletes the raw item rows (`raw_item`) collected from that source.
- **Delete-all**: a helper to erase all collected data.
  - Web UI: `/data/delete_all` (POST)
  - CLI: `python cli.py purge --yes` (or `--source <id>` for a single source)

## 5. Controller role

For data stored locally, the **operator or user who runs/uses the tool is the data controller**. The provider (CODEAID LLC / 合同会社CODEAID) is responsible for platform safety, explainability, logs, incident response, security and reasonable QA; the user is responsible for source selection, input accuracy, final decisions and obtaining professional advice.

## 6. Disclosure and international transfer

Because the tool does not transmit data externally, the tool by itself performs no third-party disclosure or international transfer. If the user exports or otherwise removes collected data, the user is responsible for complying with applicable law. The export JSON includes a personal-data caution (`privacy_note`).

## 7. Contact

- Provider: CODEAID LLC (合同会社CODEAID)
- Representative: 【___】
- Address: 【___】
- Contact (email): 【___】
