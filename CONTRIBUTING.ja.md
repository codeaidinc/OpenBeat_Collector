# コントリビューション・ガイド（情報源の追加・修正）

[English](CONTRIBUTING.md) · **日本語**

OpenBeat Collector の**情報源レジストリはコミュニティ資産**です。誰でも自国・自テーマの情報源を追加できます。コードを書かなくても、YAMLを1ブロック足すだけで貢献できます。

## いちばん簡単な貢献：情報源を1つ足す

1. `sources/` の中から該当国のファイル（例 `japan.yaml`）を開く。新しい国なら `<country>.yaml` を新規作成。
2. `sources:` の下に1ブロック足す：

   ```yaml
   - id: jp-example-org              # 一意のID（国プレフィックス推奨: jp- / uk- / fr-）
     name: 例の支援機関 — お知らせ
     source_type: support_org       # government|ministry|media|sme_media|support_org|statistics
     url: https://example.org/news.rss
     site: https://example.org/news # 人が見るトップページ
     lang: ja
     fetch_method: rss              # rss|html|api|manual|dataset
     update_freq: weekly
     license_note: "利用規約順守・要約＋出典リンクのみ"
     trust: medium                  # high|medium|low
   ```

3. 検証する（ネット不要）：

   ```
   python cli.py validate
   ```

   `OK: no problems` が出ればスキーマOK。

4. 実際に取得できるか確認（ネット必要）：

   ```
   python cli.py verify --source jp-example-org
   ```

   `[ok]` が出れば取得・解析できています。`[fetch_error]`/`[empty]` の場合は表示される「fix」に従ってURLを直すか、`fetch_method` を `html` / `manual` に変更。

5. プルリクエストを送る（変更したYAMLファイルだけでOK）。

## 受け入れ基準（レビュー時にチェックする点）

- **公開情報のみ**。ログイン必須・有料壁の裏・robots.txtで禁止された先は不可。
- `python cli.py validate` がパスする（必須項目・enum・ID一意性）。
- `license_note` に利用条件を明記（出典明記・要約のみ利用が原則）。
- 取得できない源は `fetch_method: manual`（手動貼付）にしておく。
- 政治的に偏った情報源単独ではなく、公的機関・統計・複数メディアでバランスを取る（中立性）。

## fetch_method の選び方

- `rss` … RSS/Atomフィードがある（最優先・最も安定）。
- `html` … フィードが無く、1ページの本文を抽出したい場合。
- `manual` … robots禁止・有料壁・動的生成で自動取得できない場合（人が要約/引用を貼る）。
- `api` … 公開APIがある場合（現状は html と同じ扱い。専用コネクタはプラグインで拡張予定）。
- `dataset` … 統計・業界団体の CSV / JSON リリース。1行＝1アイテムに変換（`dataset_spec` が必要。README の「dataset」節を参照）。定期巡回では新しい期のリリースだけ取り込まれます。

## 自分の源を1から足す（実践例）

担当分野の媒体を新しく足す場合、最初から最後まで：

1. **フィードURLを探す。** サイト上で RSS/フィードのアイコンや「RSS / Feeds」リンクを
   探します。見当たらなければ、よくあるパス（`/rss`、`/feed`、`/index.xml`、`.xml` や
   `.atom` で終わる節URL）を試すか、ページのソースを開いて `application/rss+xml` を検索
   ——その隣の `href` がフィードです。フィードが無くても、1記事/一覧ページに
   `fetch_method: html`、または `manual` が使えます。
2. **1ブロック追加。** 該当国のファイル（例 `japan.yaml`）に、上のテンプレートに沿って
   追記。一意な `id`（例 `jp-myoutlet-news`）を付けます。
3. **定義を検証**（ネット不要）：`python cli.py validate`。`OK: no problems` が出るまで、
   指摘された項目/enum/ID一意性を直します。
4. **実際に取得できるか確認**（ネット必要）：`python cli.py verify --source jp-myoutlet-news`。
   - `[ok]` → OK。手順5へ。
   - `[empty]` / `[parse_error]` → URLがフィードでなくWebページ。正しいフィードURLを探すか、
     `fetch_method` を `html` に変更。
   - `[fetch_error]` → URLが誤り/移転/拒否。ブラウザで再確認し、`url` を更新するか
     `html`/`manual` に切替。
   - `[robots_blocked]` → `fetch_method: manual` にして要約を手で貼る。
   - （ステータス一覧表：[TROUBLESHOOTING.ja.md](TROUBLESHOOTING.ja.md)）
5. **収集して記事が入るか確認：**
   ```
   python cli.py collect --source jp-myoutlet-news
   python cli.py list --country Japan
   ```
   出典URL付きで媒体のアイテムが見えるはずです。Web UIでも、その源が国タブに表示されます。

源を **編集・削除** する時も同じループです。YAMLを変更したら `validate` → `verify` で、
頼る前に「まだ取得できる」ことを必ず確認してください。

## テーマを足す

`themes/<name>.yaml` を作り、`keywords:` に多言語キーワードを並べるだけ。収集時に `--theme <name>`（CLI）またはUIのテーマ選択で絞り込めます（これは分類ではなく単純検索です）。

## 品質ゲート（メンテナ向け）

以下は `.github/workflows/tests.yml` で push / PR ごとに自動実行されます。手元で回す場合：

```
python cli.py validate     # 静的検証（必須・CIで自動化可）
python selftest.py         # パイプライン自己テスト（ネット不要）
python -m pytest tests/    # E2E / シナリオテスト（オフライン・決定的）
python cli.py verify       # 実フィード診断（ネット必要・手元で）
```

`pytest` は開発時のみの依存です：`pip install -r requirements.txt -r requirements-dev.txt`。
E2E テストは Web UI（Flask `test_client`）とコレクタを EN/JA 両方で、ネットワークをスタブ化して
動かします。画面・イベント・API の網羅マップは [tests/SCENARIOS.md](tests/SCENARIOS.md) を参照。

## 行動規範

公開情報の収集という性質上、著作権・各サイトの利用規約・個人情報保護を尊重してください。全文転載はせず、要約＋出典リンクに留めます。
