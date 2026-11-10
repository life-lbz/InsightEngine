"""意图识别分类器：关键词规则 + 可选 BERT 模型。"""
from __future__ import annotations

import re
from typing import Any

from observability.logger import get_logger

logger = get_logger(__name__)

# 意图类型常量
INTENT_FAQ_QUERY = "FAQ_QUERY"
INTENT_KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"
INTENT_QUESTION_PRACTICE = "QUESTION_PRACTICE"
INTENT_FOLLOW_UP = "FOLLOW_UP"

# 关键词规则表
INTENT_KEYWORDS: dict[str, list[str]] = {
    INTENT_QUESTION_PRACTICE: [
        "练习", "题目", "考试", "作业", "测验", "真题", "模拟题",
        "选择题", "填空题", "编程题", "算法题", "刷题",
    ],
    INTENT_FAQ_QUERY: [
        "什么是", "什么是", "什么叫", "如何", "怎么", "怎样",
        "为什么", "为何", "区别", "对比", "能...吗", "可以...吗",
        "是否", "能不能", "行不行",
    ],
    INTENT_FOLLOW_UP: [
        "那", "然后呢", "继续", "还有呢", "接着说", "另外",
        "刚才", "你说的", "上面提到的", "这个", "它",
    ],
}

# 意图权重映射（用于 Dense-Sparse 检索权重调整）
INTENT_DENSE_SPARSE_WEIGHTS: dict[str, tuple[float, float]] = {
    INTENT_FAQ_QUERY: (0.35, 0.65),
    INTENT_KNOWLEDGE_QUERY: (0.70, 0.30),
    INTENT_QUESTION_PRACTICE: (0.45, 0.55),
    INTENT_FOLLOW_UP: (0.55, 0.45),
}


class IntentClassifier:
    """意图识别分类器。

    分类策略：
        1. 优先使用 BERT 分类模型（如果已加载）
        2. 降级为关键词规则匹配
        3. 默认返回 KNOWLEDGE_QUERY
    """

    def __init__(self) -> None:
        """初始化分类器。"""
        self._bert_model = None
        self._labels: list[str] = []
        self._try_load_bert()

    def _try_load_bert(self) -> None:
        """尝试加载 BERT 分类模型（可选，加载失败不阻断）。"""
        try:
            from config.settings import get_settings
            from pathlib import Path

            settings = get_settings()
            model_path = Path(settings.intent_bert_model_path.replace("\\", "/"))
            if model_path.exists():
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                # 从 intent_labels.json 读取标签映射，避免硬编码不一致
                labels_file = model_path / "intent_labels.json"
                if labels_file.exists():
                    import json
                    label_data = json.loads(labels_file.read_text(encoding="utf-8"))
                    self._labels = label_data.get("labels", [])
                    logger.info(
                        "intent_labels_loaded",
                        model_path=str(model_path),
                        labels=self._labels,
                    )

                self._bert_model = {
                    "tokenizer": AutoTokenizer.from_pretrained(str(model_path)),
                    "model": AutoModelForSequenceClassification.from_pretrained(str(model_path)),
                }
                logger.info("intent_bert_loaded", model_path=str(model_path))
        except Exception as exc:
            logger.info("intent_bert_skipped", reason=str(exc)[:100])

    def classify(self, query: str, history: list[dict] | None = None) -> str:
        """识别用户查询意图。

        入参：
            query：用户查询文本
            history：对话历史（用于判断是否为追问）

        返回：
            意图类型字符串
        """
        if history:
            for msg in history[-3:]:
                if msg.get("role") == "assistant":
                    if self._is_follow_up(query):
                        return INTENT_FOLLOW_UP

        if self._bert_model is not None:
            try:
                return self._classify_with_bert(query)
            except Exception as exc:
                logger.warning("intent_bert_failed", error=str(exc)[:100])

        return self._classify_with_keywords(query)

    def _classify_with_bert(self, query: str) -> str:
        """使用 BERT 模型分类。"""
        import torch
        tokenizer = self._bert_model["tokenizer"]
        model = self._bert_model["model"]
        inputs = tokenizer(query, return_tensors="pt", truncation=True, max_length=128)
        with torch.no_grad():
            logits = model(**inputs).logits
        predicted_id = torch.argmax(logits, dim=-1).item()

        # 优先使用 intent_labels.json 的标签映射，缺失时回退默认
        labels = self._labels or [INTENT_FAQ_QUERY, INTENT_KNOWLEDGE_QUERY, INTENT_QUESTION_PRACTICE]
        if 0 <= predicted_id < len(labels):
            return labels[predicted_id]
        return INTENT_KNOWLEDGE_QUERY

    def _classify_with_keywords(self, query: str) -> str:
        """关键词规则匹配分类。"""
        scores: dict[str, int] = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query)
            scores[intent] = score

        best_intent = max(scores, key=scores.get)
        if scores[best_intent] == 0:
            return INTENT_KNOWLEDGE_QUERY

        return best_intent

    def _is_follow_up(self, query: str) -> bool:
        """判断是否为追问。"""
        follow_up_patterns = [
            r"^(那|然后呢|继续|还有呢|接着说|另外)",
            r"^(这个|它|上面提到的|你说的|刚才)",
            r"^(能不能|可以吗|行不行)",
        ]
        for pattern in follow_up_patterns:
            if re.search(pattern, query):
                return True
        return False

    def get_dense_sparse_weights(self, intent: str) -> tuple[float, float]:
        """获取意图对应的 Dense-Sparse 检索权重。"""
        return INTENT_DENSE_SPARSE_WEIGHTS.get(intent, (0.55, 0.45))


_intent_classifier: IntentClassifier | None = None


def get_intent_classifier() -> IntentClassifier:
    """返回意图分类器单例。"""
    global _intent_classifier
    if _intent_classifier is None:
        _intent_classifier = IntentClassifier()
    return _intent_classifier
