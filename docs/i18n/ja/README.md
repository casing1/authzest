<p align="center">
  <img src="../../assets/authzest-banner.png" alt="AuthZest — ソースコード認識型の認可テスト" width="100%">
</p>

<p align="center">
  <a href="../../../README.md">English</a> ·
  <a href="../ko/README.md">한국어</a> ·
  <strong>日本語</strong> ·
  <a href="../ru/README.md">Русский</a>
</p>

# AuthZest

AuthZest は、FastAPI アプリケーションのソースコードに基づいてアクセス制御を分析するための、
インストール可能な CLI 中心のオープンソースプロジェクトです。現在の Python コアは対象の
アプリケーションを import・実行せずにルートを収集します。中核となる製品目標は、Codex によるレビューと
防御的テスト・パッチの提案、ユーザーの承認または拒否、承認された変更のみの適用、別途承認された
隔離環境での検証と変更記録です。全体のフローは未完成です。現在のソースには、明示的に選択する
所有 fixture の Codex 草案・コピー承認段階を追加しています。一つの fixture で実際の草案・適用・復元の確認が1回成功し、静的スキャンは
引き続きオフラインで動作します。

React ダッシュボードは任意のローカルインターフェースです。AuthZest を使うために Web サイトを
デプロイする必要はありません。

> [!IMPORTANT]
> [v0.1.0-alpha.2](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2) は 2026-09-10 に
> Python パッケージ版 `0.1.0a2`、レポートスキーマ `1.2` として公開されました。バイナリには、
> 以下のソース一覧・レポート・直接/継承依存宣言の根拠を扱う機能が含まれます。
> 正確なコミットと検証結果は[変更履歴](../../../CHANGELOG.md)と[リリース記録](../../releases/RELEASING.md)を
> 確認してください。`main` の checkout は、このタグより先に進んでいる場合があります。
> まだアルファ段階のソース分析ツールであり、完成した脆弱性スキャナーや動作する Codex 修正フローではありません。

## 現在のソースが対応する機能

- 静的に生成された `FastAPI`・`APIRouter` 所有オブジェクトと、対応範囲内の import 別名の認識
- 文字列リテラルの HTTP ルート検出と、対応するルーター・登録 prefix の合成
- リポジトリ内の絶対・相対ルーター import の接続と、元ファイル・行番号の保持
- `scan` コマンドによる読みやすい形式または JSON のレポート
- 既存の JSON フィールドを保持し、スキーマ `1.2`、構造化された診断、bounded/partial 状態と、
  元の宣言・app・`include_router` の根拠を伴う区別可能な登録 ID を追加
- ルートに直接宣言された `Depends`・`Security`、ソース位置と既知の scopes を収集。
  通常の依存性注入を認証や認可と判断しない
- 対応する app・router・`include_router` の依存関係宣言を各登録の適用文脈に結び付け、
  ルート直接宣言のリストと元のソース位置を別々に保持
- 任意のローカル API・ダッシュボード、環境診断、独立した実行ファイルのパッケージング
- ソース限定の [Codex fixture コマンド](../../guides/CODEX_FIXTURE.md)：明示的な共有、バージョン固定
  App Server、新しいコピー限定の正確な diff 承認。一つの fixture の実連携確認は成功済み
- コピーのソース設定だけを確認する任意の個別承認付き検査を提供し、ランタイム検証は実行しない

対応するデコレーターは `get`、`post`、`put`、`patch`、`delete`、`options`、`head` です。
静的解析の対応範囲は限定され、未解決のルート宣言は省略される場合があります。
対応するルートで依存関係の根拠が未解決の場合、ルートは診断とともにレポートに残ります。
構造化された診断は一部の未解決ケースとソース/読み取りエラーを扱いますが、すべての未対応パターンを
網羅するものではありません。空のレポートや `bounded` 状態は endpoint の不在やアクセス制御の安全性を
証明しません。[パーサーの対応範囲](../../reference/PARSER_SCOPE.md)と[レポート仕様](../../reference/REPORT_CONTRACT.md)を参照してください。
入れ子の依存関係グラフ、認証・認可の分類とセキュリティ finding は未実装です。
適用文脈の根拠はソース上の文脈であり、実行時の依存関係の順序や保護を保証しません。

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
authzest scan /path/to/fastapi-project --json --strict
```

`/path/to/fastapi-project` を実際のプロジェクトディレクトリに置き換えてください。コマンドが PATH に
見つからない場合は `pipx ensurepath` を実行し、新しいターミナルを開きます。pipx でインストールした
CLI を使うために、プロジェクトの venv を有効にする必要はありません。
例では Python 3.12 を選択します。対応する別のインタープリターを使う場合は、`--python` の後の
`3.12` をそのバージョンまたは実行ファイルのパスに置き換えてください。

既定では部分的な解析でもレポートを返せば終了コードは 0 です。`--strict` を付けると、既知の部分解析では
レポートを出力したうえで 1 を返します。無効なリポジトリ入力には 2 を返します。
これらは解析の実行状態を示すコードであり、セキュリティの判定ではありません。

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
fixture の構成と期待する根拠は[サンプルガイド](../../guides/EXAMPLES.md)を参照してください。

## CLI 診断

```bash
authzest --version
authzest doctor
authzest doctor --json
```

`doctor` は Python の実行環境を確認します。PATH 上に `codex` が見つかると、`codex --version` と
`codex login status` も subprocess として実行します。AI スキャンを開始したり、認証情報ファイルを
直接読んだりはしません。Codex やログインがなくても警告にとどまり、静的スキャンは利用できます。
ログイン成功は AI スキャンやデータ共有への同意を意味しません。別の
[Codex fixture コマンド](../../guides/CODEX_FIXTURE.md) は明示的な共有承認を要求し、所有 fixture のみを扱います。

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

ダッシュボードは未実行・空の結果・部分的なスキャンを区別し、構造化された診断と parse-error の詳細を表示します。
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

[alpha.2 リリース](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.2) は Linux x64、
macOS arm64、Windows x64 の実行ファイルと対応する SHA-256 manifest を提供します。上記のソース分析機能と
レポートスキーマ `1.2` を含みます。GUI インストーラーではなく独立した CLI プログラムであり、
ビルド済みバイナリの実行に Python や Node.js のインストールは不要です。

OS/アーキテクチャに合うファイルと `.sha256` manifest をダウンロードし、実行前に
[チェックサムと実行の手順](../../releases/RELEASING.md#verify-and-recover)に従ってください。
3 プラットフォームの CI ビルドとダウンロード成果物の smoke 検査は成功しましたが、一般ユーザーの機器での
クリーンインストール・アップグレードや、すべての OS バージョンとの互換性は未確認です。署名・公証は
されていないため、OS が未確認の発行元について警告する場合があります。

現在のソースをローカルでビルドするには、開発 venv を有効にし、リポジトリルートから実行します。

```bash
python -m pip install -e '.[build]'
npm --prefix frontend ci
npm --prefix frontend run build
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest --help
```

Windows の出力は `dist\authzest.exe` です。PyInstaller は `frontend/dist` が存在する場合に同梱します。
タグの検証、checksum、公開手順については[リリースガイド](../../releases/RELEASING.md)を参照してください。

## プロジェクト構成

```text
src/authzest/
├── analyzer/   # リポジトリ解析と集約
├── parser/     # AST ルート・import の解決
├── runner/     # 共通のスキャン実行フロー
├── codex/      # オフライン契約と opt-in 所有 fixture adapter; scan はオフライン
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

