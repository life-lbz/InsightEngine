interface AgentThinkingIndicatorProps {
  stage: string;
  agentName?: string;
}

const STAGE_LABELS: Record<string, string> = {
  ready: "Agent 协作已连接",
  thinking: "Agent 正在思考...",
  retrieving: "正在检索知识库...",
  reranking: "正在重排序结果...",
  generating: "正在生成回答...",
  fallback: "回退至 RAG 模式",
};

export function AgentThinkingIndicator({
  stage,
}: AgentThinkingIndicatorProps) {
  const label = STAGE_LABELS[stage] || stage;

  return (
    <div className="flex items-center gap-1.5 px-4 py-3">
      <span className="text-sm text-gray-500">{label}</span>
      <div className="flex gap-0.5">
        <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
        <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
        <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" />
      </div>
    </div>
  );
}
