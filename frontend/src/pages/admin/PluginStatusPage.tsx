import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { PluginStatus, PluginHealthResponse } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";

export default function PluginStatusPage() {
  const [health, setHealth] = useState<PluginHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getPluginsHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const plugins: PluginStatus[] = health?.plugins || [];

  return (
    <div>
      <PageHeader
        title="插件状态"
        subtitle="实时健康检查：向量库、LLM 等核心组件状态"
        actions={
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
          >
            {loading ? "检查中..." : "重新检查"}
          </button>
        }
      />

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      ) : (
        <>
          <div className="mb-6 flex items-center gap-4 p-4 rounded-xl border border-gray-100 bg-white">
            <div
              className={`w-4 h-4 rounded-full ${health?.overall ? "bg-green-500" : "bg-red-500"}`}
            />
            <div>
              <p className="text-sm font-medium text-gray-900">
                系统总体状态: {health?.overall ? "健康" : "异常"}
              </p>
              <p className="text-xs text-gray-400">
                已检查 {health?.total || 0} 个核心组件
              </p>
            </div>
            {health?.error && (
              <span className="ml-auto text-xs text-red-500">{health.error}</span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {plugins.map((plugin) => (
              <div
                key={plugin.name}
                className={`p-5 rounded-xl border ${
                  plugin.healthy
                    ? "border-green-100 bg-green-50/50"
                    : "border-red-100 bg-red-50/50"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-3 h-3 rounded-full ${
                        plugin.healthy ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                    <h3 className="text-sm font-semibold text-gray-900 capitalize">
                      {plugin.name}
                    </h3>
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      plugin.healthy
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {plugin.healthy ? "正常" : "异常"}
                  </span>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-gray-500">
                    延迟:{" "}
                    <span className="font-mono text-gray-700">
                      {plugin.latency_ms}ms
                    </span>
                  </p>
                  {plugin.error && (
                    <p className="text-xs text-red-500 truncate">
                      错误: {plugin.error}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {plugins.length === 0 && !health?.error && (
            <div className="text-center py-12 text-gray-400 text-sm">
              无插件数据
            </div>
          )}
        </>
      )}
    </div>
  );
}
