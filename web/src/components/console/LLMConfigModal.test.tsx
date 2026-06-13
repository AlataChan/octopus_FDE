import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { LLMConfigModal } from "./LLMConfigModal";

afterEach(cleanup);

describe("LLMConfigModal", () => {
  it("can be dismissed without saving", () => {
    const onOpenChange = vi.fn();

    render(
      <LLMConfigModal
        isSaving={false}
        open
        onOpenChange={onOpenChange}
        onSubmit={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /Close modal/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
