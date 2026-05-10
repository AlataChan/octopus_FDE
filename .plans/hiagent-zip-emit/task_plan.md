# task_plan: Hiagent zip-emit (Chat + ChatFlow)

**Status**: v2, Codex Plan-Reviewed 2026-05-10 (overall 7.1, PASS). Changes from v1 marked `[v2]`.

## Goal

Sink the live-verified Hiagent zip-import path (cracked 2026-05-10 against `hia.volcenginepaas.com`) into the project so a future engagement can produce a working bundle via:

```bash
loom compile examples/ir/01-ecommerce-customer-faq.json \
    --target hiagent --mode chatflow \
    --binding config/customers/<customer>.hiagent.yaml \
    --out out.zip
# then user drags out.zip into Hiagent UI → import succeeds
```

Today this only works because I assemble the zip with inline Python inside Bash invocations; nothing in `loom/` produces it.

## Reference

`docs/runtimes/hiagent/zip-import-format.md` — full schema, the 4 zip-format hard rules, ChatFlow-specific gotchas, server-side iteration loop. **Plan must be consistent with this doc — if you find divergence, the doc wins because it captures live-verified behavior.**

## Scope (Phase 1)

### S1. `HiagentBundle.to_zip_bytes()` — emit zip with flat layout + MD5 trailer

**File**: `loom/runtimes/hiagent/v2_6/bundle.py`

`[v2]` Method named `to_zip_bytes()` (Codex review: bundle should not own adapter terminology). `HiagentAdapter.serialize_dsl(dsl)` becomes a one-line delegation `return dsl.to_zip_bytes()`.

Currently `HiagentBundle` is just a name + dict of files. Add a method that:

1. Iterate `self.files`; each entry's key is the in-zip path (already flat — no `bundle_name/` prefix).
2. yaml.safe_dump each value with `sort_keys=False, allow_unicode=True`.
3. Write to a `zipfile.ZipFile` with `ZIP_DEFLATED`.
4. Append 32-ASCII-hex bytes of `md5(zip_bytes_so_far)` past the EOCD record (literal append after the file is closed; do NOT touch zip via the zipfile API once closed).
5. Return `bytes`.

`[v2]` Add docstring on the function pointing at `docs/runtimes/hiagent/zip-import-format.md` for the 4 hard rules; future maintainers must not regress.

### S2. `loom compile --target hiagent` rewrite — emit zip, not yaml

**File**: `loom/cli/commands/compile.py`

1. Add `--mode {chat,chatflow}` flag (default: `chat` for safety; mirrors `loom hiagent push --mode`).
2. When `target == hiagent`, instead of writing the inspection yaml, call:
   - For `chat` mode: existing `compile_ir(ir, binding)` (already returns Chat-shape bundle).
   - For `chatflow` mode: a new `compile_ir_chatflow(ir, binding)` (see S3) that returns a ChatFlow-shape bundle.
3. `[v2]` `--out` extension handling — explicit, no silent rewrites:
   - `foo.zip` or `foo` (no ext) → write zip to `foo.zip`
   - `foo.yaml` / `foo.yml` / `foo.json` → **error out** with message "use `--inspect` for yaml inspection mode, or pass a .zip path"
4. `[v2]` Add `--inspect` flag (mutually exclusive with `--mode`): when set, emit the single agent yaml at `--out` (the legacy behavior). This preserves Codex's safety concern for callers who still want yaml inspection. CLI help must clearly document the breaking default change.
5. Write `bundle.to_zip_bytes()` bytes to `--out`.
6. Print success line + "drag this zip into Hiagent's 导入智能体 wizard" hint.

### S3. `compile_ir_chatflow()` + auto-emit sidecars + filename rule fix

**File**: `loom/runtimes/hiagent/v2_6/compiler.py`

