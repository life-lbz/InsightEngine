import { AgentMessageBubble } from "./AgentMessageBubble";
import type { AgentMessage } from "../../types";

interface AgentMessageListProps {
  messages: AgentMessage[];
}

export function AgentMessageList({ messages }: AgentMessageListProps) {
  return (
    <div className="flex flex-col gap-6">
      {messages.map((msg) => (
        <AgentMessageBubble key={msg.id} message={msg} />
      ))}
    </div>
  );
}
