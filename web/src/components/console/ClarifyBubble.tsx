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
  question: ClarifyQuestion;
};

export function ClarifyBubble({
  disabled = false,
  isLatestInteractive = true,
  onSend,
  question
}: Props) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string | null>(null);
  const [freeform, setFreeform] = useState("");
  const effectiveDisabled = disabled || !isLatestInteractive;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (effectiveDisabled) {
      return;
    }
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
    <form
      aria-disabled={effectiveDisabled}
      className="rounded-lg border border-accent/25 bg-bg-surface p-4 text-sm leading-6 text-fg shadow-glow sm:p-5"
      onSubmit={submit}
    >
      <div className="space-y-4">
        <div className="border-b border-border/35 pb-3">
          <div className="text-xs font-semibold uppercase tracking-[0.08em] text-accent">{t("clarify.title")}</div>
          <p className="mt-2 text-base font-semibold leading-7">{question.text}</p>
        </div>
        {question.options && question.options.length > 0 ? (
          <div className="grid gap-2 sm:grid-cols-2">
            {question.options.map((option) => (
              <ClarifyOptionButton
                key={option.value}
                disabled={effectiveDisabled}
                option={option}
                selected={selected === option.value}
                onSelect={setSelected}
              />
            ))}
          </div>
        ) : null}
        {question.allow_freeform ? (
          <Textarea
            aria-label={question.text}
            className="min-h-28 resize-y"
            disabled={effectiveDisabled}
            placeholder={t("clarify.freeformPlaceholder")}
            value={freeform}
            onChange={(event) => setFreeform(event.target.value)}
          />
        ) : null}
        <Button
          disabled={effectiveDisabled || !canSubmit}
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
