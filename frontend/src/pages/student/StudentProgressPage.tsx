import { useEffect, useState } from "react";
import apiClient from "../../api/client";

interface ProgressItem {
  course_id: string;
  current_chapter_id: string | null;
  mastered_points: string[];
  updated_at: string;
}

interface ProgressData {
  progress: ProgressItem[];
  chat_count: number;
  feedback_count: number;
}

export default function StudentProgressPage() {
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

  const totalMastered = data?.progress.reduce(
    (sum, p) => sum + (p.mastered_points?.length || 0), 0
  ) || 0;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">学习进度</h1>
        <p className="text-gray-500 mt-1">追踪你的学习进展和知识点掌握情况</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm text-center">
          <div className="text-3xl mb-2">💬</div>
          <p className="text-2xl font-bold text-gray-800">{data?.chat_count ?? 0}</p>
          <p className="text-xs text-gray-400 mt-1">总提问数</p>
        </div>
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm text-center">
          <div className="text-3xl mb-2">🎯</div>
          <p className="text-2xl font-bold text-gray-800">{totalMastered}</p>
          <p className="text-xs text-gray-400 mt-1">已掌握知识点</p>
        </div>
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm text-center">
          <div className="text-3xl mb-2">👍</div>
          <p className="text-2xl font-bold text-gray-800">{data?.feedback_count ?? 0}</p>
          <p className="text-xs text-gray-400 mt-1">反馈评价数</p>
        </div>
      </div>

      {/* Course Progress Detail */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="font-semibold text-gray-700 mb-4">课程进度详情</h3>
        {data && data.progress.length > 0 ? (
          <div className="space-y-4">
            {data.progress.map((p, idx) => (
              <div key={idx} className="border border-gray-100 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h4 className="font-medium text-gray-800">{p.course_id}</h4>
                    <p className="text-xs text-gray-400 mt-0.5">
                      更新时间: {p.updated_at || "未知"}
                    </p>
                  </div>
                  <span className="text-sm text-cyan-600 font-medium">
                    {p.mastered_points?.length || 0} 个知识点
                  </span>
                </div>

                <div className="mb-3">
                  <p className="text-xs text-gray-500 mb-1">当前章节</p>
                  <p className="text-sm text-gray-700">
                    {p.current_chapter_id || "尚未开始学习"}
                  </p>
                </div>

                {p.mastered_points && p.mastered_points.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 mb-2">已掌握知识点</p>
                    <div className="flex flex-wrap gap-2">
                      {p.mastered_points.map((point, i) => (
                        <span
                          key={i}
                          className="px-2 py-1 text-xs bg-green-50 text-green-600 rounded-md border border-green-100"
                        >
                          {point}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="mt-3">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-cyan-400 to-cyan-500 rounded-full transition-all"
                        style={{ width: `${Math.min((p.mastered_points?.length || 0) * 10, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500">
                      {Math.min((p.mastered_points?.length || 0) * 10, 100)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-8 text-center">
            暂无学习进度数据，开始提问或练习来积累进度吧
          </p>
        )}
      </div>

      {/* Tips */}
      <div className="bg-cyan-50 border border-cyan-200 rounded-xl p-5">
        <h3 className="font-semibold text-cyan-700 mb-2">学习建议</h3>
        <ul className="text-sm text-cyan-600 space-y-1">
          <li>每天坚持练习 3-5 道题目，巩固知识点</li>
          <li>遇到不懂的问题，随时使用智能答疑提问</li>
          <li>查看课程资料，提前预习章节内容</li>
          <li>对答疑结果进行反馈，帮助系统持续优化</li>
        </ul>
      </div>
    </div>
  );
}
