import { adminApi } from "../../api/admin";
import type { DashboardStats, HealthStatus } from "../../types";
import { StatCard } from "../../components/admin/StatCard";
import { useFetch } from "../../hooks/useFetch";
import { usePolling } from "../../hooks/usePolling";

export default function DashboardPage() {
  // 数据加载（loading / data / error 三态收敛）
  const { data, loading, reload, setData } = useFetch<{
    health: HealthStatus | null;
    stats: DashboardStats | null;
  }>(async () => {
    const [health, stats] = await Promise.all([
      adminApi.getHealth(),
      adminApi.getDashboardStats(),
    ]);
    return { health, stats };
  }, []);

  // 每 30 秒静默刷新（失败指数退避 + 页面隐藏暂停 + 卸载清理）
  usePolling(
    async () => {
      const [health, stats] = await Promise.all([
        adminApi.getHealth(),
        adminApi.getDashboardStats(),
      ]);
      setData({ health, stats });
    },
    [],
    { intervalMs: 30000 }
  );

  const health = data?.health ?? null;
  const stats = data?.stats ?? null;
  const components = health?.components || {};
  const maxTrendCount = Math.max(...(stats?.query_trend.map((t) => t.count) || [1]), 1);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">系统仪表盘</h2>
        <button
          onClick={reload}
          disabled={loading}
          className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition disabled:opacity-50"
        >
          {loading ? "刷新中..." : "刷新"}
        </button>
      </div>

      {/* 总体状态 */}
      <div className="mb-6 p-5 bg-white border border-gray-200 rounded-xl">
        <div className="flex items-center gap-4">
          <div
            className={`w-4 h-4 rounded-full ${
              health?.status === "healthy" ? "bg-green-500" : "bg-red-500"
            }`}
          />
          <div>
            <p className="text-sm font-medium text-gray-900">
              系统状态：{health?.status === "healthy" ? "正常运行" : "异常"}
            </p>
            <p className="text-xs text-gray-400">每 30 秒自动刷新</p>
          </div>
          <div className="ml-auto flex items-center gap-4">
            {Object.entries(components).map(([name, info]) => (
              <div key={name} className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    info.healthy ? "bg-green-500" : "bg-red-500"
                  }`}
                />
                <span className="text-xs text-gray-500">{name}</span>
                <span className="text-xs text-gray-400">{info.latency_ms}ms</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* P1 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="检索总量"
          value={stats?.total_queries ?? 0}
          accent="indigo"
          hint={`平均命中 ${stats?.avg_hit_count ?? 0}`}
        />
        <StatCard
          label="用户总数"
          value={stats?.total_users ?? 0}
          accent="green"
        />
        <StatCard
          label="已入库文档"
          value={stats?.total_docs ?? 0}
          accent="amber"
        />
        <StatCard
          label="反馈数"
          value={stats?.total_feedback ?? 0}
          accent="gray"
          hint={`有用率 ${((stats?.useful_rate ?? 0) * 100).toFixed(1)}%`}
        />
      </div>

      {/* 质量指标 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="p-4 bg-white border border-gray-200 rounded-xl">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            零命中率
          </p>
          <p className="mt-2 text-2xl font-bold text-red-600">
            {((stats?.zero_hit_rate ?? 0) * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-gray-400">检索无结果的查询比例</p>
        </div>
        <div className="p-4 bg-white border border-gray-200 rounded-xl">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            反馈率
          </p>
          <p className="mt-2 text-2xl font-bold text-amber-600">
            {((stats?.feedback_rate ?? 0) * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-gray-400">用户提交反馈的查询比例</p>
        </div>
        <div className="p-4 bg-white border border-gray-200 rounded-xl">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            有用率
          </p>
          <p className="mt-2 text-2xl font-bold text-green-600">
            {((stats?.useful_rate ?? 0) * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-gray-400">用户标记有用的反馈比例</p>
        </div>
      </div>

      {/* 查询趋势 */}
      {stats && stats.query_trend.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">
            近 7 天检索趋势
          </h3>
          <div className="flex items-end gap-2 h-32">
            {stats.query_trend.map((trend) => (
              <div
                key={trend.date}
                className="flex-1 flex flex-col items-center gap-1"
              >
                <div className="text-xs text-gray-400">{trend.count}</div>
                <div
                  className="w-full bg-indigo-100 rounded-t-md transition-all"
                  style={{
                    height: `${(trend.count / maxTrendCount) * 100}%`,
                    minHeight: trend.count > 0 ? "4px" : "0",
                  }}
                >
                  <div className="w-full h-full bg-indigo-500 rounded-t-md" />
                </div>
                <div className="text-xs text-gray-500">
                  {trend.date.slice(5)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
