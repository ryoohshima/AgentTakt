from __future__ import annotations

import json
import zlib

from textual.widgets import Static

from agenttakt.models.plan import Node
from agenttakt.tui.geometry import Rect

# type 別の色分けパレット（決定的に割り当てる）
_PALETTE = ["#7aa2f7", "#9ece6a", "#e0af68", "#bb9af7", "#f7768e", "#7dcfff", "#ff9e64"]

_MAX_DATA_LINES = 3
_MAX_LINE_WIDTH = 26
_MIN_WIDTH = 18
_MAX_WIDTH = 32


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
    """計画の 1 ステップを表す角丸ノード。タイトルは上辺、type は下辺に表示する。"""

    def __init__(self, node: Node) -> None:
        super().__init__("\n".join(summarize_data(node.data)))
        self.node = node
        self.border_title = node.title
        self.border_subtitle = node.type

    def on_mount(self) -> None:
        self.styles.border = ("round", type_color(self.node.type))

    @property
    def rect(self) -> Rect:
        """キャンバス座標系での外形矩形（offset とサイズから算出）。"""
        offset = self.styles.offset
        width, height = node_size(self.node)
        return Rect(int(offset.x.value), int(offset.y.value), width, height)
