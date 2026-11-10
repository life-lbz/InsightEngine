import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { SessionItem, SessionReplay } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { Pagination } from "../../components/admin/Pagination";

export default function ConversationReplayPage() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedSession, setSelectedSession] = useState<string>("");
  const [replay, setReplay] = useState<SessionReplay | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getSessions(page, 20);
      setSessions(data.sessions);
      setTotal(data.total);
    } catch {
      setSessions([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const fetchReplay = useCallback(async (sessionId: string) => {
    setSelectedSession(sessionId);
    setReplayLoading(true);
    try {
      const data = await adminApi.getSessionReplay(sessionId);
      setReplay(data);
    } catch {
      setReplay(null);
    } finally {
      setReplayLoading(false);
    }
  }, []);

  return (
    <div>
      <PageHeader
        title="对话回放"
        subtitle="按会话查看完整对话流、检索过程和反馈"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* 左侧：会话列表 */}
        <div className="lg:col-span-1">
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">会话列表</h3>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {loading ? (
                <div className="flex justify-center py-8">
                  <div className="w-6 h-6 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
                </div>
              ) : sessions.length === 0 ? (
                <div className="text-center py-8 text-gray-400 text-sm">暂无会话</div>
              ) : (
                sessions.map((s) => (
                  <button
                    key={s.session_id}
                    onClick={() => fetchReplay(s.session_id)}
                    className={`w-full text-left px-4 py-2.5 border-b border-gray-50 hover:bg-gray-50 transition ${
                      selectedSession === s.session_id ? "bg-indigo-50" : ""
                    }`}
                  >
                    <div className="text-xs font-mono text-gray-600 truncate">
                      {s.session_id}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {s.message_count} 条消息
                    </div>
                  </button>
                ))
              )}
            </div>
            {total > 20 && (
              <div className="p-2 border-t border-gray-100">
                <Pagination page={page} total={total} pageSize={20} onChange={setPage} />
              </div>
            )}
          </div>
        </div>

        {/* 右侧：回放详情 */}
        <div className="lg:col-span-2">
          {!selectedSession ? (
            <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
              选择左侧会话查看回放
            </div>
          ) : replayLoading ? (
            <div className="flex justify-center py-12">
              <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
            </div>
          ) : replay ? (
            <div className="space-y-4">
              {/* 对话消息 */}
              <div className="bg-white border border-gray-200 rounded-xl p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  对话消息 ({replay.messages.length})
                </h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {replay.messages.map((msg) => {
                    try {
                      const parsed = JSON.parse(msg.message);
                      const role = parsed.role || "unknown";
                      const content = parsed.content || msg.message;
                      return (
                        <div
                          key={msg.id}
                          className={`p-2 rounded-lg text-sm ${
                            role === "user"
                              ? "bg-indigo-50 text-gray-700"
                              : "bg-gray-50 text-gray-600"
                          }`}
                        >
                          <span className="text-xs font-medium text-gray-400 mr-2">
                            {role === "user" ? "用户" : "AI"}
                          </span>
                          {typeof content === "string" ? content.substring(0, 500) : JSON.stringify(content).substring(0, 500)}
                        </div>
                      );
                    } catch {
                      return (
                        <div key={msg.id} className="p-2 rounded-lg text-sm bg-gray-50 text-gray-600">
                          {msg.message.substring(0, 500)}
                        </div>
                      );
                    }
                  })}
                </div>
              </div>

              {/* 检索日志 */}
              {replay.retrieval_logs.length > 0 && (
                <div className="bg-white border border-gray-200 rounded-xl p-4">
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">
                    检索日志 ({replay.retrieval_logs.length})
                  </h3>
                  <div className="space-y-2">
                    {replay.retrieval_logs.map((log) => (
                      <div key={log.id} className="p-2.5 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-3 mb-1">
                          <span className="text-xs text-gray-500">渠道: {log.channel}</span>
                          <span className="text-xs text-gray-500">意图: {log.intent || "-"}</span>
                          <span className="text-xs text-gray-500">命中: {log.hit_count}</span>
                          {log.top_score && (
                            <span className="text-xs text-gray-500">分数: {log.top_score}</span>
                          )}
                          {log.elapsed_ms && (
                            <span className="text-xs text-gray-500">耗时: {log.elapsed_ms}ms</span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">{log.query}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 反馈 */}
              {replay.feedbacks.length > 0 && (
                <div className="bg-white border border-gray-200 rounded-xl p-4">
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">
                    用户反馈 ({replay.feedbacks.length})
                  </h3>
                  <div className="space-y-2">
                    {replay.feedbacks.map((fb) => (
                      <div key={fb.id} className="p-2.5 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            fb.rating === "useful" ? "bg-green-50 text-green-600" : "bg-red-50 text-red-600"
                          }`}>
                            {fb.rating}
                          </span>
                          {fb.comment && (
                            <span className="text-xs text-gray-500">{fb.comment}</span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">Q: {fb.question}</p>
                        <p className="text-sm text-gray-500 mt-1">A: {fb.answer}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400 text-sm">
              无法加载回放数据
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
