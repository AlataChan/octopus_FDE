# FDE Phase 1.5 — Coverage Expansion + Hiagent ↔ Dify Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Document location:** Project execution plans live in `docs/plans/`.

**Naming note:** Product-facing language is FDE / AI 驻场流程工程师. Internal implementation paths may temporarily retain the `loom/` Python namespace.

**Goal:** Take the Phase 1 MVP (deep on 2 ecommerce archetypes, dual runtime: Hiagent primary + Dify secondary) from "deep on 2" to "broad on 5". Phase 1.5 widens the *forward* compiler (and the eval corpus) to cover the 3 TCM shadow archetypes on both runtimes. Reverse compiler stays narrow on (01-ecommerce-customer-faq, 05-ecommerce-order-exception) for both runtimes per PRD §7; Phase 2A widens reverse. Eval corpus grows from ≥30 deep prompts to ≥75 across 5 archetypes (PRD §10.1). Conformance matrix stays 100% green on both runtimes for every archetype × IR-construct cell that the new corpus exercises.

**No n8n in Phase 1.5.** Decision (per project owner, 2026-05-06): n8n is removed from v1 scope. Hiagent + Dify are the only supported runtimes. The "portability probe" concept from earlier drafts is dropped — runtime portability is now proven by construction in Phase 1 (dual compile from one IR to two runtimes with parity), not by a falsifiable refusal stub. LangGraph remains a Phase 3.3 alpha candidate, not Phase 1.5 work.

**Architecture:** Phase 1.5 adds two things on top of Phase 1:

1. **Forward compiler coverage on both runtimes** — extend `loom/runtimes/hiagent/<vH_X>/compiler.py` and `loom/runtimes/dify/<vD_Y>/compiler.py` to emit valid DSL for shadow archetypes 02 (TCM intake/triage), 03 (TCM clinic-ops-summary), 04 (TCM follow-up). Phase 1 already covers archetypes 01 + 05 on both runtimes. Reverse stays narrow on (01, 05) for both.
2. **Eval corpus widening + per-archetype × per-runtime reporting** — `corpus/full/` grows to ≥75 prompts across 5 archetypes; the eval runner produces per-archetype × per-runtime × per-failure-bucket attribution (PRD §10 taxonomy).

The conformance matrix scaffolding (Phase 0) and the `RuntimeAdapter` abstraction (Phase 1) already exist; Phase 1.5 just extends both to cover more archetypes on the same two runtimes.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, ruff, mypy. Phase 0 / Phase 1 toolchain preserved; no new tools.

> **Trim note (2026-05-06):** Code snippets and test fixtures below are **illustrative**. Contracts to preserve: (a) PRD §10 corpus size (≥75 prompts), (b) PRD §10 first-try IR validity targets per runtime, (c) Phase 1.5 reverse stays narrow on (01, 05) for both runtimes, (d) Hiagent ↔ Dify parity contract (Task 5). Per project owner directive 2026-05-06: trim over-specification, keep contracts.

**Prerequisites:** Phase 1 complete:
- `reports/phase-1-gate.md` shows all rows pass.
- ≥70% first-try IR validity on the 2 deep-coverage archetypes (01-ecommerce-customer-faq, 05-ecommerce-order-exception).
- Conformance matrix is green for both Hiagent and Dify on the deep-coverage cells.
- `loom/runtimes/{hiagent,dify}/<vX_Y>/compiler.py` and `reverse.py` exist for both runtimes, tested for the 2 deep archetypes.
- `loom/eval/runner.py` produces per-bucket failure counts.

If any of these fails, do not start Phase 1.5.

---

## Repo layout extended by Phase 1.5

