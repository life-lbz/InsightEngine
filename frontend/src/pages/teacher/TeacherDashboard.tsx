import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../../stores/authStore";
import { adminApi } from "../../api/admin";
import type { DashboardStats, FeedbackStats } from "../../types";

interface QuickAction {
  label: string;
  to: string;
  icon: string;
  desc: string;
}

const quickActions: QuickAction[] = [
  { label: "课程管理", to: "/teacher/courses", icon: "📚", desc: "管理课程内容" },
  { label: "章节管理", to: "/teacher/chapters", icon: "📑", desc: "编辑章节结构" },
  { label: "题库管理", to: "/teacher/questions", icon: "✏️", desc: "维护练习题" },
  { label: "FAQ管理", to: "/teacher/faqs", icon: "💬", desc: "常见问题维护" },
  { label: "学员进度", to: "/teacher/students", icon: "📈", desc: "查看学习情况" },
  { label: "对话回放", to: "/teacher/sessions", icon: "🔄", desc: "回放答疑对话" },
  { label: "反馈查看", to: "/teacher/feedbacks", icon: "👎", desc: "学员反馈分析" },
];

export default function TeacherDashboard() {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [dashRes, fbRes] = await Promise.allSettled([
          adminApi.getDashboardStats(),
          adminApi.getFeedbackStats(),
        ]);
        if (dashRes.status === "fulfilled") setStats(dashRes.value);
        if (fbRes.status === "fulfilled") setFeedbackStats(fbRes.value);
      } catch (err) {
        setError("数据加载失败");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const statCards = [
    {
      label: "总查询数",
      value: stats?.total_queries ?? 0,
      icon: "🔍",
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      label: "用户反馈",
      value: stats?.total_feedback ?? 0,
      icon: "💬",
      color: "text-amber-600",
      bg: "bg-amber-50",
    },
    {
      label: "活跃用户",
      value: stats?.total_users ?? 0,
      icon: "👥",
      color: "text-green-600",
      bg: "bg-green-50",
    },
    {
      label: "平均命中率",
      value: stats ? `${(stats.avg_hit_count * 100).toFixed(1)}%` : "0%",
      icon: "🎯",
      color: "text-purple-600",
      bg: "bg-purple-50",
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400 text-sm">加载中...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">教师工作台</h1>
        <p className="text-gray-500 mt-1">欢迎回来，{user?.user_id}</p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm"
          >
            <div className={`w-10 h-10 rounded-lg ${card.bg} flex items-center justify-center text-xl mb-3`}>
              {card.icon}
            </div>
            <p className="text-2xl font-bold text-gray-800">{card.value}</p>
            <p className="text-xs text-gray-400 mt-1">{card.label}</p>
          </div>
        ))}
      </div>

      {/* Two columns: Trend + Feedback */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Query Trend */}
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-700">查询趋势</h3>
            <span className="text-xs text-gray-400">近7天</span>
          </div>
          {stats && stats.query_trend.length > 0 ? (
            <div className="space-y-2">
              {stats.query_trend.slice(-7).map((item, idx) => {
                const maxCount = Math.max(...stats.query_trend.map((t) => t.count), 1);
                const widthPercent = (item.count / maxCount) * 100;
                return (
                  <div key={idx} className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 w-20 shrink-0">
                      {item.date.slice(5)}
                    </span>
                    <div className="flex-1 h-6 bg-gray-50 rounded relative overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-amber-400 to-amber-500 rounded transition-all"
                        style={{ width: `${widthPercent}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium text-gray-600 w-8 text-right">
                      {item.count}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-gray-400 py-8 text-center">暂无查询数据</p>
          )}
        </div>

        {/* Feedback Overview */}
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-700">反馈概览</h3>
            <button
              onClick={() => navigate("/teacher/feedbacks")}
              className="text-xs text-amber-600 hover:underline"
            >
              查看详情 →
            </button>
          </div>
          {feedbackStats ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">总反馈数</span>
                <span className="text-lg font-bold text-gray-800">
                  {feedbackStats.total}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-green-600">有用反馈</span>
                <span className="text-sm font-medium text-green-600">
                  {feedbackStats.useful} ({(feedbackStats.useful_rate * 100).toFixed(1)}%)
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-red-500">无用反馈</span>
                <span className="text-sm font-medium text-red-500">
                  {feedbackStats.not_useful}
                </span>
              </div>
              {/* Progress bar */}
              <div className="h-2 rounded-full bg-gray-100 overflow-hidden flex">
                <div
                  className="h-full bg-green-400"
                  style={{
                    width: `${feedbackStats.total > 0 ? (feedbackStats.useful / feedbackStats.total) * 100 : 0}%`,
                  }}
                />
                <div
                  className="h-full bg-red-300"
                  style={{
                    width: `${feedbackStats.total > 0 ? (feedbackStats.not_useful / feedbackStats.total) * 100 : 0}%`,
                  }}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400 py-8 text-center">暂无反馈数据</p>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h3 className="font-semibold text-gray-700 mb-3">快捷入口</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {quickActions.map((action) => (
            <button
              key={action.to}
              onClick={() => navigate(action.to)}
              className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm hover:border-amber-300 hover:shadow-md transition-all text-center group"
            >
              <div className="text-2xl mb-2 group-hover:scale-110 transition-transform">
                {action.icon}
              </div>
              <p className="text-sm font-medium text-gray-700">{action.label}</p>
              <p className="text-xs text-gray-400 mt-0.5">{action.desc}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
