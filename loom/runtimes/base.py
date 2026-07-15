from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from loom.ir.models import IRDocument
    from loom.runtimes.warnings import CompileWarning


@dataclass(frozen=True)
class DraftHandle:
    target: str        # "hiagent" | "dify"
    draft_id: str
    canonical_ast_hash: str


@dataclass(frozen=True)
class PublishHandle:
    target: str
    publish_id: str
    canonical_ast_hash: str


@dataclass(frozen=True)
class UnrecognizedConstruct:
    target: str
    construct: str
    reason: str
    remediation: str


@dataclass(frozen=True)
class CompileContext:
    """Target-neutral inputs needed to compile an artifact safely."""

    binding: Any | None = None
    mode: Literal["chat", "chatflow"] | None = None
    actor: str | None = None
    tenant: str | None = None


@dataclass(frozen=True)
class ConstructCapability:
    supported: bool
    reason: str
    remediation: str


class UnsupportedConstruct(ValueError):
    """Structured fail-closed signal for IR semantics a runtime cannot honor."""

    def __init__(
        self,
        *,
        target: str,
        version: str,
        construct: str,
        node_id: str | None,
        reason: str,
        remediation: str,
    ) -> None:
        self.target = target
        self.version = version
        self.construct = construct
        self.node_id = node_id
        self.reason = reason
        self.remediation = remediation
        location = f" at node {node_id!r}" if node_id else ""
        super().__init__(
            f"{target} {version} does not safely support {construct}{location}: "
            f"{reason} Remediation: {remediation}"
        )

    def as_dict(self) -> dict[str, str | None]:
        return {
            "target": self.target,
            "version": self.version,
            "construct": self.construct,
            "node_id": self.node_id,
            "reason": self.reason,
            "remediation": self.remediation,
        }


class UnsupportedRuntimeOperation(NotImplementedError):
    """Structured status for adapter lifecycle operations not yet available."""

    def __init__(self, *, target: str, version: str, operation: str, reason: str) -> None:
        self.target = target
        self.version = version
        self.operation = operation
        self.reason = reason
        super().__init__(f"{target} {version} operation {operation!r} is unsupported: {reason}")


def _gap(reason: str, remediation: str) -> ConstructCapability:
    return ConstructCapability(False, reason, remediation)


RUNTIME_CAPABILITIES: dict[str, dict[str, dict[str, ConstructCapability]]] = {
    "dify": {
        "1.14": {
            "loop.bounded": _gap(
                "the compiler emitted a placeholder code node instead of enforcing max_iterations",
                "remove the loop or implement and conformance-test bounded Dify iteration",
            ),
            "parallel.fanout_merge": _gap(
                "parallel branches and merge strategy were not executed",
                "serialize the branches or implement verified Dify fan-out and merge",
            ),
            "condition.complex_expression": _gap(
                "only a single variable-to-string-or-number comparison is translated without semantic loss",
                "rewrite the condition as a simple comparison or use a verified code node",
            ),
            "agent.budget_schema_fallback": _gap(
                "agent budget, schemas, tools, and fallback behavior were replaced by placeholder code",
                "replace the agent with verified primitive nodes",
            ),
            "http.credential": _gap(
                "credential handles are not bound into Dify HTTP nodes",
                "bind credentials in a verified adapter implementation before compiling",
            ),
            "http.retry": _gap(
                "HTTP retry policy is not emitted",
                "remove the retry requirement or add a conformance-tested mapping",
            ),
            "http.idempotency_key": _gap(
                "HTTP idempotency keys are not emitted",
                "remove the idempotency requirement or add a conformance-tested mapping",
            ),
            "llm.retry": _gap(
                "LLM retry policy is not emitted",
                "remove the retry requirement or add a conformance-tested mapping",
            ),
            "retrieval.retry": _gap(
                "retrieval retry policy is not emitted",
                "remove the retry requirement or add a conformance-tested mapping",
            ),
            "retrieval.rerank": _gap(
                "rerank=true is currently emitted as reranking disabled",
                "disable reranking or add a bound, conformance-tested rerank model",
            ),
            "code.retry": _gap(
                "code-node retry policy is not emitted",
                "remove the retry requirement or add a conformance-tested mapping",
            ),
            "code.idempotency_key": _gap(
                "code-node idempotency keys are not emitted",
                "remove the idempotency requirement or add a conformance-tested mapping",
            ),
        },
    },
    "hiagent": {
        "2.6": {
            "loop.bounded": _gap(
                "bounded loops were emitted as LoopType=Infinite and child nodes were omitted",
                "remove the loop or implement and conformance-test bounded loop expansion",
            ),
            "parallel.fanout_merge": _gap(
                "branches were stored as metadata on one invalid Code node and never executed",
                "serialize the branches or implement verified fan-out and merge expansion",
            ),
            "condition.rule": _gap(
                "rule conditions were converted to an LLM Intent classifier",
                "replace the rule with verified deterministic code until native rules are supported",
            ),
            "agent.budget_schema_fallback": _gap(
                "agent budget, schema, and fallback semantics are not consistency-verified",
                "expand the agent into verified primitive nodes",
            ),
            "http.credential": _gap(
                "credential handles are not resolved into HTTP request authentication",
                "add a verified credential binding before compiling",
            ),
            "http.retry": _gap(
                "the emitted Retry object has not passed schema and behavior conformance",
                "remove the retry requirement or add a conformance-tested mapping",
            ),
            "http.idempotency_key": _gap(
                "idempotency-key behavior has not passed runtime conformance",
                "remove the idempotency requirement or add a conformance-tested mapping",
            ),
            "llm.retry": _gap(
                "only an attempt count is emitted; backoff and retry_on semantics are lost",
                "remove the retry requirement or add a conformance-tested mapping",
            ),
            "retrieval.retry": _gap(
                "retrieval retry policy is not emitted",
                "remove the retry requirement or add a conformance-tested mapping",
            ),
            "retrieval.rerank": _gap(
                "the rerank flag and bound model behavior are not consistency-verified",
                "disable reranking until the runtime mapping is verified",
            ),
            "code.retry": _gap(
                "only an attempt count is emitted; backoff and retry_on semantics are lost",
                "remove the retry requirement or add a conformance-tested mapping",
            ),
            "code.idempotency_key": _gap(
                "code-node idempotency keys are not emitted",
                "remove the idempotency requirement or add a conformance-tested mapping",
            ),
        },
    },
}