```
loom/
├── runtimes/
│   ├── hiagent/<vH_X>/
│   │   ├── compiler.py             (extended for shadow archetypes 02, 03, 04)
│   │   ├── compiler_nodes.py       (extended)
│   │   ├── reverse.py              (UNCHANGED — stays narrow on 01 + 05; Phase 2A widens)
│   │   └── wrappers.py             (extended for cells Hiagent lacks natively)
│   └── dify/<vD_Y>/
│       ├── compiler.py             (extended for shadow archetypes 02, 03, 04)
│       ├── compiler_nodes.py       (extended)
│       ├── reverse.py              (UNCHANGED — stays narrow on 01 + 05; Phase 2A widens)
│       └── wrappers.py             (extended)
└── eval/
    ├── corpus.py                   (loads full corpus; per-archetype groups; vertical_role tagged)
    ├── runner.py                   (per-archetype × per-runtime × per-bucket reporting)
    └── report.py                   (markdown + JSON writers; vertical_role + runtime columns)

corpus/
└── full/
    ├── 01-ecommerce-customer-faq/  (extends Phase 1 deep set; ≥15 prompts)
    ├── 02-tcm-intake-triage/       (NEW shadow; ≥15 prompts)
    ├── 03-clinic-ops-summary/      (NEW shadow; ≥15 prompts)
    ├── 04-tcm-followup/            (NEW shadow; ≥15 prompts)
    └── 05-ecommerce-order-exception/  (extends Phase 1 deep set; ≥15 prompts)

tests/
├── runtimes/
│   ├── hiagent/<vH_X>/
│   │   ├── test_archetypes_full.py    (NEW — DSL emission for all 5 compiles cleanly)
│   │   └── test_reverse_narrow.py     (UNCHANGED — still 2 archetypes)
│   └── dify/<vD_Y>/
│       ├── test_archetypes_full.py    (NEW — DSL emission for all 5 compiles cleanly)
│       └── test_reverse_narrow.py     (UNCHANGED)
├── eval/
│   ├── test_corpus_full.py            (NEW — ≥75 prompts loadable, archetype balance, vertical_role)
│   └── test_runner_report.py          (NEW — per-runtime breakdown in report)
└── conformance/
    └── test_runtime_parity.py         (NEW — same IR compiles to both runtimes; conformance matrix green for both per archetype)

reports/
├── phase-1-5-gate.md                  (NEW — evidence package)
├── coverage-by-archetype.md           (NEW — per-archetype × per-runtime first-try rates)
└── eval-full-corpus.json              (NEW — runner output)
```

---

## Task 1: Extend Dify compiler to shadow archetypes 02, 03, 04 (TCM)

**Files:**
- Modify: `loom/runtimes/dify/<vD_Y>/compiler.py`
- Modify: `loom/runtimes/dify/<vD_Y>/compiler_nodes.py`
- Modify: `loom/runtimes/dify/<vD_Y>/wrappers.py`
- Create: `tests/runtimes/dify/<vD_Y>/test_archetypes_full.py`

The Phase 1 Dify compiler covers ecommerce archetypes 01 + 05. Extend it to emit valid DSL for the 3 TCM shadow archetypes. Reverse compilation does *not* widen here.

- [ ] **Step 1: Inventory the new node-level constructs**

For each shadow archetype, list the IR node types that the Phase 1 Dify compiler does not yet emit. Expected new constructs:

- Archetype 02 (TCM intake/triage, shadow): `condition` with branch narrowing; `output` to clinical-staff queue.
- Archetype 03 (TCM clinic-ops-summary, shadow): `parallel` with typed merge; daily/weekly aggregations.
- Archetype 04 (TCM follow-up, shadow): scheduled `trigger` (cron) + `loop` over patient list with per-iteration policy.

Write the inventory into `reports/coverage-by-archetype.md`; this drives the rest of the task.

- [ ] **Step 2: Implement missing emit functions in `compiler_nodes.py`**

One emit fn per IR node type, dispatched from `compiler.py` via the existing registry (Phase 1 pattern). No `if-elif` chains over IR types; pure functions; same conformance matrix tests apply.

- [ ] **Step 3: Add wrappers for cells Dify lacks natively**

Each wrapper docstring states: which IR feature it implements, which Dify primitives it composes, which conformance-matrix cell verifies the equivalence.

- [ ] **Step 4: Golden tests for all 5 archetypes**

