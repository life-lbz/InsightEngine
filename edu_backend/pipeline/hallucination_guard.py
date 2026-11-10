"""幻觉检测器：校验 LLM 答案与检索上下文的一致性。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from config.settings import get_settings
from observability.logger import get_logger
from observability.metrics import hallucination_risk_total

logger = get_logger(__name__)


@dataclass
class HallucinationCheckResult:
    """幻觉检测结果。

    属性：
        risk_level：风险等级（low/medium/high）
        unsupported_claims：无依据声明列表
        risk_score：风险分（0.0~1.0）
    """

    risk_level: str
    unsupported_claims: list[str]
    risk_score: float


class HallucinationChecker:
    """幻觉检测器。

    检测项：
        1. 答案中的事实性声明（数字、日期、规则性语句）是否在上下文中出现
        2. 答案中是否包含上下文未提及的课程名称、章节编号、知识点名称
        3. 答案中是否包含"根据课程规定"等权威性声明但无对应上下文
    """

    def __init__(self) -> None:
        """初始化幻觉检测器。"""
        self.settings = get_settings()
        self.max_unsupported = self.settings.hallucination_max_unsupported_claims

    def check(
        self,
        answer: str,
        context_docs: list[dict[str, Any]],
        course_id: str = "",
    ) -> HallucinationCheckResult:
        """检测答案中的幻觉风险。

        入参：
            answer：LLM 生成的答案文本
            context_docs：检索到的上下文文档列表
            course_id：课程 ID

        返回：
            HallucinationCheckResult：检测结果
        """
        # 合并上下文文本
        context_text = " ".join(
            doc.get("text", "") for doc in context_docs
        ).lower()

        unsupported: list[str] = []

        # 1. 检测数字声明（如"需要 60 分及格"、"3 次补考机会"）
        number_claims = re.findall(
            r"(?:需要|要求|必须|总共|一共|至少|最多)\s*(\d+)\s*(?:分|次|个|题|小时|分钟|天)",
            answer,
        )
        for num in number_claims:
            if num not in context_text:
                unsupported.append(f"数字声明 '{num}' 在上下文中未找到依据")

        # 2. 检测日期声明
        date_claims = re.findall(
            r"(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2})",
            answer,
        )
        for date in date_claims:
            if date.lower() not in context_text:
                unsupported.append(f"日期声明 '{date}' 在上下文中未找到依据")

        # 3. 检测权威性声明
        authority_patterns = [
            r"根据课程规定[，,]?(.{5,50})",
            r"按照教育部门要求[，,]?(.{5,50})",
            r"学校政策规定[，,]?(.{5,50})",
        ]
        for pattern in authority_patterns:
            matches = re.findall(pattern, answer)
            for match in matches:
                if match.strip().lower() not in context_text:
                    unsupported.append(f"权威性声明 '{match.strip()[:30]}' 在上下文中未找到依据")

        # 4. 检测上下文未提及的专业术语
        terms = re.findall(r"[《「【](.+?)[》」】]", answer)
        for term in terms:
            if term.lower() not in context_text:
                unsupported.append(f"专业术语 '{term}' 在上下文中未找到依据")

        # 评估风险等级
        claim_count = len(unsupported)
        if claim_count >= self.max_unsupported:
            risk_level = "high"
            risk_score = min(1.0, claim_count / 5.0)
        elif claim_count > 0:
            risk_level = "medium"
            risk_score = claim_count / 5.0
        else:
            risk_level = "low"
            risk_score = 0.0

        if risk_level == "high":
            hallucination_risk_total.labels(course_id=course_id).inc()
            logger.warning(
                "hallucination_detected",
                course_id=course_id,
                risk_level=risk_level,
                unsupported_count=claim_count,
                claims=unsupported,
            )

        return HallucinationCheckResult(
            risk_level=risk_level,
            unsupported_claims=unsupported,
            risk_score=risk_score,
        )

    def should_degrade(
        self,
        result: HallucinationCheckResult,
    ) -> bool:
        """判断是否应降级为返回检索原文摘要。

        入参：
            result：检测结果

        返回：
            True 表示应降级
        """
        return result.risk_level == "high"