from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Position(BaseModel):
    """TUI 上の表示座標（端末セル単位）。"""

    x: int
    y: int


class Node(BaseModel):
    # Executor 独自フィールドをラウンドトリップ保持するため extra を許容する
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    title: str
    data: dict[str, Any] = Field(default_factory=dict)
    position: Position | None = None


class Edge(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    source: str
    target: str


PlanStatus = Literal["pending_approval", "approved", "rejected"]


class Plan(BaseModel):
    model_config = ConfigDict(extra="allow")

    graph_id: str
    status: PlanStatus = "pending_approval"
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_graph(self) -> Plan:
        # エラーメッセージには必ず対象 ID を含める（Executor が自己修正できるように）
        dup_nodes = _duplicates(n.id for n in self.nodes)
        if dup_nodes:
            raise ValueError(f"duplicate node ids: {dup_nodes}")

        dup_edges = _duplicates(e.id for e in self.edges)
        if dup_edges:
            raise ValueError(f"duplicate edge ids: {dup_edges}")

        known = {n.id for n in self.nodes}
        for edge in self.edges:
            unknown = [ref for ref in (edge.source, edge.target) if ref not in known]
            if unknown:
                raise ValueError(f"edge '{edge.id}' references unknown node(s): {unknown}")

        cycle = find_cycle(
            [n.id for n in self.nodes],
            [(e.source, e.target) for e in self.edges],
        )
        if cycle:
            raise ValueError("plan must be a DAG; cycle detected: " + " -> ".join(cycle))
        return self


def _duplicates(ids: Iterable[str]) -> list[str]:
    return sorted(value for value, count in Counter(ids).items() if count > 1)


def find_cycle(node_ids: list[str], edges: list[tuple[str, str]]) -> list[str] | None:
    """サイクルを 1 つ探し、閉路のノード列（先頭 = 末尾）を返す。無ければ None。

    Kahn 法でトポロジカルソートし、除去しきれなかったノードから閉路を復元する。
    """
    indegree = {node: 0 for node in node_ids}
    successors: dict[str, list[str]] = {node: [] for node in node_ids}
    for source, target in edges:
        successors[source].append(target)
        indegree[target] += 1

    queue = [node for node in node_ids if indegree[node] == 0]
    removed = 0
    while queue:
        node = queue.pop()
        removed += 1
        for succ in successors[node]:
            indegree[succ] -= 1
            if indegree[succ] == 0:
                queue.append(succ)

    if removed == len(node_ids):
        return None

    # 残存ノードは必ず残存ノードからの入力辺を持つため、前任者を辿れば有限歩で
    # 既訪問ノードに戻り閉路が確定する
    remaining = {node for node in node_ids if indegree[node] > 0}
    predecessor: dict[str, str] = {}
    for source, target in edges:
        if source in remaining and target in remaining:
            predecessor.setdefault(target, source)

    visited_at: dict[str, int] = {}
    path: list[str] = []
    node = min(remaining)  # 決定性のため辞書順で開始
    while node not in visited_at:
        visited_at[node] = len(path)
        path.append(node)
        node = predecessor[node]

    cycle = list(reversed(path[visited_at[node]:]))
    cycle.append(cycle[0])
    return cycle
