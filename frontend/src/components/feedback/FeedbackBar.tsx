interface FeedbackBarProps {
  feedback: "useful" | "not_useful" | null;
  onFeedback: (rating: "useful" | "not_useful") => void;
}

export function FeedbackBar({ feedback, onFeedback }: FeedbackBarProps) {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => onFeedback("useful")}
        className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition ${
          feedback === "useful"
            ? "bg-green-50 text-green-600"
            : "text-gray-400 hover:bg-gray-50 hover:text-gray-600"
        }`}
        title="这个回答有帮助"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"
          />
        </svg>
        <span>有帮助</span>
      </button>

      <button
        onClick={() => onFeedback("not_useful")}
        className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition ${
          feedback === "not_useful"
            ? "bg-red-50 text-red-600"
            : "text-gray-400 hover:bg-gray-50 hover:text-gray-600"
        }`}
        title="这个回答没帮助"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.737 3h4.017c.163 0 .326.02.485.06L17 4m-7 10v5a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10H5a2 2 0 00-2 2v6a2 2 0 002 2h2.5"
          />
        </svg>
        <span>没帮助</span>
      </button>
    </div>
  );
}