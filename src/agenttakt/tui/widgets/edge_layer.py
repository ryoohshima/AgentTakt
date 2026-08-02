"""エッジとポートの描画レイヤー（painting）。

geometry が計算した Route をセルバッファに焼き込み、render_line() は
バッファから Strip を組むだけにする（描画のたびに経路計算しない）。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widget import Widget

from agenttakt.models.plan import Edge
from agenttakt.tui.geometry import Rect, Route, input_port, output_port, route_orthogonal

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


class EdgeLayer(Widget):
    """キャンバス全面に敷く最背面レイヤー。エッジ線とポート ○/● を描く。"""

    DEFAULT_CSS = """
    EdgeLayer {
        width: auto;
        height: auto;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._rows: dict[int, dict[int, Cell]] = {}
        self._edge_style = Style(color="#565f89")
        self._port_style = Style(color="#7aa2f7", bold=True)
        self.can_focus = False

    def set_graph(self, rects: dict[str, Rect], edges: list[Edge]) -> None:
        """ノード矩形とエッジからセルバッファを再構築する。"""
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
        for rect in rects.values():
            buffer[output_port(rect)] = ("●", None)
            buffer[input_port(rect)] = ("○", None)

        rows: dict[int, dict[int, Cell]] = defaultdict(dict)
        for (x, y), cell in buffer.items():
            rows[y][x] = cell
        self._rows = dict(rows)
        self.refresh()

    def edge_at(self, x: int, y: int) -> str | None:
        """セル座標にあるエッジ ID（ヒットテスト用）。"""
        cell = self._rows.get(y, {}).get(x)
        return cell[1] if cell else None

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
            char, edge_id = cells[x]
            style = self._port_style if edge_id is None else self._edge_style
            segments.append(Segment(char, style))
            cursor = x + 1
        if cursor < width:
            segments.append(Segment(" " * (width - cursor)))
        return Strip(segments, width)
