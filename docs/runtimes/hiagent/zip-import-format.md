# Hiagent ZIP-import bundle format (self-hosted v2.6)

Notes recovered live from `hia.volcenginepaas.com` (Volcengine PAAS Hiagent) on 2026-05-10. All findings come from comparing a customer-exported gold sample (`用户维修方案_v1.0.6_20260508133220.zip`) against successive minimal builds and decoding the relevant front-end chunk (`static/js/async/861.0e76b8f9.js`).

These constraints are not in any public Hiagent doc.

## Where ZIP-import lives

Front-end "导入智能体" wizard:

1. `up?Action=CreateMultipartUpload` — content-addressed dedup; if `Result.Exist=true` the file already lives in TOS, no part upload needed.
2. `up?Action=UploadPart` + `Action=CompleteMultipartUpload` — actual TOS multipart upload.
3. **Client-side parse** of the uploaded ZIP (this is where every failure we hit happened).
4. `app?Action=CheckImportCreate` / `Action=CheckImportAppDepends` — server-side validation.
5. `app?Action=ImportAppFromDSL` — the actual import.

If the client-side parse throws, no `app?Action=...` ever fires. That's the case to watch for in DevTools Network.

## The four non-obvious requirements

### 1. ZIP entries must be flat at the archive root

The bundle directory name is the *filename* of the zip (e.g. `<agent>_v1.0.0_<ts>.zip`). Inside the zip, **do not** prefix entries with that directory name.

Front-end normalizes each entry path with:

```js
x = p.replace(/^(asset\/)|.yaml$/g, "")
```

then stores it in `fileTree[x]`. With a `<bundle>/` prefix, the key becomes `<bundle>/index` instead of `index`, and the lookup `fileTree.index.json.MainMetaName` throws:

> Cannot read properties of undefined (reading 'json')

Required layout (mirrors gold sample):

```
index.yaml
agent/<MainMetaName>.yaml
workflow/<workflow-name>.yaml      # ChatFlow only
knowledge/<dataset-name>.yaml      # if AppDepends.KnowledgeMap is non-empty
model/<model-name>.yaml            # if AppDepends.ModelMap is non-empty
asset/upload/full/<sha[0:2]>/<sha[2:4]>/<rest>   # binary placeholders for icons / logos
```

Note: macOS Finder extracting a zip will create a wrapper folder named after the zip, which makes it look like the zip "had" a top-level dir. `unzip -l` shows the truth.

### 2. ZIP must carry a 32-byte ASCII MD5 trailer after EOCD

Hiagent appends a content checksum after the End-Of-Central-Directory record. Without it the wizard rejects with:

> No signature found after EOCD record

The trailer is **not a cryptographic signature** — it is the md5 of the entire zip body, written as 32 ASCII hex chars (16 bytes of digest × 2). We recompute and append it ourselves:

```python
zip_bytes = path.read_bytes()
sig = hashlib.md5(zip_bytes).hexdigest().encode("ascii")  # 32 ASCII bytes
path.write_bytes(zip_bytes + sig)
```

Verification on gold sample: `md5(zip[:eocd_end]) == ascii_decode(zip[eocd_end:])` — exact match.

`unzip -l` keeps working because the trailer sits past EOCD; standard zip readers ignore it.

### 3. `MainMetaName` in `index.yaml` must equal the filename stem of the agent yaml

Front-end then does:

```js
mainContent = fileTree[`agent/${MainMetaName}`]
```

