from __future__ import annotations

import json
import zlib

from textual import events
from textual.geometry import Offset
from textual.widgets import Static

from agenttakt.models.plan import Node, Position
from agenttakt.tui.geometry import PAD_X, PAD_Y, Rect

# type 別の色分けパレット（決定的に割り当てる）
_PALETTE = ["#7aa2f7", "#9ece6a", "#e0af68", "#bb9af7", "#f7768e", "#7dcfff", "#ff9e64"]

_MAX_DATA_LINES = 3
_MAX_LINE_WIDTH = 26
_MIN_WIDTH = 18
_MAX_WIDTH = 32

_SELECTED_BORDER = ("heavy", "#c0caf5")


def type_color(node_type: str) -> str:
    return _PALETTE[zlib.crc32(node_type.encode()) % len(_PALETTE)]


def summarize_data(data: dict) -> list[str]:
    lines = []
    for key, value in list(data.items())[:_MAX_DATA_LINES]:
        rendered = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        line = f"{key}: {rendered}"
        if len(line) > _MAX_LINE_WIDTH:
            line = line[: _MAX_LINE_WIDTH - 1] + "…"
        lines.append(line)
    return lines


def node_size(node: Node) -> tuple[int, int]:
    """境界線・パディング込みの外形サイズ（幅, 高さ）。"""
    lines = summarize_data(node.data)
    content_width = max(
        [len(node.title) + 2, len(node.type) + 2, *(len(line) for line in lines)] or [0]
    )
    width = min(max(content_width + 4, _MIN_WIDTH), _MAX_WIDTH)
    height = max(len(lines), 1) + 2
    return width, height


class NodeWidget(Static):
    """計画の 1 ステップを表す角丸ノード。

    ドラッグで移動、右辺（出力ポート側）からのドラッグでエッジ作成を開始する。
    ポート判定はセル解像度が粗いため右辺 1 列全体に拡大している。
    """

    def __init__(self, node: Node) -> None:
        super().__init__("\n".join(summarize_data(node.data)))
        self.node = node
        self.border_title = node.title
        self.border_subtitle = node.type
        self._selected = False
        # None | "move" | "edge"
        self._mode: str | None = None
        self._press_screen = Offset(0, 0)
        self._origin = Offset(0, 0)
        self._moved = False

    def on_mount(self) -> None:
        self._apply_border()

    def refresh_content(self) -> None:
        """モデル変更（title / type / data）を表示へ反映する。"""
        self.border_title = self.node.title
        self.border_subtitle = self.node.type
        self.update("\n".join(summarize_data(self.node.data)))
        self._apply_border()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_border()

    def _apply_border(self) -> None:
        if self._selected:
            self.styles.border = _SELECTED_BORDER
        else:
            self.styles.border = ("round", type_color(self.node.type))

    @property
    def rect(self) -> Rect:
        """キャンバス座標系での外形矩形（offset とサイズから算出）。"""
        offset = self.styles.offset
        width, height = node_size(self.node)
        return Rect(int(offset.x.value), int(offset.y.value), width, height)

    def _canvas_pos(self, event: events.MouseEvent) -> tuple[int, int]:
        rect = self.rect
        return rect.x + event.offset.x, rect.y + event.offset.y

    # --- マウス操作 ---

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 1:
            return
        self._press_screen = Offset(event.screen_x, event.screen_y)
        # event.offset は外形（境界線込み）基準のため outer_size と比較する
        if event.offset.x >= self.outer_size.width - 1:
            self._mode = "edge"
            self.screen.start_edge_drag(self.node.id)  # type: ignore[attr-defined]
        else:
            self._mode = "move"
            self._origin = Offset(self.rect.x, self.rect.y)
            self._moved = False
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._mode is None:
            return
        if self._mode == "edge":
            self.screen.update_edge_drag(self._canvas_pos(event))  # type: ignore[attr-defined]
            return
        # 画面絶対座標の差分で移動量を計算する（ウィジェット相対だと基準が動く）
        delta = Offset(event.screen_x, event.screen_y) - self._press_screen
        if delta:
            self._moved = True
        new_x = max(PAD_X, self._origin.x + delta.x)
        new_y = max(PAD_Y, self._origin.y + delta.y)
        self.styles.offset = (new_x, new_y)
        self.node.position = Position(x=new_x - PAD_X, y=new_y - PAD_Y)
        self.screen.redraw_edges()  # type: ignore[attr-defined]

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._mode is None:
            return
        mode, self._mode = self._mode, None
        self.release_mouse()
        event.stop()
        if mode == "edge":
            self.screen.finish_edge_drag(self._canvas_pos(event))  # type: ignore[attr-defined]
        elif self._moved:
            self.screen.refresh_graph()  # type: ignore[attr-defined]
        else:
            self.screen.select_node(self.node.id)  # type: ignore[attr-defined]
