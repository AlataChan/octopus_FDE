import type {
  Artifact,
  BindingSummary,
  CompileInput,
  MarkImportedInput,
  WorkflowRecord
} from "../../lib/types";
import { CompileBar } from "./CompileBar";

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

export function CompileColumn({
  artifacts,
  bindings,
  isCompiling,
  markingWorkflowId,
  onCompile,
  onDownload,
  onMarkImported,
  workflows
}: Props) {
  return (
    <CompileBar
      artifacts={artifacts}
      bindings={bindings}
      isCompiling={isCompiling}
      markingWorkflowId={markingWorkflowId}
      workflows={workflows}
      onCompile={onCompile}
      onDownload={onDownload}
      onMarkImported={onMarkImported}
    />
  );
}
