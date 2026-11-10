import { useState } from "react";
import { adminApi } from "../../api/admin";
import type { Course } from "../../types";
import { AppSelect } from "../common/AppSelect";

export function KbVersionCreateModal({
  courses,
  defaultCourseId,
  onClose,
  onSuccess,
}: {
  courses: Course[];
  defaultCourseId?: string;
  onClose: () => void;
  onSuccess: (created: { kb_version: string; course_id: string }) => void;
}) {
  const [courseId, setCourseId] = useState(defaultCourseId || courses[0]?.course_id || "");
  const [kbVersion, setKbVersion] = useState("");
  const [description, setDescription] = useState("");
  const [activate, setActivate] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!courseId) {
      setError("请选择所属课程");
      return;
    }
    const name = kbVersion.trim();
    if (!/^[a-zA-Z][a-zA-Z0-9_]{1,63}$/.test(name)) {
      setError("版本名需以字母开头，仅含字母/数字/下划线，长度 2-64，如 kb_grade7_math_v1");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const result = await adminApi.createKbVersion({
        course_id: courseId,
        kb_version: name,
        description: description.trim(),
        activate,
      });
      if (result.created) {
        onSuccess({ kb_version: name, course_id: courseId });
      } else {
        setError(result.detail || result.error || "创建失败");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl p-6 w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-gray-900 mb-1">新建知识库版本</h3>
        <p className="text-xs text-gray-400 mb-4">
          每个版本对应独立的向量 Collection（doc/faq/question），实现不同课程、年级文档的隔离
        </p>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              所属课程
            </label>
            <AppSelect
              value={courseId}
              onChange={(v) => setCourseId(v)}
              className="w-full"
            >
              {courses.length === 0 && <option value="">暂无课程，请先创建课程</option>}
              {courses.map((c) => (
                <option key={c.course_id} value={c.course_id}>
                  {c.title || c.course_id}
                </option>
              ))}
            </AppSelect>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              知识库版本名（自定义知识库名）
            </label>
            <input
              type="text"
              value={kbVersion}
              onChange={(e) => setKbVersion(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 font-mono"
              placeholder="如 kb_grade7_math_v1"
            />
            <p className="text-xs text-gray-400 mt-1">
              将映射为 Collection：edu_doc_hybrid_{kbVersion || "..."}
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              描述
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
              placeholder="如：初一数学上册讲义"
            />
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={activate}
              onChange={(e) => setActivate(e.target.checked)}
              className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-300"
            />
            <span className="text-sm text-gray-600">创建后立即激活（作为该课程当前知识库）</span>
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? "创建中..." : "创建版本"}
          </button>
        </div>
      </div>
    </div>
  );
}
