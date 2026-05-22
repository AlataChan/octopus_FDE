import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  compileSession,
  getIRDiff,
  getIR,
  getSession,
  listBindings,
  listTurns,
  setLLMConfig
} from "../lib/api";
import type { CompileInput, LLMConfigInput } from "../lib/types";

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
      await queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    }
  });
}

export function useIRDiff(sessionId: string, fromTurnId: string | null, toTurnId: string | null) {
  return useQuery({
    enabled: Boolean(fromTurnId && toTurnId),
    queryKey: ["ir-diff", sessionId, fromTurnId, toTurnId],
    queryFn: () => getIRDiff(sessionId, fromTurnId!, toTurnId!)
  });
}
