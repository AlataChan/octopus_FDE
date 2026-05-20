import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { ArrowLeft, RotateCcw } from "lucide-react";
import { ChatColumn } from "../../components/console/ChatColumn";
import { CompileColumn } from "../../components/console/CompileColumn";
import { IRColumn } from "../../components/console/IRColumn";
import { LLMConfigModal } from "../../components/console/LLMConfigModal";
import { Button } from "../../components/ui/Button";
import { Chip, type ChipVariant } from "../../components/ui/Chip";
import { downloadArtifact } from "../../lib/api";
import type { Artifact, CompileInput, LLMConfigInput, MarkImportedInput } from "../../lib/types";
import { useCompileSession, useIRDiff, useMarkImported, useSession, useSetLLMConfig } from "../../hooks/useSession";
import { usePlannerTurn } from "../../hooks/usePlannerTurn";
import { useIsXl } from "../../hooks/useIsXl";
import { useState } from "react";

const PANEL_GROUP_AUTOSAVE_ID = "fde-session-panels-v1";
const PANEL_STORAGE_KEY = `react-resizable-panels:${PANEL_GROUP_AUTOSAVE_ID}`;

export default function SessionDetailPage() {
  const { t } = useTranslation();
  const params = useParams();
  const sessionId = params.id || "";
  const { bindings, ir, session, turns, workflows } = useSession(sessionId);
  const [highlightedPath, setHighlightedPath] = useState<string | null>(null);
  const [layoutResetVersion, setLayoutResetVersion] = useState(0);
  const isXl = useIsXl();
  const setConfig = useSetLLMConfig(sessionId);
  const plannerTurn = usePlannerTurn(sessionId);
  const compile = useCompileSession(sessionId);
  const markImported = useMarkImported();
  const needsConfig = Boolean(session.data && !session.data.llm_model);
  const errors = ir.data?.validation_errors || [];
  const compileWarningCount = (session.data?.artifacts || []).reduce(
    (count, artifact) => count + artifact.compile_warnings.length,
    0
  );
  const successfulTurns = (turns.data || []).filter((turn) => turn.status === "succeeded");
  const fromTurn =
    successfulTurns.length >= 2 ? successfulTurns[successfulTurns.length - 2].turn_id : null;
  const toTurn =
    successfulTurns.length >= 2 ? successfulTurns[successfulTurns.length - 1].turn_id : null;
  const diff = useIRDiff(sessionId, fromTurn, toTurn);

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

  function mark(workflowId: string, input: MarkImportedInput) {
    markImported.mutate({ input, workflowId });
  }

  function resetLayout() {
    try {
      window.localStorage.removeItem(PANEL_STORAGE_KEY);
    } catch {
      // localStorage may be unavailable in restricted browser contexts.
    }
    setLayoutResetVersion((version) => version + 1);
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
      diff={diff.data || null}
      errors={errors}
      highlightedPath={highlightedPath}
      ir={ir.data?.ir || null}
      status={ir.data?.validator_status || t("session.noIr")}
      onSelectPath={setHighlightedPath}
    />
  );
  const compileCol = (
    <CompileColumn
      artifacts={session.data?.artifacts || []}
      bindings={bindings.data || []}
      isCompiling={compile.isPending}
      markingWorkflowId={markImported.variables?.workflowId || null}
      workflows={workflows.data || []}
      onCompile={runCompile}
      onDownload={(artifact) => void download(artifact)}
      onMarkImported={mark}
    />
  );

  return (
    <section className="min-h-[calc(100vh-56px)] px-4 py-5 sm:px-6 lg:px-8 xl:flex xl:h-[calc(100dvh-56px)] xl:flex-col xl:overflow-hidden">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <Link className="inline-flex" to="/">
            <Button
              icon={<ArrowLeft aria-hidden className="h-4 w-4" />}
              size="sm"
              variant="ghost"
            >
              {t("session.back")}
            </Button>
          </Link>
          <h1 className="mt-3 truncate font-mono text-lg font-semibold text-fg">{sessionId}</h1>
          <p className="mt-1 text-sm text-fg-muted">{t("session.subtitle")}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {isXl ? (
            <Button
              icon={<RotateCcw aria-hidden className="h-4 w-4" />}
              size="sm"
              variant="ghost"
              onClick={resetLayout}
            >
              {t("layout.reset")}
            </Button>
          ) : null}
          <Chip variant={chipForState(session.data?.state || "draft")}>
            {session.data?.state || t("session.loading")}
          </Chip>
        </div>
      </div>
      {isXl ? (
        <div className="min-h-0 flex-1">
          {/* The xl workbench needs a complete h-full/min-h-0 chain so panels scroll internally. */}
          <PanelGroup
            autoSaveId={PANEL_GROUP_AUTOSAVE_ID}
            className="h-full w-full"
            direction="horizontal"
            key={layoutResetVersion}
          >
            <Panel className="flex min-h-0 min-w-0 flex-col overflow-hidden" defaultSize={36} id="chat" minSize={20} order={1}>
              {chatCol}
            </Panel>
            <PanelResizeHandle
              aria-label={t("layout.resizeChatIr")}
              className="group relative w-3 cursor-col-resize rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 rounded-full bg-border/45 transition-colors group-hover:bg-accent/80 group-data-[resize-handle-state=drag]:bg-accent" />
            </PanelResizeHandle>
            <Panel className="flex min-h-0 min-w-0 flex-col overflow-hidden" defaultSize={36} id="ir" minSize={20} order={2}>
              {irCol}
            </Panel>
            <PanelResizeHandle
              aria-label={t("layout.resizeIrCompile")}
              className="group relative w-3 cursor-col-resize rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 rounded-full bg-border/45 transition-colors group-hover:bg-accent/80 group-data-[resize-handle-state=drag]:bg-accent" />
            </PanelResizeHandle>
            <Panel className="flex min-h-0 min-w-0 flex-col overflow-hidden" defaultSize={28} id="compile" minSize={20} order={3}>
              {compileCol}
            </Panel>
          </PanelGroup>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-8">
          <div className="md:col-span-8">{chatCol}</div>
          <div className="max-h-[70vh] overflow-auto md:col-span-5">{irCol}</div>
          <div className="md:col-span-3">{compileCol}</div>
        </div>
      )}
      <LLMConfigModal
        isSaving={setConfig.isPending}
        open={needsConfig}
        onSubmit={saveConfig}
      />
    </section>
  );
}

function chipForState(state: string): ChipVariant {
  if (state === "compiled") {
    return "compiled";
  }
  if (state === "validated") {
    return "validated";
  }
  if (state === "llm_config_set") {
    return "llm_config_set";
  }
  return "draft";
}
