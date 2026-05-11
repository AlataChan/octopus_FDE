import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { ChatPanel } from "../../components/console/ChatPanel";
import { CompileBar } from "../../components/console/CompileBar";
import { IRDiffView } from "../../components/console/IRDiffView";
import { IRView } from "../../components/console/IRView";
import { LLMConfigModal } from "../../components/console/LLMConfigModal";
import { ValidatorPanel } from "../../components/console/ValidatorPanel";
import { downloadArtifact } from "../../lib/api";
import type { Artifact, CompileInput, LLMConfigInput, MarkImportedInput } from "../../lib/types";
import { useCompileSession, useIRDiff, useMarkImported, useSession, useSetLLMConfig } from "../../hooks/useSession";
import { usePlannerTurn } from "../../hooks/usePlannerTurn";
import { useState } from "react";

export default function SessionDetailPage() {
  const { t } = useTranslation();
  const params = useParams();
  const sessionId = params.id || "";
  const { bindings, ir, session, turns, workflows } = useSession(sessionId);
  const [highlightedPath, setHighlightedPath] = useState<string | null>(null);
  const setConfig = useSetLLMConfig(sessionId);
  const plannerTurn = usePlannerTurn(sessionId);
  const compile = useCompileSession(sessionId);
  const markImported = useMarkImported();
  const needsConfig = Boolean(session.data && !session.data.llm_model);
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

  return (
    <section className="min-h-[calc(100vh-56px)]">
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <div>
          <Link className="text-xs font-medium text-slate-500 underline" to="/">
            {t("session.back")}
          </Link>
          <h1 className="mt-1 font-mono text-sm font-semibold text-slate-950">{sessionId}</h1>
        </div>
        <span className="rounded-md bg-slate-100 px-3 py-1 text-xs text-slate-700">
          {session.data?.state || t("session.loading")}
        </span>
      </div>
      <div className="grid min-h-[calc(100vh-112px)] grid-cols-1 lg:grid-cols-[360px_1fr]">
        <ChatPanel
          isSending={plannerTurn.isPending}
          turns={turns.data || []}
          onSend={(message) => plannerTurn.mutate(message)}
        />
        <main className="flex min-w-0 flex-col">
          <IRView
            errors={ir.data?.validation_errors || []}
            highlightedPath={highlightedPath}
            ir={ir.data?.ir || null}
            status={ir.data?.validator_status || t("session.noIr")}
          />
          <IRDiffView diff={diff.data || null} onSelectPath={setHighlightedPath} />
          <ValidatorPanel
            errors={ir.data?.validation_errors || []}
            onSelectPath={setHighlightedPath}
          />
          <CompileBar
            artifacts={session.data?.artifacts || []}
            bindings={bindings.data || []}
            isCompiling={compile.isPending}
            markingWorkflowId={markImported.variables?.workflowId || null}
            workflows={workflows.data || []}
            onCompile={runCompile}
            onDownload={(artifact) => void download(artifact)}
            onMarkImported={mark}
          />
        </main>
      </div>
      <LLMConfigModal
        isSaving={setConfig.isPending}
        open={needsConfig}
        onSubmit={saveConfig}
      />
    </section>
  );
}
