"""エッジとポートの描画レイヤー（painting）。

geometry が計算した Route をセルバッファに焼き込み、render_line() は
バッファから Strip を組むだけにする（描画のたびに経路計算しない）。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.strip import Strip
from textual.widget import Widget

from agenttakt.models.plan import Edge
from agenttakt.tui.geometry import (
    Rect,
    Route,
    input_port,
    output_port,
    route_orthogonal,
    route_to_point,
)

# セル = (文字, edge_id)。edge_id が None のセルはポート。
Cell = tuple[str, str | None]

_OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}

# セルが接続する 2 辺 → box-drawing 文字
_CHAR_FOR_SIDES = {
    frozenset({"E", "W"}): "─",
    frozenset({"N", "S"}): "│",
    frozenset({"S", "E"}): "╭",
    frozenset({"S", "W"}): "╮",
    frozenset({"N", "E"}): "╰",
    frozenset({"N", "W"}): "╯",
}


def _direction(a: tuple[int, int], b: tuple[int, int]) -> str:
    if b[0] > a[0]:
        return "E"
    if b[0] < a[0]:
        return "W"
    if b[1] > a[1]:
        return "S"
    return "N"


class OrthogonalRenderer:
    """角丸 box-drawing 直角線のレンダラ。将来 braille 曲線レンダラに差し替え可能。"""

    def rasterize(self, routes: Iterable[Route]) -> dict[tuple[int, int], Cell]:
        buffer: dict[tuple[int, int], Cell] = {}
        for route in routes:
            points = [
                p for i, p in enumerate(route.points) if i == 0 or p != route.points[i - 1]
            ]
            if len(points) == 1:
                buffer[points[0]] = ("▶", route.edge_id)
                continue

            # セグメントの中間セルを直線文字で埋める
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                if y0 == y1:
                    for x in range(min(x0, x1) + 1, max(x0, x1)):
                        buffer[(x, y0)] = ("─", route.edge_id)
                else:
                    for y in range(min(y0, y1) + 1, max(y0, y1)):
                        buffer[(x0, y)] = ("│", route.edge_id)

            # 頂点セル: 前後の向きから文字を決める
            for i, point in enumerate(points):
                if i == len(points) - 1:
                    char = "▶"  # 終端は入力ポートへの矢印
                elif i == 0:
                    outgoing = _direction(point, points[1])
                    char = "─" if outgoing in "EW" else "│"
                else:
                    incoming = _direction(points[i - 1], point)
                    outgoing = _direction(point, points[i + 1])
                    char = _CHAR_FOR_SIDES[frozenset({_OPPOSITE[incoming], outgoing})]
                buffer[point] = (char, route.edge_id)
        return buffer


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

    def set_graph(self, rects: dict[str, Rect], edges: list[Edge]) -> None:
        """ノード矩形とエッジからセルバッファとポート表を再構築する。"""
        renderer = OrthogonalRenderer()
        per_source: dict[str, int] = defaultdict(int)
        routes = []
        for edge in edges:
            channel = per_source[edge.source]
            per_source[edge.source] += 1
            routes.append(
                route_orthogonal(edge.id, rects[edge.source], rects[edge.target], channel)
            )
        buffer = renderer.rasterize(routes)
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
