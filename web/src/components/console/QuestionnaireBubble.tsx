import { FormEvent, useState } from "react";
import { Send } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ClarifyQuestion } from "../../lib/types";
import { Button } from "../ui/Button";
import { Textarea } from "../ui/Textarea";

type Props = {
  disabled?: boolean;
  onSend: (message: string) => void;
  questions: ClarifyQuestion[];
};

export function QuestionnaireBubble({ disabled = false, onSend, questions }: Props) {
  const { t } = useTranslation();
  const [answers, setAnswers] = useState<Record<string, string>>({});

  function setAnswer(fieldPath: string, value: string) {
    setAnswers((current) => ({ ...current, [fieldPath]: value }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
    <form className="rounded-lg bg-bg-app/60 p-3 text-sm leading-6 text-fg ring-1 ring-warning/25" onSubmit={submit}>
      <div className="space-y-4">
        <div>
          <div className="text-xs font-semibold uppercase text-fg-muted">{t("clarify.questionnaireTitle")}</div>
          <p className="mt-1 text-sm leading-6 text-fg-muted">{t("clarify.questionnaireSubtitle")}</p>
        </div>
        {questions.map((question) => (
          <div key={question.field_path} className="space-y-2">
            <label className="block text-sm font-medium text-fg" htmlFor={`clarify-${question.field_path}`}>
              {question.text}
            </label>
            {question.options && question.options.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {question.options.map((option) => (
                  <button
                    key={option.value}
                    className={
                      answers[question.field_path] === option.value
                        ? "rounded-lg border border-accent/50 bg-accent/15 px-3 py-1.5 text-xs font-semibold text-fg"
                        : "rounded-lg border border-border/60 bg-bg-muted px-3 py-1.5 text-xs font-semibold text-fg-muted hover:text-fg"
                    }
                    disabled={disabled}
                    onClick={() => setAnswer(question.field_path, option.value)}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            ) : null}
            {question.allow_freeform ? (
              <Textarea
                aria-label={question.field_path}
                className="h-20 resize-none"
                id={`clarify-${question.field_path}`}
                placeholder={t("clarify.freeformPlaceholder")}
                value={answers[question.field_path] || ""}
                onChange={(event) => setAnswer(question.field_path, event.target.value)}
              />
            ) : null}
          </div>
        ))}
        <Button
          disabled={disabled || !canSubmit}
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
