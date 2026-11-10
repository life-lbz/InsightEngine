import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { RetrievalStats } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";
import { StatCard } from "../../components/admin/StatCard";
import { DataTable, type Column } from "../../components/admin/DataTable";
import { LoadingSpinner } from "../../components/common/LoadingSpinner";

interface ChannelRow {
  channel: string;
  count: number;
  avg_hit: number;
}

export default function TeacherRetrievalStatsPage() {
  const [stats, setStats] = useState<RetrievalStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getRetrievalStats();
      setStats(data);
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const channelColumns: Column<ChannelRow>[] = [
    {
      key: "channel",
      label: "检索渠道",
      render: (row) => (
        <span className="font-mono text-xs text-gray-700">{row.channel}</span>
      ),
    },
    {
      key: "count",
      label: "检索次数",
      render: (row) => <span className="text-gray-600">{row.count}</span>,
    },
    {
      key: "avg_hit",
      label: "平均命中数",
      render: (row) => (
        <span className="text-gray-600">{row.avg_hit.toFixed(2)}</span>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="检索统计"
        subtitle="答疑检索质量概览：命中情况、耗时与渠道分布"
        actions={
          <button
            onClick={fetchStats}
            className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition"
          >
            刷新
          </button>
        }
      />

      {stats ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard label="总检索次数" value={stats.total.toLocaleString()} accent="indigo" />
            <StatCard
              label="平均命中数"
              value={stats.avg_hit_count.toFixed(2)}
              accent="green"
            />
            <StatCard
              label="平均耗时 (ms)"
              value={stats.avg_elapsed_ms.toFixed(0)}
              accent="amber"
            />
            <StatCard
              label="零命中率"
              value={`${(stats.zero_hit_rate * 100).toFixed(1)}%`}
              accent={stats.zero_hit_rate > 0.3 ? "amber" : "gray"}
              hint={`${stats.zero_hit_count} 次未命中`}
            />
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">渠道分布</h3>
            <DataTable
              columns={channelColumns}
              data={stats.channels}
              rowKey={(r) => r.channel}
              emptyTitle="暂无渠道数据"
            />
          </div>

          <p className="text-xs text-gray-400 mt-4">
            零命中率偏高说明部分问题未检索到相关知识，可考虑补充对应课程文档或 FAQ。
          </p>
        </>
      ) : (
        <div className="text-center py-16 text-gray-400 text-sm">
          暂无检索统计数据
        </div>
      )}
    </div>
  );
}
