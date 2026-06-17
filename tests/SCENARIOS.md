# RWT オープン版 — E2E / シナリオテスト 設計書

> 目的：手動テストで頻発した不具合を**自動で回帰検知**する。画面・イベント・API を
> Flask `test_client` ベースで**オフライン・決定的**に網羅する。既存 `selftest.py`（14項目）の
> 「外部依存なし・決定的・オフライン」方針を踏襲する。
>
> 進め方：①本シナリオ一覧（本書）→ ②テストケース設計（本書の表）→ ③`tests/test_e2e.py` 実装・全緑 → ④git 格納・ドキュメント追記。
> **本書の合意後にテスト実装へ進む。**

---

## 0. テスト基盤の方針（決定的・オフライン）

| 項目 | 方針 |
|---|---|
| 実行 | `python tests/test_e2e.py`（plain assert + print・selftest と同形式）。`selftest.py` 末尾から呼べるフックも用意。pytest は任意（導入する場合のみ dev 依存・CI 別ジョブ） |
| HTTP 駆動 | `app.test_client()` で各ルートを GET/POST、`follow_redirects` と `status_code` / `Location` / flash / 本文 / DB・registry 状態を assert |
| ネット遮断 | (a) ソースURLは `file://`（fixtures の sample_feed.xml / sample_stats.csv＝urllib で取得・ネット不要）。(b) 全文取得・discover・verify の HTTP は `rwt.collector.http_get` / `http_get_bytes` を monkeypatch（決定的な擬似応答を注入）。(c) `discover_feed(fetch=...)` 注入も使用 |
| 隔離 | テストごとに一時 `OPENBEAT_DB_PATH` / `OPENBEAT_USER_SOURCES_DIR` / `OPENBEAT_SOURCES_DIR`（小さな決定的 registry を生成）/ `OPENBEAT_THEMES_DIR`。`app` モジュールは env 設定後に import / `importlib.reload`（DB・sources パスは import 時定数のため） |
| 言語 | `OPENBEAT_LANG` を `en` / `ja` で切替。`strings()` はリクエスト毎に `get_lang()` を読むため reload 不要 |
| /shutdown 対策 | `/shutdown` は 0.6 秒後に `os._exit(0)` する daemon thread を起こす＝**テストプロセスを殺す**。`threading.Thread`（または `os._exit`）を monkeypatch で no-op 化し、200 と本文のみ検証 |
| 副作用の確認 | DB は `Store` で直接開いて件数/本文を assert。overlay は `user_sources/sources.yaml` の存在・内容で assert |
| NUL/マウント癖 | 新規日本語ファイルは Write/heredoc。実行は outputs へクリーンコピー再構築 or 新マウントで直接（[[antigravity-mount-quirks]]） |

決定的フィクスチャ（テスト専用の最小 registry を一時ディレクトリに生成）:
- `t-rss`（fetch_method=rss, url=file://sample_feed.xml, country=Testland, lang=en）
- `t-stats`（dataset, url=file://sample_stats.csv, dataset_spec 既知, country=Testland）
- `t-manual`（manual, country=Testland）
- サンプルテーマ（themes/example.yaml）

---

## 1. 画面A：収集ページ（`GET /` → templates/index.html）

機能：国タブ切替 / テーマ絞り込み / 情報源チェックリスト / 収集 / 手動貼付 / デモ取込 / JSON書出 / サンプル閲覧 / 終了。

