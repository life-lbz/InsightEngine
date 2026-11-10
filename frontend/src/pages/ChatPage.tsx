import { useEffect, useRef, useState } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import { useChatStore } from "../stores/chatStore";
import { useAuthStore } from "../stores/authStore";
import { MessageList } from "../components/chat/MessageList";
import { StreamingMessage } from "../components/chat/StreamingMessage";
import { InputBar } from "../components/chat/InputBar";
import { CourseSelector } from "../components/common/CourseSelector";

export default function ChatPage() {
  const {
    connected,
    error: wsError,
    connect,
    sendQuestion,
  } = useWebSocket();

  const {
    messages,
    isStreaming,
    streamingContent,
    streamingStage,
    currentCourseId,
    setCourseId,
  } = useChatStore();

  const user = useAuthStore((s) => s.user);

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 自动连接 WebSocket
  useEffect(() => {
    if (!connected) {
      connect();
    }
  }, [connected, connect]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, streamingStage]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    sendQuestion(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* 课程选择器 */}
      <div className="px-6 py-3 bg-white border-b border-gray-200">
          <div className="flex items-center gap-4">
            <CourseSelector
              courseIds={user?.course_ids || []}
              value={currentCourseId}
              onChange={setCourseId}
            />
            <div className="flex items-center gap-2">
              <span
                className={`inline-block w-2 h-2 rounded-full ${
                  connected ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span className="text-xs text-gray-500">
                {connected ? "已连接" : "连接中..."}
              </span>
              {wsError && (
                <span className="text-xs text-red-500">（{wsError}）</span>
              )}
            </div>
          </div>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 ? (
            <WelcomeView />
          ) : (
            <>
              <MessageList messages={messages} />
              {/* 流式生成中的消息 */}
              {isStreaming && (
                <StreamingMessage
                  content={streamingContent}
                  stage={streamingStage}
                />
              )}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入栏 */}
        <InputBar
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
        />
    </div>
  );
}

/** 空状态欢迎页 */
function WelcomeView() {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 rounded-2xl mb-4">
          <svg
            className="w-8 h-8 text-indigo-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 3v-3z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-800">
          向 AI 助教提问
        </h2>
        <p className="text-sm text-gray-500 mt-2">
          我可以基于课程讲义、题库和 FAQ 为你答疑
        </p>
      </div>
    </div>
  );
}