"""TUI プロセス側の Unix domain socket サーバー。

複数同時接続を受理し、リクエストは呼び出し側（TUI）が FIFO で処理する。
応答は受信した接続オブジェクトへ書き戻すため request_id の取り違えは起きない。
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from agenttakt.bridge import protocol
from agenttakt.bridge.paths import prepare_socket_dir


@dataclass
class PendingReview:
    """未応答のレビュー依頼 1 件。接続に紐付く。"""

    request: protocol.ReviewRequest
    writer: asyncio.StreamWriter = field(repr=False)
    answered: bool = False
    disconnected: bool = False


class AlreadyRunningError(RuntimeError):
    """同じ socket で別の TUI が稼働中。"""


class BridgeServer:
    def __init__(
        self,
        socket_path: Path,
        on_request: Callable[[PendingReview], None],
        on_disconnect: Callable[[PendingReview], None],
    ) -> None:
        self._socket_path = socket_path
        self._on_request = on_request
        self._on_disconnect = on_disconnect
        self._server: asyncio.Server | None = None

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    async def start(self) -> None:
        prepare_socket_dir(self._socket_path)
        # CPython の create_unix_server は既存 socket ファイルを bind 前に黙って
        # 削除する（生きたサーバーの socket も奪う）ため、bind 前に自前で生存確認する
        if self._socket_path.exists():
            await self._reclaim_stale_socket()
        self._server = await asyncio.start_unix_server(
            self._handle, str(self._socket_path)
        )

    async def _reclaim_stale_socket(self) -> None:
        """残骸 socket（や非ソケットの残置ファイル）なら unlink する。

        生きた TUI が応答するなら起動を拒否する。
        """
        try:
            _, writer = await asyncio.open_unix_connection(str(self._socket_path))
        except OSError:
            # ConnectionRefused / ENOTSOCK / FileNotFound いずれも残骸とみなす
            self._socket_path.unlink(missing_ok=True)
            return
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        raise AlreadyRunningError(
            f"別の AgentTakt が {self._socket_path} で稼働中です"
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            # Python 3.12+ の wait_closed は全接続が閉じるまで待つため、
            # 居座る接続に道連れにされないようタイムアウトを保険にかける
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._server.wait_closed(), timeout=2)
            self._server = None
        self._socket_path.unlink(missing_ok=True)

    async def respond(self, pending: PendingReview, response: protocol.ReviewResponse) -> None:
        if pending.answered or pending.disconnected:
            return
        pending.answered = True
        pending.writer.write(protocol.encode(response))
        with contextlib.suppress(Exception):
            await pending.writer.drain()
        pending.writer.close()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        line = await reader.readline()
        if not line:
            writer.close()
            return
        try:
            message = protocol.decode(line)
        except ValidationError as error:
            await self._send_error(writer, "invalid_message", str(error))
            return
        if not isinstance(message, protocol.ReviewRequest):
            await self._send_error(writer, "unexpected_message", f"type={message.type}")
            return

        pending = PendingReview(request=message, writer=writer)
        self._on_request(pending)

        # 接続を読み続け、EOF（Executor のタイムアウト・キャンセル）を検出する
        with contextlib.suppress(Exception):
            await reader.read()
        if not pending.answered:
            pending.disconnected = True
            self._on_disconnect(pending)
        # どの経路でも必ずトランスポートを閉じる（wait_closed のハング防止）
        writer.close()

    @staticmethod
    async def _send_error(writer: asyncio.StreamWriter, code: str, message: str) -> None:
        writer.write(protocol.encode(protocol.ErrorMessage(code=code, message=message)))
        with contextlib.suppress(Exception):
            await writer.drain()
        writer.close()
