import type { Turn } from "../../lib/types";
import { ChatPanel } from "./ChatPanel";

type Props = {
  isSending: boolean;
  onSend: (message: string) => void;
  turns: Turn[];
};

export function ChatColumn({ isSending, onSend, turns }: Props) {
  return <ChatPanel isSending={isSending} turns={turns} onSend={onSend} />;
}
