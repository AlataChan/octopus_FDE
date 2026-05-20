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

  it("shows visible text on artifact download buttons", () => {
    render(
      <CompileBar
        artifacts={[
          {
            actor_id: "actor-1",
            artifact_id: "artifact-1",
            artifact_kind: "zip",
            artifact_name: "workflow.zip",
            artifact_path: "/tmp/workflow.zip",
            artifact_size: 123,
            binding_handle: "test",
            compile_warnings: [],
            created_at: "2026-05-11T00:00:00Z",
            mode: "chatflow",
            sha256: "abc1234567890def",
            session_id: "session-1",
            target: "hiagent",
            workflow_id: "workflow-1"
          }
        ]}
        bindings={[{ display_name: "Test Hiagent", handle: "test", target: "hiagent" }]}
        isCompiling={false}
        onCompile={vi.fn()}
        onDownload={vi.fn()}
        onMarkImported={vi.fn()}
        workflows={[]}
      />
    );

    const button = screen.getByRole("button", { name: /下载|Download/i });
    expect(button).toHaveTextContent(/下载|Download/i);
  });
});
