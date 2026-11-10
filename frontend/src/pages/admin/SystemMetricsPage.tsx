import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { MetricsSummary, MetricSample } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";

export default function SystemMetricsPage() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getMetricsSummary();
      setMetrics(data);
    } catch {
      setMetrics(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const renderMetricCard = (
    title: string,
    samples: MetricSample[] | undefined,
    unit: string = ""
  ) => {
    if (!samples || samples.length === 0) return null;
    const latest = samples[samples.length - 1];
    const labelParts = Object.entries(latest.labels || {})
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    return (
      <div className="p-4 rounded-xl border border-gray-100 bg-white">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-medium text-gray-600">{title}</h4>
          <span className="text-xs text-gray-300">#{samples.length}</span>
        </div>
        <p className="text-lg font-mono font-semibold text-indigo-600">
          {Number(latest.value).toFixed(2)}
          <span className="text-xs text-gray-400 ml-1">{unit}</span>
        </p>
        {labelParts && (
          <p className="text-xs text-gray-400 mt-1 truncate">{labelParts}</p>
        )}
      </div>
    );
  };

  const renderHistogram = (title: string, samples: MetricSample[] | undefined) => {
    if (!samples || samples.length === 0) return null;
    const buckets = samples.filter((s) => s.name.includes("_bucket"));
    if (buckets.length === 0) {
      return renderMetricCard(title, samples, "s");
    }
    const sum = samples.find((s) => s.name.includes("_sum"));
    const count = samples.find((s) => s.name.includes("_count"));
    return (
      <div className="p-4 rounded-xl border border-gray-100 bg-white">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-medium text-gray-600">{title}</h4>
          <span className="text-xs text-gray-300">{count?.value || 0} 次</span>
        </div>
        {sum && (
          <p className="text-lg font-mono font-semibold text-indigo-600">
            {(Number(sum.value)).toFixed(3)}
            <span className="text-xs text-gray-400 ml-1">s 总计</span>
          </p>
        )}
        {count && (
          <p className="text-xs text-gray-400 mt-1">请求计数: {count.value}</p>
        )}
      </div>
    );
  };

  return (
    <div>
      <PageHeader
        title="系统指标"
        subtitle="Prometheus 指标聚合：RAG 延迟、检索性能、LLM 用量等"
        actions={
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
          >
            {loading ? "采集中..." : "刷新"}
          </button>
        }
      />

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      ) : metrics?.error ? (
        <div className="p-4 bg-red-50 text-red-600 text-sm rounded-lg">
          指标获取失败: {metrics.error}
        </div>
      ) : (
        <>
          <div className="mb-4 p-3 bg-indigo-50/50 rounded-lg text-sm text-gray-600">
            共采集 <span className="font-semibold text-indigo-600">{metrics?.metric_count || 0}</span> 个 Prometheus 指标
          </div>

          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">RAG 性能</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {renderHistogram("请求耗时", metrics?.rag_request_duration)}
              {renderHistogram("首 Token 延迟", metrics?.rag_first_token_latency)}
              {renderHistogram("Milvus 检索耗时", metrics?.milvus_search_duration)}
              {renderMetricCard("WebSocket 活跃连接", metrics?.websocket_active_connections, "个")}
            </div>
          </div>

          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">LLM 用量</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {renderHistogram("LLM 请求耗时", metrics?.llm_request_duration)}
              {renderMetricCard("LLM Token 用量", metrics?.llm_token_usage, "tokens")}
              {renderMetricCard("LLM 请求次数", metrics?.llm_request_total, "次")}
              {renderMetricCard("Milvus 检索次数", metrics?.milvus_search_total, "次")}
            </div>
          </div>

          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">系统健康</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {renderMetricCard("缓存命中率", metrics?.cache_hit_rate, "%")}
              {renderMetricCard("降级请求", metrics?.degraded_request_total, "次")}
              {renderMetricCard("幻觉风险", metrics?.hallucination_risk_total, "次")}
              {renderMetricCard("反馈评分占比", metrics?.feedback_rating_ratio, "%")}
              {renderMetricCard("插件健康状态", metrics?.plugin_health_status)}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
