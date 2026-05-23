import { useQuery } from "@tanstack/react-query";
import { getAuthMe } from "../lib/api";

type UseAuthOptions = {
  enabled?: boolean;
};

export function useAuth(options: UseAuthOptions = {}) {
  return useQuery({
    enabled: options.enabled ?? true,
    queryKey: ["auth", "me"],
    queryFn: getAuthMe,
    retry: false
  });
}
