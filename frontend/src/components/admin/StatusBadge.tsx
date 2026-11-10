interface StatusBadgeProps {
  status: string;
}

const statusConfig: Record<string, { bg: string; text: string; dot: string }> = {
  completed: { bg: "bg-green-50", text: "text-green-700", dot: "bg-green-500" },
  pending: { bg: "bg-gray-100", text: "text-gray-600", dot: "bg-gray-400" },
  processing: { bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-500" },
  running: { bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-500" },
  failed: { bg: "bg-red-50", text: "text-red-700", dot: "bg-red-500" },
  healthy: { bg: "bg-green-50", text: "text-green-700", dot: "bg-green-500" },
  degraded: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500" },
  built: { bg: "bg-green-50", text: "text-green-700", dot: "bg-green-500" },
  not_found: { bg: "bg-red-50", text: "text-red-700", dot: "bg-red-500" },
  none: { bg: "bg-gray-100", text: "text-gray-600", dot: "bg-gray-400" },
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] || {
    bg: "bg-gray-100",
    text: "text-gray-600",
    dot: "bg-gray-400",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {status}
    </span>
  );
}
