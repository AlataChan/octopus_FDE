import { FormEvent, useState } from "react";
import { Send } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ClarifyQuestion } from "../../lib/types";
import { Button } from "../ui/Button";
import { Textarea } from "../ui/Textarea";

type Props = {
  disabled?: boolean;
  onSend: (message: string) => void;
  question: ClarifyQuestion;
};

export function ClarifyBubble({ disabled = false, onSend, question }: Props) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string | null>(null);
  const [freeform, setFreeform] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parts = [];
    if (selected) parts.push(`${question.field_path}=${selected}`);
    if (question.allow_freeform && freeform.trim()) {
      parts.push(`${question.field_path}=${freeform.trim()}`);
    }
    const message = parts.join("; ");
    if (message) onSend(message);
  }

  const canSubmit = Boolean(selected || (question.allow_freeform && freeform.trim()));

  return (
    <form className="rounded-lg bg-bg-app/60 p-3 text-sm leading-6 text-fg ring-1 ring-accent/20" onSubmit={submit}>
      <div className="space-y-3">
        <div>
          <div className="text-xs font-semibold uppercase text-fg-muted">{t("clarify.title")}</div>
          <p className="mt-1 text-sm leading-6">{question.text}</p>
        </div>
        {question.options && question.options.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {question.options.map((option) => (
              <button
                key={option.value}
                className={
                  selected === option.value
                    ? "rounded-lg border border-accent/50 bg-accent/15 px-3 py-1.5 text-xs font-semibold text-fg"
                    : "rounded-lg border border-border/60 bg-bg-muted px-3 py-1.5 text-xs font-semibold text-fg-muted hover:text-fg"
                }
                disabled={disabled}
                onClick={() => setSelected(option.value)}
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
            placeholder={t("clarify.freeformPlaceholder")}
            value={freeform}
            onChange={(event) => setFreeform(event.target.value)}
          />
        ) : null}
        <Button
          disabled={disabled || !canSubmit}
          icon={<Send aria-hidden className="h-4 w-4" />}
          size="sm"
          type="submit"
          variant="primary"
        >
          {t("clarify.reply")}
        </Button>
      </div>
    </form>
  );
}