`[v2]` **Critical filename fix (Codex high-severity flag)** — `compile_ir()` line 63 currently safe-ifies the agent filename: `safe_name = ir.metadata.name.replace(" ", "_")`. **This violates zip-format hard rule #3** (agent file path must equal `agent/<MainMetaName>.yaml`, exact, including spaces/unicode). Today's manual zip success only happened because I worked around this in inline scripts. The fix:
- Drop the safe-ify; use `ir.metadata.name` verbatim for both `index.MainMetaName` and the agent yaml filename.
- Apply this fix to both Chat (`compile_ir`) and ChatFlow (`compile_ir_chatflow`) paths.
- `bundle_name` (the dir name embedded in the zip's filename) keeps the safe-ify since that's just the visible filename, not parsed.

Add a new public function `compile_ir_chatflow(ir, binding) -> HiagentBundle` that:

1. Calls existing `build_chatflow_config_draft(ir, binding)` to get the inline `ChatFlowDetail`.
2. Builds a ChatFlow-shape agent yaml (the deltas-vs-Chat are listed in `docs/runtimes/hiagent/zip-import-format.md` "Agent yaml shape for ChatFlow"):
   - `AppConfig.AgentMode = ""`, `AppConfig.ChatFlowDetail = <chatflow_detail>`
   - `AppConfig.SingleAgentConfig` retains most fields but with `ModelID/ModelName/KnowledgeIDs/WorkflowIDs/ToolIDs` zeroed AND adds `ChatFlowConfig: {ChatAdvancedConfig, RoundsReserved: 23, Version, WorkflowID, WorkflowPublishID: ""}`.
   - `AppInfo.AgentMode = ""`, `AppInfo.AppType = "ChatFlow"`.
3. Builds index.yaml (same shape as Chat; `MainMeta: Agent` regardless). **All 5 required fields populated**: `DLVersion: "0.0.1"`, `FromWorkspaceID: <binding.workspace_id>`, `MainMeta: "Agent"`, `MainMetaName: <ir.metadata.name>`, `MainUniqueName: <agent_id>` — and `MainUniqueName` MUST equal the agent yaml's `UniqueName` and `AppConfig.AppID`.
4. **For each populated `AppDepends.ModelMap` entry, emit `model/<Name>.yaml`** with the schema in the doc. Use the entry's `Name` field as the file stem (must match exactly).
5. **For each populated `AppDepends.KnowledgeMap` entry, emit `knowledge/<Name>.yaml`** — minimal `data` block (DirectoryID:default, IndexingTechnique:0, etc.); this matches gold simpler sample's pattern.
6. `[v2]` **Empty-map behavior**: if the IR's resolved `ModelMap` is empty, the bundle still emits successfully (no sidecar) and CLI prints a warning: `"warning: no model bound; agent will require manual model selection in Hiagent UI after import"`. Same for KnowledgeMap. This makes empty-binding the default-safe path with explicit user signal.
7. Returns `HiagentBundle` with all the above as flat-keyed files.

Same auto-sidecar logic applies to the existing `compile_ir()` Chat path. Today it emits only index + agent yaml; the model sidecar must be added there too so the Chat zip is consumable end-to-end.

### S4. Model-name resolution rule

`[v2]` Collapsed per Codex review (no design alternatives in plan).

**Rule**: model sidecar `Name` = IR model handle (e.g. `configured-small-model`); `UniqueName`/`ID` = `binding.resolve_model(handle)`; sidecar filename = `Name` (so `model/<handle>.yaml`). This applies symmetrically to `AppDepends.ModelMap[<id>].Name` so that the front-end's `fileTree["model/" + n.Name]` lookup hits.

No new field needed in `HiagentBinding`. Doc's "Things that do NOT matter" section confirms `ModelName` matching the platform's display name is not required for import success — the ID is the wire.

### S5. Tests

**Files**: `tests/runtimes/hiagent/v2_6/test_compiler.py` (add cases) + new `test_bundle_zip.py` + `tests/fixtures/test.hiagent.yaml` (committed; populated bindings).

`[v2]` Codex review expanded the test surface. Schema-shape tests, not byte-for-byte (per `feedback_gold_sample_method.md`).

**`[v2]` Test fixture binding** (new file `tests/fixtures/test.hiagent.yaml`):

```yaml
customer: test
target: hiagent
target_version: "2.6"
workspace_id: ws_test_synthetic
dataset_id_map:
  product_kb: ds_test_001
  policy_kb: ds_test_002
model_id_map:
  configured-small-model: model_test_small
  configured-planner-model: model_test_planner
rerank_model_id: model_test_rerank
tool_id_map: {}
```

Populated so model/knowledge sidecar emit logic is actually exercised. Empty-binding test uses `config/customers/example.hiagent.yaml`.

**Test cases**:

1. **`test_zip_format_hard_rules`** — covers all 4 zip hard rules (regression):
   - Build via `compile_ir(ir, binding).to_zip_bytes()`.
   - Parse with `zipfile.ZipFile(BytesIO(b))`. Every `namelist()` entry must:
     - Not start with `<bundle_name>/`, not start with `/`, not contain `\\`, end with `.yaml`-stem-or-asset-path.
   - `b[-32:]` is 32 ASCII hex chars (regex `^[0-9a-f]{32}$`).
   - `hashlib.md5(b[:-32]).hexdigest() == b[-32:].decode()`.

2. **`test_index_yaml_required_fields`** — `[v2]` (Codex correctness flag):
   - Index.yaml has all 5 fields: `DLVersion`, `FromWorkspaceID`, `MainMeta`, `MainMetaName`, `MainUniqueName`.
   - `MainMeta == "Agent"`.
   - `MainMetaName` exists at path `agent/<MainMetaName>.yaml` in the bundle.
   - `MainUniqueName == agent.UniqueName == agent.AppConfig.AppID`.

3. **`test_agent_filename_preserves_spaces`** — `[v2]` (Codex high-severity flag):
   - Use an IR with `metadata.name = "Foo Bar Baz"` (spaces).
   - Assert zip contains entry `agent/Foo Bar Baz.yaml` exactly. No underscored variant.

4. **`test_chatflow_shape`** — ChatFlow agent yaml structure:
   - `AppType == "ChatFlow"`, `AgentMode == ""` at both `AppConfig` and `AppInfo` levels.
   - `ChatFlowDetail.Nodes` non-empty.
   - `SingleAgentConfig.ChatFlowConfig.WorkflowID == ChatFlowDetail.ID`.

5. **`test_chatflow_start_canonical_schema`** — `[v2]` (Codex correctness flag, both schemas):
   - Both `Configs.Start.InputSchema` AND `Configs.Start.OutputSchema` contain exactly 3 entries: `query`, `files`, `chat_histories` with Types `0, 11, 9` respectively.
   - `files.SubParameters` has `name`, `url` both required, Type 0.
   - `chat_histories.SubParameters` contains nested `files` with same SubParameters as top-level.

6. **`test_chatflow_knowledge_field_types`** — `[v2]` (Codex regression flag):
   - For every Knowledge node in `ChatFlowDetail.Nodes`:
     - `node.Type == "Knowledge"` (not "KnowledgeBase" — that's the IR-side name).
     - `Configs.Knowledge.RetrievalSearchMethod == 0` (int, not "semantic" string).
     - `Configs.Knowledge.TopK` is int.

7. **`test_model_sidecar_emitted_when_bound`** — uses populated test fixture:
   - For each `AppDepends.ModelMap[<id>].Name`, bundle has `model/<Name>.yaml` with matching `UniqueName: <id>`.

8. **`test_no_sidecar_emitted_when_unbound`** — uses empty `example.hiagent.yaml`:
   - `AppDepends.ModelMap == {}`, no `model/*` entries in bundle, no error raised.

9. **`test_cli_chat_smoke`** — end-to-end:
   - Run `loom compile --target hiagent --mode chat --binding tests/fixtures/test.hiagent.yaml --out /tmp/x.zip`.
   - Parse, assert namelist contains `index.yaml`, `agent/<name>.yaml`, `model/<name>.yaml` entries.

10. **`test_cli_chatflow_smoke`** — same but `--mode chatflow`.

11. **`test_cli_rejects_yaml_extension`** — `[v2]` (Codex auto-append flag):
    - `--out foo.yml` without `--inspect` → CLI exits non-zero with helpful error message.

No test depends on the customer gold sample (gitignored).

### S6. Cleanup

- Delete the live debug zip artifacts at project root (`Ecommerce Customer FAQ_chatflow_v1.0.0_*.zip`). They are already gitignored (`*.zip`).
- The hand-edits to `config/customers/bambu.hiagent.yaml` (model_id_map filled with our test IDs) — leave as is, file is gitignored.

## Out of scope (Phase 2+, do NOT include)

- Workflow type (`AppType: Workflow`) emit
- MultiAgent type (`AgentMode: MultiAgent`) emit
- Sub-workflow ChatFlow (with `workflow/<name>.yaml` sidecar that points to a sub-flow)
- Asset binary placeholders (`asset/upload/full/<sha>/<sha>/<rest>`) — minimal bundle leaves `LogoPath: ""` per doc
- Programmatic upload (cookie + csrf flow against `/api/bypass/up?Action=...`)
- IR `buyer_locale` and other non-canonical inputs flowing into ChatFlow Start (`VariableConfigs` route)

These all have outstanding-questions entries in the doc; revisit when a customer engagement requires them.

## Verification commands

```bash
# Type / lint / test
.venv/bin/ruff check loom/ tests/
.venv/bin/mypy loom/runtimes/hiagent/
.venv/bin/pytest tests/runtimes/hiagent/v2_6/ -v

# CLI smoke (chat)
.venv/bin/python -m loom.cli.main compile examples/ir/01-ecommerce-customer-faq.json \
    --target hiagent --mode chat \
    --binding config/customers/bambu.hiagent.yaml \
    --out /tmp/chat.zip
unzip -l /tmp/chat.zip   # expect: index.yaml, agent/<name>.yaml, model/<name>.yaml at root
xxd -s -32 /tmp/chat.zip | tail -1   # expect: 32 ASCII hex chars

# CLI smoke (chatflow)
.venv/bin/python -m loom.cli.main compile examples/ir/01-ecommerce-customer-faq.json \
    --target hiagent --mode chatflow \
    --binding config/customers/bambu.hiagent.yaml \
    --out /tmp/chatflow.zip
unzip -l /tmp/chatflow.zip
```

`[v2]` The CLI-smoke zips should be **schema- and import-behavior equivalent** to the manually-built v5 (chat) and ChatFlow v3 (chatflow) zips that imported successfully today. Specifically: (a) flat zip entries, (b) MD5 trailer present and valid, (c) index.yaml's 5 required fields all populated, (d) agent yaml satisfies the per-mode shape contract above, (e) when manually dragged into `hia.volcenginepaas.com` the import wizard accepts the bundle. No byte-for-byte equivalence is expected (gen_id() randomness + timestamps).

## Sequence (no parallelism)

1. S4 (binding model-name) — small, isolated
2. S1 (bundle serialize_dsl) — depends on nothing
3. S3 (compile_ir_chatflow + sidecar emit) — depends on S1, S4
4. S2 (CLI rewrite) — depends on S3
5. S5 (tests) — written alongside each step, run all at the end
6. S6 (cleanup) — last

## Risks

- **R1**: `zipfile.ZipFile` may write entries in the wrong order or with file metadata that breaks Hiagent's parser. **Mitigate**: today's manual-build zips work using the exact same `zipfile.ZIP_DEFLATED` API; just keep the call shape identical.
- **R2**: yaml.safe_dump's default key ordering differs from gold sample's order. Front-end normalize regex doesn't care about yaml key order, only file paths. Server's Go unmarshal also doesn't care about order. **Mitigate**: pass `sort_keys=False` and rely on Python dict insertion-preservation.
- **R3**: ChatFlow agent yaml has duplication between `ChatFlowDetail.Depends` (an AppDepends-shaped dict) and the top-level `AppDepends`. Gold sample has both populated independently. **Mitigate**: re-use `_build_app_depends()` for both, accept duplication.
- **R4**: After landing this, the existing `loom hiagent push` (TOP API path on the original `101.126.68.43` deployment) must still work. **Mitigate**: don't touch `hiagent_push.py`; it depends on `build_agent_config_draft` / `build_chatflow_config_draft` which we're not changing in shape.

## Definition of done

- All verification commands pass green
- A clean `loom compile --target hiagent --mode chatflow --out ecommerce.zip` produces a zip that, when manually dragged into `hia.volcenginepaas.com` import wizard, imports successfully (= reproduces today's manual result)
- New tests cover S1's MD5 trailer + flat-layout, S3's ChatFlow agent shape + `_CHATFLOW_START_SCHEMA` presence + Knowledge.RetrievalSearchMethod==0
- `[v2]` All 11 S5 test cases pass; the existing 14 hiagent tests still pass (no regression)
- `[v2]` `compile_ir()` and `compile_ir_chatflow()` docstrings cross-reference `docs/runtimes/hiagent/zip-import-format.md` so future edits do not drift from the live-import contract
- `[v2]` CLI help (`loom compile --help`) clearly mentions the breaking default change to zip output and points to `--inspect` for the legacy yaml path
