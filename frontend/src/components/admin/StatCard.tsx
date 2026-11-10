interface StatCardProps {
  label: string;
  value: string | number;
  hint?: string;
  accent?: "indigo" | "green" | "amber" | "red" | "gray" | "cyan";
}

const accentMap: Record<NonNullable<StatCardProps["accent"]>, string> = {
  indigo: "text-indigo-600",
  green: "text-green-600",
  amber: "text-amber-600",
  red: "text-red-600",
  gray: "text-gray-600",
  cyan: "text-cyan-600",
};

export function StatCard({ label, value, hint, accent = "indigo" }: StatCardProps) {
  return (
    <div className="p-4 bg-white border border-gray-200 rounded-xl">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
        {label}
      </p>
      <p className={`mt-2 text-2xl font-bold ${accentMap[accent]}`}>
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-gray-400">{hint}</p>}
    </div>
  );
}
