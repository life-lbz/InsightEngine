interface StreamingMessageProps {
  content: string;
  stage: string;
}

export function StreamingMessage({
  content,
  stage,
}: StreamingMessageProps) {
  const stageText: Record<string, string> = {
    retrieving: "正在检索课程资料...",
    reranking: "正在排序相关内容...",
    generating: "正在生成回答...",
    "": "正在思考...",
  };

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] w-full">
        {/* AI 头像 */}
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center">
            <svg
              className="w-5 h-5 text-indigo-600 animate-pulse"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
          </div>
          <span className="text-xs text-gray-500 font-medium">
            AI 助教
          </span>
        </div>

        {/* 消息内容 */}
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-md px-4 py-3 shadow-sm min-h-[60px]">
          {content ? (
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {content}
              <span className="inline-block w-1.5 h-4 bg-indigo-500 ml-0.5 animate-pulse" />
            </p>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">
                {stageText[stage] || stage || "正在思考..."}
              </span>
              <TypingDots />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** 打字动画圆点 */
function TypingDots() {
  return (
    <div className="flex gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}