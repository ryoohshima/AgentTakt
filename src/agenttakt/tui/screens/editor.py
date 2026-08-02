from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header

from agenttakt.models.plan import Plan
from agenttakt.tui.geometry import Rect
from agenttakt.tui.widgets.edge_layer import EdgeLayer
from agenttakt.tui.widgets.node import NodeWidget, node_size

# モデル座標 → キャンバス座標のオフセット（入力ポート ○ が左端で見切れないため）
PAD_X = 2
PAD_Y = 1


class GraphViewport(ScrollableContainer):
    """ノードグラフを描く仮想キャンバス。edges / nodes / overlay の 3 レイヤー構成。"""


class EditorScreen(Screen):
    BINDINGS = [("q", "app.quit", "終了")]

    def __init__(self, plan: Plan, summary: str | None = None) -> None:
        super().__init__()
        self.plan = plan
        self.summary = summary

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with GraphViewport():
            yield EdgeLayer()
            for node in self.plan.nodes:
                yield NodeWidget(node)
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = self.summary or self.plan.graph_id
        self.refresh_graph()

    def refresh_graph(self) -> None:
        """モデルの position からノード配置とエッジ描画を再構築する。"""
        rects: dict[str, Rect] = {}
        for widget in self.query(NodeWidget):
            node = widget.node
            width, height = node_size(node)
            x = node.position.x + PAD_X
            y = node.position.y + PAD_Y
            widget.styles.offset = (x, y)
            widget.styles.width = width
            widget.styles.height = height
            rects[node.id] = Rect(x, y, width, height)

        edge_layer = self.query_one(EdgeLayer)
        if rects:
            canvas_width = max(rect.right for rect in rects.values()) + 6
            canvas_height = max(rect.bottom for rect in rects.values()) + 4
        else:
            canvas_width, canvas_height = 40, 10
        edge_layer.styles.width = canvas_width
        edge_layer.styles.height = canvas_height
        edge_layer.set_graph(rects, self.plan.edges)
