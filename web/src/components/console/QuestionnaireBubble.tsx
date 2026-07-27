import { FormEvent, useState } from "react";
import { Send } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ClarifyQuestion } from "../../lib/types";
import { Button } from "../ui/Button";
import { Textarea } from "../ui/Textarea";
import { ClarifyOptionButton } from "./ClarifyOptionButton";

type Props = {
  disabled?: boolean;
  isLatestInteractive?: boolean;
  onSend: (message: string) => void;
  questions: ClarifyQuestion[];
};

export function QuestionnaireBubble({
  disabled = false,
  isLatestInteractive = true,
  onSend,
  questions
}: Props) {
  const { t } = useTranslation();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const effectiveDisabled = disabled || !isLatestInteractive;

  function setAnswer(fieldPath: string, value: string) {
    setAnswers((current) => ({ ...current, [fieldPath]: value }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (effectiveDisabled) {
      return;
    }
    const message = questions
      .map((question) => {
        const value = answers[question.field_path]?.trim();
        return value ? `${question.field_path}=${value}` : null;
      })
      .filter(Boolean)
      .join("; ");
    if (message) onSend(message);
  }

  const canSubmit = questions.some((question) => Boolean(answers[question.field_path]?.trim()));

  return (
    <form
      aria-disabled={effectiveDisabled}
      className="rounded-lg border border-warning/30 bg-bg-surface p-4 text-sm leading-6 text-fg shadow-glow sm:p-5"
      onSubmit={submit}
    >
      <div className="space-y-5">
        <div className="border-b border-border/35 pb-3">
          <div className="text-xs font-semibold uppercase tracking-[0.08em] text-warning">
            {t("clarify.questionnaireTitle")}
          </div>
          <p className="mt-1 text-sm leading-6 text-fg-muted">{t("clarify.questionnaireSubtitle")}</p>
        </div>
        {questions.map((question, index) => (
          <div key={question.field_path} className="space-y-3 rounded-lg border border-border/45 bg-bg-app/35 p-3">
            <div>
              <div className="text-xs font-semibold text-fg-muted">
                {t("clarify.step", { current: index + 1, total: questions.length })}
              </div>
              <label className="mt-1 block text-base font-semibold leading-7 text-fg" htmlFor={`clarify-${question.field_path}`}>
                {question.text}
              </label>
            </div>
            {question.options && question.options.length > 0 ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {question.options.map((option) => (
                  <ClarifyOptionButton
                    key={option.value}
                    disabled={effectiveDisabled}
                    option={option}
                    selected={answers[question.field_path] === option.value}
                    onSelect={(value) => setAnswer(question.field_path, value)}
                  />
                ))}
              </div>
            ) : null}
            {question.allow_freeform ? (
              <Textarea
                aria-label={question.text}
                className="min-h-28 resize-y"
                disabled={effectiveDisabled}
                id={`clarify-${question.field_path}`}
                placeholder={t("clarify.freeformPlaceholder")}
                value={answers[question.field_path] || ""}
                onChange={(event) => setAnswer(question.field_path, event.target.value)}
              />
            ) : null}
          </div>
        ))}
        <Button
          disabled={effectiveDisabled || !canSubmit}
          icon={<Send aria-hidden className="h-4 w-4" />}
          size="sm"
          type="submit"
          variant="primary"
        >
          {t("clarify.submitQuestionnaire")}
        </Button>
      </div>
    </form>
  );
}
