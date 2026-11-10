"""端到端RAG测试：WebSocket答疑流程验证。"""
import asyncio
import json
import sys

sys.path.insert(0, "d:/ProjectAll/vscode_case/InsightEngine/edu_backend")


async def test_rag_websocket():
    import websockets
    import httpx

    # 1. 登录
    login_resp = await httpx.AsyncClient().post(
        "http://127.0.0.1:8000/api/v1/auth/login",
        json={"username": "student", "password": "student123"},
        timeout=10,
    )
    token = login_resp.json()["access_token"]
    print("1. Login: SUCCESS")

    # 2. 连接WebSocket
    ws_url = f"ws://127.0.0.1:8000/api/v1/stream?token={token}"
    print("2. WebSocket connecting...")

    async with websockets.connect(ws_url) as ws:
        ready = json.loads(await ws.recv())
        print(f"3. Connected: {ready}")

        # 3. 发送问题
        question = "Python 变量是什么？"
        await ws.send(json.dumps({
            "type": "query",
            "question": question,
            "session_id": "test-rag-002",
            "course_id": "default_course",
        }))
        print(f"4. Question sent: {question}")

        # 4. 接收所有响应
        messages = []
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=120)
                data = json.loads(msg)
                messages.append(data)
                msg_type = data.get("type")
                print(f"5. Received type={msg_type}")

                if msg_type == "end":
                    sep = "=" * 60
                    print(f"\n{sep}")
                    print("RAG ANSWER:")
                    print(sep)
                    answer = data.get("answer", "")
                    print(f"Answer: {answer[:600]}")
                    print(f"Sources: {len(data.get('sources', []))} items")
                    print(f"Confidence: {data.get('confidence')} ({data.get('confidence_level')})")
                    print(f"Intent: {data.get('intent')}")
                    print(f"Degraded: {data.get('degraded')}")
                    print(sep)
                    break
                elif msg_type == "error":
                    print(f"ERROR: {data.get('error')}")
                    break
                else:
                    print(f"   Detail: {data}")
        except asyncio.TimeoutError:
            print(f"TIMEOUT after 120s. Received {len(messages)} messages.")
        except Exception as e:
            print(f"Exception: {type(e).__name__}: {e}")

    print(f"\nTotal messages: {len(messages)}")


if __name__ == "__main__":
    asyncio.run(test_rag_websocket())
