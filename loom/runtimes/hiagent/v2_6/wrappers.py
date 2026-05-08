"""Synthesis wrappers for IR -> Hiagent v2.6 cells that need transformation.

After ADR 0024 rewrite, most wrappers degenerate into the per-node emit
functions [compiler_nodes.py] because Hiagent natively supports more IR
primitives than Dify. This module is reserved for the lossy cases:

  - parallel: emits children inline with a TODO marker [v1 ship; v1.1
    proper VariableAggregator implementation pending IR extension]
  - subworkflow_call_pending: placeholder; IR has no subworkflow node
    in v0.3 [ADR 0024 §IR-Hiagent mapping notes the gap]

Anything else has its emission inlined in compiler_nodes.py for clarity.
"""
from __future__ import annotations

# Currently empty per ADR 0024 §IR-Hiagent mapping; wrappers grow as we
# learn from real customer imports.
