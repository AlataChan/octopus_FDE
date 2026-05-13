import { useTranslation } from "react-i18next";
import type { IRDiffResponse, ValidationFailure } from "../../lib/types";
import { Card, CardHeader } from "../ui/Card";
import { Chip } from "../ui/Chip";
import { IRDiffView } from "./IRDiffView";
import { IRView } from "./IRView";
import { ValidatorPanel } from "./ValidatorPanel";

type Props = {
  diff: IRDiffResponse | null;
  errors: ValidationFailure[];
  highlightedPath?: string | null;
  ir: unknown | null;
  onSelectPath: (path: string) => void;
  status: string;
};

export function IRColumn({
  diff,
  errors,
  highlightedPath,
  ir,
  onSelectPath,
  status
}: Props) {
  const { t } = useTranslation();

  return (
    <Card className="flex h-full min-h-0 min-w-0 flex-col">
      <CardHeader
        action={
          <Chip variant={errors.length ? "failed" : ir ? "ok" : "draft"}>
            {errors.length
              ? t("validator.issueCount", { count: errors.length })
              : ir
                ? t("validator.ok")
                : t("session.noIr")}
          </Chip>
        }
        subtitle={t("ir.panelSubtitle")}
        title={t("ir.panelTitle")}
      />
      <IRView errors={errors} highlightedPath={highlightedPath} ir={ir} status={status} />
      <ValidatorPanel errors={errors} onSelectPath={onSelectPath} />
      <IRDiffView diff={diff} onSelectPath={onSelectPath} />
    </Card>
  );
}