```python
# tests/runtimes/dify/<vD_Y>/test_archetypes_full.py
import json
from pathlib import Path
import pytest
from loom.ir.models import IRDocument
from loom.runtimes.dify.<vD_Y>.compiler import compile_ir

ARCHETYPES = [
    "01-ecommerce-customer-faq",
    "02-tcm-intake-triage",
    "03-clinic-ops-summary",
    "04-tcm-followup",
    "05-ecommerce-order-exception",
]

@pytest.mark.parametrize("name", ARCHETYPES)
def test_archetype_compiles(name: str) -> None:
    ir_path = Path("examples/ir") / f"{name}.json"
    ir = IRDocument.model_validate(json.loads(ir_path.read_text()))
    dsl = compile_ir(ir)
    assert dsl["graph"]["nodes"], f"{name} produced empty graph"
    assert dsl["app"]["name"] == ir.metadata.name
```

- [ ] **Step 5: Conformance matrix update**

Each new node-type/feature combination introduces a conformance-matrix row if not already present. Run the slow-lane conformance tests against pinned Dify; confirm 100% green. Red row blocks the gate (PRD §5.5).

- [ ] **Step 6: Commit**

```bash
git add loom/runtimes/dify/ tests/runtimes/dify/ reports/coverage-by-archetype.md
git commit -m "feat(dify): widen compiler to shadow archetypes 02/03/04 (TCM); reverse stays narrow"
```

---

## Task 2: Extend Hiagent compiler to shadow archetypes 02, 03, 04 (TCM)

**Files:**
- Modify: `loom/runtimes/hiagent/<vH_X>/compiler.py`
- Modify: `loom/runtimes/hiagent/<vH_X>/compiler_nodes.py`
- Modify: `loom/runtimes/hiagent/<vH_X>/wrappers.py`
- Create: `tests/runtimes/hiagent/<vH_X>/test_archetypes_full.py`

Mirror of Task 1 for Hiagent. Hiagent natively supports most IR primitives (Start / 大模型 / 知识库 / 选择器 / 循环 / 并行 / 代码 / Agent / End), so wrappers should be smaller than Dify's. Where Hiagent and Dify diverge (e.g., per-node retry shape, output_schema enforcement mode), each runtime's emit fns own the diff; the IR contract stays single.

Same 6 steps as Task 1, applied to `loom/runtimes/hiagent/<vH_X>/`. Both runtimes must emit valid DSL for all 5 archetypes after this task.

```bash
git commit -m "feat(hiagent): widen compiler to shadow archetypes 02/03/04 (TCM); reverse stays narrow"
```

---

## Task 3: Eval corpus expansion to ≥75 prompts

**Files:**
- Create: `corpus/full/01-ecommerce-customer-faq/` (≥15 prompts, extends Phase 1 deep set)
- Create: `corpus/full/02-tcm-intake-triage/` (≥15 new prompts, shadow)
- Create: `corpus/full/03-clinic-ops-summary/` (≥15 new prompts, shadow)
- Create: `corpus/full/04-tcm-followup/` (≥15 new prompts, shadow)
- Create: `corpus/full/05-ecommerce-order-exception/` (≥15 prompts, extends Phase 1 deep set)
- Modify: `loom/eval/corpus.py`
- Create: `tests/eval/test_corpus_full.py`

PRD §10.1 requires ≥75 prompts. Prompts must come from the design partner backlog (post-ADR 0001) or partner-paraphrased synthetic equivalents.

- [ ] **Step 1: Prompt schema**

Each prompt is a JSON file:

```json
{
  "id": "01-ecommerce-customer-faq/p07",
  "archetype": "ecommerce-customer-faq",
  "vertical_role": "primary",
  "language": "zh-CN",
  "intent": "<oral-style request>",
  "declared_context": { "trigger": "...", "datasets": [...], "tools": [...], "credentials": [...], "approval": "..." },
  "expected_brief_questions": [...],
  "expected_node_set": [...],
  "ground_truth_ir": null,
  "source": "<partner ticket id or paraphrase note>",
  "license": "internal-use-only"
}
```

`vertical_role` is `primary` for archetypes 01, 05 and `shadow` for 02, 03, 04. `ground_truth_ir` is optional but encouraged for the 2 deep archetypes; the runner uses canonical IR equality if present, else falls back to "validates + compiles + emits expected node set".

