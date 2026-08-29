# プロジェクト固有の Claude Code 指示

このファイルは本プロジェクトに固有のルール・コンテキストを Claude Code に伝えるためのものでござる。
全プロジェクト共通のガイドラインは `~/.claude/CLAUDE.md` に記載されており、本ファイルはそれを補完する形で記述するでござる。

## プロジェクト概要

AgentTakt — AI エージェント（Executor）が MCP 経由で送信したタスク実行計画 JSON を、人間がターミナル上の ComfyUI 風ビジュアルノードエディタでレビュー・編集・承認する MCP サーバー兼 TUI ツール。

- MCP サーバー（`agenttakt serve`）と TUI 常駐プロセス（`agenttakt`）の 2 プロセス構成。Unix domain socket（NDJSON）で接続する（詳細は [docs/architecture.md](./docs/architecture.md)）
- 親 issue: [#3](https://github.com/ryoohshima/AgentTakt/issues/3)（M0〜M4 + docs の sub-issue で進捗管理）

## 技術スタック

- 言語: Python 3.10+（開発環境は 3.12）
- TUI: Textual >= 8.2
- MCP: Python MCP SDK v1 FastMCP（`mcp>=1.9,<2` にピン留め。SDK import は `src/agenttakt/server/mcp_server.py` に閉じ込める）
- データモデル: pydantic v2
- パッケージマネージャ: uv（build backend は hatchling、src レイアウト）

## ディレクトリ構成

```
.
├── src/agenttakt/
│   ├── cli.py             # エントリポイント（agenttakt / at）
│   ├── models/            # Plan データモデル・DAG 検証・自動レイアウト
│   ├── bridge/            # socket プロトコル・クライアント・サーバー
│   ├── server/            # MCP サーバー（SDK import はここのみ）
│   └── tui/               # Textual アプリ（screens / widgets / geometry）
├── tests/                 # pytest（モデル・プロトコル・Pilot による TUI テスト）
├── examples/              # デバッグモード用サンプル計画 JSON
├── docs/                  # ユーザー向けドキュメント（dev/ 配下は開発者向け設計資料）
└── tasks/                 # Claude Code 作業記録（todo.md / lessons.md）
```

## 開発コマンド

```sh
# セットアップ
uv sync

# 実行
uv run agenttakt                                  # TUI 常駐起動
uv run agenttakt serve                            # MCP stdio サーバー
uv run agenttakt open examples/sample_plan.json   # デバッグモード（MCP なし）

# テスト
uv run pytest

# TUI 開発（textual devtools）
uv run textual console                            # 別ターミナルでログ閲覧
uv run textual run --dev src/agenttakt/tui/app.py
```

## ドッグフーディング（AgentTakt 自身を使う）

本リポジトリは `.mcp.json` で開発版の AgentTakt（`uv run agenttakt serve`）を MCP サーバーとして登録している。自分の道具は自分で使うこと。

- 3 ステップ以上の作業計画を立てたら、着手前に `show_plan(plan, summary)` でノードグラフとして提示する（プランモードに限らない）
- 不可逆な作業（リリース・スキーマ変更・広範なリファクタ）は `request_approval(plan, summary)` で承認を得てから着手する
- plan JSON の形式は [docs/schema.md](./docs/schema.md) を参照
- TUI が起動していないとツールはエラーを返す。その場合は別ターミナルで `uv run agenttakt` を起動するようユーザーに依頼する（勝手に起動しない）
- 使いにくさ・表示の不備に気づいたら issue に残す（ドッグフーディングは実運用検証を兼ねる）

## このリポジトリ固有の注意事項

- **stdio MCP サーバー内で TUI を起動してはならない**（stdio がプロトコル通信に専有されている）。TUI に触る処理は必ず TUI プロセス側に置く
- エッジ描画は経路計算（`tui/geometry.py`）と文字化（`tui/widgets/edge_layer.py`）を分離したまま保つ（braille 曲線への差し替え口）
- Plan / Node / Edge は `extra="allow"`。Executor 独自フィールドのラウンドトリップを壊さないこと
- socket パスは `AGENTTAKT_SOCKET` → 既定 `{tempdir}/agenttakt-{uid}/takt.sock`。テストでは `tmp_path` 上の実 UDS を使う

## 参照ドキュメント

- [README.md](./README.md)
- [docs/schema.md](./docs/schema.md) — Plan JSON スキーマ（ユーザー向け）
- [docs/dev/architecture.md](./docs/dev/architecture.md) — 2 プロセス構成・承認フロー
- [docs/dev/protocol.md](./docs/dev/protocol.md) — ブリッジプロトコル

なお `docs/` 配下のドキュメントはすべて英語で記述する（本ファイルと `tasks/` は日本語のまま）。
