# Hiagent ChatFlow Node Spec [v2.6, self-hosted]

> Source of truth for Hiagent ChatFlow emission. Compiler code must emit node
> fields from this file, not from memory or prompt guesses. Fields that are not
> present in the handbook but are required by live API behavior are marked
> `[LIVE]`.

Primary sources:

- Handbook: `Hiagent_MD/raw/workflow/工作流 - HiAgent Document.md`
- Live API validation on self-hosted Hiagent 2.6
- Imported customer samples: `用户维修方案_v1.0.6` and `小芸用户维修方案智能体_v1.11`

## General Rules

- `AppType=ChatFlow` uses `AppConfig.SingleAgentConfig=null` and `AppConfig.AgentMode=""`.
- `ChatFlowConfig.WorkflowID` must be the server-issued FlowID, not a client-generated ID. `[LIVE]`
- ChatFlow nodes must be created one by one through `CreateChatFlowNode`; bulk inserting client IDs is rejected. `[LIVE]`
- Creating a ChatFlow app creates server-owned Start and End nodes. The API adapter must reuse them. `[LIVE]`
- Multiple End nodes are rejected by `SaveChatflow`; multi-output IR graphs are merged into the single server End in the API adapter. `[LIVE]`
- Downstream references to Start fields must be `RefType=node_field`; `RefType=sys` is rejected by `SaveChatflow`. `[LIVE]`
- Generated nodes must be validated by `loom.runtimes.hiagent.spec_check` before save/publish.

## Start Node [Server Fixed]

- The API adapter must not patch Start node variables or output schema. `[LIVE]`
- Server default input/output fields:
  - `query`: String
  - `files`: Array<File> with `name: String`, `url: String`
  - `chat_histories`: Array<Object> with `query`, `answer`, `files`
- IR `${input.user_question}`, `${input.message}`, `${input.text}`, `${input.user_input}` map to Start `query`. `[LIVE]`
- IR `${input.files}` / `${input.attachments}` map to Start `files`. `[LIVE]`
- IR `${input.history}` / `${input.chat_history}` / `${input.conversation}` map to Start `chat_histories`. `[LIVE]`

## LLM Node

- Required conceptual fields: model, system prompt, user prompt.
- `OutputSchema` must always include `raw_output: String` by default.
- Additional output variables may follow `raw_output` when the IR asks for structured outputs.
- Output format can be JSON, Text, Markdown, or Custom in the UI. JSON is the compiler default.
- Text/Markdown output formats should not add custom variables.
- `MaxTokens` is capped at 4096 for the API path. `[LIVE]`
- Timeout range is 1-600 seconds; default 120.
- Retry range is 0-3; default 0.

## Code Node

- Handbook languages: JavaScript / Python.
- Current live API path accepts the numeric language enum used by server samples: `1=python`, `2=javascript`. `[LIVE]`
- Required field is code body in `Code`.
- Outputs are declared in `OutputSchema`.
- Supported output value types map to String, Integer, Number, Object, Boolean, Array.
- Complex parameters should not exceed five nested levels.
- Timeout range is 1-180 seconds; default 120.

## Knowledge Node

- API node type is `Knowledge`, not `KnowledgeBase`. `[LIVE]`
- Node config key after materialization is `KnowledgeNode`. `[LIVE]`
- `KnowledgeIDs` / `Knowledges` must be non-empty when saving to the API. The CLI auto-resolves a workspace dataset before push. `[LIVE]`
- `ScoreThreshold` must be greater than 0. `[LIVE]`
- `TopK` range is 1-10 in the UI; compiler should clamp or source valid IR.
- Output is a recalled segment list.

## Intent Node

- `QueryVariable` is required; default binds to Start `query`. `[LIVE]`
- Branch port IDs must be `class01`, `class02`, ... and a default `class_other`. `[LIVE]`
- `class_other` must exist even when the IR has an explicit default path. `[LIVE]`
- Intent output includes classification ID/name and reason-like text fields.

## End Node

- A ChatFlow app has one server-owned End node. `[LIVE]`
- API adapter merges multiple IR End nodes into that single server End. `[LIVE]`
- `OutputType=Content` may return template text.
- `OutputType=Variable` requires node-field references with `NodeCode`; missing `NodeCode` is rejected. `[LIVE]`

## Reply Node

- Handbook supports direct answer/reply behavior distinct from End.
- The current IR v0.3 compiler does not emit Reply nodes; user-facing terminal output maps to End.
- If Reply is added later, add a spec-check branch before emitting it.

## HTTP Node

- Handbook methods: GET, POST, HEAD, PATCH, PUT, DELETE.
- Request config includes URL, headers, params/body/auth as applicable.
- Timeout range is 0-600 seconds.
- Retry range is 0-10.
- Outputs include response body, status code, and response headers.
- Current ChatFlow API path maps IR HTTP to server `Tool` nodes when materialized. `[LIVE]`

## Loop Node

- Handbook supports loop-style workflow control.
- Current compiler emits `LoopType=Infinite` because imported v2.6 samples use this shape. `[LIVE]`
- Bounded loop semantics from IR `max_iterations` need a later server-side mapping audit.

## Condition Node

- Handbook condition/selector nodes support IF/ELSE routing.
- Current ChatFlow compiler maps IR Condition to server Intent because live API accepted Intent routing ports first. `[LIVE]`
- A future direct Condition mapping should be added only after a live `CreateChatFlowNode` + `SaveChatflow` proof.

## Parallel Node

- Hiagent v2.6 has no confirmed first-class IR parallel merge equivalent in current live tests.
- Current compiler maps parallel to a Code placeholder and marks the lossy transform in the node description.
- Do not claim semantic conformance for parallel until a VariableAggregator-style mapping is live-verified.
