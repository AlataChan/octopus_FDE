import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import type { Turn } from "../../lib/types";
import { ChatPanel } from "./ChatPanel";

function turn(overrides: Partial<Turn>): Turn {
  return {
    errors: [],
    ir_diff: null,
    kind: "plan",
    planner_reply: "IR generated",
    status: "succeeded",
    turn_id: "turn-12345678",
    ...overrides
  };
}

describe("ChatPanel clarify turns", () => {
  it("renders a clarify question and submits the selected option", () => {
    const onSend = vi.fn();
    render(
      <ChatPanel
        isSending={false}
        onSend={onSend}
        turns={[
          turn({
            kind: "clarify",
            clarify_question: {
              allow_freeform: false,
              field_path: "target_runtime",
              options: [
                { label: "HiAgent", value: "hiagent" },
                { label: "Dify", value: "dify" }
              ],
              severity: "block",
              text: "Which target runtime should this workflow compile to?"
            },
            planner_reply: "Which target runtime should this workflow compile to?"
          })
        ]}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Dify" }));
    fireEvent.click(screen.getByRole("button", { name: /回答|Reply/i }));

    expect(onSend).toHaveBeenCalledWith("target_runtime=dify");
  });

  it("renders questionnaire questions and submits a compact answer", () => {
    const onSend = vi.fn();
    render(
      <ChatPanel
        isSending={false}
        onSend={onSend}
        turns={[
          turn({
            kind: "questionnaire",
            clarify_question: {
              questions: [
                {
                  allow_freeform: false,
                  field_path: "scope",
                  options: [{ label: "Ecommerce KB", value: "ecommerce/kb" }],
                  severity: "block",
                  text: "Which registry scope should constrain datasets, tools, and credentials?"
                },
                {
                  allow_freeform: true,
                  field_path: "success_criteria",
                  severity: "block",
                  text: "What concrete success criteria should the generated workflow satisfy?"
                }
              ]
            },
            planner_reply: "Please answer the remaining clarification questions."
          })
        ]}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Ecommerce KB" }));
    fireEvent.change(screen.getByLabelText(/success_criteria/i), {
      target: { value: "Answer with citations." }
    });
    fireEvent.click(screen.getByRole("button", { name: /提交问卷|Submit questionnaire/i }));

    expect(onSend).toHaveBeenCalledWith("scope=ecommerce/kb; success_criteria=Answer with citations.");
  });
});
