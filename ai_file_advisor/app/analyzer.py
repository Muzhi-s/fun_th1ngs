"""由Ollama驱动的AI文件顾问分析功能"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import requests

DEFAULT_MODEL = "qwen3:4b"
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "explain_prompt.txt"
OLLAMA_HOST = "http://127.0.0.1:11434" #指定 Ollama API 的主机地址

def analyze_with_ollama(
    file_metadata: dict[str, Any],
    risk_result: dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    chat_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """使用 Ollama 生成自然语言文件说明。"""

    messages = [
        {
            "role": "system",
            "content": (
                "你是 Windows 文件分析专家。请优先用中文输出，除专业术语外不要使用英文。"
                "必须严格遵守用户提示词中的 JSON 输出格式，只输出 JSON。"
            ),
        },
        {
            "role": "user",
            "content": _build_user_prompt(file_metadata, risk_result),
        },
    ]

    try:
        if chat_fn:
            # 优先使用外部注入的聊天函数，失败时回退到 HTTP API
            try:
                response = chat_fn(model=model, messages=messages)
                content = _extract_message_content(response)
            except Exception:
                content = _call_ollama_api(model, messages)
                response = None
        else:
            # 直接通过 HTTP API 调用 Ollama
            content = _call_ollama_api(model, messages)
            response = None  # HTTP API 模式没有原始响应对象
    except Exception as e:
        return {
            "model": model,
            "error": str(e),
            "content": f"调用 Ollama 失败: {type(e).__name__}: {e}",
            "raw_response": None,
        }

    return {
        "model": model,
        "messages": messages,
        "content": content,
        "raw_response": response,
    }

def _call_ollama_api(model: str, messages: list[dict[str, Any]]) -> str:
    """通过 Ollama HTTP API 调用模型"""
    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
        },
        timeout=600,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if "application/x-ndjson" in content_type:
        return _extract_streamed_content(response)

    try:
        data = response.json()
    except ValueError:
        return _extract_streamed_content(response)

    if "message" in data:
        return data["message"].get("content", "")

    return _extract_streamed_content(response)


def _extract_streamed_content(response: requests.Response) -> str:
    """从 Ollama 的 NDJSON 流式响应中提取完整内容。"""

    full_content = ""
    for line in response.iter_lines(decode_unicode=True):
        if line:
            chunk = json.loads(line)
            if "message" in chunk:
                full_content += chunk["message"].get("content", "")
            if chunk.get("done"):
                break
    return full_content

def _build_user_prompt(file_metadata: dict[str, Any], risk_result: dict[str, Any]) -> str:
    prompt = _load_prompt_template()
    filled_prompt = prompt
    replacements = {
        "{name}": str(file_metadata.get("name", "")),
        "{path}": str(file_metadata.get("path", "")),
        "{company}": str(file_metadata.get("company_name") or ""),
        "{product}": str(file_metadata.get("product_name") or ""),
        "{description}": str(file_metadata.get("file_description") or ""),
        "{risk}": str(risk_result.get("risk_level", "unknown")),
    }
    for placeholder, value in replacements.items():
        filled_prompt = filled_prompt.replace(placeholder, value)

    return filled_prompt 


@lru_cache(maxsize=1)
def _load_prompt_template() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "你是 Windows 文件分析专家。\n"
            "只能根据已提供信息分析，不允许猜测、补全或编造任何事实。\n"
            "你必须只输出 JSON，不能输出 Markdown 或多余内容。\n"
            "输出格式必须严格为以下 JSON 结构：\n"
            '{\n'
            '  "summary": "",\n'
            '  "purpose": "",\n'
            '  "risk": "",\n'
            '  "confidence": "",\n'
            '  "advice": ""\n'
            '}\n'
            "输入文件信息：\n"
            "- 文件名：{name}\n"
            "- 路径：{path}\n"
            "- 公司：{company}\n"
            "- 产品：{product}\n"
            "- 描述：{description}\n"
            "- 风险等级：{risk}\n"
            "请只基于以上信息输出 JSON。\n"
        )

def _extract_message_content(response: Any) -> str:
    """兼容新版和旧版 Ollama SDK"""

    # 新版 ollama SDK（ChatResponse）
    if hasattr(response, "message"):
        message = response.message
        if hasattr(message, "content"):
            return str(message.content or "")
        if isinstance(message, dict):
            return str(message.get("content") or "")

    # 旧版 SDK（dict）
    if isinstance(response, dict):
        message = response.get("message", {})
        if isinstance(message, dict):
            return str(message.get("content") or "")
        if hasattr(message, "content"):
            return str(message.content or "")

    return ""
