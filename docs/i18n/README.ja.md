<p align="center">
  <img src="../assets/authzest-banner.png" alt="AuthZest — ソースコード認識型の認可テスト" width="100%">
</p>

<p align="center">
  <a href="../../README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <strong>日本語</strong> ·
  <a href="README.ru.md">Русский</a>
</p>

# AuthZest

AuthZest は、FastAPI アプリケーションのソースコードに基づいてアクセス制御を分析するための、
インストール可能な CLI 中心のオープンソースプロジェクトです。現在の Python コアは対象の
アプリケーションを import・実行せずにルートを収集します。認可の評価と任意の AI 支援は今後の開発段階です。

React ダッシュボードは任意のローカルインターフェースです。AuthZest を使うために Web サイトを
デプロイする必要はありません。

> [!IMPORTANT]
> 公開済みの [v0.1.0-alpha.1 preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1) は、
> 最初の実行可能なひな型です。以下に示すルート所有オブジェクトの認識、prefix の合成、ファイル間の
> ルーター解決は `main` に実装されていますが、そのバイナリには**まだリリースされていません**。
> ソースパッケージも引き続き `0.1.0a1` と表示するため、checkout のコミットと
> [変更履歴](../../CHANGELOG.md)で公開済み preview と区別してください。どちらも完成した脆弱性スキャナーではありません。

## 現在のソースが対応する機能

- 静的に生成された `FastAPI`・`APIRouter` 所有オブジェクトと、対応範囲内の import 別名の認識
- 文字列リテラルの HTTP ルート検出と、対応するルーター・登録 prefix の合成
- リポジトリ内の絶対・相対ルーター import の接続と、元ファイル・行番号の保持
- `scan` コマンドによる読みやすい形式または JSON のレポート
- 任意のローカル API・ダッシュボード、環境診断、独立した実行ファイルのパッケージング

対応するデコレーターは `get`、`post`、`put`、`patch`、`delete`、`options`、`head` です。
静的解析の対応範囲は限定されています。動的な宣言や解決できない宣言は省略されるため、空のレポートは
endpoint が存在しないことやアクセス制御が安全であることを示しません。[パーサーの対応範囲](../PARSER_SCOPE.md)を
参照してください。依存関係の収集、認証・認可の分類、セキュリティ finding は未実装です。

`scan` は Codex adapter を無効にしたローカル静的解析を行います。Codex を呼び出さず、API key や
ChatGPT へのログインも不要です。別コマンドの `doctor` は、後述のとおりインストール済み Codex CLI を
呼び出す場合があります。

## ソースから CLI をインストール

最初に Python 3.12 以降と [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html) を用意してください。
開発の基準は Python 3.12 です。次のコマンドは
PyPI のパッケージではなく、現在のリポジトリソースを独立した pipx 環境にインストールします。

```bash
git clone https://github.com/casing1/authzest.git
cd authzest
pipx install --python 3.12 .

authzest --help
authzest scan /path/to/fastapi-project
authzest scan /path/to/fastapi-project --json
```

`/path/to/fastapi-project` を実際のプロジェクトディレクトリに置き換えてください。コマンドが PATH に
見つからない場合は `pipx ensurepath` を実行し、新しいターミナルを開きます。pipx でインストールした
CLI を使うために、プロジェクトの venv を有効にする必要はありません。
例では Python 3.12 を選択します。対応する別のインタープリターを使う場合は、`--python` の後の
`3.12` をそのバージョンまたは実行ファイルのパスに置き換えてください。

このソースインストールを更新するには、未コミットの変更がない `authzest` checkout の `main` で実行します。

```bash
git pull --ff-only
pipx install --force .
```

