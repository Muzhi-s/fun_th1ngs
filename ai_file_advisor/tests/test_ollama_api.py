import requests
import json

try:
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "qwen3:4b",
            "messages": [
                {"role": "user", "content": "你好"}
            ]
        },
        timeout=30
    )
    
    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    
    if response.status_code == 200:
        # 处理 streaming 响应
        full_content = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "message" in data:
                    full_content += data["message"].get("content", "")
                if data.get("done"):
                    break
        print(f"✅ 响应内容: {full_content}")
    else:
        print(f"❌ 响应内容: {response.text}")
        
except Exception as e:
    print(f"❌ 请求异常: {type(e).__name__}: {e}")