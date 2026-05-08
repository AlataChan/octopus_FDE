# ADR 0024 — Hiagent v2.6 bundle compilation contract

**Status:** Accepted
**Date:** 2026-05-08

## Decision

The Phase 1 Hiagent compiler emits a **multi-file bundle** matching the real Hiagent v2.6 export schema (verified against customer-supplied samples on 2026-05-08), not a single-JSON "logical IR rendering". Compilation is **one-shot using a pre-supplied customer Binding file**; no placeholders, no post-generation patching.

### Bundle structure

```
<bundle-name>_v<X.Y.Z>_<timestamp>/
├── index.yaml                      DLVersion + MetaType + MainMeta + MainUniqueName
├── workflow/<name>.yaml            FlowType=Workflow + Nodes[] + Depends + Layout
├── agent/<name>.yaml               (when an IR maps to an Agent app, not just a workflow)
├── knowledge/<id>.yaml             (only emitted when binding pre-fills knowledge IDs)
├── model/<id>.yaml                 (only emitted when binding pre-fills model IDs)
└── asset/upload/                   (placeholder dirs; empty .DS_Store filtered out)
```

The bundle is delivered as a `.zip` to match Hiagent's import UX.

### Node emission contract

Per the customer samples, Hiagent workflow nodes use:

- **Node identity:** `Code` (template/factory id) + `ID` (instance id), both **20-char lowercase alphanumeric** (`^[a-z0-9]{20}$`). We generate fresh IDs client-side; self-hosted Hiagent accepts client-generated IDs on fresh import.
- **PascalCase type names:** `Start`, `End`, `LLM`, `KnowledgeBase`, `Code`, `Intent`, `Loop`, `Agent`, `HTTPRequest`, `VariableAggregator`. (Mapping from IR types in §IR-mapping below.)
- **Type-keyed config:** `Configs.<TypeName>: { ... type-specific fields ... }`.
- **Layout (required):** `Layout: { X: <float>, Y: <float> }` per node. Auto-computed by topological-sort + grid layout (300px node width, 200px row height).
- **Edges via Depends, not a separate edges array:** each node carries `Depends: [{NodeCode: <upstream-Code>, TargetPortID: <port>}]`. Edge data lives at the destination node, not the source.
- **ErrorConfig:** `{ErrorConfigType: None}` on every node (default; customizable in v1.1).

### Variable reference translation

IR string-form `${node_id.field}` / `${node_id.field.subfield}` → Hiagent object form:

```yaml
Name: <local-binding-name>      # set by the consuming node's slot definition
NodeCode: <source-node-Code>     # the `Code` of the node that produced the value
Path: field.subfield             # everything after the node_id
RefType: node_field              # or: tmp_variable | const | sys
```

