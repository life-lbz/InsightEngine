import { useState } from "react";
import type { Source } from "../../types";
import { SourceCard } from "./SourceCard";

interface SourceListProps {
  sources: Source[];
}

export function SourceList({ sources }: SourceListProps) {
  const [expanded, setExpanded] = useState(false);

  const displaySources = expanded ? sources : sources.slice(0, 2);
  const hiddenCount = sources.length - 2;

  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      {/* 标题栏 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition"
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-4 h-4 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
            />
          </svg>
          <span className="text-xs font-medium text-gray-600">
            引用来源（{sources.length} 条）
          </span>
        </div>
        {hiddenCount > 0 && (
          <span className="text-xs text-indigo-500">
            {expanded ? "收起" : `展开全部（+${hiddenCount}）`}
          </span>
        )}
      </button>

      {/* 来源列表 */}
      <div className="divide-y divide-gray-100">
        {displaySources.map((source, index) => (
          <SourceCard key={index} source={source} index={index + 1} />
        ))}
      </div>
    </div>
  );
}