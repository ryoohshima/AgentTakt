from agenttakt.tui.geometry import Rect, route_orthogonal
from agenttakt.tui.widgets.renderers import BrailleRenderer, OrthogonalRenderer


def is_braille(char: str) -> bool:
    return 0x2800 <= ord(char) < 0x2900


def test_braille_renders_curve_between_ports():
    source = Rect(0, 0, 10, 3)
    target = Rect(30, 8, 10, 3)
    route = route_orthogonal("e1", source, target)
    buffer = BrailleRenderer().rasterize([route])

    chars = {char for char, _ in buffer.values()}
    assert "▶" in chars  # 終端矢印は視認性のため残す
    assert any(is_braille(char) for char in chars)
    assert all(edge_id == "e1" for _, edge_id in buffer.values())
    xs = [x for x, _ in buffer]
    assert min(xs) >= 11  # 出力ポートの右から始まる
    assert max(xs) <= 28  # 入力ポートの手前で終わる


def test_braille_backward_edge_renders():
    source = Rect(30, 0, 10, 3)
    target = Rect(4, 8, 10, 3)  # ターゲットが左（後退エッジ）
    route = route_orthogonal("e1", source, target)
    buffer = BrailleRenderer().rasterize([route])
    assert any(is_braille(char) for char, _ in buffer.values())
    assert all(x >= 0 and y >= 0 for x, y in buffer)


def test_braille_merges_dots_in_shared_cell():
    source = Rect(0, 0, 10, 3)
    up = Rect(30, 0, 10, 3)
    down = Rect(30, 8, 10, 3)
    routes = [
        route_orthogonal("e1", source, up),
        route_orthogonal("e2", source, down, channel=1),
    ]
    buffer = BrailleRenderer().rasterize(routes)
    edge_ids = {edge_id for _, edge_id in buffer.values()}
    assert edge_ids == {"e1", "e2"}


def test_orthogonal_renderer_unchanged():
    source = Rect(0, 0, 10, 3)
    target = Rect(30, 8, 10, 3)
    buffer = OrthogonalRenderer().rasterize([route_orthogonal("e1", source, target)])
    chars = {char for char, _ in buffer.values()}
    assert "▶" in chars
    assert chars & {"─", "│", "╭", "╮", "╰", "╯"}
