"""调试脚本：查看 analyze_with_ollama 返回的 content 原文"""
import sys
from pathlib import Path

# 添加项目根目录到 sys.path（注意：项目根目录是 ai_file_advisor 的父目录）
project_root = Path(__file__).resolve().parents[1]  # tests 的上一级才是项目根目录
sys.path.insert(0, str(project_root))

from app.analyzer import analyze_with_ollama


def main():
    # 模拟 Navicat.exe 的文件元数据和风险结果
    file_metadata = {
        "name": "navicat.exe",
        "path": "D:\\MySQL\\Navicat Premium 12\\Navicat Premium 12\\navicat.exe",
        "company_name": "PremiumSoft CyberTech Ltd.",
        "product_name": "Navicat Premium",
        "file_description": "Navicat Premium 是一个数据库管理工具",
    }
    
    risk_result = {
        "risk_level": "low"
    }
    
    # 调用 analyze_with_ollama
    result = analyze_with_ollama(
        file_metadata=file_metadata,
        risk_result=risk_result,
        model="qwen3:4b"
    )
    
    # 打印完整的返回内容
    print("=" * 60)
    print("【返回的 content 原文】")
    print("=" * 60)
    print(repr(result["content"]))
    
    print("\n" + "=" * 60)
    print("【直接打印 content】")
    print("=" * 60)
    print(result["content"])
    
    print("\n" + "=" * 60)
    print("【messages 中 user 的最终 prompt】")
    print("=" * 60)
    if result.get("messages"):
        user_msg = result["messages"][1]["content"]
        print(user_msg)
    
    print("\n" + "=" * 60)
    print("【是否包含 error】")
    print("=" * 60)
    print(result.get("error", "无错误"))
    
    print("\n" + "=" * 60)
    print("【尝试解析 JSON】")
    print("=" * 60)
    import json
    try:
        parsed = json.loads(result["content"])
        print("✅ JSON 解析成功")
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        # 尝试提取代码块中的 JSON
        content = result["content"]
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            json_str = content[start:end].strip()
            print("\n尝试提取 ```json 块中的内容：")
            print(repr(json_str))
            try:
                parsed = json.loads(json_str)
                print("✅ 从代码块中提取 JSON 成功")
                print(json.dumps(parsed, ensure_ascii=False, indent=2))
            except:
                print("❌ 从代码块中提取 JSON 也失败")


if __name__ == "__main__":
    main()