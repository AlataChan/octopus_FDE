import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  createSession,
  createSessionFromTemplate,
  downloadArtifact,
  renameSession
} from "../lib/api";
import type { Artifact, CompileInput, IRDiffChange, LLMConfigInput } from "../lib/types";
import { selectIRDiffTurnIds } from "../lib/session-diff";
import {
  useCompileSession,
  useIRDiff,
  useSession,
  useSetLLMConfig
} from "./useSession";
import { usePlannerTurn } from "./usePlannerTurn";
import { useIsLg } from "./useIsLg";
import { useIsXl } from "./useIsXl";

export function useSessionWorkbench(sessionId: string) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { bindings, ir, session, turns } = useSession(sessionId);
  const [highlightedPath, setHighlightedPath] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [layoutResetVersion, setLayoutResetVersion] = useState(0);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [configDismissed, setConfigDismissed] = useState(false);
  const isLg = useIsLg();
  const isXl = useIsXl();

  const setConfig = useSetLLMConfig(sessionId);
  const plannerTurn = usePlannerTurn(sessionId);
  const compile = useCompileSession(sessionId);
  const rename = useMutation({
    mutationFn: (title: string) => renameSession(sessionId, title),
    onSuccess: async (row) => {
      queryClient.setQueryData(["session", sessionId], row);
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
    }
  });
  const create = useMutation({
    mutationFn: createSession,
    onSuccess: async (row) => {
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setTemplateModalOpen(false);
      setMobileSidebarOpen(false);
      navigate(`/sessions/${row.session_id}`);
    }
  });
  const createFromTemplate = useMutation({
    mutationFn: (templateId: string) => createSessionFromTemplate(templateId),
    onSuccess: async (row) => {
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setTemplateModalOpen(false);
      setMobileSidebarOpen(false);
      navigate(`/sessions/${row.session_id}`);
    }
  });

  useEffect(() => {
    setSelectedNodeId(null);
    setConfigDismissed(false);
  }, [sessionId]);

  useEffect(() => {
    try {
      window.localStorage.removeItem("react-resizable-panels:fde-context-vertical-v1");
    } catch {
      // localStorage may be unavailable in restricted browser contexts.
    }
  }, []);

  const needsConfig = Boolean(session.data && !session.data.llm_model);
  const errors = ir.data?.validation_errors || [];
  const compileWarningCount = (session.data?.artifacts || []).reduce(
    (count, artifact) => count + artifact.compile_warnings.length,
    0
  );
  const { fromTurn, toTurn } = selectIRDiffTurnIds(turns.data || []);
  const diff = useIRDiff(sessionId, fromTurn, toTurn);
  const compileWarnings = (session.data?.artifacts || []).flatMap((artifact) => artifact.compile_warnings);
  const flowDiffSummary = diff.data
    ? {
        added_node_ids: diff.data.changes
          .filter(isNodeDiffChange)
          .filter((change) => change.kind === "added")
          .map((change) => change.node_id),
        modified_node_ids: diff.data.changes
          .filter(isNodeDiffChange)
          .filter((change) => change.kind === "config-changed")
          .map((change) => change.node_id),
        removed_node_ids: diff.data.changes
          .filter(isNodeDiffChange)
          .filter((change) => change.kind === "removed")
          .map((change) => change.node_id)
      }
    : null;

  function saveConfig(input: LLMConfigInput) {
    setConfig.mutate(input);
  }

  function runCompile(input: CompileInput) {
    compile.mutate(input);
  }

  async function download(artifact: Artifact) {
    const blob = await downloadArtifact(sessionId, artifact.artifact_id);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = artifact.artifact_name;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function resetLayout() {
    try {
      window.localStorage.removeItem("react-resizable-panels:fde-session-panels-v1");
      window.localStorage.removeItem("react-resizable-panels:fde-context-vertical-v2");
      window.localStorage.removeItem("react-resizable-panels:fde-context-vertical-v1");
    } catch {
      // localStorage may be unavailable in restricted browser contexts.
    }
    setLayoutResetVersion((version) => version + 1);
  }

  function openTemplateModal() {
    setTemplateModalOpen(true);
  }

  return {
    bindings,
    compile,
    compileWarningCount,
    compileWarnings,
    configDismissed,
    create,
    createFromTemplate,
    diff,
    errors,
    flowDiffSummary,
    highlightedPath,
    ir,
    isLg,
    isXl,
    layoutResetVersion,
    mobileSidebarOpen,
    needsConfig,
    plannerTurn,
    rename,
    selectedNodeId,
    session,
    sessionId,
    setConfig,
    setConfigDismissed,
    setHighlightedPath,
    setMobileSidebarOpen,
    setSelectedNodeId,
    setTemplateModalOpen,
    templateModalOpen,
    t,
    turns,
    download,
    openTemplateModal,
    resetLayout,
    runCompile,
    saveConfig
  };
}

function isNodeDiffChange(change: IRDiffChange): change is Extract<IRDiffChange, { scope: "node" }> {
  return change.scope === "node";
}
