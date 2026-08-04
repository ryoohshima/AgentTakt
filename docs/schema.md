# Plan JSON Schema

The shared data model for plans exchanged between the Executor (AI agent) and AgentTakt.

## Structure

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

## Field Reference

### Plan (root)

| Field | Type | Required | Description |
|---|---|---|---|
| `graph_id` | string | ✔ | Unique plan ID (assigned by the Executor) |
| `status` | `"pending_approval"` \| `"approved"` \| `"rejected"` | — | Defaults to `"pending_approval"`. AgentTakt rewrites it on approval/rejection before returning the plan |
| `nodes` | Node[] | ✔ | List of task steps |
| `edges` | Edge[] | ✔ | Dependencies (`target` runs after `source` completes) |

### Node

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | ✔ | Unique node ID (not editable in the TUI) |
| `type` | string | ✔ | Kind of work (e.g. `grep`, `edit`, `test`). Used for node coloring in the TUI |
| `title` | string | ✔ | Short human-readable heading |
| `data` | object | — | Per-type parameters as key-value pairs — the concrete instructions for the step. Editable in the TUI |
| `position` | `{x: int, y: int}` | — | Display coordinates in the TUI (terminal cells). Filled in by auto layout when missing |

### Edge

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | ✔ | Unique edge ID |
| `source` | string | ✔ | ID of the node this edge depends on |
| `target` | string | ✔ | ID of the dependent node |

## What to write in `type` and `data`

`type` and `data` are a **free vocabulary interpreted by the Executor (AI agent)** — AgentTakt does not inspect their contents. After approval, the edited JSON is returned to the Executor as-is, which interprets and executes it. In other words, anything the Executor understands is valid, including natural-language instructions.

- `type`: the kind of step. The TUI uses it for node coloring and the bottom-edge label. Conventions: `grep` (search) / `read` (reading) / `edit` (editing) / `test` (testing) / `command` (command execution) / `docs` (documentation)
- `data`: parameters for the step. Conventions per type:
  - `grep` → `pattern` (search pattern), `files` (list of target globs)
  - `edit` → `file` (target file), `strategy` (editing approach)
  - `test` → `command` (command to run)

The same information is available in the in-TUI help (press `?`).

## Validation Rules

The following are validated at the `request_approval` entry point (and when confirming edits in the TUI). Violations are returned to the Executor as a `ValueError`.

1. **ID uniqueness**: no duplicate node ids / edge ids
2. **Endpoint existence**: every edge's `source` / `target` must exist in `nodes`
3. **DAG guarantee**: no cycles (detected with Kahn's algorithm)

### Error message policy

Errors always include the offending IDs so the agent can self-correct.

```
duplicate node ids: ['node_1']
edge 'edge_3' references unknown node(s): ['node_9']
plan must be a DAG; cycle detected: node_1 -> node_2 -> node_1
```

## Unknown Fields

Plan / Node / Edge accept unknown fields (`extra="allow"`) and preserve them through editing (round-trip guarantee), so Executor-specific metadata is never lost.

## Auto Layout

Nodes without a `position` get coordinates from a layered layout.

- Layer assignment: longest path (dependency depth), `x = layer * 36`
- Within a layer: in order of appearance, `y = index * 8`
- Nodes that already have a `position` are left untouched
