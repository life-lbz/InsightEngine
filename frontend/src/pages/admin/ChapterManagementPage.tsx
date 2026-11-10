import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { Chapter, Course } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { useToast } from "../../components/common/Toast";
import { useConfirm } from "../../components/common/ConfirmDialog";
import { AppSelect } from "../../components/common/AppSelect";

export default function ChapterManagementPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editChapter, setEditChapter] = useState<Chapter | null>(null);
  const [formData, setFormData] = useState({ chapter_no: 1, title: "", summary: "" });

  const fetchCourses = useCallback(async () => {
    try {
      const data = await adminApi.getCourses();
      setCourses(data.courses);
      setSelectedCourse((prev) => prev || data.courses[0]?.course_id || "");
    } catch {
      setCourses([]);
    }
  }, []);

  const fetchChapters = useCallback(async () => {
    if (!selectedCourse) {
      setChapters([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await adminApi.getChapters(selectedCourse);
      setChapters(data.chapters);
    } catch {
      setChapters([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCourse]);

  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  useEffect(() => {
    fetchChapters();
  }, [fetchChapters]);

  const handleCreate = async () => {
    const result = await adminApi.createChapter(selectedCourse, formData);
    if (result.chapter_id) {
      setShowForm(false);
      setFormData({ chapter_no: 1, title: "", summary: "" });
      fetchChapters();
      toast.toast("章节已创建", "success");
    } else {
      toast.toast(`创建失败: ${result.error || "未知错误"}`, "error");
    }
  };

  const handleUpdate = async () => {
    if (!editChapter) return;
    const result = await adminApi.updateChapter(editChapter.chapter_id, formData);
    if (result.updated) {
      setShowForm(false);
      setEditChapter(null);
      setFormData({ chapter_no: 1, title: "", summary: "" });
      fetchChapters();
      toast.toast("章节已更新", "success");
    } else {
      toast.toast(`更新失败: ${result.error || "未知错误"}`, "error");
    }
  };

  const handleDelete = async (chapterId: string) => {
    const ok = await confirm.confirm({
      message: "确认删除此章节？",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    const result = await adminApi.deleteChapter(chapterId);
    if (result.error) {
      toast.toast(`删除失败：${result.error}`, "error");
    } else {
      toast.toast("章节已删除", "success");
    }
    fetchChapters();
  };

  const openEdit = (chapter: Chapter) => {
    setEditChapter(chapter);
    setFormData({
      chapter_no: chapter.chapter_no,
      title: chapter.title,
      summary: chapter.summary,
    });
    setShowForm(true);
  };

  const columns: Column<Chapter>[] = [
    {
      key: "chapter_no",
      label: "序号",
      render: (row) => (
        <span className="text-sm font-mono text-gray-500">{row.chapter_no}</span>
      ),
    },
    {
      key: "title",
      label: "标题",
      render: (row) => (
        <span className="text-sm font-medium text-gray-700">{row.title}</span>
      ),
    },
    {
      key: "summary",
      label: "摘要",
      render: (row) => (
        <span className="text-sm text-gray-500 truncate max-w-md block">
          {row.summary || "-"}
        </span>
      ),
    },
    {
      key: "updated_at",
      label: "更新时间",
      render: (row) => (
        <span className="text-xs text-gray-400">
          {row.updated_at ? new Date(row.updated_at).toLocaleString("zh-CN") : "-"}
        </span>
      ),
    },
    {
      key: "actions",
      label: "操作",
      render: (row) => (
        <div className="flex gap-2">
          <button
            onClick={() => openEdit(row)}
            className="text-xs px-2 py-1 text-indigo-600 border border-indigo-200 rounded hover:bg-indigo-50"
          >
            编辑
          </button>
          <button
            onClick={() => handleDelete(row.chapter_id)}
            className="text-xs px-2 py-1 text-red-600 border border-red-200 rounded hover:bg-red-50"
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
        title="章节管理"
        subtitle="课程章节的增删改查"
        actions={
          <div className="flex items-center gap-2">
            <AppSelect
              value={selectedCourse}
              onChange={(v) => setSelectedCourse(v)}
              options={[
                { value: "", label: "选择课程" },
                ...courses.map((c) => ({ value: c.course_id, label: c.title })),
              ]}
            />
            <button
              onClick={() => {
                setEditChapter(null);
                setFormData({ chapter_no: chapters.length + 1, title: "", summary: "" });
                setShowForm(true);
              }}
              disabled={!selectedCourse}
              className="px-3 py-1.5 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              新建章节
            </button>
          </div>
        }
      />

      {showForm && (
        <div className="mb-4 p-5 bg-white border border-gray-200 rounded-xl">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            {editChapter ? "编辑章节" : "新建章节"}
          </h3>
          <div className="grid grid-cols-1 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">章节序号</label>
              <input
                type="number"
                value={formData.chapter_no}
                onChange={(e) => setFormData({ ...formData, chapter_no: parseInt(e.target.value) || 1 })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">标题</label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">摘要</label>
              <textarea
                value={formData.summary}
                onChange={(e) => setFormData({ ...formData, summary: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => editChapter ? handleUpdate() : handleCreate()}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
              >
                {editChapter ? "保存" : "创建"}
              </button>
              <button
                onClick={() => { setShowForm(false); setEditChapter(null); }}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      ) : (
        <DataTable columns={columns} data={chapters} />
      )}
    </div>
  );
}
