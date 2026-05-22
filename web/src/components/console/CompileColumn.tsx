import type {
  Artifact,
  BindingSummary,
  CompileInput
} from "../../lib/types";
import { CompileBar } from "./CompileBar";

type Props = {
  artifacts: Artifact[];
  bindings: BindingSummary[];
  isCompiling: boolean;
  onCompile: (input: CompileInput) => void;
  onDownload: (artifact: Artifact) => void;
};

export function CompileColumn({
  artifacts,
  bindings,
  isCompiling,
  onCompile,
  onDownload
}: Props) {
  return (
    <CompileBar
      artifacts={artifacts}
      bindings={bindings}
      isCompiling={isCompiling}
      onCompile={onCompile}
      onDownload={onDownload}
    />
  );
}
