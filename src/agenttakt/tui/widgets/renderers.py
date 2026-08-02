"""エッジ経路をセルバッファへ焼き込むレンダラ群。

- OrthogonalRenderer: 角丸 box-drawing 直角線（軽量・フォールバック）
- BrailleRenderer: braille ドット（セルあたり 2x4）による Bezier 曲線（既定）
"""

from __future__ import annotations

from typing import Iterable

from agenttakt.tui.geometry import Route

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
    """角丸 box-drawing 直角線のレンダラ。"""

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


# braille ドット位置 (x∈{0,1}, y∈{0..3}) → ビット（U+2800 からのオフセット）
_DOT_BITS = {
    (0, 0): 0x01,
    (0, 1): 0x02,
    (0, 2): 0x04,
    (0, 3): 0x40,
    (1, 0): 0x08,
    (1, 1): 0x10,
    (1, 2): 0x20,
    (1, 3): 0x80,
}


class BrailleRenderer:
    """3 次 Bezier 曲線を braille ドットにラスタライズするレンダラ。

    セル解像度の 2 倍（横）× 4 倍（縦）のドット空間で曲線をサンプリングし、
    同一セルに落ちたドットをビット合成して braille 文字にする。
    経路の始点・終点のみ使い、中間頂点（直交ルート用）は無視する。
    """

    def rasterize(self, routes: Iterable[Route]) -> dict[tuple[int, int], Cell]:
        # セル → [ビット, edge_id]（同一セルに複数エッジが落ちたら先勝ちの id を保持）
        cells: dict[tuple[int, int], list] = {}
        arrows: list[tuple[tuple[int, int], str]] = []
        for route in routes:
            start = route.points[0]
            end = route.points[-1]
            self._draw_bezier(cells, start, end, route.edge_id)
            arrows.append((end, route.edge_id))

        buffer: dict[tuple[int, int], Cell] = {
            cell: (chr(0x2800 + bits), edge_id)
            for cell, (bits, edge_id) in cells.items()
        }
        for cell, edge_id in arrows:
            buffer[cell] = ("▶", edge_id)  # 終端は視認性のため矢印にする
        return buffer

    @staticmethod
    def _draw_bezier(
        cells: dict[tuple[int, int], list],
        start: tuple[int, int],
        end: tuple[int, int],
        edge_id: str,
    ) -> None:
        # セル座標 → ドット座標（セルの垂直中央にアンカー）
        x0, y0 = start[0] * 2, start[1] * 4 + 2
        x1, y1 = end[0] * 2 + 1, end[1] * 4 + 2
        # 水平方向の張り出し量。後退エッジでも S 字を描けるよう距離に応じて伸ばす
        reach = max(6.0, abs(x1 - x0) * 0.5)
        cx0, cy0 = x0 + reach, float(y0)
        cx1, cy1 = x1 - reach, float(y1)

        steps = max(24, int((abs(x1 - x0) + abs(y1 - y0)) * 1.5))
        for i in range(steps + 1):
            t = i / steps
            u = 1.0 - t
            dot_x = round(
                u**3 * x0 + 3 * u**2 * t * cx0 + 3 * u * t**2 * cx1 + t**3 * x1
            )
            dot_y = round(
                u**3 * y0 + 3 * u**2 * t * cy0 + 3 * u * t**2 * cy1 + t**3 * y1
            )
            if dot_x < 0 or dot_y < 0:
                continue
            cell = (dot_x // 2, dot_y // 4)
            bit = _DOT_BITS[(dot_x % 2, dot_y % 4)]
            entry = cells.get(cell)
            if entry is None:
                cells[cell] = [bit, edge_id]
            else:
                entry[0] |= bit
