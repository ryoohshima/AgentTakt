"""常駐モード（IdleScreen + BridgeServer）の統合テスト。"""

import asyncio

from agenttakt.bridge import protocol
from agenttakt.bridge.client import request_review, send_show_plan
from agenttakt.tui.app import AgentTaktApp
from agenttakt.tui.screens.editor import EditorScreen
from agenttakt.tui.screens.idle import IdleScreen

SIZE = (120, 40)


def make_request(request_id="r1"):
    return protocol.ReviewRequest(
        request_id=request_id,
        plan={
            "graph_id": "standalone-test",
            "nodes": [
                {"id": "a", "type": "grep", "title": "A"},
                {"id": "b", "type": "edit", "title": "B"},
            ],
            "edges": [{"id": "e1", "source": "a", "target": "b"}],
        },
        meta={"summary": "常駐テスト"},
    )


async def wait_for(predicate, pilot, timeout=3.0):
    for _ in range(int(timeout / 0.05)):
        if predicate():
            return
        await pilot.pause(0.05)
    raise AssertionError("条件が時間内に成立しなかった")


async def test_standalone_approve_flow(sock_path):
    sock = sock_path
    app = AgentTaktApp(socket_path=sock)
    async with app.run_test(size=SIZE) as pilot:
        assert isinstance(app.screen, IdleScreen)
        await wait_for(sock.exists, pilot)

        task = asyncio.create_task(request_review(make_request(), sock))
        await wait_for(lambda: isinstance(app.screen, EditorScreen), pilot)

        await pilot.press("a")
        await pilot.pause()
        await pilot.click("#ok")
        result = await asyncio.wait_for(task, 3)
        assert result.decision == "approved"
        assert result.plan.status == "approved"

        await wait_for(lambda: isinstance(app.screen, IdleScreen), pilot)


async def test_show_plan_opens_view_only_editor(sock_path):
    """show_plan は送信元切断後もエディタに表示され、承認しても何も送られない。"""
    sock = sock_path
    app = AgentTaktApp(socket_path=sock)
    async with app.run_test(size=SIZE) as pilot:
        await wait_for(sock.exists, pilot)

        request = protocol.ShowPlanRequest(
            request_id="s1",
            plan=make_request().plan,
            meta={"summary": "view test"},
        )
        await asyncio.wait_for(send_show_plan(request, sock), 3)  # ack で即返る

        await wait_for(lambda: isinstance(app.screen, EditorScreen), pilot)
        assert app.screen.summary == "[view-only] view test"

        # 承認操作をしてもクラッシュせず idle に戻るだけ（応答先はもう居ない）
        await pilot.press("a")
        await pilot.pause()
        await pilot.click("#ok")
        await wait_for(lambda: isinstance(app.screen, IdleScreen), pilot)


async def test_quit_while_review_rejects_pending(sock_path):
    """レビュー中にアプリを終了しても Executor には却下応答が返る。"""
    app = AgentTaktApp(socket_path=sock_path)
    async with app.run_test(size=SIZE) as pilot:
        await wait_for(sock_path.exists, pilot)
        task = asyncio.create_task(request_review(make_request(), sock_path))
        await wait_for(lambda: isinstance(app.screen, EditorScreen), pilot)
        app.exit()
        await pilot.pause()
    result = await asyncio.wait_for(task, 3)
    assert result.decision == "rejected"
    assert result.reason is not None and "closed" in result.reason


async def test_standalone_disconnect_returns_to_idle(sock_path):
    sock = sock_path
    app = AgentTaktApp(socket_path=sock)
    async with app.run_test(size=SIZE) as pilot:
        await wait_for(sock.exists, pilot)

        task = asyncio.create_task(request_review(make_request(), sock))
        await wait_for(lambda: isinstance(app.screen, EditorScreen), pilot)

        task.cancel()  # Executor 側キャンセル相当（接続が切れる）
        await wait_for(lambda: isinstance(app.screen, IdleScreen), pilot)