- [ ] **Step 2: Authoring rules**

- **Operator-side prompts** (Author describing the workflow): default zh-CN; ≥60% zh-CN across the corpus.
- **Buyer-/patient-facing content embedded in IR examples**: multilingual (`en`, `de`, `es`, `ja`, `zh-CN` mix) for ecommerce; zh-CN only for TCM shadow.
- ≥3 prompts per archetype must include intentionally underspecified context (forces FDE clarify path).
- ≥2 prompts per archetype must contain a redlined construct so coverage exercises the compliance / PII gates.
- No PII, no real customer / patient data; partner data is paraphrased and reviewed by the partner before commit.

- [ ] **Step 3: Update corpus loader**

```python
# loom/eval/corpus.py
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

@dataclass(frozen=True)
class Prompt:
    id: str
    archetype: str
    vertical_role: Literal["primary", "shadow"]
    language: str
    intent: str
    declared_context: dict
    expected_brief_questions: list[str]
    expected_node_set: list[str]
    ground_truth_ir: dict | None
    source: str

def load(corpus_set: str) -> list[Prompt]:
    """corpus_set is 'deep' (Phase 1) or 'full' (Phase 1.5).

    Phase 1.5 layout is `corpus/full/<archetype>/`; Phase 3.1 introduces multi-tenancy
    and migrates to `corpus/full/<tenant>/<archetype>/`. The loader prefers the
    tenant-scoped layout if present and falls back to flat. Both forms must never
    coexist in a committed state — CI fails if both exist post-migration.
    """
    root = Path("corpus") / corpus_set
    return list(_iter_prompts(root))

def by_archetype(prompts: list[Prompt]) -> dict[str, list[Prompt]]:
    out: dict[str, list[Prompt]] = {}
    for p in prompts:
        out.setdefault(p.archetype, []).append(p)
    return out

def _iter_prompts(root: Path) -> Iterator[Prompt]:
    for f in sorted(root.rglob("prompt-*.json")):
        d = json.loads(f.read_text())
        yield Prompt(**d)
```

- [ ] **Step 4: Tests**

```python
# tests/eval/test_corpus_full.py
from loom.eval.corpus import load, by_archetype

PRIMARY = {"ecommerce-customer-faq", "ecommerce-order-exception"}
SHADOW = {"tcm-intake-triage", "clinic-ops-summary", "tcm-followup"}

def test_full_corpus_size_and_balance():
    prompts = load("full")
    assert len(prompts) >= 75
    grouped = by_archetype(prompts)
    assert set(grouped) == PRIMARY | SHADOW
    for archetype, ps in grouped.items():
        assert len(ps) >= 15

def test_vertical_role_consistent_with_archetype():
    for p in load("full"):
        if p.archetype in PRIMARY:
            assert p.vertical_role == "primary"
        elif p.archetype in SHADOW:
            assert p.vertical_role == "shadow"

def test_operator_side_majority_zh_cn():
    prompts = load("full")
    zh = [p for p in prompts if p.language == "zh-CN"]
    assert len(zh) / len(prompts) >= 0.60

def test_underspecified_share():
    prompts = load("full")
    underspecified = [p for p in prompts if p.expected_brief_questions]
    assert len(underspecified) / len(prompts) >= 0.20
```

- [ ] **Step 5: Commit**

```bash
git add corpus/full/ loom/eval/corpus.py tests/eval/test_corpus_full.py
git commit -m "test(eval): full corpus ≥75 prompts across 5 archetypes; vertical_role tagged"
```

---

## Task 4: Per-archetype × per-runtime eval reporting

**Files:**
- Modify: `loom/eval/runner.py`
- Create: `loom/eval/report.py`
- Create: `tests/eval/test_runner_report.py`

Phase 1's runner reported a single rolled-up failure-bucket count. Phase 1.5 attributes failures to *(archetype × runtime × bucket)* to localize regressions across the dual-runtime stack.

- [ ] **Step 1: Extend `EvalReport` shape**

