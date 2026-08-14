import asyncio

import pytest

from agenttakt.bridge import protocol
from agenttakt.bridge.client import TuiNotRunningError, request_review, send_show_plan
from agenttakt.bridge.server import AlreadyRunningError, BridgeServer


def make_request(request_id="r1"):
    return protocol.ReviewRequest(
        request_id=request_id, plan={"graph_id": "g", "nodes": [], "edges": []}
    )


class Recorder:
    def __init__(self):
        self.requests = []
        self.disconnects = []
        self.arrived = asyncio.Event()
        self.disconnected = asyncio.Event()

    def on_request(self, pending):
        self.requests.append(pending)
        self.arrived.set()

    def on_disconnect(self, pending):
        self.disconnects.append(pending)
        self.disconnected.set()


async def test_review_round_trip(sock_path):
    sock = sock_path
    recorder = Recorder()
    server = BridgeServer(sock, recorder.on_request, recorder.on_disconnect)
    await server.start()
    try:
        task = asyncio.create_task(request_review(make_request(), sock))
        await asyncio.wait_for(recorder.arrived.wait(), 2)
        pending = recorder.requests[0]
        await server.respond(
            pending,
            protocol.ReviewResponse(
                request_id=pending.request.request_id,
                decision="approved",
                plan=pending.request.plan,
            ),
        )
        result = await asyncio.wait_for(task, 2)
        assert result.decision == "approved"
        assert result.request_id == "r1"
    finally:
        await server.stop()
    assert not sock.exists()  # 終了時に unlink される


async def test_client_without_tui(sock_path):
    with pytest.raises(TuiNotRunningError):
        await request_review(make_request(), sock_path)


async def test_executor_disconnect_detected(sock_path):
    sock = sock_path
    recorder = Recorder()
    server = BridgeServer(sock, recorder.on_request, recorder.on_disconnect)
    await server.start()
    try:
        _, writer = await asyncio.open_unix_connection(str(sock))
        writer.write(protocol.encode(make_request()))
        await writer.drain()
        await asyncio.wait_for(recorder.arrived.wait(), 2)
        writer.close()  # Executor 側タイムアウト・キャンセル相当
        await asyncio.wait_for(recorder.disconnected.wait(), 2)
        assert recorder.requests[0].disconnected
    finally:
        await server.stop()


async def test_show_plan_acked_and_stays_queued(sock_path):
    """show_plan は ack で即返り、送信元の切断後もキューから消えない。"""
    sock = sock_path
    recorder = Recorder()
    server = BridgeServer(sock, recorder.on_request, recorder.on_disconnect)
    await server.start()
    try:
        request = protocol.ShowPlanRequest(
            request_id="s1", plan={"graph_id": "g", "nodes": [], "edges": []}
        )
        # ack を受けて返る（人間の応答を待たない）＝ send 側は即切断する
        await asyncio.wait_for(send_show_plan(request, sock), 2)
        await asyncio.wait_for(recorder.arrived.wait(), 2)
        pending = recorder.requests[0]
        assert isinstance(pending.request, protocol.ShowPlanRequest)
        assert pending.answered
        # 切断が on_disconnect として扱われないことを確認する
        await asyncio.sleep(0.1)
        assert recorder.disconnects == []
        assert not pending.disconnected
    finally:
        await server.stop()


async def test_stale_socket_reclaimed(sock_path):
    sock = sock_path
    sock.touch()  # 異常終了の残骸を模す
    recorder = Recorder()
    server = BridgeServer(sock, recorder.on_request, recorder.on_disconnect)
    await server.start()
    await server.stop()


async def test_second_instance_rejected(sock_path):
    sock = sock_path
    recorder = Recorder()
    first = BridgeServer(sock, recorder.on_request, recorder.on_disconnect)
    await first.start()
    try:
        second = BridgeServer(sock, recorder.on_request, recorder.on_disconnect)
        with pytest.raises(AlreadyRunningError):
            await second.start()
    finally:
        await first.stop()


async def test_invalid_message_gets_error_response(sock_path):
    sock = sock_path
    recorder = Recorder()
    server = BridgeServer(sock, recorder.on_request, recorder.on_disconnect)
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(sock))
        writer.write(b'{"type": "bogus"}\n')
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), 2)
        message = protocol.decode(line)
        assert isinstance(message, protocol.ErrorMessage)
        assert message.code == "invalid_message"
        writer.close()
    finally:
        await server.stop()
