import { AgentBadge } from "./AgentBadge";
import { FallbackNotice } from "./FallbackNotice";
import { SourceList } from "../citations/SourceList";
import type { AgentMessage } from "../../types";

interface AgentMessageBubbleProps {
  message: AgentMessage;
}

export function AgentMessageBubble({ message }: AgentMessageBubbleProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-cyan-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2.5">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-cyan-400 flex items-center justify-center text-white text-sm font-bold shrink-0">
        AI
      </div>
      <div className="flex-1 max-w-[85%] bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3">
        {message.agent_name && (
          <div className="mb-1.5">
            <AgentBadge agentName={message.agent_name} />
          </div>
        )}
        {message.degraded && (
          <div className="mb-1.5">
            <FallbackNotice />
          </div>
        )}
        <p className="text-sm text-gray-800 whitespace-pre-wrap">
          {message.content}
        </p>
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <SourceList sources={message.sources} />
          </div>
        )}
      </div>
    </div>
  );
}
