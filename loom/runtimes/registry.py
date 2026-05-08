from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from loom.runtimes.base import RuntimeAdapter

Target = Literal["hiagent", "dify"]


class UnknownTargetError(KeyError):
    """Target name is not registered."""


_REGISTRY: dict[str, RuntimeAdapter] = {}


def register(adapter: RuntimeAdapter) -> None:
    _REGISTRY[adapter.target] = adapter


def unregister(target: str) -> None:
    _REGISTRY.pop(target, None)


def get(target: str) -> RuntimeAdapter:
    try:
        return _REGISTRY[target]
    except KeyError:
        raise UnknownTargetError(f"runtime target {target!r} not registered") from None


def list_targets() -> list[str]:
    return sorted(_REGISTRY)
