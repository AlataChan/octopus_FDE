import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import "../../lib/i18n";
import { StateStepper } from "./StateStepper";

afterEach(cleanup);

describe("StateStepper", () => {
  it.each([
    ["init", "stepper.llm", "current"],
    ["llm_config_set", "stepper.draft", "current"],
    ["drafting", "stepper.draft", "current"],
    ["validated", "stepper.validate", "complete"],
    ["compiled", "stepper.compile", "complete"],
    ["downloaded", "stepper.download", "complete"]
  ])("maps %s to the expected active/completed step", (state, key, status) => {
    render(<StateStepper state={state} />);

    const step = screen.getByTestId(key);
    expect(step).toHaveAttribute("data-step-status", status);
    if (status === "current") {
      expect(step).toHaveAttribute("aria-current", "step");
    }
  });
});
