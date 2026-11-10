import { useEffect, useRef, useState } from "react";
import { useAgentWebSocket } from "../../hooks/useAgentWebSocket";
import { useAgentStore } from "../../stores/agentStore";
import { useAuthStore } from "../../stores/authStore";
import { AgentMessageList } from "../../components/agent/AgentMessageList";
import { AgentStreamingMessage } from "../../components/agent/AgentStreamingMessage";
import { AgentBadge } from "../../components/agent/AgentBadge";
import { CourseSelector } from "../../components/common/CourseSelector";

const QUICK_PROMPTS = [
  { label: "答疑", text: "请解释一下这个知识点", agent: "qa_agent" },
  { label: "出题", text: "给我出 3 道中等难度的练习题", agent: "quiz_agent" },
  { label: "规划", text: "帮我制定一个学习计划", agent: "planner_agent" },
  { label: "讲解", text: "我有一道错题需要讲解", agent: "explain_agent" },
];

export default function AgentChatPage() {
  const {
    connected,
    error: wsError,
    connect,
    sendQuestion,
    stopGeneration,
  } = useAgentWebSocket();

  const {
    messages,
    isStreaming,
    streamingContent,
    streamingStage,
    currentAgentName,
    currentCourseId,
    setCourseId,
    degraded,
  } = useAgentStore();

  const user = useAuthStore((s) => s.user);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 仅在挂载时建立连接；断线后的重连统一由 hook 内部指数退避调度
  useEffect(() => {
    connect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, streamingStage]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    sendQuestion(input.trim());
    setInput("");
  };

  const handleStop = () => {
    stopGeneration();
  };

  const displayMessages =
    isStreaming &&
    messages.length > 0 &&
    messages[messages.length - 1].role === "assistant" &&
    !messages[messages.length - 1].content
      ? messages.slice(0, -1)
      : messages;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-br from-slate-50 to-cyan-50/30">
      {/* 顶部工具栏 */}
      <div className="px-6 py-3 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center">
                <svg
                  className="w-4 h-4 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
              </div>
              <span className="font-semibold text-sm text-gray-800">
                AI 协作助手
              </span>
            </div>
            <CourseSelector
              courseIds={user?.course_ids || []}
              value={currentCourseId}
              onChange={setCourseId}
            />
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                connected ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="text-xs text-gray-500">
              {connected ? "Agent 已连接" : "连接中..."}
            </span>
            {wsError && !connected && (
              <span className="text-xs text-red-500">({wsError})</span>
            )}
          </div>
        </div>
      </div>

      {/* 消息区域 */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {displayMessages.length === 0 ? (
          <WelcomeView onQuickPrompt={(text) => sendQuestion(text)} />
        ) : (
          <>
            <AgentMessageList messages={displayMessages} />
            {isStreaming && (
              <div className="mt-6">
                <AgentStreamingMessage
                  content={streamingContent}
                  stage={streamingStage}
                  agentName={currentAgentName || "supervisor"}
                />
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 快捷入口 */}
      <div className="px-6 py-2 flex gap-2">
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p.label}
            onClick={() => !isStreaming && sendQuestion(p.text)}
            disabled={isStreaming}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-gray-200 text-xs text-gray-600 hover:border-cyan-300 hover:bg-cyan-50/50 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <AgentBadge agentName={p.agent} size="sm" />
            <span>{p.label}</span>
          </button>
        ))}
        {degraded && (
          <span className="px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-xs text-amber-700">
            RAG 回退模式
          </span>
        )}
      </div>

      {/* 输入栏 */}
      <div className="px-6 pb-4">
        <div className="flex items-end gap-2 bg-white rounded-2xl border border-gray-200 shadow-sm px-4 py-2.5">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题，AI 协作助手会自动选择最合适的 Agent 处理..."
            rows={1}
            className="flex-1 resize-none text-sm text-gray-800 placeholder-gray-400 outline-none max-h-32"
            disabled={isStreaming}
          />
          {isStreaming ? (
            <button
              onClick={handleStop}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-red-500 text-white flex items-center justify-center hover:bg-red-600 transition shadow-sm"
              title="停止生成"
            >
              <svg
                className="w-4 h-4"
                fill="currentColor"
                viewBox="0 0 24 24"
              >
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 text-white flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-md transition"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function WelcomeView({
  onQuickPrompt,
}: {
  onQuickPrompt: (text: string) => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-indigo-100 to-cyan-100 rounded-3xl mb-4">
          <svg
            className="w-10 h-10 text-indigo-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-gray-800">AI 协作助手</h2>
        <p className="text-sm text-gray-500 mt-2 max-w-md">
          多 Agent 协作系统会根据你的问题意图，自动路由到最合适的专家 Agent
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 max-w-2xl">
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p.label}
            onClick={() => onQuickPrompt(p.text)}
            className="flex items-start gap-3 p-4 bg-white border border-gray-200 rounded-xl hover:border-cyan-300 hover:shadow-sm transition text-left"
          >
            <AgentBadge agentName={p.agent} size="md" />
            <div>
              <p className="text-sm font-medium text-gray-700 mt-1">{p.label}</p>
              <p className="text-xs text-gray-400 mt-0.5">{p.text}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
