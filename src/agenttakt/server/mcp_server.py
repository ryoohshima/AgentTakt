"""MCP stdio サーバー（Claude Code 等の Executor が spawn する）。

MCP SDK の import はこのファイルに閉じ込める（v1 FastMCP → v2 MCPServer の
移行を 1 ファイル差分で済ませるため）。TUI をこのプロセスで起動してはならない
（stdio は MCP プロトコル通信に専有されている）。
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from agenttakt.bridge.client import TuiNotRunningError, request_review
from agenttakt.bridge.protocol import ReviewMeta, ReviewRequest
from agenttakt.models.plan import Plan

TUI_NOT_RUNNING_MESSAGE = (
    'AgentTakt editor is not running. Ask the user to run "agenttakt" in a '
    "separate terminal, then call request_approval again."
)

mcp = FastMCP("AgentTakt")


@mcp.tool()
async def request_approval(plan: dict[str, Any], summary: str | None = None) -> dict[str, Any]:
    """Submit a task execution plan for human review in the AgentTakt editor.

    Blocks until the human approves or rejects the plan in the TUI. Returns
    {"status": "approved" | "rejected", "plan": <edited plan>, "reason": <str | null>}.
    The returned plan may differ from the submitted one (the human can edit
    nodes, edges and parameters) — always execute the returned plan.

    Args:
        plan: Plan JSON with graph_id, nodes[] and edges[] (must be a DAG).
        summary: One-line description shown in the editor header.
    """
    try:
        validated = Plan.model_validate(plan)
    except ValidationError as error:
        # Executor が自己修正できるよう検証内容をそのまま返す
        raise ValueError(f"invalid plan: {error}") from error

    request = ReviewRequest(
        request_id=str(uuid.uuid4()),
        plan=validated,
        meta=ReviewMeta(
            summary=summary,
            cwd=os.getcwd(),
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
    )
    try:
        response = await request_review(request)
    except TuiNotRunningError as error:
        raise RuntimeError(TUI_NOT_RUNNING_MESSAGE) from error
    return {
        "status": response.decision,
        "plan": response.plan.model_dump(),
        "reason": response.reason,
    }


def run() -> int:
    mcp.run()  # stdio transport
    return 0
