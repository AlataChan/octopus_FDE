import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Turn } from "../../lib/types";

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
    <section className="flex min-h-[640px] flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-950">{t("chat.title")}</h2>
        <p className="mt-1 text-xs text-slate-500">{t("chat.subtitle")}</p>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {turns.length === 0 ? (
          <p className="text-sm text-slate-500">{t("chat.empty")}</p>
        ) : (
          turns.map((turn) => (
            <article
              className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              key={turn.turn_id}
            >
              <div className="flex items-center justify-between gap-2 text-xs text-slate-500">
                <span>{turn.turn_id.slice(0, 8)}</span>
                <span>{t(`turn.status.${turn.status}`)}</span>
              </div>
              <p className="mt-2 text-slate-700">
                {turn.planner_reply || turn.errors.join("; ") || t("chat.turnPending")}
              </p>
            </article>
          ))
        )}
      </div>
      <form className="border-t border-slate-200 p-4" onSubmit={submit}>
        <textarea
          className="h-28 w-full resize-none rounded-md border border-slate-300 px-3 py-2 text-sm"
          placeholder={t("chat.placeholder")}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
        <button
          className="mt-3 w-full rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-400"
          disabled={isSending || !message.trim()}
          type="submit"
        >
          {isSending ? t("chat.sending") : t("chat.send")}
        </button>
      </form>
    </section>
  );
}
