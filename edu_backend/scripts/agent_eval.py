"""Agent 路由评估：用 LLM 评判 Supervisor 路由正确性。

独立运行：python scripts/agent_eval.py
复用启发式评估风格（与 rag_eval.py 一致），不依赖 RAGAS。
"""
import asyncio
import sys
from pathlib import Path

CASES = [
    {
        "input": "解释 Python 列表推导式",
        "role": "student",
        "expected_keyword": "",
    },
    {
        "input": "给我几道函数练习题",
        "role": "student",
        "expected_keyword": "题",
    },
    {
        "input": "帮我规划下一步学习",
        "role": "student",
        "expected_keyword": "学习",
    },
]


async def eval_supervisor_routing(test_cases: list[dict]) -> float:
    correct = 0
    from core.agent_engine import agent_answer

    for tc in test_cases:
        try:
            result = await agent_answer(
                question=tc["input"],
                role=tc.get("role", "student"),
                course_id=tc.get("course_id", "default_course"),
                session_id="eval",
                user_id="eval_user",
            )
            answer = result.get("answer", "")
            keyword = tc.get("expected_keyword", "")
            if not keyword or keyword in answer:
                correct += 1
        except Exception as exc:
            print(f"case failed: {tc['input']} -> {exc}")
    return correct / len(test_cases) if test_cases else 0.0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    score = asyncio.run(eval_supervisor_routing(CASES))
    print(f"routing accuracy: {score:.0%}")
