"""OpenAI-compatible structured-output LLM client wrapper for the Planner.

Uses the openai SDK against any OpenAI-compatible endpoint [base_url
override]; default config targets DeepSeek-V4-Flash via env. Prompt
caching is provider-side automatic where supported [DeepSeek, OpenAI];
the system prompt is structured static-prefix-then-dynamic-suffix to
maximize cache hits.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from openai import OpenAI

from loom.ir.schema import load_schema
from loom.planner.scope import render_registry_block
from loom.validator.registry import Registry

if TYPE_CHECKING:
    from loom.fde_session.persona_brief import PersonaBrief

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_DEFAULT_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True)
class CallResult:
    ir_text: str
    cost_usd: float
    latency_s: float


def render_persona_block(persona: PersonaBrief | None) -> str:
    if persona is None:
        return "# Persona context\nPersona Brief: default-operator [no explicit persona supplied; debug / dev mode]."
    cb = persona.compliance_boundary
    return "\n".join([
        "# Persona context",
        f"Persona id: {persona.persona_id}",
        f"Author role: {persona.author_role}",
        f"Vertical: {persona.vertical}",
        f"End user: {persona.end_user}",
        f"Reviewer role: {persona.reviewer.role}",
        f"Reviewer decision_authority: {persona.reviewer.decision_authority}",
        f"Compliance: pii_class_default={cb.pii_class_default}, regulatory_tags={cb.regulatory_tags}, geographies={cb.geographies}",
        f"Success criteria: {persona.success_criteria}",
    ])


def render_target_block(target: str) -> str:
    return f"# Target runtime\nThe deployment target is **{target}**. Both runtimes implement the same IR contract; do not emit features the chosen runtime cannot honor [see runtime adapter docs]."


class PlannerClient:
    """One-call wrapper. The retry loop owns the multi-call story."""

    def __init__(
        self,
        *,
        model: str | None = None,
        max_tokens: int = 16000,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self._model = model or os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)
        self._max_tokens = max_tokens
        self._client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
            base_url=base_url or os.environ.get("OPENAI_BASE_URL"),
        )
        self._system_static = self._build_static_system()

    def _build_static_system(self) -> str:
        prompt_md = (_PROMPT_DIR / "system.md").read_text()
        schema = json.dumps(load_schema(), indent=2)
        few_shot_files = sorted((_PROMPT_DIR / "few_shot").glob("*.json"))
        few_shot = "\n\n".join(p.read_text() for p in few_shot_files)
        return (
            prompt_md
            + "\n\n# IR v0.3 JSON Schema [verbatim]\n```json\n" + schema + "\n```\n\n"
            + "# Few-shot library\n\n" + few_shot
        )

    def call(
        self,
        *,
        intent: str,
        scope: str,
        persona_brief: PersonaBrief | None = None,
        target: Literal["hiagent", "dify"] = "hiagent",
        prior_failures_md: str = "",
    ) -> CallResult:
        reg_block = render_registry_block(Registry.load("v1"), scope=scope)
        persona_block = render_persona_block(persona_brief)
        target_block = render_target_block(target)
        system_text = (
            self._system_static
            + "\n\n" + persona_block
            + "\n\n" + target_block
            + "\n\n" + reg_block
        )
        user_parts = [f"# Intent\n{intent}\n\n# Scope\n{scope}\n\n# Target runtime\n{target}"]
        if prior_failures_md:
            user_parts.append("# Validator failures from previous attempt\n" + prior_failures_md)
        user_parts.append("Emit IR v0.3 JSON only.")
        user_text = "\n\n".join(user_parts)

        t0 = time.monotonic()
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ],
            response_format={"type": "json_object"},
        )
        latency = time.monotonic() - t0
        choice = resp.choices[0]
        text = choice.message.content or ""
        cost = _estimate_cost(self._model, resp.usage)
        return CallResult(ir_text=text, cost_usd=cost, latency_s=latency)


def _estimate_cost(model: str, usage: Any) -> float:
    """USD cost estimate; reads optional rates from env. Default 0.0 [no tracking]."""
    in_per_1k = float(os.environ.get("LOOM_LLM_COST_PER_1K_INPUT", "0") or 0)
    out_per_1k = float(os.environ.get("LOOM_LLM_COST_PER_1K_OUTPUT", "0") or 0)
    in_tok = getattr(usage, "prompt_tokens", 0) or 0
    out_tok = getattr(usage, "completion_tokens", 0) or 0
    return (in_tok * in_per_1k + out_tok * out_per_1k) / 1000.0