ビルド済みファイルについては[独立した実行ファイル](#独立した実行ファイル)を参照してください。
`ui` extra は Python backend の依存関係をインストールしますが、通常の wheel・pipx インストールに
ビルド済みダッシュボードのアセットは含めません。任意のダッシュボードには、以下の editable ソース環境を使います。

## 同梱のサンプルを試す

リポジトリルートから、現在のソースのインストールで同梱のローカル fixture をスキャンします。

```bash
authzest scan examples/fastapi_inventory
authzest scan examples/fastapi_inventory --json
```

Python ファイル 4 個と `GET` ルート 3 個(`/health`、`/v1/catalog/items`、`/v2/catalog/items`)が得られます。
これは脆弱性の検出ではなく、静的な探索と同じルーターの繰り返し登録を示すサンプルです。
fixture の構成と期待する根拠は[サンプルガイド](../EXAMPLES.md)を参照してください。

## CLI 診断

```bash
authzest --version
authzest doctor
authzest doctor --json
```

`doctor` は Python の実行環境を確認します。PATH 上に `codex` が見つかると、`codex --version` と
`codex login status` も subprocess として実行します。AI スキャンを開始したり、認証情報ファイルを
直接読んだりはしません。Codex やログインがなくても警告にとどまり、静的スキャンは利用できます。
ログインに成功しても AI 解析は有効になりません。その連携はまだ実装されていません。

## 開発環境

clone したリポジトリのルートで実行してください。例は macOS/Linux shell 向けです。Windows PowerShell
では `py -3.12 -m venv .venv` で venv を作成し、`.venv\Scripts\Activate.ps1` で有効にします。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

editable インストールはこの checkout を使い、`dev` extra には任意の backend 依存関係も含まれます。
Node.js/npm は frontend の作業、ドキュメントの検証、ダッシュボードを含むビルドに必要です。
CI は Node.js 22 を使います。

## 任意のローカルダッシュボード

editable 開発環境を準備した後、リポジトリルートからダッシュボードをビルド・起動します。

```bash
npm --prefix frontend ci
npm --prefix frontend run build
authzest ui --workspace /path/to/fastapi-project --host 127.0.0.1 --port 8000
```

[http://127.0.0.1:8000](http://127.0.0.1:8000) を開いてください。editable backend は checkout 内の
`frontend/dist` を参照します。ビルドがない場合、`/` にはダッシュボードではなく API の案内が表示されます。

ダッシュボードは未実行・空の結果・部分的なスキャンを区別し、parse-error の詳細を表示します。
再スキャンに失敗すると前の結果を消去します。これらは収集状態であり、アクセス制御の判定ではありません。

frontend 開発時は、venv が有効なターミナルで
`authzest ui --workspace /path/to/fastapi-project --reload` を実行し、リポジトリルートの別ターミナルで
`npm --prefix frontend run dev` を実行してください。[http://localhost:5173](http://localhost:5173) を
開くと、Vite が `/api` と `/health` をポート 8000 に転送します。

ローカルサーバーは `GET /health`、`GET /api/health`、`POST /api/scans` と、`/docs` の API ドキュメントを
提供します。スキャン endpoint は必ずサーバー起動時に選択した workspace を使い、リクエスト本文で別の
パスを選ぶことはできません。直接の CLI スキャンはローカルユーザーが指定したパスを使います。
任意のサーバーは loopback アドレスで実行してください。

## 検証

開発 venv を有効にして実行します。

```bash
python -m pytest
ruff check .
ruff format --check .
```

frontend を変更した場合は、以下も実行してください。

```bash
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
```

ドキュメントを変更した場合は、上記の frontend 依存関係をインストールしてからリポジトリルートで実行します。

```bash
node --test scripts/check_docs.test.mjs
node scripts/check_docs.mjs
git ls-files -z '*.md' | xargs -0 frontend/node_modules/.bin/prettier --check
```

検査ツールはドキュメントの実行例を実行せず、翻訳ペア、ローカルリンク、コマンドの一致を確認します。
整形コマンドは Git が追跡する Markdown が対象なので、新しいガイドは最終確認の前に staging に含めてください。

## 独立した実行ファイル

[公開済み preview](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.1) は Linux x64、
macOS arm64、Windows x64 の実行ファイルと SHA-256 manifest を提供します。GUI インストーラーではなく
CLI プログラムであり、`main` の未リリースのパーサー変更は含まれません。まだ署名・notarization を行って
いないため、OS が未確認の発行元について警告する場合があります。

現在のソースをローカルでビルドするには、開発 venv を有効にし、リポジトリルートから実行します。

```bash
python -m pip install -e '.[build]'
npm --prefix frontend ci
npm --prefix frontend run build
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest --help
```

Windows の出力は `dist\authzest.exe` です。PyInstaller は `frontend/dist` が存在する場合に同梱します。
タグの検証、checksum、公開手順については[リリースガイド](../RELEASING.md)を参照してください。

## プロジェクト構成

```text
src/authzest/
├── analyzer/   # リポジトリ解析と集約
├── parser/     # AST ルート・import の解決
├── runner/     # 共通のスキャン実行フロー
├── codex/      # 任意の provider interface; scan adapter は無効
├── cli.py      # Typer コマンドラインインターフェース
├── api/        # 任意の FastAPI 接続層
└── models.py   # コアのレポートデータ
tests/          # 回帰テスト
frontend/       # 任意の React/Vite/TypeScript ダッシュボード
docs/           # ガイド、翻訳、アセット
scripts/        # リリース補助ツール
.github/        # CI/リリース workflow とコントリビューションのテンプレート
```

CLI と任意の API・UI は同じコアを使います。コア解析は Web サーバー、React、特定の AI provider に
依存してはいけません。

## ロードマップとコントリビューション

- [ドキュメント索引](../README.md) — 英語のガイドと韓国語訳
- [開発チェックリスト](../DEVELOPMENT_PLAN.md)と[ロードマップ issue #1](https://github.com/casing1/authzest/issues/1)
- [モデルと評価の方針](../MODEL_STRATEGY.md)
- [コントリビューションとコミットのルール](../../CONTRIBUTING.md)

範囲を定めたタスクを issue で追跡し、短期間のブランチで開発して、意味のあるコミットと検証を含む PR を
作成してください。保護された `main` は Python、frontend、CodeQL のチェックを要求します。自由テーマの
授業の開発計画は 7 週間とし、別途 4–5 週間を試験、遅延、最終準備の余裕として残します。予定順序は以下です。

1. [#32: レポート・根拠の仕様](https://github.com/casing1/authzest/issues/32)
2. [#28: ルートに直接宣言された `Depends`・`Security` の根拠](https://github.com/casing1/authzest/issues/28)
3. [#29: 継承された依存関係の根拠](https://github.com/casing1/authzest/issues/29)
4. [#33: 根拠に結び付いたオフライン AI 評価](https://github.com/casing1/authzest/issues/33)

これらの機能はまだ実装されていません。AI 支援が結果を改善するかは実証済みの利点ではなく、評価すべき
仮説です。コアは provider や特定の GPT モデルがなくても役立つものにします。

## ライセンスとセキュリティ

AuthZest は [MIT License](../../LICENSE) を採用しています。脆弱性は公開 issue ではなく、
[セキュリティポリシー](../../SECURITY.md)に記載された非公開の手順で報告してください。
