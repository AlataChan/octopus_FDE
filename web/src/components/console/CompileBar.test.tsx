import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { CompileBar } from "./CompileBar";

afterEach(() => {
  cleanup();
});

describe("CompileBar", () => {
  it("disables the compile button while a compile is in flight", () => {
    render(
      <CompileBar
        artifacts={[]}
        bindings={[{ display_name: "Test Hiagent", handle: "test", target: "hiagent" }]}
        isCompiling
        onCompile={vi.fn()}
        onDownload={vi.fn()}
      />
    );

    const button = screen.getByRole("button", { name: /正在生成交付包|Generating package/i });
    expect(button).toBeDisabled();

    fireEvent.click(button);
    expect(button).toBeDisabled();
  });

  it("renders artifact cards with download and import handoff actions", async () => {
    const onMarkDeployed = vi.fn().mockResolvedValue(undefined);
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
        onMarkDeployed={onMarkDeployed}
      />
    );

    const button = screen.getByRole("button", { name: /下载|Download/i });
    expect(button).toHaveTextContent(/下载|Download/i);
    expect(button).toHaveClass("bg-accent");
    expect(button).toHaveClass("h-10");
    expect(button).toHaveClass("text-sm");

    fireEvent.change(screen.getByPlaceholderText(/平台 App ID|Platform App ID/i), {
      target: { value: "hiagent-app-42" }
    });
    fireEvent.change(screen.getByPlaceholderText(/交接备注|Handoff note/i), {
      target: { value: "Imported into staging." }
    });
    fireEvent.click(screen.getByRole("button", { name: /标记已导入\/交接|Mark imported\/handed off/i }));

    await waitFor(() => {
      expect(onMarkDeployed).toHaveBeenCalledWith({
        artifact: expect.objectContaining({ workflow_id: "workflow-1" }),
        deployment_note: "Imported into staging.",
        platform_app_id: "hiagent-app-42"
      });
    });
  });

  it("uses the card as the single vertical scroll container", () => {
    const { container } = render(
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
        onMarkDeployed={vi.fn()}
      />
    );

    const card = container.querySelector("section");
    const formBody = container.querySelector("form")?.parentElement;
    const artifactList = container.querySelector("h3")?.closest("article")?.parentElement;

    expect(card).toHaveClass("overflow-y-auto");
    expect(card).not.toHaveClass("overflow-hidden");
    expect(formBody).not.toHaveClass("shrink-0");
    expect(artifactList).toHaveClass("grid");
    expect(artifactList).not.toHaveClass("overflow-y-auto");
    expect(artifactList).not.toHaveClass("flex-1");
    expect(artifactList).not.toHaveClass("scroll-mask-y");
  });
});
