import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { Faq } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { Pagination } from "../../components/admin/Pagination";
import { useToast } from "../../components/common/Toast";
import { useConfirm } from "../../components/common/ConfirmDialog";

export default function FaqManagementPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [faqs, setFaqs] = useState<Faq[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [courseFilter, setCourseFilter] = useState<string | undefined>(undefined);
  const [showCreate, setShowCreate] = useState(false);

  const fetchFaqs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getFaqs(page, 20, courseFilter);
      setFaqs(data.faqs);
      setTotal(data.total);
    } catch {
      setFaqs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, courseFilter]);

  useEffect(() => {
    fetchFaqs();
  }, [fetchFaqs]);

  const handleDelete = async (faqId: string) => {
    const ok = await confirm.confirm({
      message: "确认删除该 FAQ？",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    const result = await adminApi.deleteFaq(faqId);
    if (result.error) {
      toast.toast(`删除失败：${result.error}`, "error");
    } else {
      toast.toast("FAQ 已删除", "success");
    }
    fetchFaqs();
  };

  const columns: Column<Faq>[] = [
    {
      key: "question",
      label: "问题",
      render: (row) => (
        <span className="text-sm text-gray-700 truncate max-w-xs block">
          {row.question}
        </span>
      ),
    },
    {
      key: "answer",
      label: "回答摘要",
      render: (row) => (
        <span className="text-xs text-gray-500 truncate max-w-sm block">
          {row.answer}
        </span>
      ),
    },
    {
      key: "course_id",
      label: "课程",
      render: (row) => (
        <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
          {row.course_id}
        </span>
      ),
    },
    {
      key: "source",
      label: "来源",
      render: (row) => (
        <span className="text-xs text-gray-400">{row.source || "-"}</span>
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
        <button
          onClick={() => handleDelete(row.faq_id)}
          className="text-xs text-red-500 hover:text-red-700 hover:underline"
        >
          删除
        </button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="FAQ 管理"
        subtitle="管理常见问题与回答，支持检索增强"
        actions={
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="按课程筛选"
              value={courseFilter || ""}
              onChange={(e) => {
                setCourseFilter(e.target.value || undefined);
                setPage(1);
              }}
              className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg"
            />
            <button
              onClick={() => setShowCreate(true)}
              className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition"
            >
              新建 FAQ
            </button>
            <button
              onClick={fetchFaqs}
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
        data={faqs}
        rowKey={(r) => r.faq_id}
        loading={loading}
        emptyTitle="暂无 FAQ"
        emptyDescription="点击「新建 FAQ」创建常见问题"
      />
      <Pagination page={page} total={total} pageSize={20} onChange={setPage} />

      {showCreate && (
        <FaqModal
          onClose={() => setShowCreate(false)}
          onSuccess={() => {
            setShowCreate(false);
            fetchFaqs();
          }}
        />
      )}
    </div>
  );
}

function FaqModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form, setForm] = useState({
    course_id: "",
    question: "",
    answer: "",
    source: "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");
    try {
      const result = await adminApi.createFaq(form);
      if (result.error) {
        setError(result.error);
        return;
      }
      onSuccess();
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
        className="bg-white rounded-xl p-6 w-full max-w-lg mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-gray-900 mb-4">新建 FAQ</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              课程 ID
            </label>
            <input
              type="text"
              value={form.course_id}
              onChange={(e) =>
                setForm({ ...form, course_id: e.target.value })
              }
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              问题
            </label>
            <textarea
              value={form.question}
              onChange={(e) =>
                setForm({ ...form, question: e.target.value })
              }
              rows={2}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              回答
            </label>
            <textarea
              value={form.answer}
              onChange={(e) =>
                setForm({ ...form, answer: e.target.value })
              }
              rows={4}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              来源
            </label>
            <input
              type="text"
              value={form.source}
              onChange={(e) =>
                setForm({ ...form, source: e.target.value })
              }
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
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