- [ドキュメント索引](../../README.md) — 英語のガイドと韓国語訳
- [開発チェックリスト](../../development/DEVELOPMENT_PLAN.md)と[ロードマップ issue #1](https://github.com/casing1/authzest/issues/1)
- [モデルと評価の方針](../../development/MODEL_STRATEGY.md)
- [コントリビューションとコミットのルール](../../../CONTRIBUTING.md)

範囲を定めたタスクを issue で追跡し、短期間のブランチで開発して、意味のあるコミットと検証を含む PR を
作成してください。保護された `main` は Python、frontend、CodeQL のチェックを要求します。自由テーマの
授業の開発計画は 7 週間とし、別途 4–5 週間を試験、遅延、最終準備の余裕として残します。
[#32](https://github.com/casing1/authzest/issues/32) のレポート・根拠の基盤と
[#28](https://github.com/casing1/authzest/issues/28)・[#29](https://github.com/casing1/authzest/issues/29) の
ルート直接・継承宣言の根拠は alpha.2 に含まれます。
リリース準備・公開 [#39](https://github.com/casing1/authzest/issues/39) は完了しました。
現在のソースと次の作業は以下のとおりです。

1. ソースに実装済み: [#33: 根拠に結び付いたオフライン AI 契約・mock・評価](https://github.com/casing1/authzest/issues/33)。
2. [#35: Codex 提案・正確な diff の承認・承認済みパッチの適用・隔離検証](https://github.com/casing1/authzest/issues/35)

[オフライン基盤](../../reference/AI_CONTRACT.md) は alpha.2 バイナリに含まれず、#35 の全体フローは未完成です。
#35 の最初の段階である [#46 のオフライン提案・判断契約](../../reference/PROPOSAL_CONTRACT.md) はソースに実装済みです。
diff のプレビューと模擬承認の検査を提供しますが、ファイルへの適用や検証の実行は行いません。
後続の [#48 コピー専用適用デモ](../../guides/FIXTURE_APPLICATION.md) は、新しい POSIX fixture コピーで
明示的な端末承認と競合を確認する復元を提供します。元の checkout は変更せず、実際の AI 呼び出しや
検証は実行しません。alpha.2 バイナリにも含まれません。
後続の [#50 Codex fixture 段階](../../guides/CODEX_FIXTURE.md) は明示的な共有承認後にモデル草案を
一度要求し、適用と復元は別途判断します。`42ff108` で一つの所有 fixture の実際の草案・コピー適用・
復元の確認が1回成功し、元の内容は保持されました。承認文はユーザーの許可に基づき assistant が
入力したもので、独立した人間のレビューではありません。ソース限定で alpha.2 には含まれず、
ランタイム検証と一般リポジトリの AI レビューは未実装です。#52 は適用と復元の間に、別途承認する
既知のハッシュに固定したソースの AST 設定検査を制限付き子プロセスで行う選択肢を追加します。対象ソースを実行せず、
新たな実モデルの証拠や、セキュリティ修正の有効性が検証済みという主張も追加しません。
6 ケース・3 モードの mock 評価はモデル性能ではなく契約を検証します。AI 支援が結果を改善するかは実証済みの利点ではなく、評価すべき
仮説です。コアは provider や特定の GPT モデルがなくても役立つものにします。
最終デモは自ら所有・管理する fixture を対象とし、データ共有・パッチ・実行を別々に許可します。
脆弱性を悪用する PoC の生成、自律的な攻撃フロー、任意のリポジトリの実行は対象外です。

## ライセンスとセキュリティ

AuthZest は [MIT License](../../../LICENSE) を採用しています。脆弱性は公開 issue ではなく、
[セキュリティポリシー](../../../SECURITY.md)に記載された非公開の手順で報告してください。
