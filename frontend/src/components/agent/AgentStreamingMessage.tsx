import { AgentThinkingIndicator } from "./AgentThinkingIndicator";

interface AgentStreamingMessageProps {
  content: string;
  stage: string;
  agentName?: string;
}

export function AgentStreamingMessage({
  content,
  stage,
}: AgentStreamingMessageProps) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-cyan-400 flex items-center justify-center text-white text-sm font-bold shrink-0">
        AI
      </div>
      <div className="flex-1 max-w-[85%] bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 min-h-[3rem]">
        {content ? (
          <p className="text-sm text-gray-800 whitespace-pre-wrap">{content}</p>
        ) : (
          <AgentThinkingIndicator stage={stage} />
        )}
      </div>
    </div>
  );
}
