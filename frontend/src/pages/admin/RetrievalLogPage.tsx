import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { RetrievalLog, RetrievalStats } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { StatCard } from "../../components/admin/StatCard";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { Pagination } from "../../components/admin/Pagination";

export default function RetrievalLogPage() {
  const [logs, setLogs] = useState<RetrievalLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [stats, setStats] = useState<RetrievalStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getRetrievalLogs(page, 20);
      setLogs(data.logs);
      setTotal(data.total);
    } catch {
      setLogs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page]);

  const fetchStats = useCallback(async () => {
    try {
      const data = await adminApi.getRetrievalStats();
      setStats(data);
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
    fetchStats();
  }, [fetchLogs, fetchStats]);

  const columns: Column<RetrievalLog>[] = [
    {
      key: "query",
      label: "查询内容",
      render: (row) => (
        <span className="text-sm text-gray-700 truncate max-w-sm block">
          {row.query}
        </span>
      ),
    },
    {
      key: "channel",
      label: "渠道",
      render: (row) => (
        <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
          {row.channel}
        </span>
      ),
    },
    {
      key: "intent",
      label: "意图",
      render: (row) => (
        <span className="text-xs text-gray-500">{row.intent || "-"}</span>
      ),
    },
    {
      key: "hit_count",
      label: "命中数",
      render: (row) => (
        <span
          className={`font-medium ${row.hit_count > 0 ? "text-green-600" : "text-red-500"}`}
        >
          {row.hit_count}
        </span>
      ),
    },
    {
      key: "top_score",
      label: "最高分",
      render: (row) => (
        <span className="text-xs text-gray-500">
          {row.top_score !== null ? row.top_score.toFixed(4) : "-"}
        </span>
      ),
    },
    {
      key: "elapsed_ms",
      label: "耗时(ms)",
      render: (row) => (
        <span className="text-xs text-gray-500">{row.elapsed_ms ?? "-"}</span>
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
        title="检索质量监控"
        subtitle="追踪检索命中率和响应时间，发现低质量查询"
        actions={
          <button
            onClick={() => {
              fetchLogs();
              fetchStats();
            }}
            disabled={loading}
            className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition disabled:opacity-50"
          >
            {loading ? "刷新中..." : "刷新"}
          </button>
        }
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="总检索次数"
          value={stats?.total ?? 0}
          accent="indigo"
        />
        <StatCard
          label="平均命中数"
          value={stats?.avg_hit_count ?? 0}
          accent="green"
        />
        <StatCard
          label="平均耗时(ms)"
          value={stats?.avg_elapsed_ms ?? 0}
          accent="amber"
        />
        <StatCard
          label="零命中率"
          value={stats ? `${(stats.zero_hit_rate * 100).toFixed(1)}%` : "0%"}
          accent={stats && stats.zero_hit_rate > 0.1 ? "red" : "gray"}
          hint={`共 ${stats?.zero_hit_count ?? 0} 次零命中`}
        />
      </div>

      {/* 渠道分布 */}
      {stats && stats.channels.length > 0 && (
        <div className="mb-6 bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">渠道分布</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {stats.channels.map((ch) => (
              <div
                key={ch.channel}
                className="p-3 bg-gray-50 rounded-lg"
              >
                <p className="text-xs font-medium text-gray-500">{ch.channel}</p>
                <p className="mt-1 text-lg font-bold text-gray-700">
                  {ch.count}
                </p>
                <p className="text-xs text-gray-400">
                  平均命中 {ch.avg_hit}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 检索日志表 */}
      <DataTable
        columns={columns}
        data={logs}
        rowKey={(r) => String(r.id)}
        loading={loading}
        emptyTitle="暂无检索日志"
        emptyDescription="用户发起答疑后，检索记录将在此显示"
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
