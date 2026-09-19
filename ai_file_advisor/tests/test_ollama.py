import json

import requests

try:
    response = requests.post(
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": "qwen3:4b",
            "messages": [
                {"role": "user", "content": "你好"}
            ],
            "stream": False,
        },
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    full_content = payload.get("message", {}).get("content", "")

    print("✅ 调用成功！")
    print(full_content)
    
except Exception as e:
    print(f"❌ 调用失败: {type(e).__name__}: {e}")