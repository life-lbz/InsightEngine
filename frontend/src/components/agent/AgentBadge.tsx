const AGENT_META: Record<
  string,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  qa_agent: {
    label: "智能答疑",
    color: "text-cyan-700",
    bgColor: "bg-cyan-50 border-cyan-200",
    icon: "M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 3v-3z",
  },
  quiz_agent: {
    label: "出题练习",
    color: "text-violet-700",
    bgColor: "bg-violet-50 border-violet-200",
    icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
  },
  planner_agent: {
    label: "路径规划",
    color: "text-emerald-700",
    bgColor: "bg-emerald-50 border-emerald-200",
    icon: "M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7",
  },
  explain_agent: {
    label: "错题讲解",
    color: "text-orange-700",
    bgColor: "bg-orange-50 border-orange-200",
    icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  },
  teacher_insight_agent: {
    label: "学情分析",
    color: "text-amber-700",
    bgColor: "bg-amber-50 border-amber-200",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  },
  kb_ops_agent: {
    label: "知识库运维",
    color: "text-rose-700",
    bgColor: "bg-rose-50 border-rose-200",
    icon: "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4",
  },
  supervisor: {
    label: "调度中",
    color: "text-indigo-700",
    bgColor: "bg-indigo-50 border-indigo-200",
    icon: "M13 10V3L4 14h7v7l9-11h-7z",
  },
};

interface AgentBadgeProps {
  agentName?: string;
  size?: "sm" | "md";
}

export function AgentBadge({ agentName, size = "sm" }: AgentBadgeProps) {
  const meta = agentName ? AGENT_META[agentName] : null;
  if (!meta) return null;

  const sizeClass =
    size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${meta.bgColor} ${meta.color} ${sizeClass} font-medium`}
    >
      <svg
        className={size === "sm" ? "w-3 h-3" : "w-4 h-4"}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d={meta.icon}
        />
      </svg>
      {meta.label}
    </span>
  );
}
