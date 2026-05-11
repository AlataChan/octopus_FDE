export type SessionState = "created" | "llm_config_set" | "validated" | "compiled" | string;

export type SessionSummary = {
  session_id: string;
  state: SessionState;
  latest_ir_sha256: string | null;
  created_at: string;
  updated_at: string;
};

export type ArtifactKind = "zip" | "yaml";
export type CompileTarget = "hiagent" | "dify";
export type CompileMode = "chat" | "chatflow";

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
  created_at: string;
};

export type SessionDetail = SessionSummary & {
  actor_id: string;
  latest_ir_json: string | null;
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
};

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
};

export type ValidationFailure = {
  bucket: string;
  detail: string;
  location?: string | null;
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
