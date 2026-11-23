<p align="center">
  <img src="../../assets/authzest-banner.png" alt="AuthZest — ソースコードに基づく認可テスト" width="100%">
</p>

<p align="center">
  <a href="../../../README.md">English</a> ·
  <a href="../ko/README.md">한국어</a> ·
  <strong>日本語</strong> ·
  <a href="../ru/README.md">Русский</a>
</p>

# AuthZest

AuthZest は、Python CLI とローカル Web ダッシュボードを備えた、FastAPI の認可テスト用
オープンソースプロジェクトです。ソースの宣言をオフラインで調べるほか、管理対象である
所有者のアーカイブ済みノートのシナリオについて、Codex に防御的な回帰テストと修正を提案させます。
非公開コピーの検査・変更・復元は、各段階を確認してから進めます。

**この README は 0.1.0 ソースの対応範囲を説明しています。** パッケージのバージョンは `0.1.0` です。
パッケージ情報だけでは公開済みかどうかを判断できません。利用可能なタグ・ファイル・チェックサムは
[GitHub Releases](https://github.com/casing1/authzest/releases)を確認してください。2026-11-05 KST に公開された
[v0.1.0-alpha.4](https://github.com/casing1/authzest/releases/tag/v0.1.0-alpha.4) は、現在の GUI と、
新しく生成したコードによる所有者読み取り修正フローが追加される前の版です。
[0.1.0 の案内](../../releases/0.1.0.md) · [最終準備状況](../../releases/0.1.0-READINESS.md) · [変更履歴](../../../CHANGELOG.md)

## できること

| 機能                           | 現在のソースの動作                                                                                                                                                                                                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ソースの静的スキャン           | 対象アプリを import・実行せず、対応する FastAPI/router の宣言・プレフィックス・依存関係を検出します。ソース位置、診断、部分解析の状態を確認できます。                                                                    |
| AI の提案                      | 同梱の正確なソースとポリシーをプレビューしてから、既存の Codex アダプターを通じて、新しい防御的テストと、アプリファイル一つの利用可否ルールの修正を依頼します。変更なし・不明も有効な結果です。                          |
| 段階ごとに確認するコピーフロー | runtime・共有・コピー・before・diff・適用・after・復元をそれぞれ確認します。生成した回帰テストと管理対象の対照検査 7 件を、レビュー済みのネットワーク無効 Linux guest で実行します。適用先は新しい非公開コピーのみです。 |
| ローカル GUI                   | 同じ所有者読み取りエンジンを使い、現在の確認文を入力して各段階を進めます。生成コード・diff・before/after・復旧状態を確認し、完全な JSON をダウンロードできます。通常起動では静的ルート一覧と保存結果を表示します。       |

AI フローの対象は **管理対象の合成シナリオ一つ**です。静的スキャン用に選択したリポジトリが、
自動的に Codex に送信されたり修正されたりすることはありません。一般リポジトリの修正や任意の
アプリケーションの実行は対応範囲外です。[フローの契約](../../development/GENERATED_REPAIR_CONTRACT.md)

## クイックスタート：ローカルダッシュボード

現在のダッシュボードには editable ソース checkout を使います。以下は macOS または Linux 向けで、
Python 3.12 と、Node.js 22.x 系の 22.13 以降または Node.js 24、および npm が必要です。

```bash
git clone https://github.com/casing1/authzest.git
cd authzest
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[ui]'
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/authzest scan examples/fastapi_inventory
.venv/bin/authzest ui --workspace examples/fastapi_inventory
```

[ローカルダッシュボード](http://127.0.0.1:8000)を開きます。この起動は読み取り専用です。
例の Python ファイル 4 個と GET 登録 3 件を調べるか、保存したフローの JSON を選択します。
Web サイトのデプロイは不要です。コマンドは clone したディレクトリから実行してください。
`.venv` と `frontend` はその中にあります。Ctrl-C でサーバーを停止します。
フロントエンドのソースを変更した後は再ビルドしてください。

## GUI で AI による修正を実行する

このモードには、POSIX の non-frozen ソースインストール、既存の Codex ChatGPT ログイン、
信頼できる Codex CLI `0.153.0`、レビュー済みの owner-read Docker ランタイム設定とイメージが必要です。
アダプターは CLI のバージョンを固定して確認します。起動前に
[ランタイムの準備](../../development/GENERATED_REPAIR_CONTRACT.md#running-the-approved-copy-workflow)を
行ってください。以下の設定パスは、非公開の絶対パスに置き換えるための例です。

```bash
.venv/bin/authzest ui --workspace examples/fastapi_inventory --ai-runtime-config /ABSOLUTE/PRIVATE/runtime.json
```

1. ターミナルに表示された **非公開 AI ワークスペース URL 全体**を **新しいブラウザータブ**で開きます。
   最初の URL に `authzest-ai` フラグメントを含めてください。ページはこれを URL から除去し、
   接続権限をメモリ内だけに保持します。ページを再読み込みした場合は完全な起動 URL を開き直します。
   サーバーを再起動すると新しい URL が発行されます。
2. AI 修正画面で、必要に応じて既存のログインを確認し、アクセス可能なモデルの正確な識別子を入力します。
   実行の準備を開始すると runtime 計画が表示されます。この操作だけでは共有を承認しません。
3. 現在の完全な計画を確認し、その段階の正確な確認文を入力します。順序は **runtime → share → copy
   → before → diff → apply → after → restore** です。各決定は別々で、一度だけ使え、有効期限があります。
4. 生成した回帰テスト、ソース変更、正確な diff、観測結果、復元状態を確認します。
   ホストの活動欄はフローの段階を示すもので、Codex のトークン配信やアカウントの生ログではありません。
5. 次の実行を開始したりサーバーを終了したりする前に、ブラウザーのダウンロード設定で結果 JSON の
   保存先を確認します。使い慣れた非公開フォルダーを選ぶか、ダウンロード一覧で保存場所を探してください。
   必要な復旧ファイルも保持します。完了・失敗した実行のセッション反復取得は停止し、
   新しい実行が始まると更新を再開します。

管理対象のケースでは、次の比較を想定しています。

| 段階   | 所有者によるアーカイブ済みノートの読み取り | 生成した回帰テスト | 意図したポリシーとの一致 |
| ------ | ------------------------------------------ | ------------------ | ------------------------ |
| Before | HTTP 403、誤った拒否                       | assertion が失敗   | 6/7                      |
| After  | HTTP 200                                   | 合格               | 7/7                      |

これは fixture で意図したデモを示しており、新しいモデル応答の結果を保証するものではありません。
別の期待プロファイルとの一致数は、両段階とも 7/7 になる場合があります。復元と後処理も確認してください。
前のテストが合格していても、復旧が必要な状態は解消されません。適用後にキャンセルすると、変更済みの
非公開コピーが残る場合があり、自動では復元されません。元の checkout のバイト列は、このフローの
書き込み対象に含まれません。

能動モードは数値ループバック `127.0.0.1`、単一プロセス、reload なしで動作します。通常のダッシュボードへの
アクセス、保存 JSON、Vite 開発プロキシからは実行権限を得られません。workspace は静的スキャンのルートだけを
選択します。[GUI ガイド](../../guides/RESULT_VIEWER.md) · [授業デモガイド](../../guides/COURSE_DEMO.md)

## CLI を使う場合

CLI のみを使う場合は Python 3.12 と pipx をインストールし、ソース checkout から実行します。

```bash
pipx install --python 3.12 .
authzest --help
authzest scan /path/to/fastapi-project
authzest scan /path/to/fastapi-project --json
authzest scan /path/to/fastapi-project --json --strict
```

例のパスを置き換えてください。必要なら `pipx ensurepath` を実行し、ターミナルを開き直します。
静的スキャンには Codex は不要です。部分レポートを返した場合の終了コードは通常 0 ですが、
`--strict` では既知の部分解析を 1 とし、不正な入力では 2 になります。これは実行状態であり、
セキュリティ上の判定ではありません。

クイックスタートで作成した editable の `.venv` から、所有者読み取り CLI でリクエスト全体を
プレビューできます。この操作は共有や実行をしません。

```bash
.venv/bin/authzest owner-read-suggest --model EXPLICIT_MODEL --file-workflow --runtime-config /ABSOLUTE/PRIVATE/runtime.json --preview-only
```

`EXPLICIT_MODEL` と runtime パスをレビュー済みの値に置き換えます。対話型 CLI の実行、
非公開 JSON の保存、既存の登録済みテンプレートツールについては、
[授業ガイド](../../guides/COURSE_DEMO.md)と[コマンドガイド](../../README.md)を参照してください。

## インストール経路と対応範囲

| 経路                                                      | 対応する用途                                                                                                                                             |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| editable ソースと UI extra、フロントエンドのビルド        | 現在のダッシュボード。対応する POSIX システムとレビュー済み runtime では、能動的な owner-read GUI/CLI も利用できます。                                   |
| 通常の wheel またはソースから pipx でインストールした CLI | CLI コマンド。ビルド済みダッシュボードの資産は同梱されないため、GUI には editable checkout を使います。                                                  |
| タグごとの単体実行ファイル                                | 実験的な静的スキャン・オフラインプレビュー。ダッシュボードの有無は選んだタグの案内を確認してください。能動的な owner-read GUI/CLI にはソースが必要です。 |

公開ファイルとチェックサムは [GitHub Releases](https://github.com/casing1/authzest/releases)を参照してください。
実行ファイルには署名も notarization もありません。現在のソースの native ビルドと、記録されたプラットフォーム検査は
[リリースガイド](../../releases/RELEASING.md)に記載しています。過去の検査は後の候補を認証するものではありません。
PyPI や npm への公開は、このリリース手順に含まれていません。

## CLI 診断

```bash
authzest --version
authzest doctor
authzest doctor --json
```

診断は Python と、PATH 上に Codex があればそのバージョン・ログイン状態を確認します。
モデルへのリクエストは開始しません。ログインだけでソース共有やファイル操作の各段階を承認することはできません。
Codex がなくても静的スキャンは利用できます。

## 開発環境

リポジトリのルートで開発環境を作成します。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Windows PowerShell での移植可能な CLI 開発には、`py -3.12 -m venv .venv` と
`.venv\Scripts\Activate.ps1` を使います。能動的な owner-read 実行と操作用 GUI は、POSIX ソース版のみの対応です。

## 検証

開発環境を有効にした状態で実行します。

```bash
python -m pytest
ruff check .
ruff format --check .
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
node --test scripts/check_docs.test.mjs
node scripts/check_docs.mjs
node scripts/format.mjs markdown --check
```

文書の検査は、サンプルを実行せずにリンク・翻訳間のコマンド・シェル構文を確認します。
[ガード付き整形コマンド](../../development/FORMATTING.md)を使ってください。開発ツールのアドバイザリと
候補ごとの判断は [#89](https://github.com/casing1/authzest/issues/89) と
[#171](https://github.com/casing1/authzest/issues/171) で追跡しています。エディター・API で直接整形する経路は
ラッパーの対象外です。

## アーキテクチャと関連文書

Python コア、parser/analyzer、Codex アダプター、runner、表示層を分離しています。
Typer CLI と FastAPI/React UI は共通のコアフローを使います。UI の変更自体が、新たな実行権限や
ソース共有権限を与えるわけではありません。

- [文書目次](../../README.md)：コマンドの契約、セットアップ、参照 API。
- [開発計画](../../development/DEVELOPMENT_PLAN.md)：現在の範囲と過去の実装記録。
- [授業デモガイド](../../guides/COURSE_DEMO.md)：GUI、CLI、保存結果の提示。
- [貢献ガイド](../../../CONTRIBUTING.md)：意味のあるコミット、テスト、ラベル、ブランチルール。
- [セキュリティポリシー](../../../SECURITY.md)：報告方法と対応するレビュー範囲。
- [MIT ライセンス](../../../LICENSE)。

静的な宣言、与えられたポリシー、有限のテスト結果は、それぞれ異なる根拠です。診断と
不明・未実行・拒否・失敗の状態は表示に残ります。AuthZest は一般的な認可の保証、
本番環境の隔離、測定済みのモデル優位性を立証するものではありません。独立比較は
[#84](https://github.com/casing1/authzest/issues/84)、授業用安定版の提供は
[#150](https://github.com/casing1/authzest/issues/150) で追跡しています。