So if `index.yaml` has `MainMetaName: "Foo Bar"`, the agent file must be `agent/Foo Bar.yaml` (spaces and unicode preserved). Any divergence (e.g. compiler safe-name'ing spaces to underscores in the filename only) produces another `undefined.json` throw.

Same rule applies to `model/<n.Name>` and `knowledge/<n.Name>` lookups: the file names match the `Name` field in the corresponding `AppDepends.*Map` entry exactly.

### 4. `index.yaml` schema (5 required fields)

```yaml
DLVersion: 0.0.1
FromWorkspaceID: <source workspace id; can differ from importing workspace>
MainMeta: Agent                      # literal "Agent" for both Chat and ChatFlow
MainMetaName: <agent display name>   # must match agent/*.yaml filename stem
MainUniqueName: <agent UniqueName>   # 20-char base32 ID; matches agent yaml UniqueName
```

`FromWorkspaceID` does not have to match the importing workspace — gold sample had `d31pcnoboot936af1tsg` (customer's workspace) and imported fine into `personal-d65fp6amlv625h73nr80`.

## Agent YAML schema (Chat mode)

Top-level keys (verified equal to gold sample's, both ours and gold registered identical paths in deep-diff):

```yaml
AppConfig:
  AgentMode: Single | "" | MultiAgent
  AppID: <UniqueName>
  ChatFlowDetail: null              # or full graph for ChatFlow
  MultiAgentConfig: null            # or populated for MultiAgent
  SingleAgentConfig:                # required for Chat / ChatFlow Single
    A2aAgentIDs: []
    AgentIDs: []
    ChatAdvancedConfig: {...}
    DatabaseIDs: []
    GraphConfig: {MatchType, SearchDepth, SearchType, TopK}
    GraphIDs: []
    KnowledgeConfig: {RerankID, Similarity, TopK, ContextComponents, ...}
    KnowledgeIDs: []                # IDs from importing workspace
    ModelConfig: {Strategy, MaxTokens<=4096, Temperature, ...}
    ModelID: <real model ID from target workspace>
    ModelName: <model handle / display name>
    PrePrompt: <system prompt>
    PromptConfig: {PromptMode: regex}
    QADatasetConfig: {...}
    QADatasetIDs: []
    SummaryModelID: ""
    SummaryModelName: ""
    TerminologyConfig: {...}
    TerminologyIDs: []
    ToolIDs: []
    UpdateTime: "YYYY-MM-DD HH:MM:SS"
    VariableConfigs: []
    Version: v1.0.0
    VersionDescription: ""
    WorkflowIDs: []
  WorkspaceID: <importing workspace id>
AppDepends:
  AppMap: {}
  DataSourceMap: {}
  DatabaseMap: {}
  KnowledgeMap: {<id>: {ID, Name, Desc, LogoPath, ResourceWorkspaceID, SourceTypes:[SkillInfo]}}
  ModelMap: {<id>: {ID, Name, Desc, LogoPath, SourceTypes:[Agent]}}
  PluginMap: {}
  QADataSetMap: {}
  TermDatasetMap: {}
  ToolMap: {}
  WorkflowMap: {}
AppInfo:
  AgentMode: Single | "" | MultiAgent
  AppID: <UniqueName>
  AppType: Chat | ChatFlow
  WorkspaceID: <importing workspace id>
DLVersion: 0.0.1
Desc: <description>
DisplayName: <agent display name>
LogoPath: ""                        # or asset/upload/... reference
MetaType: Agent
UniqueName: <UniqueName>
UpdatedAt: <epoch ms>
VersionCode: <random 20-char base32>
VersionName: v1.0.0
```

The ID format is **20-char base32**. First char varies (we observed `d…`, `c…`, `cpg2…`); there is no `d`-prefix requirement.

## Model sidecar (`model/<Name>.yaml`)

```yaml
DLVersion: 0.0.1
DeletedAt: null
Desc: ""
DisplayName: <Name>
Implement: volcengine | openai | ...
IsDefault: true
IsPublic: true
Key: <Name>                         # gold has trailing-version variants like "doubao-seed-1.6-251015"
LogoPath: ""
MetaType: Model
Source: system | custom
SourceTypes: [Agent]
TenantId: <importing tenant id>
Type: text-generation | embedding | rerank
UniqueName: <model ID — must exist in target workspace's ListModelByWorkspaceGrant>
UpdatedAt: <epoch ms>
VersionCode: ""
VersionName: ""
```

## Knowledge sidecar (`knowledge/<Name>.yaml`)

Schema observed from gold sample. The `data` block carries the dataset metadata; the outer wrapper is the bundle-level manifest.

```yaml
DLVersion: v1.0.0
Desc: ""
DisplayName: <Name>
LogoPath: upload/full/<sha2>/<sha2>/<rest>
MetaType: kbs_dataset
UniqueName: <dataset ID>
UpdatedAt: <epoch ms>
VersionCode: <dataset ID>
VersionName: v1.0.0
data:
  DirectoryID: default
  EmbeddingModelID: <embedding model ID>
  IconSha256: <sha256 of icon binary, no slashes>
  IndexingTechnique: 0
  Name: <Name>
  RetrievalSearchMethod: 0
  SpaceType: 1
  TenantID: <tenant id>
  WorkspaceID: <source workspace id>
  XID: <dataset ID>
  # plus a dozen optional null/false fields
```

## Asset binary layout (`asset/upload/full/...`)

Hiagent uses content-addressed storage, sharded by sha256 prefix:

```
asset/upload/full/<sha[0:2]>/<sha[2:4]>/<sha[4:]>
```

These are referenced from `LogoPath` / `Icon` fields elsewhere (e.g. `LogoPath: upload/full/1b/b2/41932480...`). For minimal bundles you can leave `LogoPath: ""` and skip the asset/ tree entirely.

## Things that do NOT matter (verified by side-by-side test)

- **`.DS_Store` files** — gold sample has them; ours doesn't; both work. JSZip iterator's `if (!v.dir)` skip + the path normalization handles them as unrelated entries.
- **ID first char** — does not have to be `d`. Compiler-generated `c00...` and platform-issued `cpg2...` both accepted.
- **Bundle filename** — only used as the visible filename; not parsed.
- **`FromWorkspaceID` matching importing workspace** — gold sample's `FromWorkspaceID` was a foreign workspace; import succeeded. Front-end remaps on import.
- **`ModelName` matching the model's display name** — we used the IR handle (`configured-small-model`); import still succeeded as long as `ModelID` resolves.

## Things that DO matter, in failure-cost order

1. **Flat zip entries** — without this, every other check is moot. `fileTree.index` lookup fails first.
2. **MD5 trailer** — without this, the upload wizard rejects before parsing zip body.
3. **`MainMetaName` ↔ `agent/<name>.yaml` filename match** — exact, including spaces and unicode. Same rule for model/knowledge sidecars vs `AppDepends.*Map[*].Name`.
4. **`ModelID` resolves in target workspace** — the `aigw?Action=GetModel` lookup happens after import. If foreign, the agent imports but errors when opened. (Not a hard block on import; degrades user experience.)

## Reference: minimal Chat bundle producer

Verified working layout for `examples/ir/01-ecommerce-customer-faq.json` against `personal-d65fp6amlv625h73nr80` workspace on `hia.volcenginepaas.com`:

```python
import hashlib, time, zipfile, yaml
from pathlib import Path
from loom.runtimes.hiagent.v2_6.compiler import compile_ir
# … compile_ir returns HiagentBundle with index.yaml + agent/<safe>.yaml

agent_name = ir.metadata.name                          # keep spaces; do NOT safe-ify
files = {
    "index.yaml": {...},                               # MainMetaName == agent_name
    f"agent/{agent_name}.yaml": {...},                 # filename matches MainMetaName
    f"model/{model_name}.yaml": {...},                 # if ModelMap populated
}

zip_path = Path(f"{agent_name}_v1.0.0_{ts}.zip")
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for rel, content in files.items():
        zf.writestr(rel, yaml.safe_dump(content, sort_keys=False, allow_unicode=True))

zb = zip_path.read_bytes()
zip_path.write_bytes(zb + hashlib.md5(zb).hexdigest().encode("ascii"))
```

## Hiagent has 4 agent types — they are NOT one schema

Hiagent's "创建智能体" (Create Agent) wizard has 4 different types. Each emits a structurally different `agent/*.yaml`. **This is the biggest schema-level difference vs. Dify**, where one DSL handles all flows.

| Type (zh) | Type (en) | `AppType` | `AgentMode` | Key fields populated | Status |
|---|---|---|---|---|---|
| 对话型 | Chat | `Chat` | `Single` | `SingleAgentConfig.{ModelID, KnowledgeIDs, PrePrompt, ToolIDs, ...}` | ✅ verified working via zip |
| 对话流型 | ChatFlow | `ChatFlow` | `""` (empty) | `ChatFlowDetail.{Nodes, Depends, ...}` + `SingleAgentConfig.ChatFlowConfig` | ✅ verified working via zip |
| 流程编排型 | Workflow | likely `Workflow` | `""` | likely just a flow doc, no chat shell — **not yet exercised** | ⚠️ unverified |
| 协同协作型 (Beta) | MultiAgent | likely `MultiAgent` or `Chat` | `MultiAgent` | `MultiAgentConfig.{...}` + sub-agents in `agent/` | ⚠️ unverified — gold complex 小芸 sample is this shape |

**Operating implication**: at the start of any Hiagent FDE engagement, the very first decision is which type to target. The compiler/binding/zip emit branch on this. The sub-types are not interchangeable: a Chat-mode bundle imported as ChatFlow will fail server validation, and vice versa.

This is also why `loom hiagent push` has a `--mode {single,chatflow}` flag and why the inline ChatFlow path needs `_CHATFLOW_START_SCHEMA` (canonical) while the Chat path uses `SingleAgentConfig` directly.

## ChatFlow-specific gotchas

Cracked live on 2026-05-10 against the same `hia.volcenginepaas.com` workspace. Once the zip-import 4 hard rules above pass, the ChatFlow agent yaml has its own server-side schema rules that the back-end (`Action=ImportAppFromDSL`) enforces. These are reachable because the front-end accepts the bundle and forwards it to the server — the server returns precise Go-struct unmarshal errors.

### Iteration loop (use this pattern for further fields)

The server processes the YAML one Go field at a time. On the first type mismatch it returns:

```
ResponseMetadata.Error = {
  Code: "BadRequest.Warning",
  Message: "Bad request: AppYaml yaml.Unmarshal error: error unmarshaling JSON: ..."
}
```

The `Message` names the exact struct path, e.g. `AppMigrateConfigInfo.AppConfig.ChatFlowDetail.Nodes.NodeSnapshot.Configs.Knowledge.RetrievalSearchMethod` and the type expected (`type node.RetrievalSearchMethod`). One round = fix one field. Don't try to bulk-fix.

### Knowledge node: `RetrievalSearchMethod` is `int`, not `string`

Compiler emitted `"semantic"` (string). Server expects `node.RetrievalSearchMethod` enum, encoded as int. Use `0` (== semantic). The chat-mode `KnowledgeConfig.RetrievalSearchMethod` already used `0` correctly; this was an inconsistency.

Fix landed in `loom/runtimes/hiagent/v2_6/compiler_nodes.py::_retrieval`.

### Start node: schema is FIXED, ignore IR inputs

ChatFlow's Start node does not represent an arbitrary trigger payload — it represents the **chat shell's input**, which is a fixed canonical triplet:

```yaml
InputSchema: &start_schema
- {Name: query,          Type: 0,  Required: true,  Desc: 用户输入的原始内容}
- {Name: files,          Type: 11, Desc: 对话附件,
   SubParameters: [
     {Name: name, Type: 0, Required: true, Desc: 文件名},
     {Name: url,  Type: 0, Required: true, Desc: 文件链接},
   ]}
- {Name: chat_histories, Type: 9,  Desc: 用户与应用的对话历史,
   SubParameters: [
     {Name: query,  Type: 0, Desc: 历史对话问题},
     {Name: answer, Type: 0, Desc: 历史对话回答},
     {Name: files,  Type: 11, Desc: 对话附件, SubParameters: <recursive same as files>},
   ]}
OutputSchema: *start_schema
```

Type codes (verified): `0 = String`, `9 = Array<Object>`, `11 = Array<File>`.

If you substitute IR inputs, the server accepts (no unmarshal error) but the front-end node-config inspector flags the Start node as **invalid** and KB/LLM nodes that reference Start fields like `start.query` lose their type hints — KB then shows "参数不合法" too, even if the QueryVariable name happens to match. **Symptom: the import succeeds, the agent loads, but Start + every downstream node lights up red.**

Fix landed in `loom/runtimes/hiagent/v2_6/compiler_nodes.py::_trigger` (canonical schema constant `_CHATFLOW_START_SCHEMA`).

**Implication for IR**: extra IR inputs (e.g. `buyer_locale`) cannot be wired through the Chat shell. They must either be dropped from downstream node references, or reach the workflow via another mechanism (variable injection in chat config — not yet investigated).

### Agent yaml shape for ChatFlow (deltas vs Chat-mode)

```yaml
AppConfig:
  AgentMode: ""                       # NOT "Single"
  ChatFlowDetail:                     # populated, NOT null
    DLVersion: v2
    FlowType: Agent                   # not "Workflow" — Agent means "the agent's own logic"
    ID: <flow_id>
    Nodes: [...]                      # full graph: Start + IR nodes + End
    Depends: <AppDepends-shape>
    UniqueName: <flow_id>             # same as ID
    WorkflowID: <flow_id>             # same as ID
    Version: v1.0.0
    VersionCode: <random 20-char>
    VersionName: <random 20-char>
    UpdatedAt: <epoch ms>
    UpdateTime: "YYYY-MM-DD HH:MM:SS"
    DisplayName: <agent name>
    Desc: <description>
    LogoPath: ""
    MetaType: Workflow
  MultiAgentConfig: null
  SingleAgentConfig:                  # still present, but stripped
    ChatFlowConfig:                   # NEW — UI config for the chat shell
      ChatAdvancedConfig: <same shape as Chat-mode>
      RoundsReserved: 23
      Version: v1.0.0
      WorkflowID: <flow_id>           # points back at ChatFlowDetail.ID
      WorkflowPublishID: ""
    # other SingleAgentConfig fields kept but most empty:
    ModelID: ""                       # ChatFlow has its model on each LLM node
    ModelName: ""
    KnowledgeIDs: []                  # ChatFlow has knowledge on Knowledge nodes
    ToolIDs: []
    WorkflowIDs: []
    # ... rest unchanged
AppInfo:
  AgentMode: ""                       # NOT "Single"
  AppType: ChatFlow                   # NOT "Chat"
```

For our minimal ecommerce example, no `workflow/<name>.yaml` sidecar was needed because the graph lives entirely inside `ChatFlowDetail` (no sub-workflow nodes). Sub-workflow nodes (gold's 小芸 case) DO require a `workflow/<flow-name>.yaml` sidecar plus `AppDepends.WorkflowMap` populated.

## Outstanding questions (not yet exercised)

- **Workflow type (流程编排型)**: pure flow, no chat shell. Schema differences vs ChatFlow's inline graph are unknown. Likely `MetaType: Workflow` at index level, and no `agent/` directory.
- **MultiAgent type (协同协作型 Beta)**: `MultiAgentConfig` shape, sub-agent file naming, hand-off semantics. The 小芸 gold sample is structured like this (Multi-agent with sub-workflow + 3 sub-agents) but we have not produced one from compiler.
- **Sub-workflow ChatFlow**: agent's ChatFlow has a `Workflow` node referencing a sub-flow whose definition lives in `workflow/<name>.yaml`. Schema for that sidecar matches the inline `ChatFlowDetail` but with `FlowType: Workflow`. Cross-reference rules (UniqueName, version IDs, AppDepends.WorkflowMap entries) need verification.
- **IR-input → ChatFlow variable wiring**: how to surface non-canonical inputs (e.g. `buyer_locale`) into the chat shell so downstream nodes can reference them. Possibly via `VariableConfigs` on `SingleAgentConfig` — not yet tested.
- **Authenticated programmatic upload**: front-end goes Cookie + `x-csrf-token` + `workspaceid` header against `/api/bypass/up?Action=...`. TOP HMAC alone is not sufficient on this deployment. Could be wired up by reusing browser session cookies; not yet automated.
