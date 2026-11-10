import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { QuestionBankItem, Course } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { Pagination } from "../../components/admin/Pagination";
import { useToast } from "../../components/common/Toast";
import { useConfirm } from "../../components/common/ConfirmDialog";
import { AppSelect } from "../../components/common/AppSelect";

export default function QuestionBankPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [questions, setQuestions] = useState<QuestionBankItem[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedCourse, setSelectedCourse] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editQuestion, setEditQuestion] = useState<QuestionBankItem | null>(null);
  const [formData, setFormData] = useState({
    course_id: "",
    chapter_id: "",
    question_type: "single_choice",
    difficulty: "medium",
    question_text: "",
    answer: "",
    explanation: "",
    source: "",
  });

  const fetchCourses = useCallback(async () => {
    try {
      const data = await adminApi.getCourses();
      setCourses(data.courses);
    } catch {
      setCourses([]);
    }
  }, []);

  const fetchQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getQuestions(selectedCourse || undefined, page, 20);
      setQuestions(data.questions);
      setTotal(data.total);
    } catch {
      setQuestions([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, selectedCourse]);

  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  useEffect(() => {
    fetchQuestions();
  }, [fetchQuestions]);

  const handleCreate = async () => {
    const result = await adminApi.createQuestion(formData);
    if (result.question_id) {
      setShowForm(false);
      setFormData({ course_id: "", chapter_id: "", question_type: "single_choice", difficulty: "medium", question_text: "", answer: "", explanation: "", source: "" });
      fetchQuestions();
      toast.toast("题目已创建", "success");
    } else {
      toast.toast(`创建失败: ${result.error || "未知错误"}`, "error");
    }
  };

  const handleDelete = async (questionId: string) => {
    const ok = await confirm.confirm({
      message: "确认删除此题目？",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    const result = await adminApi.deleteQuestion(questionId);
    if (result.error) {
      toast.toast(`删除失败：${result.error}`, "error");
    } else {
      toast.toast("题目已删除", "success");
    }
    fetchQuestions();
  };

  const openEdit = (q: QuestionBankItem) => {
    setEditQuestion(q);
    setFormData({
      course_id: q.course_id,
      chapter_id: q.chapter_id || "",
      question_type: q.question_type,
      difficulty: q.difficulty,
      question_text: q.question_text,
      answer: q.answer,
      explanation: q.explanation,
      source: q.source || "",
    });
    setShowForm(true);
  };

  const handleUpdate = async () => {
    if (!editQuestion) return;
    const result = await adminApi.updateQuestion(editQuestion.question_id, formData);
    if (result.updated) {
      setShowForm(false);
      setEditQuestion(null);
      fetchQuestions();
      toast.toast("题目已更新", "success");
    } else {
      toast.toast(`更新失败: ${result.error || "未知错误"}`, "error");
    }
  };

  const difficultyColors: Record<string, string> = {
    easy: "bg-green-50 text-green-600",
    medium: "bg-amber-50 text-amber-600",
    hard: "bg-red-50 text-red-600",
  };

  const columns: Column<QuestionBankItem>[] = [
    {
      key: "question_text",
      label: "题目内容",
      render: (row) => (
        <span className="text-sm text-gray-700 truncate max-w-md block">
          {row.question_text}
        </span>
      ),
    },
    {
      key: "course_id",
      label: "课程",
      render: (row) => (
        <span className="text-sm text-gray-500">{row.course_id}</span>
      ),
    },
    {
      key: "question_type",
      label: "类型",
      render: (row) => (
        <span className="text-xs px-2 py-0.5 bg-gray-50 text-gray-600 rounded">
          {row.question_type}
        </span>
      ),
    },
    {
      key: "difficulty",
      label: "难度",
      render: (row) => (
        <span className={`text-xs px-2 py-0.5 rounded ${difficultyColors[row.difficulty] || "bg-gray-50 text-gray-500"}`}>
          {row.difficulty}
        </span>
      ),
    },
    {
      key: "answer",
      label: "答案",
      render: (row) => (
        <span className="text-sm text-gray-500 truncate max-w-xs block">
          {row.answer || "-"}
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
            onClick={() => handleDelete(row.question_id)}
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
        title="题库管理"
        subtitle="题目的增删改查"
        actions={
          <div className="flex items-center gap-2">
            <AppSelect
              value={selectedCourse}
              onChange={(v) => { setSelectedCourse(v); setPage(1); }}
              options={[
                { value: "", label: "全部课程" },
                ...courses.map((c) => ({ value: c.course_id, label: c.title })),
              ]}
            />
            <button
              onClick={() => {
                setEditQuestion(null);
                setFormData({ course_id: selectedCourse, chapter_id: "", question_type: "single_choice", difficulty: "medium", question_text: "", answer: "", explanation: "", source: "" });
                setShowForm(true);
              }}
              className="px-3 py-1.5 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
            >
              新建题目
            </button>
          </div>
        }
      />

      {showForm && (
        <div className="mb-4 p-5 bg-white border border-gray-200 rounded-xl">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            {editQuestion ? "编辑题目" : "新建题目"}
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">课程</label>
              <AppSelect
                value={formData.course_id}
                onChange={(v) => setFormData({ ...formData, course_id: v })}
                className="w-full"
              >
                <option value="">选择课程</option>
                {courses.map((c) => (
                  <option key={c.course_id} value={c.course_id}>{c.title}</option>
                ))}
              </AppSelect>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">章节ID</label>
              <input
                type="text"
                value={formData.chapter_id}
                onChange={(e) => setFormData({ ...formData, chapter_id: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
                placeholder="可选"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">题目类型</label>
              <AppSelect
                value={formData.question_type}
                onChange={(v) => setFormData({ ...formData, question_type: v })}
                className="w-full"
              >
                <option value="single_choice">单选</option>
                <option value="multiple_choice">多选</option>
                <option value="true_false">判断</option>
                <option value="short_answer">简答</option>
              </AppSelect>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">难度</label>
              <AppSelect
                value={formData.difficulty}
                onChange={(v) => setFormData({ ...formData, difficulty: v })}
                className="w-full"
              >
                <option value="easy">简单</option>
                <option value="medium">中等</option>
                <option value="hard">困难</option>
              </AppSelect>
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">题目内容</label>
              <textarea
                value={formData.question_text}
                onChange={(e) => setFormData({ ...formData, question_text: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">答案</label>
              <input
                type="text"
                value={formData.answer}
                onChange={(e) => setFormData({ ...formData, answer: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">来源</label>
              <input
                type="text"
                value={formData.source}
                onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">解析</label>
              <textarea
                value={formData.explanation}
                onChange={(e) => setFormData({ ...formData, explanation: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
              />
            </div>
            <div className="col-span-2 flex gap-2">
              <button
                onClick={() => editQuestion ? handleUpdate() : handleCreate()}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
              >
                {editQuestion ? "保存" : "创建"}
              </button>
              <button
                onClick={() => { setShowForm(false); setEditQuestion(null); }}
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
        <>
          <DataTable columns={columns} data={questions} />
          <Pagination page={page} total={total} pageSize={20} onChange={setPage} />
        </>
      )}
    </div>
  );
}
