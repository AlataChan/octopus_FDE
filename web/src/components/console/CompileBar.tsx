import { FormEvent, useMemo, useState } from "react";
import { Download, PackageCheck, Rocket } from "lucide-react";
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
import { Button } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";
import { Chip } from "../ui/Chip";
import { Input } from "../ui/Input";
import { Select } from "../ui/Select";

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
    <Card className="sticky top-[76px] overflow-hidden">
      <CardHeader
        action={
          <Chip pulse={isCompiling} variant={isCompiling ? "running" : "compiled"}>
            {isCompiling ? t("compile.compiling") : t("compile.ready")}
          </Chip>
        }
        subtitle={t("compile.subtitle")}
        title={t("compile.title")}
      />
      <CardBody>
        <form className="grid gap-3" onSubmit={submit}>
          <label className="text-xs font-medium text-fg-muted">
          {t("compile.target")}
          <Select
            className="mt-1"
            value={target}
            onChange={(event) => {
              setTarget(event.target.value as CompileTarget);
              setBinding("");
            }}
          >
            <option value="hiagent">{t("compile.targetHiagent")}</option>
            <option value="dify">{t("compile.targetDify")}</option>
          </Select>
        </label>
        <label className="text-xs font-medium text-fg-muted">
          {t("compile.mode")}
          <Select
            className="mt-1"
            disabled={target !== "hiagent"}
            value={mode}
            onChange={(event) => setMode(event.target.value as CompileMode)}
          >
            <option value="chatflow">{t("compile.modeChatflow")}</option>
            <option value="chat">{t("compile.modeChat")}</option>
          </Select>
        </label>
        <label className="text-xs font-medium text-fg-muted">
          {t("compile.binding")}
          <Select
            className="mt-1"
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
          </Select>
        </label>
        <Button
          className="w-full"
          disabled={isCompiling}
          icon={<Rocket aria-hidden className="h-4 w-4" />}
          loading={isCompiling}
          type="submit"
          variant="accent"
        >
          {isCompiling ? t("compile.compiling") : t("compile.action")}
        </Button>
      </form>
      </CardBody>
      <div className="grid gap-3 border-t border-border/30 p-4">
        {artifacts.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border/50 bg-bg-app/40 p-3 text-sm leading-6 text-fg-muted">
            {t("compile.noArtifacts")}
          </p>
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
    </Card>
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
    <article className="rounded-lg border border-border/50 bg-bg-app/45 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-fg">{artifact.artifact_name}</h3>
          <p className="mt-1 break-all font-mono text-[11px] leading-5 text-fg-muted">
            {artifact.target} / {artifact.mode || artifact.artifact_kind} / {artifact.sha256.slice(0, 12)}
          </p>
        </div>
        <Button
          icon={<Download aria-hidden className="h-4 w-4" />}
          size="sm"
          variant="ghost"
          onClick={() => onDownload(artifact)}
        >
          {t("compile.download")}
        </Button>
      </div>
      <form className="mt-3 grid gap-2" onSubmit={submit}>
        <Input
          placeholder={t("compile.platformAppId")}
          value={platformAppId}
          onChange={(event) => setPlatformAppId(event.target.value)}
        />
        <Input
          placeholder={t("compile.deploymentNote")}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        <Button
          icon={<PackageCheck aria-hidden className="h-4 w-4" />}
          loading={marking}
          size="sm"
          disabled={marking}
          type="submit"
          variant="secondary"
        >
          {marking ? t("compile.marking") : t("compile.markImported")}
        </Button>
      </form>
    </article>
  );
}
