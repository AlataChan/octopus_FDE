import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createTurn } from "../lib/api";

export function usePlannerTurn(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => createTurn(sessionId, message),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["session", sessionId] }),
        queryClient.invalidateQueries({ queryKey: ["turns", sessionId] }),
        queryClient.invalidateQueries({ queryKey: ["ir", sessionId] })
      ]);
    }
  });
}
