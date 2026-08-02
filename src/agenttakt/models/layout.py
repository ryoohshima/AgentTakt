from __future__ import annotations

from collections import defaultdict

from agenttakt.models.plan import Plan, Position

X_GAP = 36
Y_GAP = 8


def apply_auto_layout(plan: Plan) -> Plan:
    """position 欠落ノードに layered レイアウトで座標を補完する。

    依存の深さ（longest path）を層とし、`x = 層 * X_GAP`、`y = 層内の出現順 * Y_GAP`。
    position を持つノードは動かさない。plan は検証済み（DAG）である前提。
    """
    layer = {node.id: 0 for node in plan.nodes}
    successors: dict[str, list[str]] = defaultdict(list)
    indegree = {node.id: 0 for node in plan.nodes}
    for edge in plan.edges:
        successors[edge.source].append(edge.target)
        indegree[edge.target] += 1

    queue = [node.id for node in plan.nodes if indegree[node.id] == 0]
    while queue:
        node_id = queue.pop()
        for succ in successors[node_id]:
            layer[succ] = max(layer[succ], layer[node_id] + 1)
            indegree[succ] -= 1
            if indegree[succ] == 0:
                queue.append(succ)

    row_count: dict[int, int] = defaultdict(int)
    for node in plan.nodes:
        if node.position is None:
            depth = layer[node.id]
            node.position = Position(x=depth * X_GAP, y=row_count[depth] * Y_GAP)
            row_count[depth] += 1
    return plan