```python
# loom/eval/runner.py (additions)
from dataclasses import dataclass, field
from typing import Literal

Bucket = Literal["schema", "reference", "type_flow", "policy",
                 "compile", "deploy", "reverse_compile",
                 "registry_acl", "semantic_conformance", "platform", "human_review"]
Runtime = Literal["hiagent", "dify"]

@dataclass
class FailureRecord:
    prompt_id: str
    archetype: str
    runtime: Runtime
    bucket: Bucket
    detail: str

@dataclass
class ArchetypeReport:
    archetype: str
    vertical_role: Literal["primary", "shadow"]
    total: int
    by_runtime: dict[Runtime, "RuntimeArchetypeReport"]

@dataclass
class RuntimeArchetypeReport:
    runtime: Runtime
    first_try_validity: float
    by_bucket: dict[Bucket, int] = field(default_factory=dict)

@dataclass
class EvalReport:
    total: int
    first_try_validity_overall: float
    first_try_validity_by_runtime: dict[Runtime, float]
    by_archetype: dict[str, ArchetypeReport]
    by_bucket: dict[Bucket, int]
    failures: list[FailureRecord]
```

- [ ] **Step 2: Markdown + JSON writers**

```python
# loom/eval/report.py
from pathlib import Path
import json
from loom.eval.runner import EvalReport

def write_json(report: EvalReport, path: Path) -> None:
    path.write_text(json.dumps(_to_dict(report), indent=2))

def write_markdown(report: EvalReport, path: Path) -> None:
    lines: list[str] = []
    lines.append("# Eval — full corpus\n")
    lines.append(f"Total prompts: {report.total}")
    lines.append(f"First-try IR validity (overall): {report.first_try_validity_overall:.1%}")
    for rt, v in sorted(report.first_try_validity_by_runtime.items()):
        lines.append(f"First-try IR validity ({rt}): {v:.1%}")
    lines.append("\n## By archetype × runtime\n")
    lines.append("| Archetype | Vertical role | Hiagent | Dify |\n|---|---|---|---|")
    for a, r in sorted(report.by_archetype.items()):
        h = r.by_runtime.get("hiagent")
        d = r.by_runtime.get("dify")
        lines.append(f"| {a} | {r.vertical_role} | {h.first_try_validity:.1%if h else '—'} | {d.first_try_validity:.1% if d else '—'} |")
    lines.append("\n## By failure bucket\n")
    lines.append("| Bucket | Count |\n|---|---|")
    for b, n in sorted(report.by_bucket.items()):
        lines.append(f"| {b} | {n} |")
    path.write_text("\n".join(lines) + "\n")

def _to_dict(report: EvalReport) -> dict:
    return {
        "total": report.total,
        "first_try_validity_overall": report.first_try_validity_overall,
        "first_try_validity_by_runtime": dict(report.first_try_validity_by_runtime),
        "by_archetype": {k: vars(v) for k, v in report.by_archetype.items()},
        "by_bucket": dict(report.by_bucket),
        "failures": [vars(f) for f in report.failures],
    }
```

- [ ] **Step 3: Tests**

```python
# tests/eval/test_runner_report.py
from pathlib import Path
from loom.eval.runner import EvalReport, ArchetypeReport, RuntimeArchetypeReport, FailureRecord
from loom.eval.report import write_json, write_markdown

def test_report_writes_json_and_markdown(tmp_path):
    a = ArchetypeReport(
        archetype="ecommerce-customer-faq",
        vertical_role="primary",
        total=2,
        by_runtime={
            "hiagent": RuntimeArchetypeReport(runtime="hiagent", first_try_validity=0.5, by_bucket={"schema": 1}),
            "dify": RuntimeArchetypeReport(runtime="dify", first_try_validity=0.5, by_bucket={"schema": 1}),
        },
    )
    r = EvalReport(
        total=2,
        first_try_validity_overall=0.5,
        first_try_validity_by_runtime={"hiagent": 0.5, "dify": 0.5},
        by_archetype={"ecommerce-customer-faq": a},
        by_bucket={"schema": 1},
        failures=[FailureRecord(prompt_id="01/p1", archetype="ecommerce-customer-faq",
                                  runtime="hiagent", bucket="schema", detail="missing rationale")],
    )
    write_json(r, tmp_path / "r.json")
    write_markdown(r, tmp_path / "r.md")
    md = (tmp_path / "r.md").read_text()
    assert "Hiagent" in md and "Dify" in md
    assert "primary" in md
```

