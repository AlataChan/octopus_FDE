import { useTranslation } from "react-i18next";
import { cn } from "../../lib/cn";

const steps = [
  {
    id: "llm",
    labelKey: "stepper.llm",
    tooltipKey: "stepper.llmTooltip"
  },
  {
    id: "draft",
    labelKey: "stepper.draft",
    tooltipKey: "stepper.draftTooltip"
  },
  {
    id: "validate",
    labelKey: "stepper.validate",
    tooltipKey: "stepper.validateTooltip"
  },
  {
    id: "compile",
    labelKey: "stepper.compile",
    tooltipKey: "stepper.compileTooltip"
  },
  {
    id: "download",
    labelKey: "stepper.download",
    tooltipKey: "stepper.downloadTooltip"
  }
] as const;

type StepStatus = "complete" | "current" | "upcoming";

export function StateStepper({ state }: { state?: string | null }) {
  const { t } = useTranslation();
  const statuses = statusForState(state || "init");

  return (
    <nav aria-label={t("stepper.aria")} className="flex h-7 min-w-0 items-center gap-2">
      {steps.map((step, index) => {
        const status = statuses[index];
        return (
          <div
            aria-current={status === "current" ? "step" : undefined}
            className="flex min-w-0 flex-1 items-center gap-2"
            data-step-status={status}
            data-testid={`stepper.${step.id}`}
            key={step.id}
            title={t(step.tooltipKey)}
          >
            <span
              aria-hidden
              className={cn(
                "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
                status === "complete" && "border-accent bg-accent",
                status === "current" && "border-ring bg-ring",
                status === "upcoming" && "border-border bg-transparent"
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  status === "complete" && "bg-primary dark:bg-bg-app",
                  status === "current" && "bg-primary-fg",
                  status === "upcoming" && "bg-transparent"
                )}
              />
            </span>
            <span
              className={cn(
                "truncate text-xs",
                status === "current" ? "font-semibold text-fg" : "font-medium text-fg-muted"
              )}
            >
              {t(step.labelKey)}
            </span>
            {index < steps.length - 1 ? (
              <span
                aria-hidden
                className={cn(
                  "h-px min-w-3 flex-1",
                  status === "complete" ? "bg-accent" : "bg-border/70"
                )}
              />
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}

function statusForState(state: string): StepStatus[] {
  if (state === "downloaded") {
    return ["complete", "complete", "complete", "complete", "complete"];
  }
  if (state === "compiled") {
    return ["complete", "complete", "complete", "complete", "upcoming"];
  }
  if (state === "validated") {
    return ["complete", "complete", "complete", "upcoming", "upcoming"];
  }
  if (state === "llm_config_set" || state === "drafting") {
    return ["complete", "current", "upcoming", "upcoming", "upcoming"];
  }
  return ["current", "upcoming", "upcoming", "upcoming", "upcoming"];
}
