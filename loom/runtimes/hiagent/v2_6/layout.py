"""Auto-layout for Hiagent workflow nodes.

Per ADR 0024 §Node emission contract: every node carries `Layout: {X, Y}`.
We compute it via topological-sort + grid layout:

  - Group nodes by topological depth [longest path from any root]
  - Same-depth nodes share a column [X = depth * 300]
  - Within a column, distribute vertically centered around Y=0
  - Branch and merge nodes get bumped to keep the graph readable
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

COLUMN_WIDTH = 300.0
ROW_HEIGHT = 200.0


class LayoutError(ValueError):
    pass


def topological_layout(
    node_ids: Iterable[str],
    edges: Iterable[tuple[str, str]],
) -> dict[str, tuple[float, float]]:
    """Return {node_id: (X, Y)} positions for the given graph.

    Args:
      node_ids: iterable of all node IDs in the graph [order does not matter]
      edges: iterable of (from_id, to_id) tuples; cycles raise LayoutError

    Raises:
      LayoutError if the graph contains a cycle [Hiagent workflows are DAGs
      except for explicit Loop nodes whose body is laid out independently]
    """
    nodes = list(node_ids)
    parents: dict[str, list[str]] = defaultdict(list)
    children: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        children[src].append(dst)
        parents[dst].append(src)

    # Topological sort [Kahn]; raise on cycle
    in_degree = {n: len(parents[n]) for n in nodes}
    ready = [n for n in nodes if in_degree[n] == 0]
    order: list[str] = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for c in children[n]:
            in_degree[c] -= 1
            if in_degree[c] == 0:
                ready.append(c)
    if len(order) != len(nodes):
        raise LayoutError("graph contains a cycle; cannot layout")

    # Depth [longest path from a root]
    depth: dict[str, int] = {}
    for n in order:
        if not parents[n]:
            depth[n] = 0
        else:
            depth[n] = max(depth[p] for p in parents[n]) + 1

    # Group by depth, distribute vertically
    column: dict[int, list[str]] = defaultdict(list)
    for n in nodes:
        column[depth[n]].append(n)

    positions: dict[str, tuple[float, float]] = {}
    for col, ns in column.items():
        x = col * COLUMN_WIDTH
        # Center vertically: span from -h/2 to +h/2
        h = (len(ns) - 1) * ROW_HEIGHT
        y0 = -h / 2.0
        for i, n in enumerate(sorted(ns)):  # stable order for tests
            positions[n] = (x, y0 + i * ROW_HEIGHT)
    return positions