- [ ] **Step 4: Commit**

```bash
git add loom/eval/runner.py loom/eval/report.py tests/eval/test_runner_report.py
git commit -m "feat(eval): per-archetype × per-runtime × per-bucket reporting"
```

---

## Task 5: Runtime parity conformance

**Files:**
- Create: `loom/conformance/parity.py`
- Create: `tests/conformance/test_runtime_parity.py`

The product promise is "one IR runs the same on Hiagent or Dify". Phase 1.5 enforces that with a parity test: same IR through both compilers must produce DSL whose runtime behavior passes the same conformance matrix cells. We do not require byte-equal DSL; we require *semantic* parity verified via the existing PRD §5.5 conformance suite.

- [ ] **Step 1: Parity runner**

```python
# loom/conformance/parity.py
from dataclasses import dataclass, field
from loom.ir.models import IRDocument
from loom.runtimes import registry as runtime_registry


@dataclass
class ParityOutcome:
    ir_id: str
    targets_evaluated: list[str]                    # registered targets at evaluation time
    compiled_by: dict[str, bool]                    # {target: True/False}
    conformance_cells_passed_by: dict[str, set[str]]  # {target: cells_that_passed}
    parity_ok: bool                                  # True iff every evaluated target compiled AND all targets passed the same set of cells
    parity_skipped_reason: str | None = None         # set when only one runtime is registered


def run(ir: IRDocument, conformance_cells: list[str]) -> ParityOutcome:
    """Drive parity off the live runtime registry. If only one runtime is registered
    (e.g., Cost-budget escape hatch invoked → Dify dropped), parity is *skipped*
    (parity_ok=True with parity_skipped_reason set), because parity is meaningless
    with a single runtime. The rest of the conformance gate still runs per runtime.
    """
    targets = sorted(runtime_registry.list_targets())
    compiled_by: dict[str, bool] = {}
    cells_by: dict[str, set[str]] = {}
    for t in targets:
        adapter = runtime_registry.get(t)
        ok, cells = _try_compile_and_check(adapter, ir, conformance_cells)
        compiled_by[t] = ok
        cells_by[t] = cells

    if len(targets) <= 1:
        return ParityOutcome(
            ir_id=ir.metadata.name,
            targets_evaluated=targets,
            compiled_by=compiled_by,
            conformance_cells_passed_by=cells_by,
            parity_ok=True,
            parity_skipped_reason="single runtime registered (cost-budget escape hatch invoked or only one runtime configured for this tenant)",
        )

    all_compiled = all(compiled_by.values())
    cell_sets = list(cells_by.values())
    same_cells = all(s == cell_sets[0] for s in cell_sets)
    return ParityOutcome(
        ir_id=ir.metadata.name,
        targets_evaluated=targets,
        compiled_by=compiled_by,
        conformance_cells_passed_by=cells_by,
        parity_ok=(all_compiled and same_cells),
    )


def _try_compile_and_check(adapter, ir, cells):
    """Returns (compiled_ok, set of conformance cells that passed)."""
    ...
```

- [ ] **Step 2: Test for all 5 archetypes**

```python
# tests/conformance/test_runtime_parity.py
import json
from pathlib import Path
import pytest
from loom.ir.models import IRDocument
from loom.conformance.parity import run

ARCHETYPES = [
    "01-ecommerce-customer-faq",
    "02-tcm-intake-triage",
    "03-clinic-ops-summary",
    "04-tcm-followup",
    "05-ecommerce-order-exception",
]

@pytest.mark.parametrize("name", ARCHETYPES)
def test_runtime_parity(name: str) -> None:
    ir = IRDocument.model_validate(json.loads((Path("examples/ir") / f"{name}.json").read_text()))
    cells = _conformance_cells_used_by(ir)  # derived from IR node types + features
    outcome = run(ir, cells)
    if outcome.parity_skipped_reason:
        pytest.skip(f"{name} parity skipped: {outcome.parity_skipped_reason}")
    assert outcome.parity_ok, (
        f"{name} parity failed: targets={outcome.targets_evaluated}, "
        f"compiled_by={outcome.compiled_by}, "
        f"cells_by_target={ {t: sorted(c) for t, c in outcome.conformance_cells_passed_by.items()} }"
    )
```

