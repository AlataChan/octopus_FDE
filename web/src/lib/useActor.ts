export type Actor = {
  id: string;
  role: "fde";
};

export const DEFAULT_ACTOR: Actor = {
  id: "single-user",
  role: "fde"
};

export function useActor(): Actor {
  return DEFAULT_ACTOR;
}
