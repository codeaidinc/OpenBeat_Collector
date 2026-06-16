# 単一インストーラ（.exe / .app）のビルド手順

[English](BUILD_INSTALLER.md) · **日本語**


OpenBeat Collector（収集UI）を、Python のインストール不要で配れる
**単一実行ファイル**にする手順です。

> 重要：**配布したい OS と同じ OS でビルド**してください（PyInstaller はクロスビルド不可）。
> Windows の `.exe` は Windows で、macOS の `.app` は macOS でビルドします。
> 「とりあえず配って使ってもらう」だけなら、ビルド不要の **ワンクリック起動スクリプト**
> （`start_windows.bat` / `start_mac.command`）で十分です（推奨）。

## 0. 共通の準備（リポジトリ直下で）
```
python -m venv .venv
# Windows: .venv\Scripts\activate    /    macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
```

## 1. Windows（.exe を作る）
```
pyinstaller installer\rwt.spec
```
- 生成物：`dist\OpenBeat_Collector.exe`（単一ファイル）。
- 配布：この exe を渡すだけ。ダブルクリックでUIが起動しブラウザが開きます。
- データ（収集結果 `data\rwt.sqlite`）は **exe と同じ場所の `data\` フォルダ**に作られます（書き込み権限のある場所に置いてください）。
- 注意：SmartScreen 警告が出る場合があります。社内配布なら「詳細情報→実行」。正式配布は
  **コードサイニング証明書**で署名すると警告が出にくくなります。

## 2. macOS（.app を作る）
```
pyinstaller installer/rwt.spec
```
- 生成物：`dist/OpenBeat_Collector.app`。
- 配布：`.app` を zip にして渡す、または `.dmg` 化（`hdiutil create -volname RWT -srcfolder dist/OpenBeat_Collector.app -ov RWT.dmg`）。
- 初回起動：Gatekeeper の警告が出たら **右クリック→開く**（または「システム設定→プライバシーとセキュリティ→このまま開く」）。
- 正式配布は **Apple Developer 署名 + 公証（notarization）** を行うと警告なしで開けます。

## 3. アイコン（任意）
- Windows：`installer/app.ico` を用意し、spec の `icon='installer/app.ico'`。
- macOS：`installer/app.icns` を用意し、`icon='installer/app.icns'`。

## 4. うまくいかないとき
- `feedparser` 等が「ModuleNotFoundError」：spec の `hiddenimports` に追加。
- 起動はするが画面が出ない：`console=True` のままビルドし、表示されるログを確認。
- 本文抽出を高精度にしたい：`requirements.txt` の `trafilatura` を入れ、spec の `hiddenimports` に `'trafilatura'` を追加（サイズは増えます）。
- ポート競合：環境変数 `OPENBEAT_PORT` で変更（例：`set OPENBEAT_PORT=5050`）。

## 5. パスの考え方（参考）
`app.py` は次のように解決します（ビルド済みでも動くよう対応済み）：
- 読み取り専用リソース（templates/sources/themes/tests）：`sys._MEIPASS`（onefile 展開先）から読む。
- 書き込みDB：`OPENBEAT_DB_PATH` 環境変数、無ければ exe/app と同じ場所の `data/rwt.sqlite`。
- 情報源やテーマの差し替え：`OPENBEAT_SOURCES_DIR` / `OPENBEAT_THEMES_DIR` で外部フォルダを指定可能。

---

## 6. GitHub Actions で自動ビルド＆配布（推奨・手作業ゼロ）

`.github/workflows/build.yml` を同梱しています。**バージョンタグを push するだけ**で、
Windows（exe＋Inno Setup インストーラ）と macOS（.app＋.dmg）を自動ビルドし、**GitHub Releases に添付**します。

```bash
# 例: v1.0.0 を切ってタグを push
git tag v1.0.0
git push origin v1.0.0
```

- 実行は GitHub の「Actions」タブで確認できます。完了すると「Releases」に各OSのファイルが付きます。
- タグなしで試したいときは Actions タブ →「Build installers」→ **Run workflow**（手動実行）。この場合は成果物（Artifacts）にだけ出力され、Release は作られません。
- アイコンは `installer/app.ico`（Windows）/ `installer/app.icns`（macOS）を同梱済みで、ビルドに自動反映されます（差し替え可）。
- 配布物：
  - `OpenBeat_Collector-Setup-<版>.exe`（Windows インストーラ。スタートメニュー登録・アンインストール対応）
  - `OpenBeat_Collector-Windows-portable.zip`（インストール不要の単体exe）
  - `OpenBeat_Collector-macOS.dmg`（Apple Silicon。Intel Mac 向けに配るなら `build-macos` の `runs-on` を `macos-13` にしたジョブを追加）

### 署名・公証について
- 無署名でも動きますが、Windows は SmartScreen、macOS は Gatekeeper の警告が出ます。
- 正式配布では、Windows はコードサイニング証明書、macOS は Apple Developer の署名＋公証（notarization）を Actions に追加するのが理想です（証明書をリポジトリ Secrets に登録）。

## 7. 開発時の自動リロード（任意）

編集を即反映したいときは環境変数 `OPENBEAT_DEBUG=1` を付けて起動します（自動リロード）。配布時は付けないこと（本番モード）。

```powershell
# Windows
$env:OPENBEAT_DEBUG = "1"; python app.py
```
```bash
# macOS / Linux
OPENBEAT_DEBUG=1 python3 app.py
```
