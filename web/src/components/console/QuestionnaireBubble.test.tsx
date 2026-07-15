import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ClarifyQuestion } from "../../lib/types";
import "../../lib/i18n";
import { QuestionnaireBubble } from "./QuestionnaireBubble";

afterEach(cleanup);

function makeQuestions(): ClarifyQuestion[] {
  return [
    {
      allow_freeform: false,
      field_path: "scope",
      options: [
        { description: "Ecommerce knowledge base.", label: "Ecommerce KB", value: "ecommerce/kb" }
      ],
      severity: "block",
      text: "Which registry scope?"
    },
    {
      allow_freeform: true,
      field_path: "success_criteria",
      severity: "block",
      text: "What success criteria?"
    }
  ];
}

describe("QuestionnaireBubble", () => {
  it("renders all questions with step labels", () => {
    render(<QuestionnaireBubble onSend={vi.fn()} questions={makeQuestions()} />);

    expect(screen.getByText(/Which registry scope/)).toBeInTheDocument();
    expect(screen.getByText(/What success criteria/)).toBeInTheDocument();
    expect(screen.getByText(/问题 1|Question 1|Step 1/i)).toBeInTheDocument();
    expect(screen.getByText(/问题 2|Question 2|Step 2/i)).toBeInTheDocument();
  });

  it("submits selected options in compact format", () => {
    const onSend = vi.fn();
    render(<QuestionnaireBubble onSend={onSend} questions={makeQuestions()} />);

    fireEvent.click(screen.getByRole("button", { name: "Ecommerce KB" }));
    fireEvent.change(screen.getByLabelText("What success criteria?"), {
      target: { value: "Answer with citations." }
    });
    fireEvent.click(screen.getByRole("button", { name: /提交问卷|Submit questionnaire/i }));

    expect(onSend).toHaveBeenCalledWith(
      "scope=ecommerce/kb; success_criteria=Answer with citations."
    );
  });

  it("disables all fields when disabled is true", () => {
    render(
      <QuestionnaireBubble disabled onSend={vi.fn()} questions={makeQuestions()} />
    );

    const option = screen.getByRole("button", { name: "Ecommerce KB" });
    const submit = screen.getByRole("button", { name: /提交问卷|Submit questionnaire/i });

    expect(option).toBeDisabled();
    expect(submit).toBeDisabled();
  });

  it("disables the submit button when no answers are provided", () => {
    render(<QuestionnaireBubble onSend={vi.fn()} questions={makeQuestions()} />);

    expect(screen.getByRole("button", { name: /提交问卷|Submit questionnaire/i })).toBeDisabled();
  });

  it("shows a freeform textarea for questions with allow_freeform", () => {
    render(<QuestionnaireBubble onSend={vi.fn()} questions={makeQuestions()} />);

    expect(screen.getByLabelText("What success criteria?")).toBeInTheDocument();
  });
});
