import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { chatApi } from "../../api/chat";
import { useChatStore } from "../../stores/chatStore";
import type { ChatMessage } from "../../types";
import { LoadingSpinner } from "../../components/common/LoadingSpinner";

interface SessionItem {
  session_id: string;
  message_count: number;
  preview: string;
  role: string;
}

export default function StudentHistoryPage() {
  const navigate = useNavigate();
  const setSessionId = useChatStore((s) => s.setSessionId);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ChatMessage[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await chatApi.getSessions();
      setSessions(data.sessions);
    } catch {
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const toggleDetail = async (sessionId: string) => {
    if (expandedId === sessionId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(sessionId);
    setDetailLoading(true);
    try {
      const data = await chatApi.getHistory(sessionId, 30);
      setDetail(data.messages);
    } catch {
      setDetail([]);
    } finally {
      setDetailLoading(false);
    }
  };

  const continueChat = (sessionId: string) => {
    setSessionId(sessionId);
    navigate("/student/chat");
  };

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">聊天历史</h1>
        <p className="text-gray-500 mt-1">回顾与 AI 答疑的历史对话，可继续提问</p>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <LoadingSpinner size="lg" />
        </div>
      ) : sessions.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-100">
          <div className="text-4xl mb-3">💬</div>
          <p className="text-gray-500 text-sm">暂无历史对话</p>
          <button
            onClick={() => navigate("/student/chat")}
            className="mt-4 px-4 py-2 text-sm font-medium text-white bg-cyan-600 rounded-lg hover:bg-cyan-700 transition"
          >
            去 AI 答疑提问
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => (
            <div
              key={s.session_id}
              className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden"
            >
              <button
                onClick={() => toggleDetail(s.session_id)}
                className="w-full flex items-center gap-3 p-4 text-left hover:bg-gray-50/60 transition"
              >
                <div className="w-9 h-9 rounded-full bg-cyan-100 text-cyan-600 flex items-center justify-center text-base shrink-0">
                  💬
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 truncate">
                    {s.preview || "（空会话）"}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {s.message_count} 条消息 · {s.role === "user" ? "最后提问" : "最后回答"}
                  </p>
                </div>
                <span className="text-xs text-gray-400 shrink-0">
                  {expandedId === s.session_id ? "收起 ▴" : "查看 ▾"}
                </span>
              </button>

              {expandedId === s.session_id && (
                <div className="border-t border-gray-100 p-4 space-y-3 bg-gray-50/40">
                  {detailLoading ? (
                    <div className="flex justify-center py-6">
                      <LoadingSpinner size="md" />
                    </div>
                  ) : detail.length === 0 ? (
                    <p className="text-sm text-gray-400 text-center py-4">
                      该会话暂无消息记录
                    </p>
                  ) : (
                    detail.map((m) => (
                      <div
                        key={m.id}
                        className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                      >
                        <div
                          className={`max-w-[85%] px-3 py-2 rounded-xl text-sm whitespace-pre-wrap ${
                            m.role === "user"
                              ? "bg-cyan-600 text-white rounded-br-md"
                              : "bg-white border border-gray-200 text-gray-700 rounded-bl-md"
                          }`}
                        >
                          <p className="text-xs opacity-60 mb-1">
                            {m.role === "user" ? "我" : "AI 助手"}
                          </p>
                          {m.content || "（空）"}
                        </div>
                      </div>
                    ))
                  )}
                  <div className="flex justify-end pt-2">
                    <button
                      onClick={() => continueChat(s.session_id)}
                      className="px-3 py-1.5 text-xs font-medium text-cyan-700 border border-cyan-200 rounded-lg hover:bg-cyan-50 transition"
                    >
                      继续提问 →
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
