# OpenBeat Collector（収集ツール・オープン側）

[English](README.md) · **日本語**

> 📍 製品全体のロードマップ・実装状況は [ROADMAP.ja.md](ROADMAP.ja.md) を参照。

> 🛟 うまく動かない（源が失敗する・0件・本文が乱れる）場合は [TROUBLESHOOTING.ja.md](TROUBLESHOOTING.ja.md) を参照。

> ⬇ **すぐ使う（インストール）**：[**最新リリースをダウンロード**](https://github.com/codeaidinc/OpenBeat_Collector/releases/latest) → Windows は `OpenBeat_Collector-Setup-x.y.z.exe`（インストーラ）/ `...-Windows-portable.zip`、macOS は `OpenBeat_Collector-macOS.dmg`。**Python 不要**で、ダウンロードして実行するだけです。

各国で「現地企業が普通に目にするオープン情報」（政府・担当省・一般メディア・中小企業メディア・支援機関・統計）を**定点で収集**し、**来歴付きの生コーパスJSON**にするオープンソース・ツールです。

> **境界**：このリポジトリは設計書の **オープン側（収集まで）** だけを実装します。
> 翻訳・分類・分析・編集ダッシュボード・成果物生成・配信は **クローズ層**（別提供）。
> 受け渡し物 = **生コーパスJSON**（`schema: rwt.raw_corpus` v1.0）。

コードを書けない人（企業・フリーランス・記者・支援機関）が、**国・テーマ・情報源を選んで「収集」ボタンを押すだけ**で使えます。

> **言語**：UI は既定で**英語**です。環境変数 `OPENBEAT_LANG=ja` を設定すると、Web UI と CLI のメッセージが日本語になります。

> **APIキー・クラウドAIは不要です。** この収集ツールは**あなたのPC内だけ**で動作し、公開された RSS/HTML/CSV を取得してローカルの SQLite に保存するだけです。**AIサービスに何かを送信することは一切なく、アカウント・APIキー・サインアップも不要**です。（AIによる分類・分析は、別途提供の有料「クローズ層」の機能で、本ツールには含まれません。だからAPIキー設定のオンボーディングが無いのは仕様どおりです。）

---

## できること（収集まで）

- 情報源レジストリ（国 × 情報源タイプ）から **RSS/Atom・HTML・統計データ(CSV/JSON)・手動貼付** で取り込み
- robots.txt / 利用規約を尊重（取得不可先は手動貼付フォールバック）
- 本文抽出（広告・ナビ除去）、言語判定、**重複排除**（URL/本文ハッシュ）
- すべてに**来歴**（出典URL・取得時刻・情報源・国・言語・ライセンス注記・ハッシュ）を付与
- **テーマ絞り込み** — 収集を特定テーマに絞る単純検索（分類ではない）
- **フィード健全性チェック**（`verify`）と**定義の静的検証**（`validate`）
- **自動巡回**（定期ジョブ）で定点観測を自動化
- **SQLite** にローカル保存、**生コーパスJSON** を書き出し

やらないこと：翻訳・分類・分析・成果物生成・配信（=クローズ層）、全文転載、個人情報、非公開/有料壁の裏。

---

## ダウンロード（ビルド済み・Python不要）

最も簡単なのは、配布済みの実行ファイルを使う方法です。**▶ [Releases ページ（最新版）](https://github.com/codeaidinc/OpenBeat_Collector/releases/latest)** から OS に合うものを入手してください。

- Windows：`OpenBeat_Collector-Setup-<版>.exe`（インストーラ）または `...-Windows-portable.zip`（単体exe）
- macOS：`OpenBeat_Collector-macOS.dmg`

メンテナ向け：`git tag vX.Y.Z && git push origin vX.Y.Z` で GitHub Actions が Win/Mac を自動ビルドし Releases に添付します（`installer/BUILD_INSTALLER.md` 参照）。

### macOS で「開発元を検証できません／マルウェアが含まれていないことを検証できませんでした」と出たら
本アプリは現在 Apple の署名・公証を行っていない無料ビルドのため、初回は macOS にブロックされます（アプリに問題はありません）。次のいずれかで開けます。

1. **設定から許可（推奨）**：`.dmg` 内の `OpenBeat_Collector.app` を「アプリケーション」へドラッグ → 一度ダブルクリック（ブロック表示でOK）→ **アップルメニュー → システム設定 → プライバシーとセキュリティ** → 下部の「"OpenBeat_Collector" はブロックされました」の **「このまま開く（Open Anyway）」** → 認証 → もう一度開く →「開く」。
2. **ターミナルで隔離属性を解除**（最も確実。アプリを移動後）：
   ```bash
   xattr -dr com.apple.quarantine "/Applications/OpenBeat_Collector.app"
   open "/Applications/OpenBeat_Collector.app"
   ```
3. **署名不要の代替**：ソース版のワンクリック起動（`start_mac.command`）はこの警告の影響を受けにくく、すぐ使えます（要 Python 3.10+）。

> 配布先で警告を完全になくすには Apple Developer ID 署名＋公証（notarization）が必要です（将来対応）。

> 開発時に編集を即反映したい場合は `OPENBEAT_DEBUG=1` を付けて起動（自動リロード。配布時は付けない）。

## かんたんセットアップ（Windows / Mac・ダブルクリック起動）

コードを書かない方は、これだけで使い始められます。

1. **Python 3.10 以上**をインストール（[python.org](https://www.python.org/downloads/)。Windows はインストール時に「Add python.exe to PATH」にチェック）。
2. このフォルダの中の起動ファイルを**ダブルクリック**：
   - **Windows**：`start_windows.bat`
   - **Mac**：`start_mac.command`（初回は警告が出たら**右クリック→開く**）
3. 初回だけ自動で実行環境を用意し（専用の `.venv` を作成・必要部品を導入）、**ブラウザが自動で開きます**（http://127.0.0.1:5000）。
4. 画面の **「🧪 サンプルで今すぐ体験（ネット不要）」** を押すと、同梱サンプルが読み込まれ**すぐに結果**が表示されます。
5. 実運用は **国を選ぶ →（任意）テーマ →「▶ 収集する」→「⬇ 生コーパスJSONを書き出し」**。

> 配布用に Python 不要の**単一実行ファイル（.exe / .app）**を作る手順は `installer/BUILD_INSTALLER.md` を参照（各 OS 上でビルド）。

## いちばん簡単な使い方（ノーコード・Web UI／手動起動）

1. Python 3.10+ をインストール
2. このフォルダで依存をインストール：`pip install -r requirements.txt`
3. 起動：`python app.py`（ブラウザが自動で開きます）
4. 画面で **国を選ぶ →（任意）テーマを選ぶ → 情報源にチェック → 「▶ 収集する」**（初めてなら **「🧪 サンプルで今すぐ体験」**）
5. **「⬇ 生コーパスJSONを書き出し」** で境界の受け渡し物（JSON）を保存

> 日本語UIにするには、起動前に環境変数 `OPENBEAT_LANG=ja` を設定してください（PowerShell は `$env:OPENBEAT_LANG="ja"`、Mac/Linux は `export OPENBEAT_LANG=ja`）。

取得できない源（robots禁止・有料壁など）は、右の **「手で貼る」** で本文を要約/引用の範囲で追加できます。

---

## 収集したあと — ジャーナリストとしての使い方

出典付きのコーパスが手元にあります。その先の使い方です。

- **画面で読む。** 国タブとテーマ絞り込みで一覧を絞ります。各行は種別・タイトル・出典・言語・取得時刻を表示。**「本文（全文）/ 要旨」** を展開して読み、出典の **「↗」** リンクで元記事を開けば、内容を確認し出典明記つきで引用できます。
- **1つの話題に集中する。** テーマを選ぶ（または `themes/*.yaml` に自分のキーワードを足す）と、1つのショック——エネルギー価格・サプライチェーンなど——を、全ての源・国にわたって一度に絞り込めます。
- **自分のツールに取り込む。** **「⬇ 生コーパスJSONを書き出し」** で、全アイテムと**来歴**（出典URL・取得時刻・出典名・国・言語・ライセンス注記・本文ハッシュ）を含む1ファイルが得られます。JSON対応ツール・表計算・メモアプリで開き、リード（手がかり）の振り分け、時系列の作成、「どの事実がどこ由来か」の監査証跡づくりに使えます。来歴こそが価値で、各アイテムは元リンクと取得時刻を保持するので、取材は検証可能・引用可能なまま保てます。
- **最新に保つ。** `run_scheduled.py` をスケジュール実行（下記）すれば、新しい公表や記事が自動で入ります。**「記事本文まで取得」** で再収集すると、サイトが許す範囲で本文を取得します。
- **さらに深く（任意）。** 翻訳・分類・国別分析・ドラフト生成は別途の**クローズ層**の役割です。オープン版の仕事は、信頼できる「綺麗で出典が揃ったコーパス」を渡すことです。

> 収集が思うように動かない（源が失敗する・0件・本文が乱れる）場合は **[TROUBLESHOOTING.ja.md](TROUBLESHOOTING.ja.md)** を参照してください（症状→原因→対処の表とFAQ）。

---

## CLI（上級者・自動化向け）

```
python cli.py sources                        # 情報源一覧
python cli.py validate                       # 定義を静的検証（ネット不要・PR品質ゲート）
python cli.py verify --country Japan          # 各フィードに実接続して診断（URL修正の支援）
python cli.py collect --country Japan         # 日本の全源を収集
python cli.py collect --theme example          # テーマに絞って収集（themes/*.yaml）
python cli.py collect --source jp-meti --full # 1源・本文ページまで取得（丁寧/低速）
python cli.py list --country France
python cli.py export corpus.json --country Japan
```

`--full`（または Web UI の「記事本文まで取得」）を付けると、以前に要約だけで
保存した記事も本文を取り直して**その場で上書き更新**します。URL 単位の重複排除は
維持され（記事 1 件＝1 行）、内容が変わらない記事はスキップされるため、再実行は
安全で冪等です。本文を取得できない源（ボット拒否・JavaScript 描画ページ）は要約に
フォールバックし、その理由を CLI 出力と Web UI に表示します。

※ CLI のメッセージは既定で英語です（`OPENBEAT_LANG=ja` の対象は Web UI のみ）。

### 自動巡回（定期ジョブ）

```
python run_scheduled.py --country Japan --theme example
```

- Linux/macOS（毎日6時）: `0 6 * * * cd /path/to/repo && python3 run_scheduled.py >> data/cron.out 2>&1`
- Windows タスクスケジューラ: プログラム `python` / 引数 `run_scheduled.py` / 開始 = リポジトリのフォルダ

巡回ログは `data/collect.log`、出力JSONは `exports/` にタイムスタンプ付きで保存されます。1源が失敗しても全体は止まりません。

---

## 動作確認（ネット不要）

```
python selftest.py                 # パイプライン自己テスト
python -m pytest tests/            # E2E / シナリオテスト（開発依存）
```

`selftest.py` は同梱サンプルで、収集→本文抽出→重複排除→来歴→境界JSON、さらにテーマ絞り込み・健全性チェック・レジストリ検証までを検証します。`OK all tests passed` が出れば正常です。

`pytest` は加えて、Web UI 全体（収集 / 情報源マネージャ / 書き出し / デモ）とコレクタを EN/JA 両方で、ネットワークをスタブ化して（オフライン・決定的に）動かします。先に開発依存を入れてください：`pip install -r requirements.txt -r requirements-dev.txt`。網羅マップは [tests/SCENARIOS.md](tests/SCENARIOS.md)。どちらも CI（`.github/workflows/tests.yml`）で自動実行されます。

---

## 情報源を足す／直す

`sources/*.yaml` を編集するだけ（コミュニティはPRで拡充できます）。書式と手順は `CONTRIBUTING.ja.md` を参照。初期同梱：**UK / France / Japan** の代表源（20源。公的統計・業界団体を含む）。

> 注：同梱URLは代表的な公開フィードですが、各サイトのフィードURLは変わることがあります。
> `python cli.py verify` で取得できない源を見つけ、`url` を最新RSSに直すか `html`/`manual` に切り替えてください。

---

## テーマ（収集の絞り込み）

`themes/*.yaml` に多言語キーワードを定義。初期同梱は `example`（サンプル）。
`--theme example` またはUIのテーマ選択で、キーワードに一致する記事だけを収集します。
※これは分類タグ（クローズ §4.4）ではなく、収集側の単純テキスト検索です。精緻な分類はクローズ層が担います。

---

## 構成

```
OpenBeat_Collector/
├─ app.py            # ノーコードWeb UI（非開発者向け・入口）
├─ cli.py            # CLI（sources/validate/verify/collect/list/export）
├─ run_scheduled.py  # 自動巡回（定期ジョブ）
├─ selftest.py       # オフライン自己テスト
├─ requirements.txt
├─ README.md  CONTRIBUTING.md  ROADMAP.md  TROUBLESHOOTING.md   # ドキュメント（+ *.ja.md ＝ 日本語）
├─ sources/          # 情報源レジストリ（YAML・コミュニティ資産）
│   └─ uk.yaml  france.yaml  japan.yaml
├─ themes/           # テーマ定義（収集の絞り込みキーワード）
│   └─ example.yaml
├─ templates/index.html
├─ tests/sample_feed.xml
├─ data/             # SQLite・ログ（初回実行時に自動生成・gitignore）
├─ exports/          # 巡回ジョブのJSON出力（gitignore）
└─ rwt/              # 収集エンジン（裏側・ユーザーは触れない）
    ├─ schema.py registry.py collector.py storage.py export.py themes.py i18n.py
```

依存（feedparser/trafilatura/httpx/PyYAML/Flask）はどれが欠けても**フォールバックで動作**しますが、`requirements.txt` を入れると本格運用できます。

---

## 法務・倫理

要約＋出典リンクのみ（全文転載しない）／ robots.txt・利用規約を尊重 ／ 全アイテムに出典を付与 ／ 個人情報は扱わない（企業・制度・統計レベル）／ 地政学テーマゆえ中立に徹し、出典の提示に徹する。

## ライセンス

Apache-2.0（採用最大化・能力配布のため）。詳細は `LICENSE`。


## 公的統計・業界団体の継続収集（fetch_method: dataset）

記事だけでなく、**公的統計や業界団体のデータリリース（CSV/JSON）を一次情報として継続取り込み**できます。
1行（=1つの期のリリース）を1アイテムに変換し、来歴付きで生コーパスに流します。
スケジュール実行（`run_scheduled.py`）と重複排除を併用すると、**新しい期のリリースだけ**が自動で増えていきます。

`sources/*.yaml` で `fetch_method: dataset` と `dataset_spec`（`key=value;...` 形式の文字列）を設定します：

```yaml
- id: example-stats-csv
  name: 例：月次指標統計
  source_type: statistics
  url: https://www.example.go.jp/stats/index.csv
  lang: ja
  fetch_method: dataset
  dataset_spec: "format=csv;label=月次指標(前年比);period=month;value=index_yoy;unit=%;delta=mom;max=6"
  license_note: "公的統計・数値は出典に忠実"
  trust: high
```

このアダプタは**縦持ち**のCSV/JSON（1行＝1期。期の列と値の列を持つ）・UTF-8・単一ヘッダ行を前提とします。公的統計の中にはZIP配布・非UTF-8（Shift-JIS等）・横持ち（期が列）のものもあり、その場合は `fetch_method: html` で公表ページを収集してください（同梱の `jp-boj-cgpi`＝日銀CGPIはこの方式）。`dataset` アダプタ自体の動作は同梱デモ（`tests/sample_stats.csv`・UIのサンプルボタン）で端から端まで確認できます。

`dataset_spec` のキー：

| キー | 意味 |
|---|---|
| `format` | `csv` または `json`（既定 `csv`） |
| `label` | 指標名（固定文字列。例「企業物価指数(前年比)」） |
| `period` | 期を表す列／キー名 |
| `value` | 値を表す列／キー名（必須） |
| `unit` | 単位（固定文字列。例「%」）任意 |
| `delta` | 前期比などの列／キー名（任意） |
| `max` | 取り込む最新行数（既定 6） |
| `records` | JSON時、配列までのドットパス（任意。既定はルートが配列） |
| `template` | 文テンプレ（`{label}{period}{value}{unit}{delta}`）任意 |

期ごとに一意な出典URL（例 `...index.csv#2026-06`）が付き、トレーサビリティと重複排除に使われます。数値は出典データに忠実です。`python cli.py verify --source <id>` でエンドポイントと解析を確認できます。
