import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ClarifyQuestion } from "../../lib/types";
import "../../lib/i18n";
import { ClarifyBubble } from "./ClarifyBubble";

afterEach(cleanup);

function question(overrides: Partial<ClarifyQuestion> = {}): ClarifyQuestion {
  return {
    allow_freeform: false,
    field_path: "target_runtime",
    options: [
      { description: "For HiAgent deployment.", label: "HiAgent", value: "hiagent" },
      { description: "For Dify deployment.", label: "Dify", value: "dify" }
    ],
    severity: "block",
    text: "Which target runtime?",
    ...overrides
  };
}

describe("ClarifyBubble", () => {
  it("renders the question text and option buttons", () => {
    render(<ClarifyBubble onSend={vi.fn()} question={question()} />);

    expect(screen.getByText("Which target runtime?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "HiAgent" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dify" })).toBeInTheDocument();
  });

  it("selects an option and submits with the correct format", () => {
    const onSend = vi.fn();
    render(<ClarifyBubble onSend={onSend} question={question()} />);

    fireEvent.click(screen.getByRole("button", { name: "Dify" }));
    fireEvent.click(screen.getByRole("button", { name: /回答|Reply/i }));

    expect(onSend).toHaveBeenCalledWith("target_runtime=dify");
  });

  it("submits freeform text when allow_freeform is enabled", () => {
    const onSend = vi.fn();
    render(
      <ClarifyBubble
        onSend={onSend}
        question={question({ allow_freeform: true })}
      />
    );

    fireEvent.change(screen.getByLabelText("Which target runtime?"), {
      target: { value: "custom value" }
    });
    fireEvent.click(screen.getByRole("button", { name: /回答|Reply/i }));

    expect(onSend).toHaveBeenCalledWith("target_runtime=custom value");
  });

  it("disables all interactive elements when disabled is true", () => {
    render(<ClarifyBubble disabled onSend={vi.fn()} question={question()} />);

    const option = screen.getByRole("button", { name: "HiAgent" });
    const submit = screen.getByRole("button", { name: /回答|Reply/i });

    expect(option).toBeDisabled();
    expect(submit).toBeDisabled();
  });

  it("disables when isLatestInteractive is false", () => {
    render(
      <ClarifyBubble
        isLatestInteractive={false}
        onSend={vi.fn()}
        question={question()}
      />
    );

    const option = screen.getByRole("button", { name: "HiAgent" });
    expect(option).toBeDisabled();
  });

  it("renders a freeform textarea when allow_freeform is true", () => {
    render(
      <ClarifyBubble
        onSend={vi.fn()}
        question={question({ allow_freeform: true })}
      />
    );

    expect(screen.getByLabelText("Which target runtime?")).toBeInTheDocument();
  });

  it("does not render options when the options array is empty", () => {
    render(
      <ClarifyBubble
        onSend={vi.fn()}
        question={question({ options: undefined })}
      />
    );

    expect(screen.queryByRole("button", { name: "HiAgent" })).not.toBeInTheDocument();
  });
});
