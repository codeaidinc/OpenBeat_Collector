# Beat Packs（ビート・パック）

各ジャーナリストの**専門領域（ビート）**を、「テーマ＋情報源」を 1 つにまとめた
**パック**として配布・取り込みできるようにする、マーケットプレイスの種（プロトタイプ）です。
形式の詳細は [SCHEMA.md](SCHEMA.md) を参照。

> **オープン/クローズ境界**：パックの収集部分（`theme.yaml`＋`sources.yaml`）はオープン。
> 精緻な分類辞書・分析プロンプト（`tags.yaml`／prompts）はクローズ層（有料）で、ここには通常含めません。

## 同梱パック（パイロット）

| ID | 領域 | 源数 | 信頼ティア |
|---|---|---|---|
| [`science-tech`](science-tech/) | 科学・技術 | 6 | verified |
| [`food-agriculture`](food-agriculture/) | 食品・食料 | 6 | verified |
| [`health-publichealth`](health-publichealth/) | 医療・公衆衛生 | 6 | verified |
| [`climate-energy`](climate-energy/) | 気候・エネルギー | 6 | verified |
| [`crisis-response`](crisis-response/) | 世界危機・緊急対応（**緊急パック** `type: emergency`） | 5 | federation-certified |

> **緊急パック（Rapid-Response Pack）**：世界的危機の発生時に世界同時配布する中核商品。専門家監修・連盟認定（`trust_tier: federation-certified`）で、会員価格／一般価格で販売します。`crisis-response` は WHO・国連OCHA(ReliefWeb)・UN News・GDACS・IFRC の信頼ソースを収録。

各源は調査時点で取得可否を検証していますが、フィードURLは変わることがあります。
取り込み後に `python cli.py verify` で健全性を確認し、必要に応じて `url` を最新に直すか
`fetch_method` を `html`／`manual` に切り替えてください（[CONTRIBUTING.md](../CONTRIBUTING.md)）。

## ストアから取得（実装済み）

アプリの「📦 パックストア」画面から、サーバ配信のカタログ（`packs.json`）を取得して
パックを有効化できます。WordPress 型のオープンコア課金：本体は無料 OSS、一部パックは有料。

- **無料パック**：そのまま有効化。
- **有料パック**：ストアで購入 → 発行されたライセンスキーを画面に貼付して解錠。
- **ティア**：無料＝同時1パック、Pro＝複数パックを同時利用（新聞の各面のように）。
- カタログURLは `OPENBEAT_PACK_INDEX_URL` 環境変数 / 実行ファイル隣の `pack_url.txt` で設定。未設定時は同梱カタログ（`packs.json`）で動作。

サーバ側（カタログ・パックファイル・ライセンス検証API・購入導線）の設置手順は
別冊「OPENBEAT_パックストア_サーバ設置手順.md」を参照。`packs.json` がカタログのひな形、
`licenses.demo.json` はオフライン検証用のデモキー（**本番サーバには公開しない**）。

## 取り込み方（暫定・手動）

ストアを使わず手作業で取り込むこともできます（`pack` サブコマンド実装前の方法）。

1. `packs/<id>/theme.yaml` を `themes/<id>.yaml` にコピー
2. `packs/<id>/sources.yaml` を `sources/<id>.yaml`（または `OPENBEAT_USER_SOURCES_DIR` のオーバーレイ）にコピー
3. `python cli.py validate` → `python cli.py verify` で検証

将来は `python cli.py pack install <path-or-url>` / `pack list` / `pack validate` で自動化します（ROADMAP 参照）。

## 自分のビートのパックを作る

`science-tech/` を雛形にコピーし、`manifest.yaml` の id/領域/作者を書き換え、
`theme.yaml` のキーワードと `sources.yaml` の情報源を自分の専門領域に差し替えるだけです。
コミュニティ投稿は PR で受け付けます（`trust_tier: community`）。編集機関・専門団体が
監修したものは `verified` ティアとして区別します。
