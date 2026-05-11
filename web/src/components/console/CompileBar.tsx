import { FormEvent, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type {
  Artifact,
  BindingSummary,
  CompileInput,
  CompileMode,
  CompileTarget,
  MarkImportedInput,
  WorkflowRecord
} from "../../lib/types";

type Props = {
  artifacts: Artifact[];
  bindings: BindingSummary[];
  isCompiling: boolean;
  markingWorkflowId?: string | null;
  onCompile: (input: CompileInput) => void;
  onDownload: (artifact: Artifact) => void;
  onMarkImported: (workflowId: string, input: MarkImportedInput) => void;
  workflows: WorkflowRecord[];
};

export function CompileBar({
  artifacts,
  bindings,
  isCompiling,
  markingWorkflowId,
  onCompile,
  onDownload,
  onMarkImported,
  workflows
}: Props) {
  const { t } = useTranslation();
  const [target, setTarget] = useState<CompileTarget>("hiagent");
  const [mode, setMode] = useState<CompileMode>("chatflow");
  const [binding, setBinding] = useState("");
  const targetBindings = useMemo(
    () => bindings.filter((candidate) => candidate.target === target),
    [bindings, target]
  );
  const selectedBinding = binding || targetBindings[0]?.handle || "test";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCompile({
      binding: selectedBinding,
      mode: target === "hiagent" ? mode : null,
      target
    });
  }

  return (
    <section className="border-t border-slate-200 bg-white">
      <form className="grid gap-3 px-4 py-3 md:grid-cols-[160px_160px_1fr_160px]" onSubmit={submit}>
        <label className="text-xs font-medium text-slate-600">
          {t("compile.target")}
          <select
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm"
            value={target}
            onChange={(event) => {
              setTarget(event.target.value as CompileTarget);
              setBinding("");
            }}
          >
            <option value="hiagent">{t("compile.targetHiagent")}</option>
            <option value="dify">{t("compile.targetDify")}</option>
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">
          {t("compile.mode")}
          <select
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm disabled:bg-slate-100"
            disabled={target !== "hiagent"}
            value={mode}
            onChange={(event) => setMode(event.target.value as CompileMode)}
          >
            <option value="chatflow">{t("compile.modeChatflow")}</option>
            <option value="chat">{t("compile.modeChat")}</option>
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">
          {t("compile.binding")}
          <select
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2 text-sm"
            value={selectedBinding}
            onChange={(event) => setBinding(event.target.value)}
          >
            {targetBindings.length ? (
              targetBindings.map((candidate) => (
                <option key={candidate.handle} value={candidate.handle}>
                  {candidate.display_name}
                </option>
              ))
            ) : (
              <option value="test">{t("compile.bindingFallback")}</option>
            )}
          </select>
        </label>
        <button
          className="self-end rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-400"
          disabled={isCompiling}
          type="submit"
        >
          {isCompiling ? t("compile.compiling") : t("compile.action")}
        </button>
      </form>
      <div className="grid gap-3 border-t border-slate-200 px-4 py-3 lg:grid-cols-2">
        {artifacts.length === 0 ? (
          <p className="text-sm text-slate-500">{t("compile.noArtifacts")}</p>
        ) : (
          artifacts.map((artifact) => {
            const workflow = workflows.find((row) => row.workflow_id === artifact.workflow_id);
            return (
              <ArtifactCard
                artifact={artifact}
                key={artifact.artifact_id}
                marking={markingWorkflowId === artifact.workflow_id}
                workflow={workflow}
                onDownload={onDownload}
                onMarkImported={onMarkImported}
              />
            );
          })
        )}
      </div>
    </section>
  );
}

type ArtifactCardProps = {
  artifact: Artifact;
  marking: boolean;
  onDownload: (artifact: Artifact) => void;
  onMarkImported: (workflowId: string, input: MarkImportedInput) => void;
  workflow?: WorkflowRecord;
};

function ArtifactCard({
  artifact,
  marking,
  onDownload,
  onMarkImported,
  workflow
}: ArtifactCardProps) {
  const { t } = useTranslation();
  const [platformAppId, setPlatformAppId] = useState(workflow?.platform_app_id || "");
  const [note, setNote] = useState(workflow?.deployment_note || "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onMarkImported(artifact.workflow_id, {
      deployment_note: note,
      platform_app_id: platformAppId
    });
  }

  return (
    <article className="rounded-md border border-slate-200 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-950">{artifact.artifact_name}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {artifact.target} / {artifact.mode || artifact.artifact_kind} / {artifact.sha256.slice(0, 12)}
          </p>
        </div>
        <button
          className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          type="button"
          onClick={() => onDownload(artifact)}
        >
          {t("compile.download")}
        </button>
      </div>
      <form className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]" onSubmit={submit}>
        <input
          className="rounded-md border border-slate-300 px-2 py-2 text-xs"
          placeholder={t("compile.platformAppId")}
          value={platformAppId}
          onChange={(event) => setPlatformAppId(event.target.value)}
        />
        <input
          className="rounded-md border border-slate-300 px-2 py-2 text-xs"
          placeholder={t("compile.deploymentNote")}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        <button
          className="rounded-md bg-slate-800 px-3 py-2 text-xs font-semibold text-white disabled:bg-slate-400"
          disabled={marking}
          type="submit"
        >
          {marking ? t("compile.marking") : t("compile.markImported")}
        </button>
      </form>
    </article>
  );
}
