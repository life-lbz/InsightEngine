import { useEffect, useState } from "react";
import apiClient from "../../api/client";
import { useAuthStore } from "../../stores/authStore";

interface ChapterMaterial {
  chapter_id: string;
  course_id: string;
  chapter_no: number;
  title: string;
  summary: string;
  point_count: number;
  question_count: number;
  faq_count: number;
}

export default function StudentMaterialsPage() {
  const user = useAuthStore((s) => s.user);
  const [chapters, setChapters] = useState<ChapterMaterial[]>([]);
  const [assigned, setAssigned] = useState(true);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [courseId] = useState(user?.course_ids?.[0] || "");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await apiClient.get("/student/materials", {
          params: { course_id: courseId },
        });
        setChapters(res.data.chapters || []);
        setAssigned(res.data.assigned !== false);
      } catch {
        setChapters([]);
        setAssigned(true);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [courseId]);

  const toggleExpand = (chapterId: string) => {
    setExpandedId(expandedId === chapterId ? null : chapterId);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400 text-sm">加载中...</div>
      </div>
    );
  }

  if (!assigned) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-center">
        <div className="text-5xl mb-4">📚</div>
        <h2 className="text-lg font-semibold text-gray-800 mb-2">尚未分配课程</h2>
        <p className="text-sm text-gray-500 max-w-sm">
          管理员尚未为你分配课程，请联系管理员在用户管理中分配后重新登录查看。
        </p>
      </div>
    );
  }

  const totalPoints = chapters.reduce((sum, ch) => sum + ch.point_count, 0);
  const totalQuestions = chapters.reduce((sum, ch) => sum + ch.question_count, 0);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">课程资料</h1>
        <p className="text-gray-500 mt-1">浏览章节内容、知识点和练习题</p>
      </div>

      {/* Course Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm text-center">
          <div className="text-3xl mb-2">📑</div>
          <p className="text-2xl font-bold text-gray-800">{chapters.length}</p>
          <p className="text-xs text-gray-400 mt-1">章节数</p>
        </div>
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm text-center">
          <div className="text-3xl mb-2">💡</div>
          <p className="text-2xl font-bold text-gray-800">{totalPoints}</p>
          <p className="text-xs text-gray-400 mt-1">知识点</p>
        </div>
        <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm text-center">
          <div className="text-3xl mb-2">✏️</div>
          <p className="text-2xl font-bold text-gray-800">{totalQuestions}</p>
          <p className="text-xs text-gray-400 mt-1">练习题</p>
        </div>
      </div>

      {/* Chapter List */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="font-semibold text-gray-700 mb-4">章节目录</h3>
        {chapters.length > 0 ? (
          <div className="space-y-2">
            {chapters.map((ch) => (
              <div key={ch.chapter_id} className="border border-gray-100 rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleExpand(ch.chapter_id)}
                  className={`w-full flex items-center gap-4 p-4 text-left transition-colors ${
                    expandedId === ch.chapter_id ? "bg-cyan-50" : "hover:bg-gray-50"
                  }`}
                >
                  <span className="w-8 h-8 rounded-full bg-cyan-100 text-cyan-600 flex items-center justify-center text-sm font-bold shrink-0">
                    {ch.chapter_no}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">{ch.title}</p>
                    <p className="text-xs text-gray-400 mt-0.5 truncate">
                      {ch.summary || "暂无简介"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs text-gray-400">
                      {ch.point_count} 知识点 · {ch.question_count} 题
                    </span>
                    <span className={`text-gray-400 text-xs transition-transform ${expandedId === ch.chapter_id ? "rotate-90" : ""}`}>
                      ▶
                    </span>
                  </div>
                </button>
                {expandedId === ch.chapter_id && (
                  <div className="px-4 py-3 bg-gray-50 border-t border-gray-100">
                    <div className="grid grid-cols-3 gap-3">
                      <div className="bg-white rounded-lg p-3 border border-gray-100 text-center">
                        <p className="text-lg font-bold text-cyan-600">{ch.point_count}</p>
                        <p className="text-xs text-gray-400">知识点</p>
                      </div>
                      <div className="bg-white rounded-lg p-3 border border-gray-100 text-center">
                        <p className="text-lg font-bold text-blue-600">{ch.question_count}</p>
                        <p className="text-xs text-gray-400">练习题</p>
                      </div>
                      <div className="bg-white rounded-lg p-3 border border-gray-100 text-center">
                        <p className="text-lg font-bold text-amber-600">{ch.faq_count}</p>
                        <p className="text-xs text-gray-400">FAQ</p>
                      </div>
                    </div>
                    {ch.summary && (
                      <p className="text-sm text-gray-500 mt-3 leading-relaxed">{ch.summary}</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-8 text-center">
            暂无课程资料，请稍后再来查看
          </p>
        )}
      </div>
    </div>
  );
}
