import { useState } from "react";
import type { ChatMessage } from "../../types";
import { SourceList } from "../citations/SourceList";
import { ConfidenceBadge } from "../common/ConfidenceBadge";
import { FeedbackBar } from "../feedback/FeedbackBar";
import { chatApi } from "../../api/chat";
import { useChatStore } from "../../stores/chatStore";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const updateMessage = useChatStore((s) => s.updateMessage);

  const handleFeedback = async (rating: "useful" | "not_useful") => {
    if (feedbackSubmitted) return;

    try {
      await chatApi.submitFeedback({
        session_id: useChatStore.getState().sessionId,
        course_id: useChatStore.getState().currentCourseId,
        question:
          [...useChatStore.getState().messages]
            .reverse()
            .find(
              (m) => m.role === "user" && m.timestamp < message.timestamp
            )?.content || "",
        answer: message.content,
        rating,
        sources: message.sources,
      });

      updateMessage(message.id, { feedback: rating });
      setFeedbackSubmitted(true);
    } catch (err) {
      console.error("Feedback submission failed:", err);
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%] bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-3">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] w-full">
        {/* AI 头像 */}
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center">
            <svg
              className="w-5 h-5 text-indigo-600"
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
          {/* 置信度徽章 */}
          {message.confidence_level && (
            <ConfidenceBadge level={message.confidence_level} />
          )}
          {/* 缓存命中标记 */}
          {message.cache_hit && (
            <span className="text-xs px-2 py-0.5 bg-green-50 text-green-600 rounded-full">
              缓存命中
            </span>
          )}
          {/* 降级标记 */}
          {message.degraded && (
            <span className="text-xs px-2 py-0.5 bg-orange-50 text-orange-600 rounded-full">
              降级响应
            </span>
          )}
        </div>

        {/* 消息内容 */}
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-md px-4 py-3 shadow-sm">
          <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        </div>

        {/* 引用来源 */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3">
            <SourceList sources={message.sources} />
          </div>
        )}

        {/* 反馈栏 */}
        {!feedbackSubmitted && message.content && (
          <div className="mt-2">
            <FeedbackBar
              feedback={message.feedback ?? null}
              onFeedback={handleFeedback}
            />
          </div>
        )}

        {/* Trace ID（调试用） */}
        {message.trace_id && (
          <div className="mt-1">
            <span className="text-xs text-gray-300 font-mono">
              trace: {message.trace_id.slice(0, 8)}...
            </span>
          </div>
        )}
      </div>
    </div>
  );
}