- [ ] **Step 3: Commit**

```bash
git add loom/conformance/parity.py tests/conformance/test_runtime_parity.py
git commit -m "test(conformance): runtime parity contract on all 5 archetypes (Hiagent ↔ Dify)"
```

---

## Task 6: Run full corpus through Phase 1.5 metrics

- [ ] **Step 1: Run eval**

```bash
ANTHROPIC_API_KEY=<key> python -c "
from loom.eval.corpus import load
from loom.eval.runner import run_eval
from loom.eval.report import write_json, write_markdown
from pathlib import Path
report = run_eval(load('full'), runtimes=('hiagent', 'dify'))
write_json(report, Path('reports/eval-full-corpus.json'))
write_markdown(report, Path('reports/coverage-by-archetype.md'))
print({'overall': report.first_try_validity_overall, 'by_runtime': report.first_try_validity_by_runtime})
"
```

- [ ] **Step 2: Check thresholds**

PRD §7 / §10 Phase 1.5 success criteria, restated for dual-runtime:

- Overall first-try IR validity ≥ 75% (intermediate between Phase 1 ≥70% and Phase 2A ≥85%).
- Per-runtime first-try validity ≥ 70% (no runtime falls behind).
- Each archetype individually ≥ 60% first-try (no archetype is a quiet outlier).
- End-to-end pipeline success (validate → compile → push-as-draft) ≥ 90% on prompts with `ground_truth_ir`, on both runtimes.
- Conformance matrix 100% green on both runtimes for all cells touched by the corpus.
- Runtime parity test: 5/5 archetypes pass `parity_ok`.

If any threshold misses, do not write the gate report green. Iterate prompts / Planner / compiler until met or document the deviation in `reports/coverage-by-archetype.md`.

- [ ] **Step 3: Commit artifacts**

```bash
git add reports/eval-full-corpus.json reports/coverage-by-archetype.md
git commit -m "docs(eval): Phase 1.5 full-corpus pass; per-archetype × per-runtime breakdown"
```

---

## Task 7: CI wiring

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/conformance.yml`

- [ ] **Step 1: Fast lane** — Phase 1.5 corpus structure tests + parity tests run on every PR (without live runtime; uses fakes).

- [ ] **Step 2: Slow lane** — pinned Hiagent + pinned Dify both up; conformance matrix runs against both; parity test runs end-to-end. Tear down on completion.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/conformance.yml
git commit -m "ci: dual-runtime conformance + parity in slow lane"
```

---

## Task 8: Phase 1.5 release gate

**Files:**
- Create: `reports/phase-1-5-gate.md`

PRD §7: "Phase 1.5 — 覆盖扩展. 扩展至 5 类场景；Hiagent + Dify 双运行时覆盖率达成。"

- [ ] **Step 1: Run all gates**

```bash
ruff check . && mypy loom && pytest -v
LOOM_DIFY_LIVE=1 LOOM_DIFY_KEY=<key> pytest tests/conformance/ tests/runtimes/dify/ -v
LOOM_HIAGENT_LIVE=1 LOOM_HIAGENT_KEY=<key> pytest tests/conformance/ tests/runtimes/hiagent/ -v
```

- [ ] **Step 2: Write `reports/phase-1-5-gate.md`**

