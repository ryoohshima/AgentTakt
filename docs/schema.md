# Plan JSON スキーマ

Executor（AI エージェント）と AgentTakt の間で受け渡す計画（Plan）の共通データモデル。

## 構造

```json
{
  "graph_id": "unique-task-id",
  "status": "pending_approval",
  "nodes": [
    {
      "id": "node_1",
      "type": "grep",
      "title": "Existing Auth Check",
      "data": {
        "pattern": "useAuth",
        "files": ["src/**"]
      },
      "position": { "x": 100, "y": 100 }
    }
  ],
  "edges": [
    { "id": "edge_1", "source": "node_1", "target": "node_2" }
  ]
}
```

## フィールド定義

### Plan（ルート）

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `graph_id` | string | ✔ | 計画の一意 ID（Executor が採番） |
| `status` | `"pending_approval"` \| `"approved"` \| `"rejected"` | — | 既定 `"pending_approval"`。承認/却下時に AgentTakt が書き換えて返す |
| `nodes` | Node[] | ✔ | タスクステップの一覧 |
| `edges` | Edge[] | ✔ | 依存関係（`source` の完了後に `target` を実行） |

### Node

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `id` | string | ✔ | ノードの一意 ID |
| `type` | string | ✔ | ステップ種別（例: `grep`, `edit`, `test`）。TUI の色分けに使用 |
| `title` | string | ✔ | 人間向けの短い表題 |
| `data` | object | — | 種別ごとの任意パラメータ。TUI で編集可能 |
| `position` | `{x: int, y: int}` | — | TUI 上の表示座標（端末セル単位）。欠落時は自動レイアウトで補完 |

### Edge

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `id` | string | ✔ | エッジの一意 ID |
| `source` | string | ✔ | 依存元ノード ID |
| `target` | string | ✔ | 依存先ノード ID |

## バリデーション規則

`request_approval` の入口（および TUI での編集確定時）に以下を検証する。違反は `ValueError` として Executor に返す。

1. **ID の一意性**: node id / edge id の重複禁止
2. **端点の存在**: edge の `source` / `target` が `nodes` に存在すること
3. **DAG 保証**: サイクル禁止（Kahn 法で検出）

### エラーメッセージの方針

エージェントが自己修正できるよう、エラーには対象 ID を必ず含める。

```
duplicate node ids: ['node_1']
edge 'edge_3' references unknown node(s): ['node_9']
plan must be a DAG; cycle detected: node_1 -> node_2 -> node_1
```

## 未知フィールドの扱い

Plan / Node / Edge は未知フィールドを許容し（`extra="allow"`）、編集後もそのまま保持して返す（ラウンドトリップ保証）。Executor 独自のメタデータを壊さないためである。

## 自動レイアウト

`position` 欠落ノードには layered レイアウトで座標を補完する。

- 層割当: longest-path（依存の深さ）で `x = layer * 36`
- 層内: 出現順に `y = index * 8`
- `position` を持つノードは動かさない