`RefType` selection:
- `node_field` for normal node-output references
- `tmp_variable` for loop-internal variables (Hiagent's `InterVariables` mechanism)
- `const` and `sys` reserved for v1.1

The translator lives inside per-node emit functions (each node knows its slot semantics); a standalone `parse_varref` helper extracts `(node_id, dotted_path)` from the `${...}` string.

### Type code table

Hiagent uses numeric type codes in `InputSchema` / `OutputSchema`. Best-guess mapping based on customer sample (verified at first customer import; revise if wrong):

| IR TypeName | Hiagent `Type` code |
|---|---|
| `string` | 0 |
| `number` | 2 |
| `boolean` | 3 |
| `object` / `json` | 4 |
| `string[]` / `number[]` / `json[]` | 5 |
| `null` | 6 |
| `any` / `chunks` / `file` | 0 (string fallback; v1.1 may add codes) |
| (integers only) | 1 |

The mapper raises if it encounters an unmappable type; the IR Validator must reject those before compile.

### IR ↔ Hiagent node mapping

| IR | Hiagent | Loss / wrapper |
|---|---|---|
| `trigger` (manual / schedule / webhook) | `Start` (mode in `Configs.Start`) | none |
| `llm` | `LLM` | `output_schema` JSON Schema → Hiagent `OutputSchema` array (lossy: nested object schemas flatten one level) |
| `retrieval` | `KnowledgeBase` | `dataset` → binding `dataset_id_map[handle]` (empty string if not pre-bound) |
| `http` | `HTTPRequest` | `idempotency_key` carried as data field (Hiagent honors via retry config) |
| `code` | `Code` | python/javascript pass-through |
| `condition` | `Intent` | IR `branches[].when` becomes Intent `Intentions[].Description`. **Lossy**: Hiagent `Intent` is LLM-classifier-driven, IR `condition` is rule-driven. v1.1 may add an IR `intent` node to express this faithfully. |
| `loop` | `Loop` | `max_iterations` honored. IR cannot express `LoopType: Infinite` (Hiagent's chat-dispatch loop). |
| `parallel` | (children expanded; no native `Parallel` node in v2.6 graph mode) | Branches emitted as parallel paths from a fan-out source; merge handled at merge-strategy level. v1.1 may use `VariableAggregator` for `object_merge`. |
| `agent` | `LLM` (with tools list) | Hiagent's workflow-level `Agent` node = sub-agent call (not our IR `agent`). v1.1 may add IR `subworkflow_call` node. |
| `output` | `End` | `bindings` → Hiagent `OutputSchema` + `Template` |

### Customer Binding file

A **per-customer artifact** filled once at onboarding:

```yaml
customer: <customer-id>
target: hiagent
target_version: "2.6"

# Required — fail-fast if missing.
workspace_id: <hiagent-workspace-id>

# Optional — empty / unset means "customer wires in Hiagent UI after import".
dataset_id_map: {}        # IR dataset handle → Hiagent KB id
model_id_map: {}          # IR model handle → Hiagent model id
rerank_model_id: ""       # Hiagent rerank model id (single, used by all KB nodes)
tool_id_map: {}           # IR tool handle → Hiagent tool/plugin id
```

The Binding lives at `config/customers/<customer>.<target>.yaml` and is passed to `loom compile` via `--binding <path>`. CLI errors if path is missing or `workspace_id` is empty.

### CLI surface

```
loom compile <ir.json> --target hiagent --binding <path> --out <name>.zip
```

- Output is a `.zip` ready to import via Hiagent self-hosted "Import App / Import Workflow" flow
- If binding is incomplete on optional fields, CLI **prints a one-line summary** of what's empty so the customer knows what to fill in the UI after import
- If binding is missing or incomplete on required fields (workspace_id), CLI fails with a clear diagnostic

### HITL placement

| Touchpoint | What | When | Why here |
|---|---|---|---|
| Customer onboarding | Fill Binding file (workspace_id minimum, KB/Model optionally) | Before any workflow generation | Customer-level info, not workflow-level; one-shot |
| FDE Session | Persona Brief → Workflow Brief → clarify questions | Per workflow | Workflow-specific intent / data / approval policy |
| (Optional) Hiagent UI | Wire empty KB/Model slots | After import, if binding wasn't pre-filled for them | Hiagent's native UI handles this faster than us re-emitting |

There is **no HITL after compile and before import**. Either compile is one-shot ready or it's an error.

## Consequences

- The current `loom/runtimes/hiagent/v2_6/{compiler,compiler_nodes,wrappers}.py` (Phase 1 Task 11.5 forward-only output) is replaced wholesale; existing tests (`tests/runtimes/hiagent/v2_6/test_compiler_nodes.py`) are rewritten to match the new bundle output.
- `HiagentAdapter.compile(ir)` returns a structured `HiagentBundle` object (a Pydantic model with the full file tree); `serialize_dsl(bundle)` writes a real ZIP file.
- Future option C (auto-fetch binding via Hiagent API) adds `loom/runtimes/hiagent/client.py` + a `loom hiagent fetch-binding` CLI subcommand; declared out-of-scope for v1.
- Dify compilation will follow the same Binding pattern (separate ADR 0025 once Hiagent is validated by a real customer import).
- The Type code table and the IR↔Hiagent mapping in this ADR are best-guess until the first real customer import succeeds; both are revised in-place (this ADR is the living source of truth) when reality contradicts.
