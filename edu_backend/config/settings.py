"""教育答疑场景配置管理：集中读取环境变量和 .env，支持多环境隔离与连接池治理。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """在线教育答疑场景运行配置。

    新增字段：
        - app_env：运行环境标识（dev/staging/prod），驱动配置隔离与安全校验
        - mysql_pool_* / redis_max_connections：连接池治理参数
        - milvus_search_timeout / search_cache_ttl：检索超时与缓存配置
        - llm_fallback_model：LLM 降级备用模型
        - max_history_tokens：聊天历史 Token 预算
        - cors_allow_origins：CORS 白名单
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / "config" / "config.example.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 运行环境 ──
    app_env: str = "dev"
    active_scenario_id: str = "education_qa"
    default_course_id: str = "default_course"
    default_kb_version: str = "kb_manual_v1"
    upload_max_size_mb: int = 50
    api_port: int = 8000
    cors_allow_origins: list[str] = ["*"]

    # ── MySQL 配置（增强连接池参数）──
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 13307
    mysql_user: str = "root"
    mysql_password: str = "root123"
    mysql_database: str = "insight_engine"
    mysql_pool_size: int = 20
    mysql_max_overflow: int = 10
    mysql_pool_recycle: int = 3600
    mysql_pool_pre_ping: bool = True

    # ── Redis 配置（增强连接池参数）──
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_max_connections: int = 50
    cache_enabled: bool = False

    # ── Milvus 配置（增强超时参数）──
    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_database: str = "insight_engine"
    milvus_search_timeout: float = 3.0
    milvus_connect_retry: int = 3

    # ── LLM 配置（增强降级链）──
    # deepseek-chat 为非思考模式：不返回 reasoning_content，
    # 避免 langgraph supervisor 多代理消息流回传该字段导致 API 400
    llm_model: str = "deepseek-chat"
    llm_fallback_model: str = "deepseek-chat"
    llm_api_key: str = Field(
        default="PROJECT_DEEPSEEK_API_KEY",
        validation_alias="PROJECT_DEEPSEEK_API_KEY",
    )
    llm_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias="PROJECT_DEEPSEEK_BASE_URL",
    )
    llm_temperature: float = 0.1
    llm_timeout: float = 60.0
    llm_retry_count: int = 2

    # ── Embedding / Reranker 配置 ──
    # 占位符：请通过环境变量覆盖为实际模型路径或 HF model_id
    embedding_model_path: str = "${EMBEDDING_MODEL_PATH}"
    reranker_model_path: str = "${RERANKER_MODEL_PATH}"
    embedding_model_version: str = "placeholder"
    reranker_model_version: str = "placeholder"
    chunk_schema_version: str = "edu_parent_child_v1"

    # ── 意图分类模型配置 ──
    # 占位符：请通过环境变量覆盖为实际模型路径或 HF model_id
    intent_bert_model_path: str = "${INTENT_BERT_MODEL_PATH}"
    intent_model_version: str = "placeholder"

    # ── 检索参数 ──
    faq_top_k: int = 20
    doc_top_k: int = 20
    question_top_k: int = 20
    rerank_top_n: int = 5
    final_context_top_n: int = 4
    rag_min_score_threshold: float = 0.2
    max_prompt_context_chars: int = 6000
    max_context_doc_chars: int = 1600

    # ── 分块参数 ──
    parent_chunk_size: int = 1000
    child_chunk_size: int = 350
    parent_overlap: int = 100
    child_overlap: int = 50

    # ── 缓存配置（新增）──
    search_cache_ttl: int = 300
    answer_cache_ttl: int = 3600

    # ── 安全配置 ──
    enable_fallback_users: bool = True
    admin_api_token: str = "replace-with-random-token"
    jwt_secret_key: str = "replace-with-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    jwt_refresh_expire_days: int = 7

    # ── 限流配置 ──
    api_rate_limit_per_minute: int = 300
    api_rate_limit_read_multiplier: int = 3
    admin_rate_limit_per_minute: int = 60

    # ── 日志配置 ──
    log_dir: str = "/var/log/insight_engine"
    log_level: str = "INFO"
    log_json_output: bool = True

    # ── 生成增强配置 ──
    max_history_tokens: int = 2000
    hallucination_max_unsupported_claims: int = 2

    # ── 数据工程配置 ──
    min_chunk_chars: int = 20
    chunk_dedup_jaccard_threshold: float = 0.85
    collection_archive_after_days: int = 7
    collection_delete_after_days: int = 30

    # ── Embedding 批处理 ──
    embedding_batch_size: int = 64
    rerank_batch_size: int = 32

    # ── Agent 协作配置（二期新增，灰度开关默认关闭）──
    enable_agent_collab: bool = True
    agent_router_prefix: str = "/api/v1/agent"
    agent_recursion_limit: int = 25
    agent_max_token_budget: int = 8000
    agent_llm_concurrency: int = 20
    agent_enable_input_guard: bool = True
    agent_enable_output_guard: bool = True
    agent_enable_role_guard: bool = True
    agent_enable_cost_guard: bool = True
    agent_role_whitelist: dict[str, list[str]] = Field(
        default={
            "student": ["qa_agent", "quiz_agent", "planner_agent", "explain_agent"],
            "teacher": ["teacher_insight_agent"],
            "admin": ["teacher_insight_agent", "kb_ops_agent"],
        }
    )

    @field_validator(
        "embedding_model_path",
        "reranker_model_path",
        "intent_bert_model_path",
        mode="after",
    )
    @classmethod
    def resolve_relative_paths(cls, value: str) -> str:
        """把相对模型路径解析到工程根目录。占位符原样保留。"""
        if value.startswith("${") or value == "placeholder":
            return value
        path = Path(value).expanduser()
        return str(path) if path.is_absolute() else str(PROJECT_ROOT / path)

    @field_validator("cors_allow_origins", mode="after")
    @classmethod
    def validate_cors_in_prod(cls, value: list[str], info: Any) -> list[str]:
        """生产环境禁止 CORS 配置为通配符 *。"""
        values = info.data
        if values.get("app_env") == "prod" and "*" in value:
            raise ValueError(
                "CORS allow_origins 不允许在生产环境使用 '*'，"
                "请配置具体域名列表"
            )
        return value

    @property
    def mysql_sync_uri(self) -> str:
        """构造 SQLAlchemy 连接串。"""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def mysql_engine_kwargs(self) -> dict[str, Any]:
        """SQLAlchemy 引擎连接池参数。"""
        return {
            "pool_size": self.mysql_pool_size,
            "max_overflow": self.mysql_max_overflow,
            "pool_recycle": self.mysql_pool_recycle,
            "pool_pre_ping": self.mysql_pool_pre_ping,
        }

    @property
    def redis_url(self) -> str:
        """构造 Redis 连接串。"""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def redis_pool_kwargs(self) -> dict[str, Any]:
        """Redis 连接池参数。"""
        return {
            "max_connections": self.redis_max_connections,
            "decode_responses": True,
        }

    @property
    def is_production(self) -> bool:
        """判断是否为生产环境。"""
        return self.app_env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回进程级配置单例，避免每次请求重复解析。"""
    return Settings()