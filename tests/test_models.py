import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agenttakt.models import Plan, apply_auto_layout
from agenttakt.models.layout import X_GAP, Y_GAP

EXAMPLES = Path(__file__).parent.parent / "examples"


def make_plan(nodes, edges, **kwargs):
    return {
        "graph_id": "test",
        "nodes": nodes,
        "edges": edges,
        **kwargs,
    }


def node(node_id, **kwargs):
    return {"id": node_id, "type": "task", "title": node_id, **kwargs}


def edge(edge_id, source, target):
    return {"id": edge_id, "source": source, "target": target}


class TestPlanValidation:
    def test_valid_plan(self):
        plan = Plan.model_validate(
            make_plan([node("a"), node("b")], [edge("e1", "a", "b")])
        )
        assert plan.status == "pending_approval"
        assert [n.id for n in plan.nodes] == ["a", "b"]

    def test_sample_plan_is_valid(self):
        raw = json.loads((EXAMPLES / "sample_plan.json").read_text())
        plan = Plan.model_validate(raw)
        assert plan.graph_id == "sample-auth-refactor"
        assert len(plan.nodes) == 5

    def test_duplicate_node_ids(self):
        with pytest.raises(ValidationError, match=r"duplicate node ids: \['a'\]"):
            Plan.model_validate(make_plan([node("a"), node("a")], []))

    def test_duplicate_edge_ids(self):
        with pytest.raises(ValidationError, match=r"duplicate edge ids: \['e1'\]"):
            Plan.model_validate(
                make_plan(
                    [node("a"), node("b"), node("c")],
                    [edge("e1", "a", "b"), edge("e1", "b", "c")],
                )
            )

    def test_unknown_edge_endpoint(self):
        with pytest.raises(ValidationError, match=r"edge 'e1' references unknown node\(s\): \['ghost'\]"):
            Plan.model_validate(make_plan([node("a")], [edge("e1", "a", "ghost")]))

    def test_cycle_detected(self):
        with pytest.raises(ValidationError, match="cycle detected") as exc_info:
            Plan.model_validate(
                make_plan(
                    [node("a"), node("b"), node("c")],
                    [edge("e1", "a", "b"), edge("e2", "b", "c"), edge("e3", "c", "a")],
                )
            )
        # 閉路の経路がメッセージに含まれる（Executor の自己修正材料）
        message = str(exc_info.value)
        assert "a -> " in message and message.count("->") == 3

    def test_self_loop_is_cycle(self):
        with pytest.raises(ValidationError, match="cycle detected: a -> a"):
            Plan.model_validate(make_plan([node("a")], [edge("e1", "a", "a")]))

    def test_extra_fields_round_trip(self):
        raw = make_plan(
            [node("a", cost_estimate=42)],
            [],
            executor_meta={"session": "xyz"},
        )
        plan = Plan.model_validate(raw)
        dumped = plan.model_dump()
        assert dumped["executor_meta"] == {"session": "xyz"}
        assert dumped["nodes"][0]["cost_estimate"] == 42


class TestAutoLayout:
    def test_layers_follow_dependency_depth(self):
        plan = Plan.model_validate(
            make_plan(
                [node("a"), node("b"), node("c")],
                [edge("e1", "a", "b"), edge("e2", "b", "c")],
            )
        )
        apply_auto_layout(plan)
        xs = {n.id: n.position.x for n in plan.nodes}
        assert xs == {"a": 0, "b": X_GAP, "c": 2 * X_GAP}

    def test_same_layer_nodes_stack_vertically(self):
        plan = Plan.model_validate(
            make_plan(
                [node("a"), node("b"), node("c")],
                [edge("e1", "a", "b"), edge("e2", "a", "c")],
            )
        )
        apply_auto_layout(plan)
        positions = {n.id: (n.position.x, n.position.y) for n in plan.nodes}
        assert positions["b"] == (X_GAP, 0)
        assert positions["c"] == (X_GAP, Y_GAP)

    def test_existing_position_is_kept(self):
        plan = Plan.model_validate(
            make_plan(
                [node("a", position={"x": 7, "y": 9}), node("b")],
                [edge("e1", "a", "b")],
            )
        )
        apply_auto_layout(plan)
        assert (plan.nodes[0].position.x, plan.nodes[0].position.y) == (7, 9)
        assert plan.nodes[1].position is not None

    def test_deterministic(self):
        raw = make_plan(
            [node("a"), node("b"), node("c"), node("d")],
            [edge("e1", "a", "c"), edge("e2", "b", "c"), edge("e3", "c", "d")],
        )
        first = apply_auto_layout(Plan.model_validate(raw))
        second = apply_auto_layout(Plan.model_validate(raw))
        assert first.model_dump() == second.model_dump()
