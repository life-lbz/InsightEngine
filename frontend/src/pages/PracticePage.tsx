import { useState } from "react";
import { chatApi } from "../api/chat";
import { useAuthStore } from "../stores/authStore";
import { CourseSelector } from "../components/common/CourseSelector";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import type { Question } from "../types";

export default function PracticePage() {
  const user = useAuthStore((s) => s.user);
  const [courseId, setCourseId] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});

  const handleFetch = async () => {
    if (!courseId) {
      setError("请先选择课程");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await chatApi.getPracticeQuestions({
        course_id: courseId,
        count: 5,
      });
      setQuestions(result.questions);
      setAnswers({});
      setRevealed({});
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "获取练习题失败");
    } finally {
      setLoading(false);
    }
  };

  const handleAnswer = (questionId: string, answer: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: answer }));
  };

  const handleReveal = (questionId: string) => {
    setRevealed((prev) => ({ ...prev, [questionId]: true }));
  };

  const difficultyColors: Record<string, string> = {
    easy: "bg-green-50 text-green-600",
    medium: "bg-yellow-50 text-yellow-600",
    hard: "bg-red-50 text-red-600",
  };

  const difficultyLabels: Record<string, string> = {
    easy: "简单",
    medium: "中等",
    hard: "困难",
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-gray-50">
        {/* 顶部控制栏 */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <h1 className="text-lg font-semibold text-gray-900 mb-3">练习题</h1>
          <div className="flex items-center gap-3">
            <CourseSelector
              courseIds={user?.course_ids || []}
              value={courseId}
              onChange={setCourseId}
            />
            <button
              onClick={handleFetch}
              disabled={loading || !courseId}
              className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? (
                <>
                  <LoadingSpinner size="sm" />
                  <span>获取中...</span>
                </>
              ) : (
                <span>获取练习题</span>
              )}
            </button>
          </div>
          {error && (
            <p className="text-sm text-red-500 mt-2">{error}</p>
          )}
        </div>

        {/* 题目列表 */}
        <div className="flex-1 px-6 py-6">
          {questions.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <svg
                className="w-16 h-16 mb-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                />
              </svg>
              <p className="text-sm">选择课程后点击"获取练习题"开始练习</p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-6">
              {questions.map((q, index) => (
                <div
                  key={q.id}
                  className="bg-white border border-gray-200 rounded-xl p-6"
                >
                  {/* 题目头部 */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-400">
                        第 {index + 1} 题
                      </span>
                      <span className="text-xs text-gray-400">
                        {q.knowledge_point}
                      </span>
                    </div>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        difficultyColors[q.difficulty]
                      }`}
                    >
                      {difficultyLabels[q.difficulty]}
                    </span>
                  </div>

                  {/* 题目内容 */}
                  <p className="text-sm text-gray-800 mb-4 leading-relaxed">
                    {q.question}
                  </p>

                  {/* 选项 */}
                  {q.options && q.options.length > 0 ? (
                    <div className="space-y-2 mb-4">
                      {q.options.map((option, optIndex) => {
                        const optionLetter = String.fromCharCode(65 + optIndex);
                        const isSelected = answers[q.id] === optionLetter;
                        const isCorrect =
                          revealed[q.id] && q.answer === optionLetter;
                        const isWrong =
                          revealed[q.id] &&
                          isSelected &&
                          q.answer !== optionLetter;

                        return (
                          <button
                            key={optIndex}
                            onClick={() => handleAnswer(q.id, optionLetter)}
                            disabled={revealed[q.id]}
                            className={`w-full text-left px-3 py-2 rounded-lg border text-sm transition ${
                              isCorrect
                                ? "border-green-300 bg-green-50 text-green-700"
                                : isWrong
                                ? "border-red-300 bg-red-50 text-red-700"
                                : isSelected
                                ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                                : "border-gray-200 hover:border-gray-300"
                            }`}
                          >
                            <span className="font-medium mr-2">
                              {optionLetter}.
                            </span>
                            {option}
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <textarea
                      value={answers[q.id] || ""}
                      onChange={(e) => handleAnswer(q.id, e.target.value)}
                      disabled={revealed[q.id]}
                      placeholder="输入你的答案..."
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition mb-4"
                      rows={3}
                    />
                  )}

                  {/* 操作按钮 */}
                  {!revealed[q.id] ? (
                    <button
                      onClick={() => handleReveal(q.id)}
                      className="text-sm text-indigo-600 hover:text-indigo-700"
                    >
                      查看答案与解析 →
                    </button>
                  ) : (
                    <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                      <p className="text-sm text-gray-700 mb-1">
                        <span className="font-medium">正确答案：</span>
                        {q.answer}
                      </p>
                      {q.explanation && (
                        <p className="text-sm text-gray-600 mt-2 leading-relaxed">
                          <span className="font-medium">解析：</span>
                          {q.explanation}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
    </div>
  );
}