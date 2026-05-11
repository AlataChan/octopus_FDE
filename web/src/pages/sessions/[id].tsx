import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { ChatPanel } from "../../components/console/ChatPanel";
import { CompileBar } from "../../components/console/CompileBar";
import { IRDiffView } from "../../components/console/IRDiffView";
import { IRView } from "../../components/console/IRView";
import { LLMConfigModal } from "../../components/console/LLMConfigModal";
import { ValidatorPanel } from "../../components/console/ValidatorPanel";
import { Button } from "../../components/ui/Button";
import { Card, CardHeader } from "../../components/ui/Card";
import { Chip, type ChipVariant } from "../../components/ui/Chip";
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
    <section className="min-h-[calc(100vh-56px)] px-4 py-5 sm:px-6 lg:px-8">
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
        <Chip variant={chipForState(session.data?.state || "draft")}>
          {session.data?.state || t("session.loading")}
        </Chip>
      </div>
      <div className="grid gap-4 md:grid-cols-8 xl:grid-cols-12">
        <div className="md:col-span-8 xl:col-span-4">
          <ChatPanel
            isSending={plannerTurn.isPending}
            turns={turns.data || []}
            onSend={(message) => plannerTurn.mutate(message)}
          />
        </div>
        <Card className="min-w-0 md:col-span-5 xl:col-span-6">
          <CardHeader
            action={
              <Chip
                variant={(ir.data?.validation_errors || []).length ? "failed" : ir.data?.ir ? "ok" : "draft"}
              >
                {(ir.data?.validation_errors || []).length
                  ? t("validator.issueCount", { count: ir.data?.validation_errors.length || 0 })
                  : ir.data?.ir
                    ? t("validator.ok")
                    : t("session.noIr")}
              </Chip>
            }
            subtitle={t("ir.panelSubtitle")}
            title={t("ir.panelTitle")}
          />
          <IRView
            errors={ir.data?.validation_errors || []}
            highlightedPath={highlightedPath}
            ir={ir.data?.ir || null}
            status={ir.data?.validator_status || t("session.noIr")}
          />
          <ValidatorPanel
            errors={ir.data?.validation_errors || []}
            onSelectPath={setHighlightedPath}
          />
          <IRDiffView diff={diff.data || null} onSelectPath={setHighlightedPath} />
        </Card>
        <div className="md:col-span-3 xl:col-span-2">
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
        </div>
      </div>
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
