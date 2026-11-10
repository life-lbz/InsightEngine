"""聊天历史存储（生产级增强：Token 预算控制）。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import create_engine, text

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


class ChatHistoryStore:
    """聊天历史存储器（生产级增强版）。

    增强能力：
        - Token 预算控制：从最新消息向前遍历累加 token 数，超出预算时截断
        - 紧凑格式化：历史消息格式化为 [学员]: ... [助手]: ... 减少 token 占用
    """

    def __init__(self) -> None:
        """初始化聊天历史存储。"""
        settings = get_settings()
        self.engine = create_engine(
            settings.mysql_sync_uri,
            **settings.mysql_engine_kwargs,
        )
        self.max_tokens = settings.max_history_tokens

    def save_message(
        self,
        session_id: str,
        role_or_message: str,
        content: str | None = None,
        user_id: str = "",
    ) -> None:
        """保存一条聊天消息。

        支持两种调用方式：
            save_message(sid, message_json)          # 传入完整 JSON 字符串（兼容旧调用）
            save_message(sid, "user", "内容")        # 按角色 + 内容拆分，内部组装 JSON

        入参：
            session_id：会话 ID
            role_or_message：角色（user/assistant）或完整 JSON 消息
            content：消息内容（当使用三参形式时传入）
            user_id：所属用户 ID（用于个人统计）
        """
        if content is not None:
            message = json.dumps(
                {"role": role_or_message, "content": content},
                ensure_ascii=False,
            )
        else:
            message = role_or_message

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO chat_messages (session_id, user_id, message) "
                    "VALUES (:sid, :uid, :msg)"
                ),
                {"sid": session_id, "uid": user_id or None, "msg": message},
            )

    def get_context_messages(
        self,
        session_id: str,
        max_messages: int = 8,
        max_tokens: int | None = None,
    ) -> list[dict[str, str]]:
        """获取会话的上下文消息（带 Token 预算控制）。

        入参：
            session_id：会话 ID
            max_messages：最大消息条数
            max_tokens：最大 Token 数（默认使用配置的 max_history_tokens）

        返回：
            消息列表 [{"role": "user/assistant", "content": "..."}]

        边界条件：
            - 从最新消息向前遍历，超出 Token 预算时截断
            - 使用 tiktoken 估算 token 数
        """
        token_budget = max_tokens or self.max_tokens

        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT message FROM chat_messages "
                    "WHERE session_id = :sid "
                    "ORDER BY id DESC LIMIT :limit"
                ),
                {"sid": session_id, "limit": max_messages},
            )
            rows = result.fetchall()

        if not rows:
            return []

        # 反序列化并倒序（从旧到新）
        messages: list[dict[str, str]] = []
        for row in reversed(rows):
            try:
                import json
                msg = json.loads(row[0])
                messages.append(msg)
            except (json.JSONDecodeError, TypeError):
                continue

        # Token 预算控制：从最新消息向前累加，超出预算时截断
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            # tiktoken 不可用时使用字符数估算（1 token ≈ 2 个中文字符）
            enc = None

        budgeted: list[dict[str, str]] = []
        total_tokens = 0

        for msg in reversed(messages):
            content = msg.get("content", "")
            if enc:
                msg_tokens = len(enc.encode(content))
            else:
                msg_tokens = len(content) // 2

            if total_tokens + msg_tokens > token_budget:
                logger.info(
                    "history_truncated_by_token_budget",
                    session_id=session_id,
                    total_tokens=total_tokens,
                    budget=token_budget,
                    included=len(budgeted),
                    total=len(messages),
                )
                break

            total_tokens += msg_tokens
            budgeted.insert(0, msg)

        return budgeted

    def format_compact(self, messages: list[dict[str, str]]) -> str:
        """将历史消息格式化为紧凑文本。

        入参：
            messages：消息列表

        返回：
            紧凑格式的文本（[学员]: xxx [助手]: yyy）
        """
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            label = "学员" if role == "user" else "助手"
            parts.append(f"[{label}]: {content}")
        return "\n".join(parts)