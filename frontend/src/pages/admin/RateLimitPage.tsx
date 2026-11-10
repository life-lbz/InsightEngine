import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { RateLimit } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { DataTable, type Column } from "../../components/admin/DataTable";

export default function RateLimitPage() {
  const [limits, setLimits] = useState<RateLimit[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getRateLimits();
      setLimits(data.rate_limits);
    } catch {
      setLimits([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const columns: Column<RateLimit>[] = [
    {
      key: "endpoint",
      label: "端点标识",
      render: (row) => (
        <span className="text-sm font-mono text-gray-700">{row.endpoint}</span>
      ),
    },
    {
      key: "current_count",
      label: "当前计数",
      render: (row) => {
        const ratio = row.limit > 0 ? (row.current_count / row.limit) * 100 : 0;
        const color = ratio > 80 ? "text-red-600" : ratio > 50 ? "text-amber-600" : "text-green-600";
        return <span className={`text-sm font-medium ${color}`}>{row.current_count}</span>;
      },
    },
    {
      key: "limit",
      label: "限流上限",
      render: (row) => <span className="text-sm text-gray-600">{row.limit}/min</span>,
    },
    {
      key: "usage",
      label: "使用率",
      render: (row) => {
        const ratio = row.limit > 0 ? (row.current_count / row.limit) * 100 : 0;
        const barColor = ratio > 80 ? "bg-red-500" : ratio > 50 ? "bg-amber-500" : "bg-green-500";
        return (
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full ${barColor} transition-all`}
                style={{ width: `${Math.min(ratio, 100)}%` }}
              />
            </div>
            <span className="text-xs text-gray-400">{ratio.toFixed(1)}%</span>
          </div>
        );
      },
    },
    {
      key: "window_seconds",
      label: "窗口",
      render: (row) => <span className="text-sm text-gray-500">{row.window_seconds}s</span>,
    },
    {
      key: "blocked_count_today",
      label: "今日拦截",
      render: (row) => (
        <span className={`text-sm ${row.blocked_count_today > 0 ? "text-red-600 font-medium" : "text-gray-400"}`}>
          {row.blocked_count_today}
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="限流监控"
        subtitle="实时监控各端点的请求限流状态（Redis 滑动窗口）"
        actions={
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
          >
            {loading ? "刷新中..." : "刷新"}
          </button>
        }
      />

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      ) : limits.length === 0 ? (
        <div className="text-center py-12 text-gray-400 text-sm">
          暂无限流数据（当前无活跃请求窗口）
        </div>
      ) : (
        <DataTable columns={columns} data={limits} />
      )}
    </div>
  );
}
