import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  compileSession,
  getIR,
  getSession,
  listBindings,
  listTurns,
  listWorkflows,
  markWorkflowDeployed,
  setLLMConfig
} from "../lib/api";
import type { CompileInput, LLMConfigInput, MarkImportedInput } from "../lib/types";

export function useSession(sessionId: string | undefined) {
  const enabled = Boolean(sessionId);
  return {
    bindings: useQuery({
      queryKey: ["bindings"],
      queryFn: listBindings
    }),
    ir: useQuery({
      enabled,
      queryKey: ["ir", sessionId],
      queryFn: () => getIR(sessionId!)
    }),
    session: useQuery({
      enabled,
      queryKey: ["session", sessionId],
      queryFn: () => getSession(sessionId!)
    }),
    turns: useQuery({
      enabled,
      queryKey: ["turns", sessionId],
      queryFn: () => listTurns(sessionId!)
    }),
    workflows: useQuery({
      queryKey: ["workflows"],
      queryFn: listWorkflows
    })
  };
}

export function useSetLLMConfig(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: LLMConfigInput) => setLLMConfig(sessionId, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    }
  });
}

export function useCompileSession(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CompileInput) => compileSession(sessionId, input),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["session", sessionId] }),
        queryClient.invalidateQueries({ queryKey: ["workflows"] })
      ]);
    }
  });
}

export function useMarkImported() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workflowId, input }: { workflowId: string; input: MarkImportedInput }) =>
      markWorkflowDeployed(workflowId, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["workflows"] });
    }
  });
}
