# AgentTakt

AI エージェント（Executor）が生成したタスク実行計画（Plan）を、人間がターミナル上で視覚的にレビュー・編集・承認するための MCP（Model Context Protocol）サーバー兼 TUI ツール。

Claude Code 等の Executor が MCP 経由で送ってきた計画 JSON を、ComfyUI 風のビジュアルノードエディタとしてターミナルに描画する。人間はマウスとキーボードでノードの移動・追加・削除、依存関係（エッジ）の線引き、パラメータ編集を行い、「Approve」すると編集後の JSON が Executor に返って実行が始まる。

```
Claude Code (Executor)
   │ stdio (MCP)                          人間の別ターミナル
   ▼                                            │
[agenttakt serve] ── Unix domain socket ──▶ [agenttakt (TUI 常駐)]
 MCP サーバー                                レビュー / 編集 / 承認
```

## 特徴

- **ターミナル完結**: Web UI を使わず、ターミナル環境のみで動作する
- **ビジュアルノードエディタ**: Textual による角丸ノード・依存関係の接続線・type 別色分け
- **マウス中心の直感操作**: ノードドラッグ、ポート間の線引き（ラバーバンド）、クリック選択・削除
- **安全な承認ループ**: サイクル検出（DAG 保証）等のバリデーションを入口で行い、エージェントが自己修正できるエラーを返す

## 必要環境

- Python 3.10+（推奨: [uv](https://docs.astral.sh/uv/)）
- マウスレポート対応のターミナルエミュレータ（iTerm2, WezTerm, kitty, Ghostty 等）

## インストール

```sh
git clone https://github.com/ryoohshima/AgentTakt.git
cd AgentTakt
uv sync
```

## クイックスタート

### 1. TUI を起動する（人間側・別ターミナル）

```sh
uv run agenttakt        # 短縮 alias: uv run at
```

待機画面が表示され、Executor からの計画到着を待つ。

### 2. Executor（Claude Code）に MCP サーバーを登録する

プロジェクトの `.mcp.json` に以下を追加する。

```json
{
  "mcpServers": {
    "agenttakt": {
      "command": "uv",
      "args": ["--directory", "/path/to/AgentTakt", "run", "agenttakt", "serve"],
      "timeout": 1800000
    }
  }
}
```

> [!IMPORTANT]
> **`timeout`（ミリ秒）の明示設定は必須。** `request_approval` ツールは人間がレビューを終えるまでブロックする。MCP の progress notification ではクライアント側タイムアウトは延長されないため、既定のままだと承認前に打ち切られる。上記例は 30 分（`1800000`）。

### 3. Executor から承認を依頼する

Executor が MCP ツール `request_approval(plan, summary)` を呼ぶと、TUI に計画がノードグラフとして表示される。人間が編集して承認/却下すると、結果が以下の形で返る。

```json
{ "status": "approved", "plan": { "...編集後の計画..." }, "reason": null }
```

計画 JSON の形式は [docs/schema.md](docs/schema.md) を参照。

### デバッグモード（MCP なしで試す）

```sh
uv run agenttakt open examples/sample_plan.json --out edited.json
```

ファイルから計画を読み込んでエディタを開き、承認結果を `--out` に書き出す。

## キー操作

| キー | 動作 |
|---|---|
| `a` | 承認（確認ダイアログ） |
| `r` | 却下（理由入力） |
| `n` | ノード追加 |
| `d` / `Delete` | 選択中のノード/エッジを削除 |
| 矢印 | 選択ノードを 1 セル移動（マウスの微調整） |
| `p` | パラメータパネルの表示切替 |
| `q` | 終了 |

マウス: ノードのタイトルバーをドラッグで移動、出力ポート ● からドラッグして入力ポート ○ で離すとエッジ作成。

## ドキュメント

- [アーキテクチャ](docs/architecture.md) — 2 プロセス構成の理由と承認フロー
- [Plan JSON スキーマ](docs/schema.md) — データモデルとバリデーション規則
- [ブリッジプロトコル](docs/protocol.md) — MCP サーバー ⇔ TUI 間の socket プロトコル

## 開発

```sh
uv sync                  # 依存関係のインストール（dev 含む）
uv run pytest            # テスト
uv run textual console   # 開発コンソール（別ターミナル）
uv run textual run --dev src/agenttakt/tui/app.py
```

実装の進捗は [親 issue #3](https://github.com/ryoohshima/AgentTakt/issues/3) と `tasks/todo.md` を参照。

## ステータス

MVP 開発中。マイルストーン: M0 足場 → M1 静的描画 → M2 マウス編集 → M3 MCP 連携 → M4 磨き込み（braille 曲線ほか）。