| # | イベント / API | 入力・操作 | 期待結果（検証観点） |
|---|---|---|---|
| A1 | `GET /` | 既定 | 200。国タブ（Testland等）、テーマ`select`、情報源チェックリスト（既定 checked）、「保存済み合計」、「✎情報源を管理」リンク描画。既定国=`countries(reg)[0]` |
| A2 | `GET /?country=Testland` | 国指定 | 200。`sel_country` 反映、その国の源だけ表示、タブが `on` |
| A3 | `GET /?theme=example` | テーマ指定 | 200。表示がテーマキーワードで絞り込み、「Showing theme」注記、export リンクに `theme` 付与 |
| A4 | `GET /?full=1` | 全文チェック保持 | 200。「記事本文まで取得」チェックが **checked**（`sel_full` 往復・v1.0.3 修正点） |
| A5 | `POST /collect`（rss, file://） | 既定収集 | 302 → `/?country=...`。flash「収集完了：新規 N / 重複 0」。再 `GET /` で N 件表示。DB 件数=N |
| A6 | `POST /collect` 再実行 | 同条件2回目 | 302。flash「新規 0 / 重複 N」。DB 件数不変（dedup） |
| A7 | `POST /collect` full=on | 全文取得ON（http_get 注入で擬似本文） | 302 で `Location` に `full=1`。要約のみ既存行が**全文でその場更新**（`add_or_update_items(overwrite_by_url=True)`）。flash に「全文更新 M 件」 |
| A8 | `POST /collect` theme=example | テーマ付き収集 | 302。テーマ一致のみ収集（< 全件）。flash にテーマ表記 `（テーマ: example）` |
| A9 | `POST /collect` source_ids 部分選択 | 一部源のみ | 302。選択した源のみ収集 |
| A10 | `POST /manual` 正常 | source_id+url+title+text | 302 → `/?country&theme`。flash「手動アイテムを追加」。DB に1件追加 |
| A11 | `POST /manual` 不備 | text 空 or 不正 source_id | 302。flash「情報源と本文は必須」。追加なし |
| A12 | `POST /manual` 重複 | 同 url+body を2回 | 302。flash「重複のため追加されませんでした」 |
| A13 | `GET /export.json` | country/theme 付き | 200・`application/json`・`Content-Disposition: attachment; filename="rwt_corpus_<country>[_theme].json"`。本文 `schema=rwt.raw_corpus` / `schema_version` / `item_count` / `filter.country` / `filter.keywords`。theme 指定で items 絞り込み |
| A14 | `POST /demo` | デモ取込 | 302。flash「デモデータを読み込みました（N 件）」N>0。items の url が `/sample/<id>`。**再実行で件数が増えない**（`delete_by_source` 入替） |
| A15 | `GET /sample/<id>` | 既存 id / 不明 id | 既存=200・sample.html（黄色バナー・本文）。不明=404「Not found」 |
| A16 | `POST /shutdown` | 終了（thread を no-op 化） | 200。本文に `shutdown_h2`（プロセスは殺さない） |
| A17 | i18n | `OPENBEAT_LANG=ja` で A1/A5 | 日本語UI（「▶ 収集する」等）、flash も日本語（「収集完了…」）。EN モードでは日本語が出ない |

---

## 2. 画面B：情報源マネージャ（`GET /sources` → templates/sources.html）

機能：一覧 / 追加・編集フォーム（方式の日本語ラベル・詳細折りたたみ）/ かんたん追加（自動検出）/ 候補ボタン / 対応依頼（コピー＋依頼ページ）/ 削除 / 接続テスト / 既定に戻す。

