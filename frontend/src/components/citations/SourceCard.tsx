import type { Source } from "../../types";

interface SourceCardProps {
  source: Source;
  index: number;
}

export function SourceCard({ source, index }: SourceCardProps) {
  const fileName = source.metadata.source || "未知来源";
  const docType = source.metadata.doc_type || "未知";
  const scorePercent = Math.round((source.score || 0) * 100);

  const docTypeLabels: Record<string, string> = {
    lecture: "讲义",
    question: "题库",
    faq: "FAQ",
    syllabus: "大纲",
  };

  return (
    <div className="px-3 py-2.5 hover:bg-gray-50 transition">
      <div className="flex items-start gap-2">
        {/* 序号 */}
        <span className="flex-shrink-0 w-5 h-5 bg-indigo-100 text-indigo-600 text-xs font-medium rounded-full flex items-center justify-center">
          {index}
        </span>

        <div className="flex-1 min-w-0">
          {/* 来源信息 */}
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-gray-500 truncate">
              {fileName}
            </span>
            <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
              {docTypeLabels[docType] || docType}
            </span>
            {source.metadata.page && (
              <span className="text-xs text-gray-400">
                P{source.metadata.page}
              </span>
            )}
          </div>

          {/* 内容摘要 */}
          <p className="text-xs text-gray-600 line-clamp-2 leading-relaxed">
            {source.content}
          </p>

          {/* 相关度 */}
          <div className="flex items-center gap-1 mt-1">
            <div className="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-400 rounded-full"
                style={{ width: `${scorePercent}%` }}
              />
            </div>
            <span className="text-xs text-gray-400 font-mono">
              {scorePercent}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}