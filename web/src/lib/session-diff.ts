import type { Turn } from "./types";

export function selectIRDiffTurnIds(turns: Turn[]) {
  const irTurns = turns.filter((turn) => turn.status === "succeeded" && isIRProducingTurn(turn));
  if (irTurns.length < 2) {
    return { fromTurn: null, toTurn: null };
  }
  return {
    fromTurn: irTurns[irTurns.length - 2].turn_id,
    toTurn: irTurns[irTurns.length - 1].turn_id
  };
}

function isIRProducingTurn(turn: Turn) {
  const kind = turn.kind || "plan";
  return kind === "plan" || kind === "design_preview";
}
