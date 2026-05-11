import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { CompileBar } from "./CompileBar";

describe("CompileBar", () => {
  it("disables the compile button while a compile is in flight", () => {
    render(
      <CompileBar
        artifacts={[]}
        bindings={[{ display_name: "Test Hiagent", handle: "test", target: "hiagent" }]}
        isCompiling
        onCompile={vi.fn()}
        onDownload={vi.fn()}
        onMarkImported={vi.fn()}
        workflows={[]}
      />
    );

    const button = screen.getByRole("button", { name: /正在编译|Compiling/i });
    expect(button).toBeDisabled();

    fireEvent.click(button);
    expect(button).toBeDisabled();
  });
});
