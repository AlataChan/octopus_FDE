import { describe, expect, it } from "vitest";
import type { Turn } from "./types";
import { selectIRDiffTurnIds } from "./session-diff";

function turn(overrides: Partial<Turn>): Turn {
  return {
    errors: [],
    ir_diff: null,
    kind: "plan",
    planner_reply: null,
    status: "succeeded",
    turn_id: "turn-default",
    ...overrides
  };
}

describe("selectIRDiffTurnIds", () => {
  it("ignores clarification turns when selecting the latest IR diff pair", () => {
    const pair = selectIRDiffTurnIds([
      turn({ kind: "clarify", turn_id: "clarify-a" }),
      turn({ kind: "plan", turn_id: "plan-a" }),
      turn({ kind: "questionnaire", turn_id: "questionnaire-a" }),
      turn({ kind: "clarify", turn_id: "clarify-b" }),
      turn({ kind: "plan", turn_id: "plan-b" })
    ]);

    expect(pair).toEqual({ fromTurn: "plan-a", toTurn: "plan-b" });
  });

  it("returns nulls until two IR-producing turns exist", () => {
    const pair = selectIRDiffTurnIds([
      turn({ kind: "clarify", turn_id: "clarify-a" }),
      turn({ kind: "plan", turn_id: "plan-a" })
    ]);

    expect(pair).toEqual({ fromTurn: null, toTurn: null });
  });
});
