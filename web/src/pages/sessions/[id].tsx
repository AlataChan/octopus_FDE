import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Menu } from "lucide-react";
import { ChatColumn } from "../../components/console/ChatColumn";
import { CompileColumn } from "../../components/console/CompileColumn";
import { IRColumn } from "../../components/console/IRColumn";
import { LLMConfigModal } from "../../components/console/LLMConfigModal";
import { SessionsSidebar } from "../../components/console/SessionsSidebar";
import { StateStepper } from "../../components/console/StateStepper";
import { TemplateModal } from "../../components/console/TemplateModal";
import { WorkbenchHeader } from "../../components/console/WorkbenchHeader";
import { Button } from "../../components/ui/Button";
import {
  createSession,
  createSessionFromTemplate,
  downloadArtifact,
  renameSession
} from "../../lib/api";
import type { Artifact, CompileInput, IRDiffChange, LLMConfigInput } from "../../lib/types";
import { useCompileSession, useIRDiff, useSession, useSetLLMConfig } from "../../hooks/useSession";
import { usePlannerTurn } from "../../hooks/usePlannerTurn";
import { useIsXl } from "../../hooks/useIsXl";
import { useIsLg } from "../../hooks/useIsLg";
import { selectIRDiffTurnIds } from "../../lib/session-diff";
import { useEffect, useState } from "react";

const PANEL_GROUP_AUTOSAVE_ID = "fde-session-panels-v1";
const LEGACY_CONTEXT_PANEL_STORAGE_KEY = "react-resizable-panels:fde-context-vertical-v1";
const CONTEXT_PANEL_GROUP_AUTOSAVE_ID = "fde-context-vertical-v2";
const PANEL_STORAGE_KEY = `react-resizable-panels:${PANEL_GROUP_AUTOSAVE_ID}`;
const CONTEXT_PANEL_STORAGE_KEY = `react-resizable-panels:${CONTEXT_PANEL_GROUP_AUTOSAVE_ID}`;

