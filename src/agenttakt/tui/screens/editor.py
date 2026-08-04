from __future__ import annotations

import time
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header

from agenttakt.models.plan import Edge, Node, Plan, Position, find_cycle
from agenttakt.tui.geometry import PAD_X, PAD_Y, Rect, output_port
from agenttakt.tui.screens.help import HelpScreen
from agenttakt.tui.screens.modals import ConfirmApproveScreen, RejectReasonScreen
from agenttakt.tui.widgets.edge_layer import EdgeLayer
from agenttakt.tui.widgets.node import NodeWidget, node_size
from agenttakt.tui.widgets.param_panel import ParamPanel

_NUDGE = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


@dataclass
class ReviewResult:
    decision: str  # "approved" | "rejected"
    plan: Plan
    reason: str | None = None


class GraphViewport(ScrollableContainer):
    """ノードグラフを描く仮想キャンバス。edges / nodes / overlay の 3 レイヤー構成。"""

    # 矢印キーをノード微調整に譲るためフォーカスを取らない（スクロールはマウスで）
    can_focus = False


class EditorScreen(Screen[ReviewResult]):
    BINDINGS = [
        Binding("a", "approve", "Approve"),
        Binding("r", "reject", "Reject"),
        Binding("n", "add_node", "Add node"),
        Binding("d,delete", "delete_selected", "Delete"),
        Binding("p", "toggle_panel", "Panel"),
        Binding("u", "undo", "Undo"),
        Binding("U", "redo", "Redo", show=False),
        Binding("up", "nudge('up')", "Move", show=False),
        Binding("down", "nudge('down')", "Move", show=False),
        Binding("left", "nudge('left')", "Move", show=False),
        Binding("right", "nudge('right')", "Move", show=False),
        Binding("question_mark", "show_help", "Help", key_display="?"),
        Binding("escape", "deselect", "Deselect", show=False),
        Binding("q", "quit_editor", "Quit"),
    ]

    def __init__(self, plan: Plan, summary: str | None = None) -> None:
        super().__init__()
        self.plan = plan
        self.summary = summary
        self._rects: dict[str, Rect] = {}
        # ("node" | "edge", id)
        self._selected: tuple[str, str] | None = None
        self._edge_source: str | None = None
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        # 連続入力（title 編集の 1 打鍵ごと等）を 1 つの undo 単位にまとめるためのキー
        self._last_edit_key: tuple | None = None
        self._started = time.monotonic()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="editor-body"):
            with GraphViewport():
                yield EdgeLayer()
                for node in self.plan.nodes:
                    yield NodeWidget(node)
            yield ParamPanel()
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = self.summary or self.plan.graph_id
        self.set_interval(1.0, self._update_elapsed)
        self.refresh_graph()

    def _update_elapsed(self) -> None:
        """承認待ちの経過時間をサブタイトルに表示する（放置に気づかせる）。"""
        elapsed = int(time.monotonic() - self._started)
        base = self.summary or self.plan.graph_id
        self.sub_title = f"{base}  ⏱ {elapsed // 60:02d}:{elapsed % 60:02d}"

    # --- 描画 ---

    def refresh_graph(self) -> None:
        """モデルの position からノード配置とエッジ描画を再構築する。"""
        for widget in self.query(NodeWidget):
            node = widget.node
            width, height = node_size(node)
            widget.styles.offset = (node.position.x + PAD_X, node.position.y + PAD_Y)
            widget.styles.width = width
            widget.styles.height = height
        self.redraw_edges()

    def redraw_edges(self) -> None:
        """現在のウィジェット位置からエッジ層のみ再構築する（ドラッグ中の追従用）。"""
        rects: dict[str, Rect] = {
            widget.node.id: widget.rect for widget in self.query(NodeWidget)
        }
        self._rects = rects
        if rects:
            canvas_width = max(rect.right for rect in rects.values()) + 6
            canvas_height = max(rect.bottom for rect in rects.values()) + 4
        else:
            canvas_width, canvas_height = 40, 10
        edge_layer = self.query_one(EdgeLayer)
        edge_layer.styles.width = canvas_width
        edge_layer.styles.height = canvas_height
        edge_layer.set_graph(rects, self.plan.edges)

    # --- 選択 ---

    def select_node(self, node_id: str) -> None:
        self.deselect()
        self._selected = ("node", node_id)
        widget = self._node_widget(node_id)
        if widget:
            widget.set_selected(True)
            self.query_one(ParamPanel).show_node(widget.node)

    def select_edge(self, edge_id: str) -> None:
        self.deselect()
        self._selected = ("edge", edge_id)
        self.query_one(EdgeLayer).selected_edge = edge_id

    def deselect(self) -> None:
        if self._selected is None:
            return
        kind, ident = self._selected
        self._selected = None
        if kind == "node":
            widget = self._node_widget(ident)
            if widget:
                widget.set_selected(False)
        else:
            self.query_one(EdgeLayer).selected_edge = None
        self.query_one(ParamPanel).show_none()

    def _node_widget(self, node_id: str) -> NodeWidget | None:
        for widget in self.query(NodeWidget):
            if widget.node.id == node_id:
                return widget
        return None

    # --- エッジ作成（ラバーバンド） ---

    def start_edge_drag(self, node_id: str) -> None:
        self._edge_source = node_id
        rect = self._rects.get(node_id)
        if rect:
            port = output_port(rect)
            self.query_one(EdgeLayer).set_preview(
                (port[0] + 1, port[1]), (port[0] + 1, port[1])
            )

    def update_edge_drag(self, pos: tuple[int, int]) -> None:
        if self._edge_source is None:
            return
        rect = self._rects.get(self._edge_source)
        if rect is None:
            return
        port = output_port(rect)
        self.query_one(EdgeLayer).set_preview((port[0] + 1, port[1]), pos)

    def finish_edge_drag(self, pos: tuple[int, int]) -> None:
        source, self._edge_source = self._edge_source, None
        self.query_one(EdgeLayer).clear_preview()
        if source is None:
            return
        target = self._node_at(pos, exclude=source)
        if target is None:
            return
        self.create_edge(source, target)

    def _node_at(self, pos: tuple[int, int], exclude: str | None = None) -> str | None:
        """セル座標にあるノード（入力ポート列を含む）を返す。"""
        x, y = pos
        for node_id, rect in self._rects.items():
            if node_id == exclude:
                continue
            if rect.x - 1 <= x < rect.right + 1 and rect.y <= y < rect.bottom:
                return node_id
        return None

    def create_edge(self, source: str, target: str) -> None:
        if any(e.source == source and e.target == target for e in self.plan.edges):
            self.notify("That connection already exists", severity="warning")
            return
        node_ids = [n.id for n in self.plan.nodes]
        proposed = [(e.source, e.target) for e in self.plan.edges] + [(source, target)]
        cycle = find_cycle(node_ids, proposed)
        if cycle:
            self.notify("Cannot connect: this would create a cycle: " + " -> ".join(cycle), severity="error")
            return
        self.checkpoint()
        self.plan.edges.append(
            Edge(id=self._unique_id("edge", (e.id for e in self.plan.edges)), source=source, target=target)
        )
        self.redraw_edges()

    @staticmethod
    def _unique_id(prefix: str, existing) -> str:
        taken = set(existing)
        index = 1
        while f"{prefix}_{index}" in taken:
            index += 1
        return f"{prefix}_{index}"

    # --- undo / redo ---

    def snapshot_plan(self) -> dict:
        return self.plan.model_dump()

    def push_undo(self, snapshot: dict, edit_key: tuple | None = None) -> None:
        """編集前スナップショットを積む。同一 edit_key の連続編集は 1 単位にまとめる。"""
        if edit_key is not None and edit_key == self._last_edit_key:
            return
        self._last_edit_key = edit_key
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > 100:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def checkpoint(self, edit_key: tuple | None = None) -> None:
        self.push_undo(self.snapshot_plan(), edit_key)

    async def action_undo(self) -> None:
        if not self._undo_stack:
            self.notify("Nothing left to undo", severity="warning")
            return
        self._redo_stack.append(self.snapshot_plan())
        self._last_edit_key = None
        await self._restore(self._undo_stack.pop())

    async def action_redo(self) -> None:
        if not self._redo_stack:
            self.notify("Nothing to redo", severity="warning")
            return
        self._undo_stack.append(self.snapshot_plan())
        self._last_edit_key = None
        await self._restore(self._redo_stack.pop())

    async def _restore(self, snapshot: dict) -> None:
        self.deselect()
        self.plan = Plan.model_validate(snapshot)
        viewport = self.query_one(GraphViewport)
        await self.query(NodeWidget).remove()
        await viewport.mount_all(NodeWidget(node) for node in self.plan.nodes)
        self.refresh_graph()

    # --- 編集操作 ---

    def apply_node_edit(self, node_id: str, field: str, value) -> None:
        widget = self._node_widget(node_id)
        if widget is None or getattr(widget.node, field) == value:
            return
        self.checkpoint(edit_key=("edit", node_id, field))
        setattr(widget.node, field, value)
        widget.refresh_content()
        self.refresh_graph()  # サイズ変化に追従

    async def action_add_node(self) -> None:
        self.checkpoint()
        viewport = self.query_one(GraphViewport)
        node = Node(
            id=self._unique_id("node", (n.id for n in self.plan.nodes)),
            type="task",
            title="New Step",
            data={},
            position=Position(
                x=int(viewport.scroll_x) + 4, y=int(viewport.scroll_y) + 2
            ),
        )
        self.plan.nodes.append(node)
        widget = NodeWidget(node)
        await viewport.mount(widget)
        self.refresh_graph()
        self.select_node(node.id)

    async def action_delete_selected(self) -> None:
        if self._selected is None:
            return
        self.checkpoint()
        kind, ident = self._selected
        self.deselect()
        if kind == "edge":
            self.plan.edges = [e for e in self.plan.edges if e.id != ident]
        else:
            self.plan.nodes = [n for n in self.plan.nodes if n.id != ident]
            # 接続エッジをカスケード削除
            self.plan.edges = [
                e for e in self.plan.edges if ident not in (e.source, e.target)
            ]
            widget = self._node_widget(ident)
            if widget:
                await widget.remove()
        self.refresh_graph()

    def action_nudge(self, direction: str) -> None:
        if self._selected and self._selected[0] == "node":
            widget = self._node_widget(self._selected[1])
            if widget is None:
                return
            self.checkpoint(edit_key=("nudge", widget.node.id))
            dx, dy = _NUDGE[direction]
            node = widget.node
            node.position = Position(
                x=max(0, node.position.x + dx), y=max(0, node.position.y + dy)
            )
            self.refresh_graph()
        else:
            dx, dy = _NUDGE[direction]
            self.query_one(GraphViewport).scroll_relative(x=dx * 4, y=dy * 2, animate=False)

    def action_show_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_deselect(self) -> None:
        self.deselect()

    def action_toggle_panel(self) -> None:
        panel = self.query_one(ParamPanel)
        panel.styles.display = "none" if panel.styles.display == "block" else "block"

    # --- 承認 / 却下 ---

    def action_approve(self) -> None:
        def done(approved: bool | None) -> None:
            if approved:
                self.plan.status = "approved"
                self.dismiss(ReviewResult("approved", self.plan))

        self.app.push_screen(ConfirmApproveScreen(), done)

    def action_reject(self) -> None:
        def done(reason: str | None) -> None:
            if reason is not None:
                self.plan.status = "rejected"
                self.dismiss(ReviewResult("rejected", self.plan, reason or None))

        self.app.push_screen(RejectReasonScreen(), done)

    def action_quit_editor(self) -> None:
        self.app.exit()
