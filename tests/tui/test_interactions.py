import json

from agenttakt.models import Plan
from agenttakt.tui.app import AgentTaktApp
from agenttakt.tui.widgets.edge_layer import EdgeLayer
from agenttakt.tui.widgets.node import NodeWidget
from agenttakt.tui.widgets.param_panel import ParamPanel

from textual.widgets import Input

SIZE = (120, 40)


def build_plan() -> Plan:
    return Plan.model_validate(
        {
            "graph_id": "interaction-test",
            "nodes": [
                {
                    "id": "a",
                    "type": "grep",
                    "title": "A",
                    "position": {"x": 0, "y": 0},
                    "data": {"pattern": "useAuth", "files": ["src/**"]},
                },
                {"id": "b", "type": "edit", "title": "B", "position": {"x": 40, "y": 0}},
                {"id": "c", "type": "test", "title": "C", "position": {"x": 40, "y": 10}},
            ],
            "edges": [{"id": "e1", "source": "a", "target": "b"}],
        }
    )


def make_app(**kwargs) -> AgentTaktApp:
    return AgentTaktApp(plan=build_plan(), **kwargs)


async def test_click_selects_node():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        node_a = editor._node_widget("a")
        await pilot.click(node_a, offset=(4, 1))
        assert editor._selected == ("node", "a")
        # 選択でパラメータパネルに値が載る
        assert app.screen.query_one("#panel-title", Input).value == "A"


async def test_drag_moves_node():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        node_a = editor._node_widget("a")
        # ドラッグ中はウィジェット自体が動くため、目標位置は画面絶対座標で指定する
        down_screen = node_a.region.offset
        target = (down_screen.x + 4 + 6, down_screen.y + 1 + 3)  # +6 列, +3 行
        await pilot.mouse_down(node_a, offset=(4, 1))
        await pilot.hover(None, offset=target)
        await pilot.mouse_up(None, offset=target)
        assert (node_a.node.position.x, node_a.node.position.y) == (6, 3)


async def test_rubberband_creates_edge():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        node_a = editor._node_widget("a")
        node_c = editor._node_widget("c")
        right_column = node_a.rect.width - 1
        await pilot.mouse_down(node_a, offset=(right_column, 1))
        await pilot.hover(node_c, offset=(3, 1))
        await pilot.mouse_up(node_c, offset=(3, 1))
        assert any(e.source == "a" and e.target == "c" for e in editor.plan.edges)


async def test_edge_drag_preview_merges_into_edge_layer():
    """仮線は EdgeLayer に合成され、前面レイヤーで既存描画を覆い隠さない。"""
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        node_a = editor._node_widget("a")
        node_c = editor._node_widget("c")
        edge_layer = app.screen.query_one(EdgeLayer)
        await pilot.mouse_down(node_a, offset=(node_a.rect.width - 1, 1))
        await pilot.hover(node_c, offset=(3, 1))
        assert edge_layer._preview_rows  # 仮線が描かれている
        assert edge_layer._rows  # 既存エッジ・ポートのバッファも残っている
        await pilot.mouse_up(node_c, offset=(3, 1))
        assert not edge_layer._preview_rows  # ドロップで消える


async def test_create_edge_rejects_cycle():
    app = make_app()
    async with app.run_test(size=SIZE):
        editor = app.screen
        editor.create_edge("b", "a")  # a→b が既にあるため循環
        assert [e.id for e in editor.plan.edges] == ["e1"]


async def test_create_edge_rejects_duplicate():
    app = make_app()
    async with app.run_test(size=SIZE):
        editor = app.screen
        editor.create_edge("a", "b")
        assert [e.id for e in editor.plan.edges] == ["e1"]


async def test_delete_node_cascades_edges():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        editor.select_node("a")
        await pilot.press("d")
        assert [n.id for n in editor.plan.nodes] == ["b", "c"]
        assert editor.plan.edges == []
        assert editor._node_widget("a") is None


async def test_delete_selected_edge():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        editor.select_edge("e1")
        await pilot.press("d")
        assert editor.plan.edges == []
        assert len(editor.plan.nodes) == 3