export default function SessionDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const params = useParams();
  const queryClient = useQueryClient();
  const sessionId = params.id || "";
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
      window.localStorage.removeItem(LEGACY_CONTEXT_PANEL_STORAGE_KEY);
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
      window.localStorage.removeItem(PANEL_STORAGE_KEY);
      window.localStorage.removeItem(CONTEXT_PANEL_STORAGE_KEY);
      window.localStorage.removeItem(LEGACY_CONTEXT_PANEL_STORAGE_KEY);
    } catch {
      // localStorage may be unavailable in restricted browser contexts.
    }
    setLayoutResetVersion((version) => version + 1);
  }

  function openTemplateModal() {
    setTemplateModalOpen(true);
  }

  const chatCol = (
    <ChatColumn
      isSending={plannerTurn.isPending}
      turns={turns.data || []}
      onSend={(message) => plannerTurn.mutate(message)}
    />
  );
  const irCol = (
    <IRColumn
      compileWarningCount={compileWarningCount}
      compileWarnings={compileWarnings}
      diff={diff.data || null}
      diffSummary={flowDiffSummary}
      errors={errors}
      highlightedPath={highlightedPath}
      ir={ir.data?.ir || null}
      resetKey={sessionId}
      selectedNodeId={selectedNodeId}
      status={ir.data?.validator_status || t("session.noIr")}
      onSelectedNodeIdChange={setSelectedNodeId}
      onSelectPath={setHighlightedPath}
    />
  );
  const compileCol = (
    <CompileColumn
      artifacts={session.data?.artifacts || []}
      bindings={bindings.data || []}
      isCompiling={compile.isPending}
      onCompile={runCompile}
      onDownload={(artifact) => void download(artifact)}
    />
  );
  const header = (
    <WorkbenchHeader
      session={session.data || null}
      onRename={(title) => rename.mutateAsync(title)}
      onResetLayout={resetLayout}
    />
  );
  const stepper = (
    <div className="shrink-0 border-b border-border/30 bg-bg-surface/75 px-3 py-2">
      <StateStepper state={session.data?.state || "init"} />
    </div>
  );
  const desktopSidebar = (
    <SessionsSidebar
      currentSessionId={sessionId}
      defaultCollapsed={!isXl}
      onCreateSession={openTemplateModal}
    />
  );
  const mobileSidebar = (
    <SessionsSidebar
      currentSessionId={sessionId}
      forceExpanded
      onCreateSession={openTemplateModal}
    />
  );

  return (
    <section className="min-h-[calc(100vh-56px)] lg:h-[calc(100dvh-56px)] lg:overflow-hidden">
      <div className="flex h-12 items-center justify-between border-b border-border/30 bg-bg-surface/85 px-3 lg:hidden">
        <Button
          aria-label={t("sidebar.openMobile")}
          icon={<Menu aria-hidden className="h-4 w-4" />}
          size="sm"
          variant="ghost"
          onClick={() => setMobileSidebarOpen(true)}
        >
          {t("workbench.sessionsLink")}
        </Button>
      </div>
      {mobileSidebarOpen && !isLg ? (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <button
            aria-label={t("sidebar.closeMobile")}
            className="absolute inset-0 bg-primary/40"
            type="button"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div className="relative z-10 h-full">
            {mobileSidebar}
          </div>
        </div>
      ) : null}
      <div className="lg:flex lg:h-full lg:min-h-0">
        {isLg ? <div className="hidden lg:flex lg:h-full">{desktopSidebar}</div> : null}
        <div className="min-w-0 flex-1 lg:min-h-0">
          {isLg ? (
            <div className="min-h-0 flex-1 lg:h-full">
              <PanelGroup
                autoSaveId={PANEL_GROUP_AUTOSAVE_ID}
                className="h-full w-full"
                direction="horizontal"
                key={layoutResetVersion}
              >
                <Panel className="flex min-h-0 min-w-0 flex-col overflow-hidden" defaultSize={60} id="chat" minSize={36} order={1}>
                  {header}
                  {stepper}
                  <div className="min-h-0 flex-1 p-3">{chatCol}</div>
                </Panel>
                <PanelResizeHandle
                  aria-label={t("layout.resizeChatIr")}
                  className="group relative w-3 cursor-col-resize rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 rounded-full bg-border/45 transition-colors group-hover:bg-accent/80 group-data-[resize-handle-state=drag]:bg-accent" />
                </PanelResizeHandle>
                <Panel className="flex min-h-0 min-w-0 flex-col overflow-hidden p-3" defaultSize={40} id="context" minSize={28} order={2}>
                  <PanelGroup
                    autoSaveId={CONTEXT_PANEL_GROUP_AUTOSAVE_ID}
                    className="h-full min-h-0 w-full"
                    direction="vertical"
                  >
                    <Panel className="flex min-h-0 min-w-0 overflow-hidden" defaultSize={30} id="context-ir" minSize={30} order={1}>
                      <div className="h-full min-h-0 w-full overflow-hidden" data-testid="context-ir-pane">{irCol}</div>
                    </Panel>
                    <PanelResizeHandle
                      aria-label={t("layout.resizeIrCompile")}
                      className="group relative h-3 cursor-row-resize rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span className="absolute left-0 top-1/2 h-0.5 w-full -translate-y-1/2 rounded-full bg-border/45 transition-colors group-hover:bg-accent/80 group-data-[resize-handle-state=drag]:bg-accent" />
                    </PanelResizeHandle>
                    <Panel
                      className="flex min-h-0 min-w-0 overflow-hidden"
                      defaultSize={70}
                      id="context-compile"
                      minSize={28}
                      order={2}
                    >
                      <div className="h-full min-h-0 w-full overflow-hidden" data-testid="context-compile-pane">{compileCol}</div>
                    </Panel>
                  </PanelGroup>
                </Panel>
              </PanelGroup>
            </div>
          ) : (
            <div className="grid gap-4 p-4 md:grid-cols-8 lg:h-full lg:min-h-0 lg:overflow-y-auto">
              <div className="md:col-span-8">
                {header}
                {stepper}
              </div>
              <div className="md:col-span-8">{chatCol}</div>
              <div className="max-h-[70vh] overflow-auto md:col-span-5">{irCol}</div>
              <div className="md:col-span-3">{compileCol}</div>
            </div>
          )}
        </div>
      </div>
      <LLMConfigModal
        isSaving={setConfig.isPending}
        open={needsConfig && !configDismissed}
        onOpenChange={(open) => {
          if (!open) {
            setConfigDismissed(true);
          }
        }}
        onSubmit={saveConfig}
      />
      <TemplateModal
        creatingBlank={create.isPending}
        creatingTemplateId={(createFromTemplate.variables as string | undefined) || null}
        open={templateModalOpen}
        onCreateBlank={() => create.mutate()}
        onCreateTemplate={(templateId) => createFromTemplate.mutate(templateId)}
        onOpenChange={setTemplateModalOpen}
      />
    </section>
  );
}

function isNodeDiffChange(change: IRDiffChange): change is Extract<IRDiffChange, { scope: "node" }> {
  return change.scope === "node";
}
