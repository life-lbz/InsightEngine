"""Sprint 7 工厂验收（生产级增强：健康检查 + 降级提示）。"""
from __future__ import annotations

import argparse
import json
import sys

from core.rag_engine import RagEngine
from core.runtime import load_config
from factory.component_factory import (
    create_llm,
    create_vector_store,
    health_check_all,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="教育答疑 RAG 系统命令行入口")
    parser.add_argument(
        "--question",
        default="Python 变量是什么",
        help="提问内容",
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="仅执行健康检查后退出",
    )
    parser.add_argument(
        "--course-id",
        default="",
        help="课程 ID（用于过滤检索范围）",
    )
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 健康检查
    if args.health_check:
        status = health_check_all(config)
        print(json.dumps(status, indent=2, ensure_ascii=False))
        sys.exit(0 if status.get("overall") else 1)

    # 创建组件
    vector_store = create_vector_store(config)
    llm = create_llm(config)

    print(f"向量库类型: {type(vector_store).__name__}")
    print(f"LLM 类型: {type(llm).__name__}")
    print(f"问题: {args.question}")
    print("-" * 60)

    # 执行问答
    engine = RagEngine(vector_store, llm)
    filters = {"course_id": args.course_id} if args.course_id else None
    result = engine.answer(args.question, top_k=5, filters=filters)

    print(f"答案: {result['answer']}")
    print(f"置信度: {result['confidence']:.2f}")
    print(f"降级: {'是' if result['degraded'] else '否'}")
    if result.get("error"):
        print(f"错误: {result['error']}")
    print(f"引用来源: {len(result['sources'])} 条")
    for i, src in enumerate(result["sources"]):
        print(f"  [{i + 1}] score={src.get('score', 0):.4f} "
              f"source={src.get('metadata', {}).get('source', 'unknown')}")


if __name__ == "__main__":
    main()