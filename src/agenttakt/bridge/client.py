"""MCP サーバープロセス側の socket クライアント。

1 接続 1 リクエスト（接続 → review_request 送信 → review_response 受信 → 切断）。
状態は持たない。
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from agenttakt.bridge import protocol
from agenttakt.bridge.paths import default_socket_path


class TuiNotRunningError(ConnectionError):
    """TUI プロセスが起動しておらず socket に接続できない。"""


class BridgeProtocolError(RuntimeError):
    """TUI 側からエラー応答や不正な応答が返った。"""


async def request_review(
    request: protocol.ReviewRequest, socket_path: Path | None = None
) -> protocol.ReviewResponse:
    path = socket_path or default_socket_path()
    try:
        reader, writer = await asyncio.open_unix_connection(str(path))
    except (FileNotFoundError, ConnectionRefusedError, NotADirectoryError) as error:
        raise TuiNotRunningError(str(path)) from error
    try:
        writer.write(protocol.encode(request))
        await writer.drain()
        line = await reader.readline()
        if not line:
            raise BridgeProtocolError(
                "AgentTakt TUI closed the connection without a response."
            )
        message = protocol.decode(line)
        if isinstance(message, protocol.ErrorMessage):
            raise BridgeProtocolError(f"{message.code}: {message.message}")
        if not isinstance(message, protocol.ReviewResponse):
            raise BridgeProtocolError("unexpected message type from TUI")
        return message
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
