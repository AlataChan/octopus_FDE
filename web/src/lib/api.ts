import type { paths } from "./types.generated";
import type {
  BindingSummary,
  CompileInput,
  CompileResponse,
  IRDiffResponse,
  IRResponse,
  LLMConfigInput,
  MarkImportedInput,
  SessionDetail,
  SessionSummary,
  TemplateDetail,
  TemplateSummary,
  Turn,
  WorkflowRecord
} from "./types";
import { DEFAULT_ACTOR } from "./useActor";

type HealthResponse =
  paths["/v1/health"]["get"]["responses"][200]["content"]["application/json"];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Actor-Id", DEFAULT_ACTOR.id);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function apiBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const headers = new Headers(init.headers);
  headers.set("X-Actor-Id", DEFAULT_ACTOR.id);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.blob();
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/v1/health");
}

export function listSessions(): Promise<SessionSummary[]> {
  return apiFetch<SessionSummary[]>("/v1/sessions");
}

export function createSession(): Promise<{ session_id: string; state: string }> {
  return apiFetch<{ session_id: string; state: string }>("/v1/sessions", {
    body: JSON.stringify({}),
    method: "POST"
  });
}

export function createSessionFromTemplate(
  templateId: string,
  scope = "ecommerce/kb"
): Promise<{ session_id: string; state: string }> {
  return apiFetch<{ session_id: string; state: string }>("/v1/sessions", {
    body: JSON.stringify({ scope, template_id: templateId }),
    method: "POST"
  });
}

export function listTemplates(params: {
  scope?: string;
  target?: "hiagent" | "dify";
} = {}): Promise<TemplateSummary[]> {
  const query = new URLSearchParams();
  if (params.scope) query.set("scope", params.scope);
  if (params.target) query.set("target", params.target);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<TemplateSummary[]>(`/v1/templates${suffix}`);
}

export function getTemplate(templateId: string): Promise<TemplateDetail> {
  return apiFetch<TemplateDetail>(`/v1/templates/${templateId}`);
}

export function getSession(sessionId: string): Promise<SessionDetail> {
  return apiFetch<SessionDetail>(`/v1/sessions/${sessionId}`);
}

export function setLLMConfig(sessionId: string, input: LLMConfigInput): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/v1/sessions/${sessionId}/llm-config`, {
    body: JSON.stringify(input),
    method: "PATCH"
  });
}

export function listTurns(sessionId: string): Promise<Turn[]> {
  return apiFetch<Turn[]>(`/v1/sessions/${sessionId}/turns`);
}

export function createTurn(sessionId: string, userMessage: string): Promise<Turn> {
  return apiFetch<Turn>(`/v1/sessions/${sessionId}/turns`, {
    body: JSON.stringify({ user_message: userMessage }),
    method: "POST"
  });
}

export function getIR(sessionId: string): Promise<IRResponse> {
  return apiFetch<IRResponse>(`/v1/sessions/${sessionId}/ir`);
}

export function getIRDiff(
  sessionId: string,
  fromTurn: string,
  toTurn: string
): Promise<IRDiffResponse> {
  const params = new URLSearchParams({ from_turn: fromTurn, to_turn: toTurn });
  return apiFetch<IRDiffResponse>(`/v1/sessions/${sessionId}/ir/diff?${params.toString()}`);
}

export function listBindings(): Promise<BindingSummary[]> {
  return apiFetch<BindingSummary[]>("/v1/bindings");
}

export function compileSession(
  sessionId: string,
  input: CompileInput
): Promise<CompileResponse> {
  return apiFetch<CompileResponse>(`/v1/sessions/${sessionId}/compile`, {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function downloadArtifact(sessionId: string, artifactId: string): Promise<Blob> {
  return apiBlob(`/v1/sessions/${sessionId}/artifacts/${artifactId}`);
}

export function listWorkflows(): Promise<WorkflowRecord[]> {
  return apiFetch<WorkflowRecord[]>("/v1/registry/workflows");
}

export function markWorkflowDeployed(
  workflowId: string,
  input: MarkImportedInput
): Promise<WorkflowRecord> {
  return apiFetch<WorkflowRecord>(`/v1/registry/workflows/${workflowId}/deployed`, {
    body: JSON.stringify({
      deployment_note: input.deployment_note || null,
      platform_app_id: input.platform_app_id || null
    }),
    method: "POST"
  });
}
