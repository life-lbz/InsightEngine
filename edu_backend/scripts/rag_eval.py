"""RAG 效果评估脚本：Faithfulness / Relevance / Context Recall / Answer Correctness。

使用方式：
    python scripts/rag_eval.py --dataset eval_dataset.json
    python scripts/rag_eval.py --dataset eval_dataset.json --output eval_report.json

数据集格式（JSON）：
    [
        {
            "question": "Python 变量是什么？",
            "ground_truth": "变量是存储数据的容器...",
            "course_id": "default_course"
        },
        ...
    ]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from observability.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def load_dataset(path: str) -> list[dict[str, Any]]:
    """加载评估数据集。"""
    p = Path(path)
    if not p.exists():
        print(f"数据集文件不存在: {path}")
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def run_rag_pipeline(question: str, course_id: str) -> dict[str, Any]:
    """运行 RAG 管道获取答案。"""
    import asyncio
    from core.rag_engine import get_rag_pipeline

    pipeline = get_rag_pipeline()
    result = asyncio.run(
        pipeline.answer(question=question, course_id=course_id)
    )
    return result


def evaluate_with_ragas(
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str,
) -> dict[str, float]:
    """使用 RAGAS 库评估。"""
    try:
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from datasets import Dataset

        data = {
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],
            "ground_truth": [ground_truth],
        }
        ds = Dataset.from_dict(data)
        scores = evaluate(
            ds,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )
        return {
            "faithfulness": float(scores.get("faithfulness", 0)),
            "answer_relevancy": float(scores.get("answer_relevancy", 0)),
            "context_precision": float(scores.get("context_precision", 0)),
            "context_recall": float(scores.get("context_recall", 0)),
        }
    except ImportError:
        logger.warning("ragas_not_installed_fallback_to_heuristic")
        return evaluate_heuristic(question, answer, contexts, ground_truth)


def evaluate_heuristic(
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str,
) -> dict[str, float]:
    """启发式评估（RAGAS 不可用时的降级方案）。"""
    context_text = " ".join(contexts).lower()
    answer_lower = answer.lower()
    ground_truth_lower = ground_truth.lower()

    # Faithfulness：答案中的关键句是否在上下文中有依据
    answer_sentences = [s.strip() for s in answer.split("。") if len(s.strip()) > 10]
    if answer_sentences:
        supported = sum(
            1 for s in answer_sentences
            if any(word in context_text for word in s.split()[:5])
        )
        faithfulness = supported / len(answer_sentences)
    else:
        faithfulness = 0.0

    # Answer Relevancy：答案是否包含问题中的关键词
    question_words = [w for w in question.lower().split() if len(w) > 2]
    if question_words:
        relevant = sum(1 for w in question_words if w in answer_lower)
        answer_relevancy = relevant / len(question_words)
    else:
        answer_relevancy = 0.5

    # Context Recall：ground truth 的关键词是否在上下文中
    gt_words = [w for w in ground_truth_lower.split() if len(w) > 2]
    if gt_words:
        recalled = sum(1 for w in gt_words if w in context_text)
        context_recall = recalled / len(gt_words)
    else:
        context_recall = 0.5

    # Context Precision：上下文中与问题相关的比例
    if contexts:
        relevant_contexts = sum(
            1 for c in contexts
            if any(w in c.lower() for w in question_words)
        )
        context_precision = relevant_contexts / len(contexts)
    else:
        context_precision = 0.0

    return {
        "faithfulness": round(faithfulness, 4),
        "answer_relevancy": round(answer_relevancy, 4),
        "context_precision": round(context_precision, 4),
        "context_recall": round(context_recall, 4),
    }


def run_evaluation(dataset: list[dict[str, Any]]) -> dict[str, Any]:
    """运行完整评估。"""
    results: list[dict[str, Any]] = []
    total_scores: dict[str, list[float]] = {
        "faithfulness": [],
        "answer_relevancy": [],
        "context_precision": [],
        "context_recall": [],
    }

    for i, item in enumerate(dataset):
        question = item["question"]
        ground_truth = item.get("ground_truth", "")
        course_id = item.get("course_id", "default_course")

        logger.info("eval_item_start", index=i, question=question[:80])

        start = time.perf_counter()
        try:
            rag_result = run_rag_pipeline(question, course_id)
            answer = rag_result.get("answer", "")
            sources = rag_result.get("sources", [])
            contexts = [s.get("text", s.get("content", "")) for s in sources]
            degraded = rag_result.get("degraded", False)
        except Exception as exc:
            logger.error("eval_item_failed", index=i, error=str(exc)[:200])
            answer = ""
            contexts = []
            degraded = True

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        scores = evaluate_with_ragas(question, answer, contexts, ground_truth)
        for key, value in scores.items():
            total_scores[key].append(value)

        results.append({
            "index": i,
            "question": question,
            "answer": answer[:200],
            "ground_truth": ground_truth[:200],
            "scores": scores,
            "degraded": degraded,
            "elapsed_ms": elapsed_ms,
            "context_count": len(contexts),
        })

        print(f"  [{i + 1}/{len(dataset)}] faithfulness={scores['faithfulness']:.2f} "
              f"relevancy={scores['answer_relevancy']:.2f} "
              f"recall={scores['context_recall']:.2f} "
              f"({elapsed_ms}ms)")

    avg_scores = {
        key: round(sum(vals) / len(vals), 4) if vals else 0.0
        for key, vals in total_scores.items()
    }

    return {
        "total_questions": len(dataset),
        "average_scores": avg_scores,
        "degraded_count": sum(1 for r in results if r["degraded"]),
        "avg_latency_ms": int(sum(r["elapsed_ms"] for r in results) / len(results)) if results else 0,
        "details": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 效果评估脚本")
    parser.add_argument(
        "--dataset",
        default="tests/eval_dataset.json",
        help="评估数据集 JSON 文件路径",
    )
    parser.add_argument(
        "--output",
        default="eval_report.json",
        help="评估报告输出路径",
    )
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    print(f"加载评估数据集: {len(dataset)} 条")

    report = run_evaluation(dataset)

    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("RAG 评估报告")
    print("=" * 60)
    print(f"总问题数: {report['total_questions']}")
    print(f"降级次数: {report['degraded_count']}")
    print(f"平均延迟: {report['avg_latency_ms']}ms")
    print("-" * 60)
    print(f"Faithfulness:       {report['average_scores']['faithfulness']:.4f}")
    print(f"Answer Relevancy:   {report['average_scores']['answer_relevancy']:.4f}")
    print(f"Context Precision:  {report['average_scores']['context_precision']:.4f}")
    print(f"Context Recall:     {report['average_scores']['context_recall']:.4f}")
    print("=" * 60)
    print(f"报告已保存: {output_path.absolute()}")


if __name__ == "__main__":
    main()
