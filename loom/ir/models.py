"""Pydantic v2 models for FDE IR v0.3/v0.4.

These mirror schemas/ir-v0.3.schema.json and schemas/ir-v0.4.schema.json. Any divergence is a bug; the
test_archetype_validates suite + test_models suite catch most cases.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# ---- Primitives ----------------------------------------------------------

NodeId = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")]
RegistrySha = Annotated[str, StringConstraints(pattern=r"^sha:[0-9a-f]{7,40}$")]
NonEmptyShort = Annotated[str, StringConstraints(min_length=1, max_length=500)]
NonEmptyLong = Annotated[str, StringConstraints(min_length=1, max_length=1000)]

VarRef = str  # Validator owns the syntax

TypeName = Literal[
    "string", "number", "boolean", "null", "json",
    "string[]", "number[]", "json[]",
    "chunks", "file", "any",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---- Top-level pieces ---------------------------------------------------

class Metadata(_Strict):
    name: Annotated[str, StringConstraints(min_length=1)]
    description: str | None = None
    owner: Annotated[str, StringConstraints(min_length=1)]
    rationale: NonEmptyLong


class RegistryRef(_Strict):
    registry_version: RegistrySha
    tools: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    credentials: list[str] = Field(default_factory=list)


class Retry(_Strict):
    max_attempts: Annotated[int, Field(ge=1, le=10)]
    backoff: Literal["none", "linear", "exponential"] = "exponential"
    retry_on: list[Literal["5xx", "4xx", "timeout", "network", "rate_limit"]] | None = None


class AgentBudget(_Strict):
    max_iterations: Annotated[int, Field(ge=1, le=50)]
    max_tokens: Annotated[int, Field(ge=1000, le=200000)]
    max_wall_clock_s: Annotated[int, Field(ge=1, le=3600)]


class PolicyGuardrails(_Strict):
    input_filters: list[str] = Field(default_factory=list)
    output_filters: list[str] = Field(default_factory=list)
    custom_patterns: list[str] = Field(default_factory=list)


class PolicyEscalation(_Strict):
    confidence_min: Annotated[float, Field(ge=0, le=1)]
    confidence_from: VarRef
    handoff_node: NodeId


class PolicyAudit(_Strict):
    log_inputs: bool = False
    log_decisions: bool = True
    retention_days: Annotated[int, Field(ge=1)] = 90


class Policy(_Strict):
    default_timeout_s: Annotated[float, Field(gt=0)] | None = None
    default_retry: Retry | None = None
    agent_budget: AgentBudget | None = None
    guardrails: PolicyGuardrails | None = None
    escalation: PolicyEscalation | None = None
    audit: PolicyAudit | None = None


class PortDecl(_Strict):
    name: Identifier
    type: TypeName
    required: bool = False
    description: str | None = None


# ---- Nodes --------------------------------------------------------------

class _NodeBase(_Strict):
    id: NodeId
    rationale: NonEmptyShort
    description: str | None = None


class TriggerWebhook(_Strict):
    path: str | None = None
    method: Literal["POST", "GET", "PUT", "PATCH", "DELETE"] | None = None


class TriggerNode(_NodeBase):
    type: Literal["trigger"]
    mode: Literal["manual", "schedule", "webhook"]
    schedule: str | None = None
    webhook: TriggerWebhook | None = None


class LLMNode(_NodeBase):
    type: Literal["llm"]
    model: str
    prompt: VarRef
    system_prompt: VarRef | None = None
    temperature: Annotated[float, Field(ge=0, le=2)] | None = None
    max_tokens: Annotated[int, Field(ge=1)] | None = None
    output_schema: dict[str, Any] | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None
    retry: Retry | None = None


class RetrievalNode(_NodeBase):
    type: Literal["retrieval"]
    dataset: str
    query: VarRef
    top_k: Annotated[int, Field(ge=1, le=100)] = 5
    rerank: bool = False
    timeout_s: Annotated[float, Field(gt=0)] | None = None
    retry: Retry | None = None


class HTTPNode(_NodeBase):
    type: Literal["http"]
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    url: VarRef
    headers: dict[str, VarRef] | None = None
    body: Any = None
    credential: str | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None
    retry: Retry | None = None
    idempotency_key: VarRef | None = None


class CodeNode(_NodeBase):
    type: Literal["code"]
    language: Literal["python", "javascript"]
    source: str
    inputs: dict[str, VarRef] | None = None
    output_schema: dict[str, Any] | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None
    retry: Retry | None = None
    idempotency_key: VarRef | None = None


class ConditionBranchNarrowing(_Strict):
    var: str
    to_type: TypeName


class ConditionBranch(_Strict):
    when: str
    next: NodeId
    narrows: ConditionBranchNarrowing | None = None


class ConditionNode(_NodeBase):
    type: Literal["condition"]
    branches: Annotated[list[ConditionBranch], Field(min_length=1)]
    default: NodeId | None = None


class LoopNode(_NodeBase):
    type: Literal["loop"]
    over: VarRef
    as_: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")] = Field(alias="as")
    body: list[AnyNode]
    max_iterations: Annotated[int, Field(ge=1, le=1000)]
    collect: VarRef | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None


class ParallelNode(_NodeBase):
    type: Literal["parallel"]
    branches: dict[str, list[AnyNode]]
    merge_strategy: Literal["concat", "object_merge", "first_success"]
    branch_types: dict[str, TypeName] | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None


class AgentNode(_NodeBase):
    type: Literal["agent"]
    model: str
    tools: Annotated[list[str], Field(min_length=1)]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    inputs: dict[str, VarRef] | None = None
    system_prompt: VarRef | None = None
    budget: AgentBudget
    on_budget_exhausted: Literal["fallback", "fail", "return_partial"]
    fallback_edge: NodeId | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None


class OutputNode(_NodeBase):
    type: Literal["output"]
    bindings: Annotated[dict[str, VarRef], Field(min_length=1)]


AnyNode = (
    TriggerNode | LLMNode | RetrievalNode | HTTPNode | CodeNode |
    ConditionNode | LoopNode | ParallelNode | AgentNode | OutputNode
)
LoopNode.model_rebuild()
ParallelNode.model_rebuild()


class Edge(_Strict):
    from_: NodeId = Field(alias="from")
    to: NodeId
    when: str | None = None
    data: bool = True


class IRDocument(_Strict):
    ir_version: Literal["0.3", "0.4"]
    metadata: Metadata
    registry_ref: RegistryRef
    policy: Policy
    inputs: list[PortDecl]
    outputs: list[PortDecl]
    nodes: Annotated[list[AnyNode], Field(min_length=1)]
    edges: list[Edge]

    @model_validator(mode="after")
    def _gate_v04_policy_fields(self) -> IRDocument:
        if self.ir_version == "0.3" and (
            self.policy.guardrails is not None
            or self.policy.escalation is not None
            or self.policy.audit is not None
        ):
            raise ValueError("policy.guardrails, policy.escalation, and policy.audit require ir_version 0.4")
        return self
