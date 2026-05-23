export type SessionState = "created" | "llm_config_set" | "validated" | "compiled" | string;

export type SessionSummary = {
  session_id: string;
  state: SessionState;
  latest_ir_sha256: string | null;
  created_at: string;
  updated_at: string;
  display_title: string;
};

export type ArtifactKind = "zip" | "yaml";
export type CompileTarget = "hiagent" | "dify";
export type CompileMode = "chat" | "chatflow";

export type CompileWarning = {
  target: CompileTarget;
  node_id: string | null;
  field: string;
  message: string;
  code: string;
};

export type Artifact = {
  artifact_id: string;
  session_id: string;
  workflow_id: string;
  actor_id: string;
  artifact_name: string;
  artifact_kind: ArtifactKind;
  artifact_path: string;
  artifact_size: number;
  sha256: string;
  target: CompileTarget;
  mode: CompileMode | string | null;
  binding_handle: string;
  compile_warnings: CompileWarning[];
  created_at: string;
};

export type SessionDetail = SessionSummary & {
  actor_id: string;
  latest_ir_json: string | null;
  title: string | null;
  llm_base_url: string | null;
  llm_model: string | null;
  llm_key_version: number | null;
  artifacts: Artifact[];
};

export type Turn = {
  turn_id: string;
  status: "running" | "succeeded" | "failed";
  planner_reply: string | null;
  errors: string[];
  ir_diff: unknown;
  kind?: "clarify" | "plan" | "questionnaire";
  clarify_question?: ClarifyQuestion | { questions: ClarifyQuestion[] } | null;
  brief_after?: WorkflowBriefSnapshot | null;
  clarify_round?: number | null;
  error_correlation_id?: string | null;
};

export type ClarifyQuestion = {
  text: string;
  field_path: string;
  options?: { label: string; value: string }[] | null;
  allow_freeform: boolean;
  severity: "block" | "warn";
};

export type WorkflowBriefSnapshot = Record<string, unknown>;

export type BindingSummary = {
  handle: string;
  target: CompileTarget;
  display_name: string;
};

export type LLMConfigInput = {
  api_key: string;
  base_url: string;
  model: string;
};

export type CompileInput = {
  target: CompileTarget;
  mode?: CompileMode | null;
  binding: string;
};

export type CompileResponse = {
  artifact_id: string;
  workflow_id: string;
  artifact_name: string;
  artifact_size: number;
  sha256: string;
  compile_warnings: CompileWarning[];
};

export type ValidationFailure = {
  bucket: string;
  detail: string;
  location?: string | null;
};

export type IRDiffFieldChange = {
  path: string;
  before: unknown;
  after: unknown;
};

export type IRDiffChange =
  | {
      scope: "node";
      kind: "added" | "removed" | "renamed";
      node_id: string;
      before?: unknown;
      after?: unknown;
    }
  | {
      scope: "node";
      kind: "config-changed";
      node_id: string;
      fields: IRDiffFieldChange[];
    }
  | {
      scope: "edge";
      kind: "added" | "removed";
      from: string;
      to: string;
    };

export type IRDiffResponse = {
  from: string;
  to: string;
  changes: IRDiffChange[];
  summary: {
    nodes: number;
    edges: number;
    total: number;
  };
};

export type IRResponse = {
  ir: unknown | null;
  latest_ir_sha256: string | null;
  validator_status: "ok" | "failed" | string;
  validation_errors: ValidationFailure[];
};

export type WorkflowRecord = {
  workflow_id: string;
  session_id: string;
  artifact_id: string;
  artifact_name: string;
  artifact_kind: ArtifactKind;
  artifact_sha256: string;
  ir_signature: string;
  ir_version: string;
  target: CompileTarget;
  mode: CompileMode | string | null;
  binding_handle: string;
  compiler_version: string;
  created_by_actor: string;
  compiled_at: string;
  platform_app_id: string | null;
  deployment_note: string | null;
  deployed_at: string | null;
  deployed_by_actor: string | null;
};

export type MarkImportedInput = {
  platform_app_id: string;
  deployment_note?: string | null;
};

export type LocalizedText = {
  zh: string;
  en: string;
};

export type TemplateSummary = {
  id: string;
  name: LocalizedText;
  description: LocalizedText;
  tags: string[];
  scopes: string[];
  compile_targets: CompileTarget[];
};

export type TemplateDetail = TemplateSummary & {
  ir: unknown;
};
