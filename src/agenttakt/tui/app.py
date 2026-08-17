from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
from collections import deque
from pathlib import Path

from textual.app import App

import agenttakt.tui.textual_header_patch  # noqa: F401  Header の mount 前に適用が必要
from agenttakt import __version__
from agenttakt.bridge.paths import default_socket_path
from agenttakt.bridge.protocol import ReviewResponse, ShowPlanRequest
from agenttakt.bridge.server import AlreadyRunningError, BridgeServer, PendingReview
from agenttakt.models import Plan, apply_auto_layout
from agenttakt.tui.screens.editor import EditorScreen, ReviewResult
from agenttakt.tui.screens.idle import IdleScreen
from agenttakt.update_check import fetch_latest_version, is_newer


class AgentTaktApp(App):
    """AgentTakt の TUI アプリ。

    - plan を渡すと直接エディタを開く（open デバッグモード）
    - 渡さない場合は BridgeServer を起動して常駐し、MCP からの依頼を FIFO で処理する
    """

    TITLE = "AgentTakt"
    CSS_PATH = "styles.tcss"

    def __init__(
        self,
        plan: Plan | None = None,
        out_path: str | None = None,
        socket_path: Path | None = None,
        edge_style: str = "braille",
        check_updates: bool = False,
    ) -> None:
        super().__init__()
        self._initial_plan = plan
        self._out_path = out_path
        self._socket_path = socket_path or default_socket_path()
        self.edge_style = edge_style  # "braille" | "orthogonal"
        self._check_updates = check_updates
        self._bridge: BridgeServer | None = None
        self._queue: deque[PendingReview] = deque()
        self._active: PendingReview | None = None

    def on_mount(self) -> None:
        if self._initial_plan is not None:
            self.push_screen(EditorScreen(self._initial_plan), self._finish_open)
        else:
            self.push_screen(IdleScreen(str(self._socket_path)))
            self.run_worker(self._run_bridge(), exclusive=True)
            if self._check_updates and not os.environ.get("AGENTTAKT_NO_UPDATE_CHECK"):
                self.run_worker(self._check_for_update, thread=True)

    def _check_for_update(self) -> None:
        """PyPI の新バージョン確認（thread worker）。失敗は沈黙する。"""
        latest = fetch_latest_version()
        if latest is not None and is_newer(latest, __version__):
            # 取得中（~3 秒）にアプリが終了していると RuntimeError になるため黙殺する
            with contextlib.suppress(RuntimeError):
                self.call_from_thread(
                    self.notify,
                    f"agenttakt {latest} is available (you have {__version__}).",
                    title="Update available",
                    timeout=10,
                )

    # --- open デバッグモード ---

    def _finish_open(self, result: ReviewResult | None) -> None:
        if result is not None and self._out_path:
            Path(self._out_path).write_text(
                result.plan.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
        self.exit(result)

    # --- 常駐モード（BridgeServer 連携） ---

    async def _run_bridge(self) -> None:
        self._bridge = BridgeServer(
            self._socket_path,
            on_request=self._on_request,
            on_disconnect=self._on_disconnect,
        )
        try:
            await self._bridge.start()
        except AlreadyRunningError as error:
            # 下の finally に入る前に抜ける。stop() は無条件に unlink するため、
            # 進むと稼働中インスタンスの socket を奪ってしまう
            self.exit(
                return_code=1,
                message=f"{error}. Use the existing instance or quit it first.",
            )
            return
        # SIGTERM でも socket を後始末してから終了する（unlink は stop() が行う）
        loop = asyncio.get_running_loop()
        with contextlib.suppress(NotImplementedError, ValueError):
            loop.add_signal_handler(signal.SIGTERM, self.exit)
        try:
            await asyncio.Event().wait()  # アプリ終了（worker キャンセル）まで常駐
        finally:
            # 終了時も Executor を宙吊りにしない: 未応答の依頼へ却下を返してから閉じる
            await self._flush_pending(
                "AgentTakt TUI was closed before the review finished. "
                "Ask the user to restart it, then call request_approval again."
            )
            await self._bridge.stop()

    async def _flush_pending(self, reason: str) -> None:
        pendings = [p for p in ([self._active] if self._active else []) + list(self._queue)]
        self._queue.clear()
        self._active = None
        for pending in pendings:
            if pending.answered:  # show_plan は ack 済みで応答不要
                continue
            response = ReviewResponse(
                request_id=pending.request.request_id,
                decision="rejected",
                plan=pending.request.plan,
                reason=reason,
            )
            await self._bridge.respond(pending, response)

    def _on_request(self, pending: PendingReview) -> None:
        self._queue.append(pending)
        self._show_next_review()

    def _on_disconnect(self, pending: PendingReview) -> None:
        if pending in self._queue:
            self._queue.remove(pending)
            self._update_idle_status()
            return
        if pending is self._active:
            self.notify("The requester disconnected", severity="warning")
            # コールバックに None が渡り、応答はスキップされる
            self.screen.dismiss(None)

    def _show_next_review(self) -> None:
        self._update_idle_status()
        if self._active is not None or not self._queue:
            return
        pending = self._queue.popleft()
        self._active = pending
        plan = apply_auto_layout(pending.request.plan)
        summary = pending.request.meta.summary
        if isinstance(pending.request, ShowPlanRequest):
            # 表示のみ（ack 済み）。承認結果はどこにも送られないことを明示する
            summary = f"[view-only] {summary or plan.graph_id}"
        editor = EditorScreen(plan, summary=summary)
        self.push_screen(editor, lambda result: self._finish_review(pending, result))
        self._update_idle_status()

    def _finish_review(self, pending: PendingReview, result: ReviewResult | None) -> None:
        self._active = None
        if isinstance(pending.request, ShowPlanRequest):
            # 表示のみ: ack 済みで応答先もないため何も送らない
            self._show_next_review()
            return
        if result is not None and self._bridge is not None and not pending.disconnected:
            response = ReviewResponse(
                request_id=pending.request.request_id,
                decision=result.decision,  # type: ignore[arg-type]
                plan=result.plan,
                reason=result.reason,
            )
            self.run_worker(self._bridge.respond(pending, response), exclusive=False)
        self._show_next_review()

    def _update_idle_status(self) -> None:
        for screen in self.screen_stack:
            if isinstance(screen, IdleScreen):
                screen.update_status(len(self._queue))


def load_plan(path: str | Path) -> Plan:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return apply_auto_layout(Plan.model_validate(raw))


def run_open(plan_path: str, out_path: str | None = None, edge_style: str = "braille") -> int:
    app = AgentTaktApp(plan=load_plan(plan_path), out_path=out_path, edge_style=edge_style)
    result = app.run()
    if isinstance(result, ReviewResult):
        detail = f"（{result.reason}）" if result.reason else ""
        print(f"{result.decision}: {result.plan.graph_id} {detail}".rstrip())
        if out_path:
            print(f"Wrote the edited plan to {out_path}")
    return 0


def run_standalone(edge_style: str = "braille") -> int:
    app = AgentTaktApp(edge_style=edge_style, check_updates=True)
    app.run()
    return app.return_code or 0
