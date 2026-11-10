"""输出内容风控：LLM 输出敏感词过滤。"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)

# 敏感词替换文本
FILTERED_TEXT = "[内容已过滤]"


class OutputFilter:
    """输出内容风控过滤器。

    功能：
        - 检测 LLM 输出中的敏感词（政治、色情、暴力、广告引流等）
        - 命中时替换为 [内容已过滤]
        - 记录审计日志（含原始内容 hash）
    """

    def __init__(self) -> None:
        """初始化风控过滤器，加载敏感词库。"""
        self.sensitive_words: list[str] = []
        self._load_rules()

    def _load_rules(self) -> None:
        """从 config/risk_rules.yaml 加载敏感词库。"""
        rules_path = Path(__file__).resolve().parents[1] / "config" / "risk_rules.yaml"
        if rules_path.exists():
            data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
            self.sensitive_words = data.get("sensitive_words", [])
        else:
            # 默认敏感词（生产环境应从文件加载完整词库）
            self.sensitive_words = []

    def filter_output(self, text: str) -> tuple[str, list[str]]:
        """过滤输出中的敏感词。

        入参：
            text：LLM 原始输出

        返回：
            (过滤后的文本, 命中的敏感词列表)
        """
        if not text:
            return text, []

        filtered_text = text
        hit_words: list[str] = []

        for word in self.sensitive_words:
            if word in filtered_text:
                hit_words.append(word)
                filtered_text = filtered_text.replace(word, FILTERED_TEXT)

        if hit_words:
            # 记录审计日志（仅记录 hash，不记录明文）
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            logger.warning(
                "output_filtered",
                hit_words=hit_words,
                content_hash=content_hash,
            )

        return filtered_text, hit_words

    def reload_rules(self) -> None:
        """热更新敏感词库。"""
        self._load_rules()
        logger.info("risk_rules_reloaded", word_count=len(self.sensitive_words))