| # | イベント / API | 入力・操作 | 期待結果（検証観点） |
|---|---|---|---|
| B1 | `GET /sources` | 既定 | 200。源一覧（件数表示）、追加フォーム、かんたん追加ボックス、方式ラベルがローカライズ、`using_bundled` ピル |
| B2 | `GET /sources?edit=<id>` | 編集 | 200。フォームが当該源で prefill、見出し「情報源を編集」、orig_id hidden |
| B3 | `POST /sources/save`（新規追加） | 必須一式 | 302 → `/sources`。registry **N→N+1**。overlay `user_sources/sources.yaml` 生成。以後 `using_user=True`。flash「保存しました」。per-source `country` 保持 |
| B4 | `POST /sources/save`（編集上書き） | url/trust 変更 | 302。当該源の値が更新。flash 保存 |
| B5 | `POST /sources/save`（id 改名） | orig_id≠新id | 302。旧 id 消滅・新 id 出現（others は orig_id と新 id を除外） |
| B6 | `POST /sources/save`（dup id） | 既存と同じ id | 302 → `?edit=...`。flash「保存できませんでした…ID重複」。**保存されない** |
| B7 | `POST /sources/save`（必須欠落 / license無） | name欠落・非manualでurl欠落・不正type / license_note無し | 必須欠落=エラー flash・**未保存**。license_note 無しは **警告のみで保存可**（`recommended` はブロックしない） |
| B8 | `POST /sources/delete` | id 指定 | 302。overlay から当該源削除。flash「削除しました」 |
| B9 | `POST /sources/reset` | 既定復帰 | 302。overlay ファイル削除→既定 N 件に復帰。flash「既定に戻しました」。`using_user=False` |
| B10 | `POST /sources/verify` | file:// rss / dataset / manual / 取得不可 | 302（**ネット遮断でも 500 で落ちない**）。flash `[status] id: detail`。rss=ok / manual=manual / 取得不可=fetch_error 等 |
| B11 | `POST /sources/verify` 不明 id | 存在しない id | 302。flash「情報源が見つかりません」 |
| B12 | `POST /sources/discover`（rss 検出） | フィードURL（http_get 注入で feed 返却） | 302 → `/sources`。`session['disc']` に rss/url 設定。続く `GET /sources` で方式 rss 選択 & url prefill & flash「見つかりました」 |
| B13 | `POST /sources/discover` 分岐 | html / manual / error | 各 status に応じた flash・候補ボタン（`candidates`）・`request_text`（言語別）・`support_url` 解決。`disc.status!='rss'` 時に対応依頼UI描画 |
| B14 | `POST /sources/discover` URL無 | page_url 空 | 302。flash「先にサイトのURLを貼ってください」 |
| B15 | i18n | `OPENBEAT_LANG=ja/en` で B1/B12/B13 | 一覧・方式ラベル・flash・`request_text` が言語追従 |

---

## 3. 横断・モジュール単位（ルートで検証しづらい分岐を補完）

| # | 対象 | 検証観点 |
|---|---|---|
| C1 | i18n EN/JA | 両画面・全 flash・`req_text` が `OPENBEAT_LANG` に追従。英語モードに日本語が混入しない（回帰防止） |
| C2 | `collector.discover_feed`（fetch 注入） | 分岐：宣言 `<link rel=alternate>` / common パス / html フォールバック / manual / error（完全ブロック）/ 貼付URL自体がフィード（self-feed）/ candidates 返却 |
| C3 | `collector.collect_source` | rss 全文上書き（overwrite）/ dataset（CSV→items・期ごと一意URL・max・dedup）/ keywords 絞り込み |
| C4 | `collector.verify_source` | ok / empty / parse_error / fetch_error / robots_blocked / manual / dataset ok の各 status（monkeypatch / file://） |
| C5 | `registry` | load（源ごと country 上書き）/ `save_sources` 往復（PyYAML 有無両対応）/ `validate_registry`（正常・dup・必須欠落・scheme）/ overlay 実効化 |
| C6 | `storage` | `upsert_item`（added/updated/skipped）/ dedup（hash OR url）/ 全文その場上書き（1行維持・冪等 no-op） |
| C7 | `app._support_url` / `_read_support_template` | 解決順 env > `support_url.txt` > GitHub。`{site}`/`{detail}` の URL エンコード置換 |

---

## 4. 受け入れ基準

- 画面A/B の主要イベント・API を網羅。EN/JA 両方、主要分岐（dup / invalid / discover 各 status / overwrite / reset / support_url 解決）を検証。
- オフライン・決定的・外部依存最小で**全緑**。`selftest.py` の 14 項目も維持。
- `tests/test_e2e.py` を追加し、`python tests/test_e2e.py` 単体で実行可。`selftest.py` からも呼べるフック。
- README / CONTRIBUTING（en/ja）の「Quality gate」に実行コマンドを追記。
- NUL=0・マウント癖を踏まえた手順で検証。コミット/タグはユーザー実機。

> 概算ボリューム：A 17 + B 15 + C 7 ≒ **39 シナリオ**。E2E（ルート）を主、C 群を単体補完として実装する。
