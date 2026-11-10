import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { Course, CourseCreateRequest, KbVersion } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { useToast } from "../../components/common/Toast";
import { useConfirm } from "../../components/common/ConfirmDialog";
import { AppSelect } from "../../components/common/AppSelect";

export default function CourseManagementPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [kbVersions, setKbVersions] = useState<KbVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editCourse, setEditCourse] = useState<Course | null>(null);
  const toast = useToast();
  const confirm = useConfirm();

  const fetchCourses = useCallback(async () => {
    setLoading(true);
    try {
      const [courseData, versionData] = await Promise.all([
        adminApi.getCourses(),
        adminApi.getKbVersions(),
      ]);
      setCourses(courseData.courses);
      setKbVersions(versionData.versions);
    } catch {
      setCourses([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  const handleDelete = async (courseId: string) => {
    if (!courseId || !courseId.trim()) {
      toast.toast("该课程数据异常（缺少课程 ID），无法删除，请先刷新列表", "error");
      return;
    }
    const ok = await confirm.confirm({
      message: "确认删除该课程？删除后课程将不再展示。",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    const result = await adminApi.deleteCourse(courseId);
    if (result.error) {
      toast.toast(`删除失败：${result.error}`, "error");
    } else {
      toast.toast("课程已删除", "success");
    }
    fetchCourses();
  };

  const columns: Column<Course>[] = [
    {
      key: "course_id",
      label: "课程 ID",
      render: (row) => (
        <span className="font-mono text-xs text-gray-600">
          {row.course_id}
        </span>
      ),
    },
    {
      key: "title",
      label: "课程名称",
      render: (row) => (
        <span className="font-medium text-gray-700">{row.title}</span>
      ),
    },
    {
      key: "description",
      label: "描述",
      render: (row) => (
        <span className="text-sm text-gray-500 truncate max-w-xs block">
          {row.description || "-"}
        </span>
      ),
    },
    {
      key: "active_kb_version",
      label: "活跃版本",
      render: (row) => (
        <span className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded">
          {row.active_kb_version}
        </span>
      ),
    },
    {
      key: "created_at",
      label: "创建时间",
      render: (row) => (
        <span className="text-xs text-gray-400">{row.created_at}</span>
      ),
    },
    {
      key: "actions",
      label: "操作",
      render: (row) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setEditCourse(row)}
            className="text-xs text-indigo-500 hover:text-indigo-700 hover:underline"
          >
            编辑
          </button>
          <button
            onClick={() => handleDelete(row.course_id)}
            className="text-xs text-red-500 hover:text-red-700 hover:underline"
          >
            删除
          </button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="课程管理"
        subtitle="管理课程信息与知识库版本绑定"
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCreate(true)}
              className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition"
            >
              新建课程
            </button>
            <button
              onClick={fetchCourses}
              disabled={loading}
              className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition disabled:opacity-50"
            >
              {loading ? "刷新中..." : "刷新"}
            </button>
          </div>
        }
      />

      <DataTable
        columns={columns}
        data={courses}
        rowKey={(r) => r.course_id}
        loading={loading}
        emptyTitle="暂无课程"
        emptyDescription="点击「新建课程」创建第一个课程"
      />

      {(showCreate || editCourse) && (
        <CourseModal
          course={editCourse}
          kbVersions={kbVersions}
          onClose={() => {
            setShowCreate(false);
            setEditCourse(null);
          }}
          onSuccess={() => {
            setShowCreate(false);
            setEditCourse(null);
            fetchCourses();
          }}
        />
      )}
    </div>
  );
}

function CourseModal({
  course,
  kbVersions,
  onClose,
  onSuccess,
}: {
  course: Course | null;
  kbVersions: KbVersion[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form, setForm] = useState<CourseCreateRequest>({
    course_id: course?.course_id || "",
    title: course?.title || "",
    description: course?.description || "",
    active_kb_version: course?.active_kb_version || "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [kbCreateMode, setKbCreateMode] = useState(false);
  const [newKbName, setNewKbName] = useState("");
  const [kbDesc, setKbDesc] = useState("");

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");
    try {
      if (course) {
        const result = await adminApi.updateCourse(course.course_id, {
          title: form.title,
          description: form.description,
          active_kb_version: form.active_kb_version,
        });
        if (result.error) {
          setError(result.error);
          return;
        }
      } else {
        const payload: CourseCreateRequest = kbCreateMode
          ? {
              ...form,
              active_kb_version: "",
              create_kb_version: newKbName.trim(),
              kb_description: kbDesc.trim(),
            }
          : form;
        if (kbCreateMode && !/^[a-zA-Z][a-zA-Z0-9_]{1,63}$/.test(newKbName.trim())) {
          setError("知识库版本名需以字母开头，仅含字母/数字/下划线，长度 2-64，如 kb_grade7_math_v1");
          return;
        }
        const result = await adminApi.createCourse(payload);
        if (result.error) {
          setError(result.error);
          return;
        }
      }
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "操作失败");
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
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {course ? "编辑课程" : "新建课程"}
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              课程 ID
            </label>
            <input
              type="text"
              value={form.course_id}
              disabled={!!course}
              onChange={(e) =>
                setForm({ ...form, course_id: e.target.value })
              }
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:bg-gray-50"
              placeholder="请填写课程 ID"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              课程名称
            </label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              课程描述
            </label>
            <textarea
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
              rows={3}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              活跃知识库版本
            </label>
            <AppSelect
              value={kbCreateMode ? "__create__" : form.active_kb_version}
              onChange={(v) => {
                if (v === "__create__") {
                  setKbCreateMode(true);
                } else {
                  setKbCreateMode(false);
                  setForm({ ...form, active_kb_version: v });
                }
              }}
              className="w-full"
            >
              <option value="">（使用默认版本）</option>
              {(() => {
                const map = new Map<string, KbVersion>();
                kbVersions.forEach((v) => {
                  if (!map.has(v.kb_version)) map.set(v.kb_version, v);
                });
                if (form.active_kb_version && !map.has(form.active_kb_version)) {
                  map.set(form.active_kb_version, {
                    course_id: "",
                    kb_version: form.active_kb_version,
                    version_seq: 0,
                    status: "",
                    description: "",
                    doc_collection: "",
                    faq_collection: "",
                    question_collection: "",
                    created_at: "",
                    updated_at: "",
                  });
                }
                return Array.from(map.values());
              })().map((v) => (
                <option key={v.kb_version} value={v.kb_version}>
                  {v.kb_version}
                  {v.course_id ? `（${v.course_id}）` : ""}
                </option>
              ))}
              {!course && (
                <option value="__create__">＋ 同时创建新知识库版本…</option>
              )}
            </AppSelect>
            {kbCreateMode && (
              <div className="mt-2 space-y-2">
                <input
                  type="text"
                  value={newKbName}
                  onChange={(e) => setNewKbName(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 font-mono"
                  placeholder="知识库版本名，如 kb_grade7_math_v1"
                />
                <input
                  type="text"
                  value={kbDesc}
                  onChange={(e) => setKbDesc(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  placeholder="版本描述（可选），如：七年级数学讲义"
                />
                <p className="text-xs text-gray-400">
                  创建课程时将同时创建并激活版本，映射 Collection：edu_doc_hybrid_{newKbName.trim() || "..."}
                </p>
              </div>
            )}
            <p className="text-xs text-gray-400 mt-1">
              {course
                ? "选择该课程使用的知识库版本，可在「KB 版本管理」页创建"
                : "可绑定已有版本，或选择「同时创建新知识库版本」一步完成"}
            </p>
          </div>
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
            {submitting ? "提交中..." : "确认"}
          </button>
        </div>
      </div>
    </div>
  );
}
