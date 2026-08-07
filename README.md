<!-- mcp-name: io.github.ryoohshima/agenttakt -->

# <img src="https://raw.githubusercontent.com/ryoohshima/AgentTakt/main/docs/images/icon.png" alt="AgentTakt icon" width="40" align="top" /> AgentTakt

[![PyPI - Version](https://img.shields.io/pypi/v/agenttakt)](https://pypi.org/project/agenttakt/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/agenttakt)](https://pypi.org/project/agenttakt/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/ryoohshima/AgentTakt/blob/main/LICENSE)

Review, edit, and approve AI agent task plans in a ComfyUI-style visual node editor — right in your terminal.

![AgentTakt demo: drag nodes, draw a dependency edge, approve](https://raw.githubusercontent.com/ryoohshima/AgentTakt/main/docs/images/demo.gif)

AgentTakt is an MCP (Model Context Protocol) server and TUI tool. When an AI agent (an "Executor" such as Claude Code) sends a task execution plan over MCP, AgentTakt renders it as a node graph in your terminal. You review it with mouse and keyboard — move, add, and delete nodes, draw dependency edges, edit parameters — then approve, and the edited plan JSON is returned to the Executor for execution.

```
Claude Code (Executor)
   │ stdio (MCP)                        your other terminal
   ▼                                           │
[agenttakt serve] ── Unix domain socket ──▶ [agenttakt (TUI)]
 MCP server                               review / edit / approve
```

## Features

- **Terminal-native** — no web UI; everything runs inside your terminal
- **Visual node editor** — rounded nodes, dependency edges, and per-type coloring, powered by [Textual](https://textual.textualize.io/)
- **Mouse-first editing** — drag nodes to move them, draw edges between ports (rubber band), click to select and delete
- **Safe approval loop** — cycle detection (DAG guarantee) and other validations at the entry point, returning errors the agent can self-correct

## Requirements

- Python 3.10+ (recommended: [uv](https://docs.astral.sh/uv/))
- A terminal emulator with mouse reporting (iTerm2, WezTerm, kitty, Ghostty, ...)

## Installation

**If you have [uv](https://docs.astral.sh/uv/), no installation is needed.** `uvx agenttakt` fetches and runs AgentTakt on demand, and the `.mcp.json` example below starts the MCP server the same way.

**If you don't have uv, install AgentTakt once:**

```sh
brew install ryoohshima/tap/agenttakt    # Homebrew
pipx install agenttakt                   # pipx
```

Installing is also handy for everyday use even with uv — you start the TUI by hand, so plain `agenttakt` beats typing `uvx agenttakt` each time:

```sh
uv tool install agenttakt
```

## Quick Start

AgentTakt runs as **two processes**: the MCP server, which Claude Code starts for you, and the TUI, which **you start yourself in a separate terminal**. The TUI is what displays the plan, so start it before asking the Executor for approval.

```
┌─ Terminal A: you ───────────────────┐   ┌─ Terminal B: Claude Code ───────────┐
│ $ uvx agenttakt                     │   │ $ claude                            │
│                                     │   │                                     │
│   ╭─ grep ───╮                      │   │ > Plan the refactor, then ask       │
│   │ pattern  │───╮                  │   │   me to approve it                  │
│   ╰──────────╯   │                  │   │                                     │
│             ╭────▼─────╮            │   │   calls request_approval(plan)      │
│             │   edit   │            │   │   waiting for approval...           │
│             ╰──────────╯            │   │   (blocked until you decide)        │
│                                     │   │                                     │
│   [a] Approve   [r] Reject          │   │                                     │
└─────────────────────────────────────┘   └─────────────────────────────────────┘
             ▲                                                    │
             ╰──────────────── Unix domain socket ────────────────╯
```

Running the TUI in the same session as Claude Code does not work. A stdio MCP server has its standard input and output reserved for protocol traffic, so the same process cannot also drive a full-screen terminal UI. That is why the two halves are separate processes talking over a Unix domain socket.

### 1. Start the TUI (in its own terminal)

```sh
uvx agenttakt           # if installed: agenttakt (short alias: agt)
```

An idle screen appears, waiting for plans from the Executor. Leave this terminal open. If no TUI is running when the Executor calls `request_approval`, the call fails with:

> AgentTakt editor is not running. Ask the user to run "agenttakt" in a separate terminal, then call request_approval again.

### 2. Register the MCP server with the Executor (Claude Code)

Add the following to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "agenttakt": {
      "command": "uvx",
      "args": ["agenttakt", "serve"],
      "timeout": 1800000
    }
  }
}
```

> [!IMPORTANT]
> **Setting `timeout` (milliseconds) explicitly is required.** The `request_approval` tool blocks until the human finishes reviewing. MCP progress notifications do not extend client-side timeouts, so the default would cut the request off before approval. The example above sets 30 minutes (`1800000`).

### 3. Request approval from the Executor

When the Executor calls the MCP tool `request_approval(plan, summary)`, the plan appears in the TUI as a node graph. Once the human edits and approves (or rejects) it, the result is returned as:

```json
{ "status": "approved", "plan": { "...edited plan..." }, "reason": null }
```

See [docs/schema.md](docs/schema.md) for the plan JSON format and what to write in each node.

### Debug mode (try it without MCP)

```sh
uvx agenttakt open examples/sample_plan.json --out edited.json
```

Loads a plan from a file, opens the editor, and writes the approval result to `--out`.

## Key Bindings

| Key | Action |
|---|---|
| `a` | Approve the plan (confirmation dialog) |
| `r` | Reject the plan (with a reason) |
| `n` | Add a node |
| `d` / `Delete` | Delete the selected node/edge |
| `u` / `U` | Undo / Redo |
| Arrow keys | Move the selected node by one cell (fine-tuning) |
| `Escape` | Clear selection |
| `p` | Toggle the parameter panel |
| `?` | Help (controls and how to write `type` / `data`) |
| `q` | Quit |

Mouse: drag a node to move it; drag from a node's output port (●, right edge) and release on another node to create an edge.

Edges are drawn as braille Bezier-like curves by default. If they render poorly in your environment, switch to rounded orthogonal lines with `--edges orthogonal`.

## Documentation

- [Plan JSON schema](docs/schema.md) — data model, node fields, what to write in `type` / `data`, and validation rules

## License

[MIT](LICENSE)
