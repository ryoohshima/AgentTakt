"""エッジとポートの描画レイヤー（painting）。

geometry が計算した Route をレンダラ（renderers.py）でセルバッファに焼き込み、
render_line() はバッファから Strip を組むだけにする（描画のたびに経路計算しない）。
"""

from __future__ import annotations

from collections import defaultdict

from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.strip import Strip
from textual.widget import Widget

from agenttakt.models.plan import Edge
from agenttakt.tui.geometry import (
    Rect,
    input_port,
    output_port,
    route_orthogonal,
    route_to_point,
)
from agenttakt.tui.widgets.renderers import BrailleRenderer, Cell, OrthogonalRenderer


class CellSurface(Widget):
    """(x, y) → (文字, edge_id) のセルバッファを行単位で描画する基底ウィジェット。"""

    def __init__(self) -> None:
        super().__init__()
        self._rows: dict[int, dict[int, Cell]] = {}
        self.can_focus = False

    def load_buffer(self, buffer: dict[tuple[int, int], Cell]) -> None:
        rows: dict[int, dict[int, Cell]] = defaultdict(dict)
        for (x, y), cell in buffer.items():
            rows[y][x] = cell
        self._rows = dict(rows)
        self.refresh()

    def cell_style(self, cell: Cell) -> Style:
        raise NotImplementedError

    def render_line(self, y: int) -> Strip:
        width = self.size.width
        cells = self._rows.get(y)
        if not cells:
            return Strip.blank(width)
        segments: list[Segment] = []
        cursor = 0
        for x in sorted(cells):
            if x < 0 or x >= width:
                continue
            if x > cursor:
                segments.append(Segment(" " * (x - cursor)))
            segments.append(Segment(cells[x][0], self.cell_style(cells[x])))
            cursor = x + 1
        if cursor < width:
            segments.append(Segment(" " * (width - cursor)))
        return Strip(segments, width)


class EdgeLayer(CellSurface):
    """キャンバス全面に敷く最背面レイヤー。エッジ線とポート ○/● を描く。

    ポートのヒットテストとエッジ選択の逆引きもこのレイヤーが担う。
    レンダラは App の edge_style（braille | orthogonal）で切り替わる。
    """

    _edge_style = Style(color="#565f89")
    _selected_style = Style(color="#e0af68", bold=True)
    _port_style = Style(color="#7aa2f7", bold=True)

    def __init__(self) -> None:
        super().__init__()
        # ポートセル → (kind, node_id)。kind は "in" / "out"
        self._ports: dict[tuple[int, int], tuple[str, str]] = {}
        self._selected_edge: str | None = None
        self._dragging_from: str | None = None

    @property
    def selected_edge(self) -> str | None:
        return self._selected_edge

    @selected_edge.setter
    def selected_edge(self, edge_id: str | None) -> None:
        self._selected_edge = edge_id
        self.refresh()

    def _renderer(self):
        if getattr(self.app, "edge_style", "braille") == "orthogonal":
            return OrthogonalRenderer()
        return BrailleRenderer()

    def set_graph(self, rects: dict[str, Rect], edges: list[Edge]) -> None:
        """ノード矩形とエッジからセルバッファとポート表を再構築する。"""
        per_source: dict[str, int] = defaultdict(int)
        routes = []
        for edge in edges:
            channel = per_source[edge.source]
            per_source[edge.source] += 1
            routes.append(
                route_orthogonal(edge.id, rects[edge.source], rects[edge.target], channel)
            )
        buffer = self._renderer().rasterize(routes)
        ports: dict[tuple[int, int], tuple[str, str]] = {}
        for node_id, rect in rects.items():
            out_cell, in_cell = output_port(rect), input_port(rect)
            buffer[out_cell] = ("●", None)
            buffer[in_cell] = ("○", None)
            ports[out_cell] = ("out", node_id)
            ports[in_cell] = ("in", node_id)
        self._ports = ports
        self.load_buffer(buffer)

    def edge_at(self, x: int, y: int) -> str | None:
        """セル座標にあるエッジ ID（ヒットテスト用）。"""
        cell = self._rows.get(y, {}).get(x)
        return cell[1] if cell else None

    def cell_style(self, cell: Cell) -> Style:
        _, edge_id = cell
        if edge_id is None:
            return self._port_style
        if edge_id == self._selected_edge:
            return self._selected_style
        return self._edge_style

    # --- マウス: 出力ポートからの線引き開始、エッジのクリック選択 ---

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 1:
            return
        pos = (event.offset.x, event.offset.y)
        port = self._ports.get(pos)
        if port and port[0] == "out":
            self._dragging_from = port[1]
            self.capture_mouse()
            self.screen.start_edge_drag(port[1])  # type: ignore[attr-defined]
            event.stop()
            return
        edge_id = self.edge_at(*pos)
        if edge_id:
            self.screen.select_edge(edge_id)  # type: ignore[attr-defined]
        else:
            self.screen.deselect()  # type: ignore[attr-defined]
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging_from is None:
            return
        self.screen.update_edge_drag((event.offset.x, event.offset.y))  # type: ignore[attr-defined]

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging_from is None:
            return
        self.release_mouse()
        self._dragging_from = None
        self.screen.finish_edge_drag((event.offset.x, event.offset.y))  # type: ignore[attr-defined]
        event.stop()


class RubberBand(CellSurface):
    """エッジ新規作成中の仮線。overlay レイヤーに置き、ドラッグ中のみ表示する。"""

    _style = Style(color="#e0af68", bold=True)

    def set_line(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        self.load_buffer(OrthogonalRenderer().rasterize([route_to_point(start, end)]))

    def clear(self) -> None:
        self.load_buffer({})

    def cell_style(self, cell: Cell) -> Style:
        return self._style
