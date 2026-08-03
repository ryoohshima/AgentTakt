"""エッジの経路計算（geometry）。文字化（painting）は widgets/edge_layer.py が担う。

座標系はキャンバスの端末セル単位（x: 列, y: 行, y は下方向が正)。
"""

from __future__ import annotations

from dataclasses import dataclass

# モデル座標 → キャンバス座標のオフセット（入力ポート ○ が左端で見切れないため）
PAD_X = 2
PAD_Y = 1


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        """右端の外側（exclusive）の列。"""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2


@dataclass(frozen=True)
class Route:
    """直交ポリライン。points は頂点列（両端含む）。"""

    edge_id: str
    points: tuple[tuple[int, int], ...]


def output_port(rect: Rect) -> tuple[int, int]:
    """出力ポート ● のセル（ノード右辺のすぐ外）。"""
    return rect.right, rect.center_y


def input_port(rect: Rect) -> tuple[int, int]:
    """入力ポート ○ のセル（ノード左辺のすぐ外）。"""
    return rect.x - 1, rect.center_y


def route_orthogonal(edge_id: str, source: Rect, target: Rect, channel: int = 0) -> Route:
    """出力ポート → 入力ポートの直交経路を返す。

    channel は同一始点からの複数エッジの垂直区間をずらすオフセット。
    """
    sx, sy = output_port(source)
    tx, ty = input_port(target)
    start = (sx + 1, sy)
    end = (tx - 1, ty)

    if sy == ty and end[0] >= start[0]:
        points = (start, end)
    elif end[0] - start[0] >= 2:
        # 右へ伸ばし、垂直チャネルを経由して入力ポートへ
        xm = max(start[0] + 1, min(start[0] + 1 + channel, end[0] - 1))
        points = (start, (xm, sy), (xm, ty), end)
    else:
        # 後退エッジ: 両ノードの下を回り込む
        x_right = start[0] + 1 + channel
        x_left = end[0] - 1 - channel
        ym = max(source.bottom, target.bottom) + 1 + channel
        points = (start, (x_right, sy), (x_right, ym), (x_left, ym), (x_left, ty), end)
    return Route(edge_id, points)


def route_to_point(
    start: tuple[int, int], end: tuple[int, int], edge_id: str = "__rubber__"
) -> Route:
    """出力ポートから任意のセルへの仮経路（ラバーバンド用）。"""
    sx, sy = start
    ex, ey = end
    if sy == ey:
        points = (start, end)
    else:
        xm = max(sx + 1, (sx + ex) // 2) if ex > sx + 1 else sx + 1
        points = (start, (xm, sy), (xm, ey), end)
    return Route(edge_id, points)