```markdown
# Phase 1.5 gate

Date: YYYY-MM-DD
Pinned Hiagent: <tag@digest>   # ADR 0002 (Hiagent section)
Pinned Dify: <tag@digest>      # ADR 0002 (Dify section); enter "N/A — escape hatch invoked YYYY-MM-DD" if dropped
Cost-budget escape hatch: not invoked | invoked YYYY-MM-DD reason: <brief>

## Coverage success criteria

| Criterion | Target | Hiagent | Dify | Notes |
|---|---|---|---|---|
| Per-runtime first-try IR validity | ≥ 70% | NN% | NN% (or N/A) | If Dify dropped, mark N/A; Hiagent must still hit ≥70%. |
| Min per-archetype first-try validity | ≥ 60% | NN% | NN% (or N/A) | per archetype × runtime |
| End-to-end pipeline success on prompts with ground-truth IR | ≥ 90% | NN% | NN% (or N/A) | per runtime |
| Per-runtime compiler covers all 5 archetypes | 5/5 | N/5 | N/5 (or N/A) | |
| Reverse compiler stays narrow on (01, 05) | confirmed | confirmed/violated | confirmed/violated (or N/A) | |
| Semantic conformance (touched cells) | 100% green | NN of NN | NN of NN (or N/A) | |
| Conformance flake rate | <2% (>5% blocks) | NN% | NN% (or N/A) | |

| Cross-runtime criterion | Target | Status | Notes |
|---|---|---|---|
| Overall first-try IR validity (combined registered runtimes) | ≥ 75% | NN% | If only one runtime registered, equals that runtime's rate. |
| Runtime parity test | 5/5 | N/5 (or "skipped — single runtime") | parity is `skipped` per `loom.conformance.parity.run` when only one runtime is registered (see Task 5); skipped is not a fail. |

## Failure taxonomy breakdown (PRD §10)

| Bucket | Hiagent | Dify | Total |
|---|---|---|---|
| schema | NN | NN | NN |
| reference | NN | NN | NN |
| type_flow | NN | NN | NN |
| policy | NN | NN | NN |
| compile | NN | NN | NN |
| deploy | NN | NN | NN |
| reverse_compile | NN | NN | NN |
| registry_acl | NN | NN | NN |
| semantic_conformance | NN | NN | NN |
| platform | NN | NN | NN |
| human_review | NN | NN | NN |

## Cost / latency

- Median Planner cost per prompt: $0.NN (target <$0.20)
- P95 Planner cost: $0.NN (target <$1.00)
- Median Planner latency: NNs (target <30s)
- Median intent-to-draft visible time: NN minutes (target <10)

## Decision

If every row above is `pass` → Phase 2A unblocked.
If any row is `fail` → iterate until green. Do not advance.
```

- [ ] **Step 3: Commit + reviewer pass**

```bash
git add reports/phase-1-5-gate.md
git commit -m "docs: Phase 1.5 gate report"
```

Send to reviewer (`/ask codex "[CODE REVIEW REQUEST] ..."`). Pass criteria per CLAUDE.md §5.

---

## Self-review summary

- **Spec coverage:** PRD §7 Phase 1.5 mandates "扩展至 5 类场景" + dual-runtime parity. Both are present (Tasks 1–2 widen Dify + Hiagent compilers; Task 5 enforces parity contract). PRD §10.1 corpus ≥75 → Task 3. PRD §10.3 first-try IR validity targets are explicit in Tasks 6 + 8.
- **Removed in this revision:** n8n compiler stub, ADR 0006 (n8n version pin), ADR 0007 (portability redlines), n8n docker compose, n8n live import, redline manifest UI plumbing. n8n is out of v1 scope per project owner decision 2026-05-06. Runtime portability is now proven by construction in Phase 1 (dual compile from one IR), not by a falsifiable refusal stub.
- **Type consistency:** `IRDocument`, `Prompt`, `EvalReport`, `ArchetypeReport`, `RuntimeArchetypeReport`, `FailureRecord`, `Bucket`, `Runtime`, `ParityOutcome` — names stable across compiler / runner / report / conformance / runtime-adapter modules.
- **Known seams to Phase 2A:** (a) Reverse compilers still narrow; Phase 2A widens to all 5 on both runtimes. (b) Deployer is push-as-draft on both; Phase 2A adds drift detection + publish-blocking on both. (c) Registry is in-tree; Phase 2A makes it git-versioned + Postgres-mirrored.

---

## Execution Handoff

Plan complete. Recommended execution modes:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task; review between tasks.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch with checkpoints.
