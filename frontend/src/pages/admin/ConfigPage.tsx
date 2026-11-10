import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/admin";
import type { SystemConfig } from "../../types";
import { PageHeader } from "../../components/admin/PageHeader";

export default function ConfigPage() {
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [docTopK, setDocTopK] = useState(20);
  const [faqTopK, setFaqTopK] = useState(20);
  const [rerankTopN, setRerankTopN] = useState(5);
  const [minScore, setMinScore] = useState(0.2);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState("");

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getConfig();
      setConfig(data);
      setDocTopK(data.doc_top_k);
      setFaqTopK(data.faq_top_k);
      setRerankTopN(data.rerank_top_n);
      setMinScore(data.rag_min_score_threshold);
    } catch {
      setConfig(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const result = await adminApi.updateConfig({
        doc_top_k: docTopK,
        faq_top_k: faqTopK,
        rerank_top_n: rerankTopN,
        rag_min_score_threshold: minScore,
      });
      setSavedMsg(`已更新: ${result.updated.join(", ")}`);
      setTimeout(() => setSavedMsg(""), 3000);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }

  if (!config) {
    return <p className="text-sm text-gray-500">无法加载配置信息</p>;
  }

  const configItems: { label: string; value: string; sensitive?: boolean }[] = [
    { label: "LLM 模型", value: config.llm_model },
    { label: "LLM 降级模型", value: config.llm_fallback_model },
    { label: "Embedding 模型路径", value: config.embedding_model_path },
    { label: "Reranker 模型路径", value: config.reranker_model_path },
    { label: "Milvus 地址", value: config.milvus_uri },
    { label: "Redis 地址", value: config.redis_url, sensitive: true },
    { label: "MySQL 主机", value: config.mysql_host },
    { label: "数据库名", value: config.mysql_database },
    { label: "Embedding 批量大小", value: String(config.embedding_batch_size) },
    { label: "最小 Chunk 字符数", value: String(config.min_chunk_chars) },
    {
      label: "Chunk 去重阈值",
      value: String(config.chunk_dedup_jaccard_threshold),
    },
  ];

  return (
    <div>
      <PageHeader
        title="系统配置"
        subtitle="查看系统运行参数，支持检索参数热更新"
        actions={
          <button
            onClick={fetchConfig}
            disabled={loading}
            className="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition disabled:opacity-50"
          >
            {loading ? "刷新中..." : "刷新"}
          </button>
        }
      />

      {/* 只读配置展示 */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">
          系统参数
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {configItems.map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between py-2 border-b border-gray-50"
            >
              <span className="text-sm text-gray-500">{item.label}</span>
              <span
                className={`text-sm font-mono ${
                  item.sensitive
                    ? "text-gray-400"
                    : "text-gray-700"
                } truncate max-w-xs block`}
              >
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 检索参数热更新 */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">
          检索参数热更新
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              文档检索 Top-K（向量召回数量）
            </label>
            <input
              type="number"
              value={docTopK}
              onChange={(e) =>
                setDocTopK(parseInt(e.target.value) || 20)
              }
              min={1}
              max={50}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
            <p className="mt-1 text-xs text-gray-400">
              从 Milvus 召回的文档候选数量，推荐 5-30
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              FAQ 检索 Top-K
            </label>
            <input
              type="number"
              value={faqTopK}
              onChange={(e) =>
                setFaqTopK(parseInt(e.target.value) || 20)
              }
              min={1}
              max={50}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
            <p className="mt-1 text-xs text-gray-400">
              FAQ 召回的候选数量，推荐 5-30
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Rerank Top-N（最终保留数量）
            </label>
            <input
              type="number"
              value={rerankTopN}
              onChange={(e) =>
                setRerankTopN(parseInt(e.target.value) || 5)
              }
              min={1}
              max={20}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
            <p className="mt-1 text-xs text-gray-400">
              Reranker 重排后保留的最终 chunk 数量，推荐 3-10
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              最低分数阈值
            </label>
            <input
              type="number"
              step="0.05"
              value={minScore}
              onChange={(e) =>
                setMinScore(parseFloat(e.target.value) || 0.2)
              }
              min={0}
              max={1}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
            <p className="mt-1 text-xs text-gray-400">
              低于此分数的检索结果将被过滤，推荐 0.1-0.5
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? "保存中..." : "保存参数"}
          </button>
          {savedMsg && (
            <span className="text-sm text-green-600">{savedMsg}</span>
          )}
        </div>
      </div>
    </div>
  );
}