async def test_add_node():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        await pilot.press("n")
        assert len(editor.plan.nodes) == 4
        new_node = editor.plan.nodes[-1]
        assert new_node.id == "node_1"
        assert editor._selected == ("node", new_node.id)


async def test_nudge_moves_selected_node():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        editor.select_node("a")
        await pilot.press("right")
        await pilot.press("down")
        node = editor._node_widget("a").node
        assert (node.position.x, node.position.y) == (1, 1)


async def test_param_edit_updates_node():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        editor.select_node("a")
        await pilot.pause()
        title_input = app.screen.query_one("#panel-title", Input)
        title_input.value = "Renamed Step"
        await pilot.pause()
        widget = editor._node_widget("a")
        assert widget.node.title == "Renamed Step"
        assert widget.border_title == "Renamed Step"


async def test_param_data_fields_split_by_key():
    """data は JSON 直書きではなく、キーごとの入力欄で編集できる。"""
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        editor.select_node("a")
        await pilot.pause()
        fields = {
            field.name: field
            for field in app.screen.query("#panel-data-fields Input").results(Input)
        }
        assert set(fields) == {"pattern", "files"}
        # 文字列値はそのまま編集して反映される
        fields["pattern"].value = "signIn"
        await pilot.pause()
        assert editor._node_widget("a").node.data["pattern"] == "signIn"
        # リスト値は JSON 断片として parse されて反映される
        fields["files"].value = '["app/**", "lib/**"]'
        await pilot.pause()
        assert editor._node_widget("a").node.data["files"] == ["app/**", "lib/**"]


async def test_param_data_add_new_key():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        editor.select_node("a")
        await pilot.pause()
        new_key = app.screen.query_one("#panel-data-new-key", Input)
        new_key.focus()
        new_key.value = "timeout"
        await pilot.press("enter")
        await pilot.pause()
        assert editor._node_widget("a").node.data["timeout"] == ""
        names = {
            field.name for field in app.screen.query("#panel-data-fields Input").results(Input)
        }
        assert "timeout" in names


async def test_approve_writes_out_file(tmp_path):
    out = tmp_path / "edited.json"
    app = make_app(out_path=str(out))
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("a")
        await pilot.pause()
        await pilot.click("#ok")
        await pilot.pause()
    data = json.loads(out.read_text())
    assert data["status"] == "approved"
    assert data["graph_id"] == "interaction-test"


async def test_reject_with_reason(tmp_path):
    out = tmp_path / "edited.json"
    app = make_app(out_path=str(out))
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("r")
        await pilot.pause()
        reason_input = app.screen.query_one("#reject-reason", Input)
        reason_input.value = "手順が不足"
        await pilot.click("#ok")
        await pilot.pause()
    data = json.loads(out.read_text())
    assert data["status"] == "rejected"


async def test_undo_redo_delete():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        editor.select_node("a")
        await pilot.press("d")
        assert len(editor.plan.nodes) == 2
        await pilot.press("u")  # undo
        await pilot.pause()
        assert len(editor.plan.nodes) == 3
        assert editor._node_widget("a") is not None
        assert len(editor.plan.edges) == 1
        await pilot.press("U")  # redo
        await pilot.pause()
        assert len(editor.plan.nodes) == 2
        assert editor.plan.edges == []


async def test_undo_edge_creation():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        editor.create_edge("a", "c")
        assert len(editor.plan.edges) == 2
        await pilot.press("u")
        await pilot.pause()
        assert [e.id for e in editor.plan.edges] == ["e1"]


async def test_escape_deselects():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        editor = app.screen
        editor.select_node("a")
        assert editor._selected == ("node", "a")
        await pilot.press("escape")
        await pilot.pause()
        assert editor._selected is None
        # エッジ選択も解除できる
        editor.select_edge("e1")
        await pilot.press("escape")
        await pilot.pause()
        assert editor._selected is None


async def test_help_screen_opens_and_closes():
    from agenttakt.tui.screens.help import HelpScreen

    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


async def test_panel_toggle():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        panel = app.screen.query_one(ParamPanel)
        assert panel.styles.display == "block"
        await pilot.press("p")
        assert panel.styles.display == "none"
        await pilot.press("p")
        assert panel.styles.display == "block"
