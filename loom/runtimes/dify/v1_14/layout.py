"""Simple topological layout for Dify React Flow graphs."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

COLUMN_WIDTH = 350.0
ROW_HEIGHT = 200.0


def topological_layout(
    node_ids: Iterable[str],
    edges: Iterable[tuple[str, str]],
) -> dict[str, dict[str, float]]:
    nodes = list(node_ids)
    parents: dict[str, list[str]] = defaultdict(list)
    children: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        children[src].append(dst)
        parents[dst].append(src)

    in_degree = {node_id: len(parents[node_id]) for node_id in nodes}
    ready = deque(node_id for node_id in nodes if in_degree[node_id] == 0)
    order: list[str] = []
    while ready:
        node_id = ready.popleft()
        order.append(node_id)
        for child in children[node_id]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                ready.append(child)
    if len(order) != len(nodes):
        order = nodes

    depth: dict[str, int] = {}
    for node_id in order:
        depth[node_id] = max((depth.get(parent, 0) + 1 for parent in parents[node_id]), default=0)

    columns: dict[int, list[str]] = defaultdict(list)
    for node_id in nodes:
        columns[depth[node_id]].append(node_id)

    positions: dict[str, dict[str, float]] = {}
    for col, col_nodes in columns.items():
        for row, node_id in enumerate(col_nodes):
            positions[node_id] = {"x": col * COLUMN_WIDTH, "y": row * ROW_HEIGHT}
    return positions
