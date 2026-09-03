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

AuthZest は、FastAPI プロジェクト向けのオープンソースなソースコード認識型認可セキュリティ
テストツールです。リポジトリ構造とルート宣言を解析し、将来の決定論的ルールおよび任意の AI
解析で利用できる根拠を生成します。

> [!IMPORTANT]
> AuthZest は開発初期段階です。バージョン `0.1.0-alpha.1` は実行可能なプロジェクトのひな型であり、
> 完成した脆弱性スキャナーではありません。認可状態の分類、セキュリティ finding、能動的な
> テスト、Codex を利用した解析は今後実装する予定です。

## 現在利用できる機能

- 一般的な FastAPI ルートデコレーターの Python AST による検出
- Typer CLI コマンド: `scan`、`doctor`、`ui`
- JSON および人が読みやすい形式のスキャン概要
- FastAPI のヘルスチェックおよびリポジトリスキャン endpoint
- localhost で動作する任意の React/Vite ダッシュボード
- PyInstaller による単一実行ファイルのパッケージング
- 分離された `analyzer`、`parser`、`runner`、`codex` のモジュール境界
- GitHub Actions による Python および frontend CI

Codex adapter は現在無効です。ローカル解析に API key や ChatGPT へのログインは必要ありません。

## pipx でのインストール

AuthZest には Python 3.12 以降が必要です。

```bash
git clone https://github.com/casing1/authzest.git
cd authzest
pipx install .

authzest --version
authzest doctor
authzest scan /path/to/fastapi-project
```

任意のローカルダッシュボードも含める場合は `pipx install '.[ui]'` を使用します。開発中の
checkout を再インストールする場合は `pipx install . --force` を使用します。

## 開発環境

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

cd frontend
npm ci
cd ..
```

## CLI

```bash
authzest --help
authzest --version
authzest doctor
authzest scan <path>
authzest scan <path> --json
authzest ui --workspace <path> --host 127.0.0.1 --port 8000
```

`doctor` は実行環境と、任意で使用する Codex CLI のインストールおよびログイン状態を確認します。
Codex が利用できない場合でも静的解析は動作します。

`scan` は現在、Python ファイル数を数え、`get`、`post`、`put`、`patch`、`delete`、`options`、
`head` の FastAPI 形式のルートデコレーターを検出します。endpoint の認可が安全かどうかは
まだ判断しません。

## 任意機能: ローカルダッシュボード

ダッシュボードはローカルソフトウェアとして動作するため、Web サイトへのデプロイは不要です。
HTTP API がスキャンできるのは、選択した workspace の内部だけです。CLI から直接実行する
スキャンでは、現在のユーザーが読み取れる任意のパスを引き続き指定できます。

```bash
cd frontend
npm ci
npm run build
cd ..

authzest ui --workspace .
```

`http://127.0.0.1:8000` を開いてください。frontend の開発時は `authzest ui --reload` と
`npm run dev` を別々のターミナルで実行します。Vite は `/api` と `/health` をローカルの
FastAPI サーバーへプロキシします。

## ローカル API

- `GET /health` — backend の状態
- `GET /api/health` — frontend 向けの同等 endpoint
- `POST /api/scans` — ローカルサーバー起動時に選択した workspace をスキャンし、パス本文は受け付けない
- `GET /docs` — FastAPI が生成する API ドキュメント

## 検証

```bash
pytest
ruff check .
ruff format --check .

cd frontend
npm run lint
npm run format:check
npm run build
```

## 単一実行ファイル

```bash
source .venv/bin/activate
python -m pip install -e '.[build]'
cd frontend && npm ci && npm run build && cd ..
python -m PyInstaller --clean --noconfirm authzest.spec
./dist/authzest doctor
```

[GitHub Releases ページ](https://github.com/casing1/authzest/releases)からビルド済みの preview 実行ファイルを
取得できます。公開配布向けの notarization や署名はまだないため、OS が未確認の発行元に関する警告を
表示する場合があります。

検証済みの `v*` タグを push すると、macOS、Linux、Windows 向けの実行ファイルと SHA-256
checksum を作成する release workflow が開始されます。[変更履歴](../../CHANGELOG.md)と
[リリースガイド](../RELEASING.md)を参照してください。

## プロジェクト構成

```text
.
├── src/authzest/
│   ├── analyzer/        # リポジトリ単位の解析と集約
│   ├── parser/          # 言語およびフレームワークのソース解析
│   ├── codex/           # 任意の AI adapter interface と実装
│   ├── runner/          # 解析フローの orchestration
│   ├── api/             # FastAPI transport
│   ├── cli.py           # Typer CLI transport
│   └── models.py        # core データモデル
├── tests/
├── frontend/            # 任意の React/Vite/TypeScript UI
├── docs/                # 開発計画とブランド素材
├── scripts/             # release パッケージング用ツール
├── authzest.spec        # PyInstaller 設定
└── .github/workflows/   # CI および release workflow
```

依存関係は CLI、API、UI から core の方向にのみ向かいます。core は Web サーバー、React、特定の
AI provider に依存してはいけません。

## ロードマップとコントリビューション

- [開発計画](../DEVELOPMENT_PLAN.md)
- [公開ロードマップ issue](https://github.com/casing1/authzest/issues/1)
- [コントリビューションとコミットのルール](../../CONTRIBUTING.md)

実装前に issue を作成し、その issue に紐づく短期間のブランチを使用してください。Pull request
はマージ前に Python と frontend のチェックを通過する必要があります。

## ライセンスとセキュリティ

AuthZest は [MIT License](../../LICENSE) の下で公開されています。脆弱性は公開 issue ではなく、
[SECURITY.md](../../SECURITY.md) に記載された非公開の手順で報告してください。
