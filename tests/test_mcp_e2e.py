"""MCP レイヤーの E2E テスト（インメモリの client-server セッションで検証）。"""

import asyncio
import json

from mcp.shared.memory import create_connected_server_and_client_session

from agenttakt.bridge import protocol
from agenttakt.bridge.server import BridgeServer
from agenttakt.server.mcp_server import mcp

PLAN = {
    "graph_id": "e2e",
    "nodes": [
        {"id": "a", "type": "grep", "title": "A"},
        {"id": "b", "type": "edit", "title": "B"},
    ],
    "edges": [{"id": "e1", "source": "a", "target": "b"}],
}


def result_text(result) -> str:
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


async def test_request_approval_round_trip(sock_path, monkeypatch):
    sock = sock_path
    monkeypatch.setenv("AGENTTAKT_SOCKET", str(sock))

    server: BridgeServer | None = None

    async def auto_approve(pending):
        plan = pending.request.plan
        plan.status = "approved"
        await server.respond(
            pending,
            protocol.ReviewResponse(
                request_id=pending.request.request_id, decision="approved", plan=plan
            ),
        )

    def on_request(pending):
        asyncio.get_running_loop().create_task(auto_approve(pending))

    server = BridgeServer(sock, on_request, lambda pending: None)
    await server.start()
    try:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                "request_approval", {"plan": PLAN, "summary": "E2E テスト"}
            )
            assert not result.isError
            payload = json.loads(result_text(result))
            assert payload["status"] == "approved"
            assert payload["plan"]["graph_id"] == "e2e"
    finally:
        await server.stop()


async def test_request_approval_without_tui(sock_path, monkeypatch):
    monkeypatch.setenv("AGENTTAKT_SOCKET", str(sock_path))
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool(
            "request_approval", {"plan": {"graph_id": "x", "nodes": [], "edges": []}}
        )
        assert result.isError
        assert "editor is not running" in result_text(result)


async def test_request_approval_invalid_plan(sock_path, monkeypatch):
    monkeypatch.setenv("AGENTTAKT_SOCKET", str(sock_path))
    cyclic = {
        "graph_id": "bad",
        "nodes": [
            {"id": "a", "type": "t", "title": "A"},
            {"id": "b", "type": "t", "title": "B"},
        ],
        "edges": [
            {"id": "e1", "source": "a", "target": "b"},
            {"id": "e2", "source": "b", "target": "a"},
        ],
    }
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        result = await client.call_tool("request_approval", {"plan": cyclic})
        assert result.isError
        assert "cycle detected" in result_text(result)
