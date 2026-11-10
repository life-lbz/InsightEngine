"""Prometheus 指标定义：覆盖检索、生成、缓存、插件等核心维度。

使用方式：
    from observability.metrics import rag_request_duration, llm_token_usage
    rag_request_duration.labels(course_id="default_course", intent="KNOWLEDGE_QUERY").observe(3.2)
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


# ── RAG 请求指标 ──
rag_request_duration = Histogram(
    "rag_request_duration_seconds",
    "RAG 请求端到端耗时",
    labelnames=["course_id", "intent", "hit_type"],
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 15.0],
)

rag_first_token_latency = Histogram(
    "rag_first_token_latency_seconds",
    "首 Token 生成延迟",
    labelnames=["course_id", "intent"],
    buckets=[0.3, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0],
)

# ── 检索指标 ──
milvus_search_duration = Histogram(
    "milvus_search_duration_seconds",
    "Milvus 检索耗时",
    labelnames=["collection"],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0],
)

milvus_search_total = Counter(
    "milvus_search_total",
    "Milvus 检索次数",
    labelnames=["collection", "cache_hit"],
)

retrieval_hit_count = Histogram(
    "retrieval_hit_count",
    "每通道检索命中数",
    labelnames=["channel"],
    buckets=[0, 1, 3, 5, 10, 20],
)

# ── LLM 指标 ──
llm_request_duration = Histogram(
    "llm_request_duration_seconds",
    "LLM 请求耗时",
    labelnames=["model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

llm_token_usage = Counter(
    "llm_token_usage_total",
    "LLM Token 使用量",
    labelnames=["model", "type"],
)

llm_request_total = Counter(
    "llm_request_total",
    "LLM 请求次数",
    labelnames=["model", "status"],
)

# ── 缓存指标 ──
cache_hit_rate = Gauge(
    "cache_hit_rate",
    "缓存命中率",
    labelnames=["cache_type"],
)

# ── 降级指标 ──
degraded_request_total = Counter(
    "degraded_request_total",
    "降级请求次数",
    labelnames=["degraded_type"],
)

# ── WebSocket 指标 ──
websocket_active_connections = Gauge(
    "websocket_active_connections",
    "WebSocket 活跃连接数",
)

# ── 幻觉检测指标 ──
hallucination_risk_total = Counter(
    "hallucination_risk_total",
    "幻觉风险检测次数",
    labelnames=["course_id"],
)

# ── 插件指标 ──
plugin_health_status = Gauge(
    "plugin_health_status",
    "插件健康状态（1=healthy, 0=unhealthy）",
    labelnames=["plugin_name", "type"],
)

plugin_operation_duration = Histogram(
    "plugin_operation_duration_seconds",
    "插件操作耗时",
    labelnames=["plugin_name", "operation"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

# ── 反馈指标 ──
feedback_rating_ratio = Gauge(
    "feedback_rating_ratio",
    "反馈评分占比",
    labelnames=["course_id", "rating"],
)