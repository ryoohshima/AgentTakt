from pathlib import Path

from agenttakt.tui.app import AgentTaktApp, load_plan
from agenttakt.tui.widgets.edge_layer import EdgeLayer
from agenttakt.tui.widgets.node import NodeWidget

SAMPLE = Path(__file__).parent.parent.parent / "examples" / "sample_plan.json"


async def test_editor_mounts_nodes_and_edges():
    app = AgentTaktApp(plan=load_plan(SAMPLE))
    async with app.run_test(size=(100, 32)):
        nodes = app.screen.query(NodeWidget)
        assert len(nodes) == 5
        edge_layer = app.screen.query_one(EdgeLayer)
        # 全ノードのポートと全エッジがセルバッファに焼き込まれている
        # （終端の矢印は同一入力ポートへの合流で重なり得るため ID の存在で確認する）
        cells = [cell for row in edge_layer._rows.values() for cell in row.values()]
        assert sum(1 for char, _ in cells if char == "●") == 5
        assert sum(1 for char, _ in cells if char == "○") == 5
        drawn_edges = {edge_id for _, edge_id in cells if edge_id is not None}
        assert drawn_edges == {"edge_1", "edge_2", "edge_3", "edge_4", "edge_5"}


def test_editor_snapshot(snap_compare):
    assert snap_compare(AgentTaktApp(plan=load_plan(SAMPLE)), terminal_size=(100, 32))