_SIMPLE_CONDITION_RE = re.compile(
    r"^\s*(\$\{[^}]+\})\s*(<=|>=|==|!=|<|>)\s*"
    r"(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|-?(?:\d+(?:\.\d*)?|\.\d+))\s*$"
)


def is_simple_condition_expression(expression: str) -> bool:
    return _SIMPLE_CONDITION_RE.fullmatch(expression) is not None


def capability_redlines(target: str, version: str) -> list[str]:
    capabilities = RUNTIME_CAPABILITIES.get(target, {}).get(version, {})
    return [
        f"{construct}: {capability.reason} Remediation: {capability.remediation}"
        for construct, capability in capabilities.items()
        if not capability.supported
    ]


def _raise_unsupported(
    *,
    target: str,
    version: str,
    construct: str,
    node_id: str | None,
) -> None:
    capability = RUNTIME_CAPABILITIES[target][version][construct]
    raise UnsupportedConstruct(
        target=target,
        version=version,
        construct=construct,
        node_id=node_id,
        reason=capability.reason,
        remediation=capability.remediation,
    )


def assert_runtime_node_supported(node: Any, *, target: str, version: str) -> None:
    """Reject node semantics that the versioned runtime cannot preserve."""

    node_type = str(node.type)
    node_id = str(node.id)
    structural = {
        "loop": "loop.bounded",
        "parallel": "parallel.fanout_merge",
        "agent": "agent.budget_schema_fallback",
    }
    if node_type in structural:
        _raise_unsupported(
            target=target,
            version=version,
            construct=structural[node_type],
            node_id=node_id,
        )
    if node_type == "condition":
        if target == "hiagent":
            _raise_unsupported(
                target=target,
                version=version,
                construct="condition.rule",
                node_id=node_id,
            )
        if any(not is_simple_condition_expression(branch.when) for branch in node.branches):
            _raise_unsupported(
                target=target,
                version=version,
                construct="condition.complex_expression",
                node_id=node_id,
            )
    optional_fields = {
        "http": (
            ("credential", "http.credential"),
            ("retry", "http.retry"),
            ("idempotency_key", "http.idempotency_key"),
        ),
        "llm": (("retry", "llm.retry"),),
        "retrieval": (("retry", "retrieval.retry"), ("rerank", "retrieval.rerank")),
        "code": (("retry", "code.retry"), ("idempotency_key", "code.idempotency_key")),
    }
    for field, construct in optional_fields.get(node_type, ()):
        if getattr(node, field, None):
            _raise_unsupported(
                target=target,
                version=version,
                construct=construct,
                node_id=node_id,
            )


def assert_runtime_ir_supported(
    ir: Any,
    *,
    target: str,
    version: str,
    binding: Any | None = None,
) -> None:
    for node in ir.nodes:
        assert_runtime_node_supported(node, target=target, version=version)
        if (
            target == "hiagent"
            and node.type == "llm"
            and binding is not None
            and not binding.resolve_model(node.model)
        ):
            raise UnsupportedConstruct(
                target=target,
                version=version,
                construct="llm.model_binding",
                node_id=node.id,
                reason=f"model handle {node.model!r} is not present in the customer binding",
                remediation="add the model handle to model_id_map before compiling",
            )


@dataclass(frozen=True)
class PushContext:
    actor: str
    workflow_name: str | None = None


@dataclass(frozen=True)
class PublishContext:
    actor: str


class RuntimeAdapter(Protocol):
    target: str
    version: str
    # IR ↔ DSL
    def compile(
        self,
        ir: IRDocument,
        *,
        context: CompileContext | None = None,
    ) -> tuple[Any, list[CompileWarning]]: ...
    def reverse(self, dsl: Any) -> tuple[IRDocument, list[UnrecognizedConstruct]]: ...
    def canonical_ast_hash(self, dsl: Any) -> str: ...
    # DSL serialization (str for text formats like YAML / JSON; bytes for
    # binary formats like Hiagent's Agent-bundle ZIP).
    def serialize_dsl(self, dsl: Any) -> str | bytes: ...
    def parse_dsl(self, raw: str) -> Any: ...
    # Lifecycle
    async def push_draft(self, dsl: Any, ctx: PushContext) -> DraftHandle: ...
    async def publish(self, handle: DraftHandle, ctx: PublishContext) -> PublishHandle: ...
    async def export_draft(self, draft_id: str) -> Any: ...
    # Conformance / parity
    async def run_draft(self, draft_id: str, *, inputs: dict[str, Any]) -> dict[str, Any]: ...
    # Planner consultation
    def redlines(self) -> list[str]: ...
