interface ConfidenceBadgeProps {
  level: "high" | "medium" | "low";
  score?: number;
}

export function ConfidenceBadge({ level, score }: ConfidenceBadgeProps) {
  const config = {
    high: {
      label: "高置信度",
      classes: "bg-green-50 text-green-700 border-green-200",
    },
    medium: {
      label: "中置信度",
      classes: "bg-yellow-50 text-yellow-700 border-yellow-200",
    },
    low: {
      label: "低置信度",
      classes: "bg-red-50 text-red-700 border-red-200",
    },
  };

  const { label, classes } = config[level];

  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full border ${classes}`}
      title={score ? `置信度: ${(score * 100).toFixed(1)}%` : label}
    >
      {label}
      {score && ` ${(score * 100).toFixed(0)}%`}
    </span>
  );
}