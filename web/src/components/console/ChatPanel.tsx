import { FormEvent, useState } from "react";
import { Bot, Send, User } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Turn } from "../../lib/types";
import { Button } from "../ui/Button";
import { Card, CardBody, CardHeader } from "../ui/Card";
import { Chip } from "../ui/Chip";
import { Textarea } from "../ui/Textarea";

type Props = {
  isSending: boolean;
  onSend: (message: string) => void;
  turns: Turn[];
};

export function ChatPanel({ isSending, onSend, turns }: Props) {
  const { t } = useTranslation();
  const [message, setMessage] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    onSend(trimmed);
    setMessage("");
  }

  return (
    <Card className="flex h-full min-h-0 flex-col">
      <CardHeader
        action={
          <Chip pulse={isSending} variant={isSending ? "running" : "draft"}>
            {isSending ? t("chat.sendingShort") : t("chat.ready")}
          </Chip>
        }
        subtitle={t("chat.subtitle")}
        title={t("chat.title")}
      />
      <CardBody className="flex min-h-0 flex-1 flex-col p-0">
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {turns.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border/60 bg-bg-app/35 p-4 text-sm leading-6 text-fg-muted">
              {t("chat.empty")}
            </div>
          ) : (
            turns.map((turn) => <TurnBubble key={turn.turn_id} turn={turn} />)
          )}
        </div>
        <form className="shrink-0 border-t border-border/30 p-4" onSubmit={submit}>
          <Textarea
            className="h-28 resize-none"
            placeholder={t("chat.placeholder")}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
          <Button
            className="mt-3 w-full"
            disabled={isSending || !message.trim()}
            icon={<Send aria-hidden className="h-4 w-4" />}
            loading={isSending}
            type="submit"
            variant="primary"
          >
            {isSending ? t("chat.sending") : t("chat.send")}
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

function TurnBubble({ turn }: { turn: Turn }) {
  const { t } = useTranslation();
  const isFailed = turn.status === "failed";
  return (
    <article className="space-y-2">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="inline-flex items-center gap-1.5 font-mono text-fg-muted">
          <User aria-hidden className="h-3.5 w-3.5" />
          {turn.turn_id.slice(0, 8)}
        </span>
        <Chip
          pulse={turn.status === "running"}
          variant={turn.status === "running" ? "running" : turn.status === "failed" ? "failed" : "succeeded"}
        >
          {t(`turn.status.${turn.status}`)}
        </Chip>
      </div>
      <div
        className={
          isFailed
            ? "rounded-lg bg-destructive/10 p-3 text-sm leading-6 text-fg ring-1 ring-destructive/30"
            : "rounded-lg bg-bg-app/60 p-3 text-sm leading-6 text-fg ring-1 ring-accent/15"
        }
      >
        <p className="flex items-start gap-2">
          <Bot aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <span>{turn.planner_reply || turn.errors.join("; ") || t("chat.turnPending")}</span>
        </p>
      </div>
    </article>
  );
}
