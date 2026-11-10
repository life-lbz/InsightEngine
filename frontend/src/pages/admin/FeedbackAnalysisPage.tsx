import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { Feedback, FeedbackStats } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { AppSelect } from "../../components/common/AppSelect";
import { StatCard } from "../../components/admin/StatCard";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { Pagination } from "../../components/admin/Pagination";

export default function FeedbackAnalysisPage() {
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [ratingFilter, setRatingFilter] = useState<string | undefined>(undefined);

  const fetchFeedbacks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getFeedbacks(page, 20, ratingFilter);
      setFeedbacks(data.feedbacks);
      setTotal(data.total);
    } catch {
      setFeedbacks([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, ratingFilter]);

  const fetchStats = useCallback(async () => {
    try {
      const data = await adminApi.getFeedbackStats();
      setStats(data);
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    fetchFeedbacks();
    fetchStats();
  }, [fetchFeedbacks, fetchStats]);

  const columns: Column<Feedback>[] = [
    {
      key: "question",
      label: "问题",
      render: (row) => (
        <span className="text-sm text-gray-700 truncate max-w-sm block">
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
      key: "rating",
      label: "评价",
      render: (row) => (
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
            row.rating === "useful"
              ? "bg-green-50 text-green-700"
              : "bg-red-50 text-red-700"
          }`}
        >
          {row.rating === "useful" ? "有用" : "无用"}
        </span>
      ),
    },
    {
      key: "comment",
      label: "评论",
      render: (row) => (
        <span className="text-xs text-gray-500 truncate max-w-xs block">
          {row.comment || "-"}
        </span>
      ),
    },
    {
      key: "course_id",
      label: "课程",
      render: (row) => (
        <span className="text-xs text-gray-400">{row.course_id}</span>
      ),
    },
    {
      key: "created_at",
      label: "时间",
      render: (row) => (
        <span className="text-xs text-gray-400">{row.created_at}</span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="用户反馈分析"
        subtitle="收集学员对答疑质量的评价，发现改进方向"
        actions={
          <div className="flex items-center gap-2">
            <AppSelect
              value={ratingFilter || ""}
              onChange={(v) => {
                setRatingFilter(v || undefined);
                setPage(1);
              }}
              options={[
                { value: "", label: "全部评价" },
                { value: "useful", label: "有用" },
                { value: "not_useful", label: "无用" },
              ]}
            />
            <button
              onClick={() => {
                fetchFeedbacks();
                fetchStats();
              }}
              disabled={loading}
              className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition disabled:opacity-50"
            >
              {loading ? "刷新中..." : "刷新"}
            </button>
          </div>
        }
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="总反馈数"
          value={stats?.total ?? 0}
          accent="indigo"
        />
        <StatCard
          label="有用评价"
          value={stats?.useful ?? 0}
          accent="green"
        />
        <StatCard
          label="无用评价"
          value={stats?.not_useful ?? 0}
          accent="red"
        />
        <StatCard
          label="有用率"
          value={stats ? `${(stats.useful_rate * 100).toFixed(1)}%` : "0%"}
          accent={stats && stats.useful_rate >= 0.7 ? "green" : "amber"}
        />
      </div>

      {/* 反馈列表 */}
      <DataTable
        columns={columns}
        data={feedbacks}
        rowKey={(r) => String(r.id)}
        loading={loading}
        emptyTitle="暂无反馈"
        emptyDescription="学员在答疑页面提交反馈后，将在此显示"
      />
      <Pagination
        page={page}
        total={total}
        pageSize={20}
        onChange={setPage}
      />
    </div>
  );
}
