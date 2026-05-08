"""Register concrete RuntimeAdapter implementations with the runtime registry.

Idempotent. CLI calls register_all() at startup. Tests do their own setup.
"""
from __future__ import annotations

from loom.runtimes import registry
from loom.runtimes.dify.adapter import DifyAdapter
from loom.runtimes.hiagent.adapter import HiagentAdapter


def register_all() -> None:
    if "hiagent" not in registry.list_targets():
        registry.register(HiagentAdapter())
    if "dify" not in registry.list_targets():
        registry.register(DifyAdapter())
