import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../../stores/authStore";
import apiClient from "../../api/client";

interface ProgressData {
  progress: {
    course_id: string;
    current_chapter_id: string | null;
    mastered_points: string[];
    updated_at: string;
  }[];
  chat_count: number;
  feedback_count: number;
}

interface QuickAction {
  label: string;
  to: string;
  icon: string;
  desc: string;
  color: string;
}

const quickActions: QuickAction[] = [
  { label: "智能答疑", to: "/student/chat", icon: "💬", desc: "向AI老师提问", color: "bg-cyan-50 text-cyan-600" },
  { label: "练习题库", to: "/student/practice", icon: "✏️", desc: "巩固知识点", color: "bg-blue-50 text-blue-600" },
  { label: "学习进度", to: "/student/progress", icon: "📈", desc: "查看个人进度", color: "bg-green-50 text-green-600" },
  { label: "课程资料", to: "/student/materials", icon: "📚", desc: "浏览学习材料", color: "bg-amber-50 text-amber-600" },
];

export default function StudentDashboard() {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const [data, setData] = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await apiClient.get("/student/progress");
        setData(res.data);
      } catch {
        setData({ progress: [], chat_count: 0, feedback_count: 0 });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400 text-sm">加载中...</div>
      </div>
    );
  }

  const masteredCount = data?.progress.reduce(
    (sum, p) => sum + (p.mastered_points?.length || 0), 0
  ) || 0;

  const statCards = [
    { label: "提问次数", value: data?.chat_count ?? 0, icon: "💬", bg: "bg-cyan-50", color: "text-cyan-600" },
    { label: "掌握知识点", value: masteredCount, icon: "🎯", bg: "bg-green-50", color: "text-green-600" },
    { label: "反馈评价", value: data?.feedback_count ?? 0, icon: "👍", bg: "bg-amber-50", color: "text-amber-600" },
    { label: "学习课程", value: data?.progress.length ?? 0, icon: "📚", bg: "bg-blue-50", color: "text-blue-600" },
  ];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">学习中心</h1>
        <p className="text-gray-500 mt-1">欢迎回来，{user?.user_id}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div key={card.label} className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
            <div className={`w-10 h-10 rounded-lg ${card.bg} flex items-center justify-center text-xl mb-3`}>
              {card.icon}
            </div>
            <p className="text-2xl font-bold text-gray-800">{card.value}</p>
            <p className="text-xs text-gray-400 mt-1">{card.label}</p>
          </div>
        ))}
      </div>

      <div>
        <h3 className="font-semibold text-gray-700 mb-3">快捷入口</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {quickActions.map((action) => (
            <button
              key={action.to}
              onClick={() => navigate(action.to)}
              className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm hover:border-cyan-300 hover:shadow-md transition-all text-center group"
            >
              <div className={`w-12 h-12 rounded-xl ${action.color} flex items-center justify-center text-2xl mb-2 mx-auto group-hover:scale-110 transition-transform`}>
                {action.icon}
              </div>
              <p className="text-sm font-medium text-gray-700">{action.label}</p>
              <p className="text-xs text-gray-400 mt-0.5">{action.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {data && data.progress.length > 0 && (
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <h3 className="font-semibold text-gray-700 mb-3">学习进度概览</h3>
          <div className="space-y-3">
            {data.progress.map((p, idx) => (
              <div key={idx} className="flex items-center gap-4">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-700">{p.course_id}</p>
                  <p className="text-xs text-gray-400">
                    当前章节: {p.current_chapter_id || "未开始"} · 已掌握 {p.mastered_points?.length || 0} 个知识点
                  </p>
                </div>
                <div className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-cyan-400 rounded-full"
                    style={{ width: `${Math.min((p.mastered_points?.length || 0) * 10, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
