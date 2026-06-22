import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import type { Turn } from "../../lib/types";
import { ChatPanel } from "./ChatPanel";

afterEach(() => {
  cleanup();
});

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
                { description: "适合先交付到当前主平台。", label: "HiAgent", value: "hiagent" },
                { description: "适合验证 Dify YAML 导入。", label: "Dify", value: "dify" }
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

    expect(screen.getByText("适合验证 Dify YAML 导入。")).toBeInTheDocument();
    expect(onSend).toHaveBeenCalledWith("target_runtime=dify");
  });

  it("disables historical clarify turns and only allows the latest interactive turn to submit", () => {
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
              field_path: "old_target_runtime",
              options: [{ label: "Dify", value: "dify" }],
              severity: "block",
              text: "Old target runtime?"
            },
            turn_id: "turn-old"
          }),
          turn({
            kind: "clarify",
            clarify_question: {
              allow_freeform: false,
              field_path: "target_runtime",
              options: [{ label: "Dify", value: "dify" }],
              severity: "block",
              text: "Latest target runtime?"
            },
            turn_id: "turn-new"
          })
        ]}
      />
    );

    const optionButtons = screen.getAllByRole("button", { name: "Dify" });
    expect(optionButtons[0]).toBeDisabled();
    expect(optionButtons[1]).not.toBeDisabled();

    fireEvent.click(optionButtons[0]);
    fireEvent.click(screen.getAllByRole("button", { name: /回答|Reply/i })[0]);
    expect(onSend).not.toHaveBeenCalled();

    fireEvent.click(optionButtons[1]);
    fireEvent.click(screen.getAllByRole("button", { name: /回答|Reply/i })[1]);
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
                  options: [
                    {
                      description: "围绕商品、政策和 FAQ 知识库回答问题。",
                      label: "Ecommerce KB",
                      value: "ecommerce/kb"
                    }
                  ],
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

    expect(screen.getByText(/问题 1 \/ 2|Question 1 \/ 2/i)).toBeInTheDocument();
    expect(screen.getByText(/问题 2 \/ 2|Question 2 \/ 2/i)).toBeInTheDocument();
    expect(screen.getByText("围绕商品、政策和 FAQ 知识库回答问题。")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ecommerce KB" }));
    fireEvent.change(screen.getByLabelText(/success criteria/i), {
      target: { value: "Answer with citations." }
    });
    fireEvent.click(screen.getByRole("button", { name: /提交问卷|Submit questionnaire/i }));

    expect(onSend).toHaveBeenCalledWith("scope=ecommerce/kb; success_criteria=Answer with citations.");
  });

  it("renders a brief review card and sends the flow generation confirmation", () => {
    const onSend = vi.fn();
    render(
      <ChatPanel
        isSending={false}
        onSend={onSend}
        turns={[
          turn({
            kind: "brief_review",
            brief_after: {
              approval_points: ["Human approval before refund"],
              business_rules: ["Refund is blocked after shipment"],
              compliance_boundary: {
                geographies: ["CN"],
                pii_class_default: "medium",
                regulatory_tags: ["PIPL"]
              },
              credentials: ["OMS readonly token"],
              data_sources: [
                { handle: "oms_order_api", kind: "http" },
                { handle: "logistics_tracking_api", kind: "http" }
              ],
              intent_clarifications: ["Buyer asks about order cancellation, tracking, and refund policy."],
              risks: ["Missing order id triggers handoff"],
              success_criteria: ["Returns a validated action JSON"],
              trigger: { mode: "manual" }
            },
            planner_reply: "Please confirm the brief before generating the workflow."
          })
        ]}
      />
    );

    expect(screen.getByText(/流程设计简报确认|Flow design brief review/i)).toBeInTheDocument();
    expect(screen.getByText("manual")).toBeInTheDocument();
    expect(screen.getByText("Buyer asks about order cancellation, tracking, and refund policy.")).toBeInTheDocument();
    expect(screen.getByText("oms_order_api (http)")).toBeInTheDocument();
    expect(screen.getByText("pii class default: medium")).toBeInTheDocument();
    expect(screen.getByText("Refund is blocked after shipment")).toBeInTheDocument();
    expect(screen.getByText("Missing order id triggers handoff")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /确认生成流程|Confirm flow generation/i }));
    expect(onSend).toHaveBeenCalledWith("确认生成流程");
  });
});
