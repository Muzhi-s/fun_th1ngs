from __future__ import annotations

import json
import re
import ast
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

# 入口函数
def render_answer_result(selected_path: str, result: dict[str, Any]) -> None:
    metadata = _dict_value(result.get("metadata"))
    risk = _dict_value(result.get("risk"))
    analysis = _dict_value(result.get("analysis"))
    answer = _normalize_answer(selected_path, metadata, risk, analysis)

    components.html(_build_card_html(answer), height=680, scrolling=False)

    if result.get("cache_hit"):
        st.caption("本次结果来自本地缓存。")

# 数据标准化
def _normalize_answer(
    selected_path: str,
    metadata: dict[str, Any],
    risk: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, str]:
    content = _clean_model_text(analysis.get("content"))
    parsed = _try_parse_json(content) or _parse_labeled_text(content) or {}

    full_path = str(metadata.get("path") or selected_path)
    file_name = str(metadata.get("name") or Path(full_path).name or "未知文件")
    company = _text_or(metadata.get("company_name"), "未知发布方")
    product = _text_or(metadata.get("product_name"), "未知产品")
    description = _text_or(metadata.get("file_description"), "暂无可用描述")
    version = _text_or(metadata.get("version"), "版本未知")

    # 风险等级英文→中文映射
    risk_en = str(risk.get("risk_level", "unknown")).casefold()
    risk_level_cn = _risk_level_to_chinese(risk_en)
    rule_reason = _text_or(risk.get("reason"), "未命中明确规则")

    # 翻译成中文
    summary = _translate_to_chinese(_text_or(parsed.get("summary"), ""))
    purpose = _translate_to_chinese(_text_or(parsed.get("purpose"), ""))
    risk_field = _translate_to_chinese(_text_or(parsed.get("risk"), ""))
    advice = _translate_to_chinese(_text_or(parsed.get("advice"), ""))
    confidence = _text_or(parsed.get("confidence"), "")

    # 如果模型给出的是显式不确定，则回退到更稳定的本地信息
    if _is_uncertain_text(summary):
        summary = _fallback_summary(file_name, company, risk_level_cn)
    if not purpose or _is_uncertain_text(purpose):
        purpose = _fallback_purpose(description)
    if _is_uncertain_text(advice):
        advice = _fallback_advice(risk_level_cn, rule_reason)
    if _is_uncertain_text(risk_field):
      risk_field = risk_level_cn
    if _is_uncertain_text(confidence):
      confidence = "中等(模型判断结果可能不够准确，请谨慎处理)"
    if not confidence:
      confidence = "中等(模型判断结果可能不够准确，请谨慎处理)"


    # 从各数据源中提取信息，构建标准化的回答字典
    return {
        "status": _status_text(advice, risk_level_cn),
        "status_class": _status_class(advice, risk_level_cn),
        "summary": summary,
        "file_name": file_name,
        "mini_path": _compact_path(full_path),
        "full_path": full_path,
        "company": company,
        "product": product,
        "description": description,
        "version": version,
        "purpose": purpose,
        "advice": advice,
        "risk": risk_field,
        "confidence": confidence,
        "confidence_class": _confidence_class(confidence),
    }

def _risk_level_to_chinese(risk_en: str) -> str:
    """将英文风险等级转为中文"""
    mapping = {
        "high": "高风险",
        "medium": "中风险",
        "low": "低风险",
        "unknown": "未知风险",
        "danger": "高风险",
        "safe": "低风险",
    }
    return mapping.get(risk_en.casefold(),risk_en)

def _translate_to_chinese(text: str) -> str:
    """将常见的英文AI回答片段翻译为中文"""
    if not text:
        return ""
    #常见文件类型描述翻译
    translations = {
        "summary": "概要",
        "purpose": "用途",
        "risk": "风险",
        "advice": "建议",
        "confidence": "置信度",
        "unknown": "未知",
        "high risk": "高风险",
        "medium risk": "中风险",
        "low risk": "低风险",
        "delete advice": "删除建议",
        "keep advice": "保留建议",
    }
    for eng, chi in translations.items():
        text = re.sub(rf"\b{re.escape(eng)}\b", chi, text, flags=re.IGNORECASE)
    return text


# HTML卡片
def _build_card_html(answer: dict[str, str]) -> str:
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}
    body {{
      background: transparent;
      color: #1e1f22;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      padding: 2px;
    }}
    .card {{
      width: 100%;
      background: #ffffff;
      border: 1px solid #edf0f5;
      border-radius: 28px;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.02);
      padding: 34px 38px 36px;
    }}
    .status-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 28px;
      border-bottom: 1px solid #eef0f3;
      padding-bottom: 18px;
    }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: #f0f2f5;
      padding: 6px 16px 6px 12px;
      border-radius: 40px;
      font-size: 0.85rem;
      font-weight: 600;
      color: #3e4046;
      white-space: nowrap;
    }}
    .dot {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #f7b731;
      box-shadow: 0 0 0 2px rgba(247, 183, 49, 0.2);
    }}
    .status-safe .dot {{
      background: #2e9b6b;
      box-shadow: 0 0 0 2px rgba(46, 155, 107, 0.15);
    }}
    .status-risk .dot {{
      background: #d65f5f;
      box-shadow: 0 0 0 2px rgba(214, 95, 95, 0.15);
    }}
    .file-path-mini {{
      margin-left: auto;
      min-width: 0;
      max-width: 46%;
      font-size: 0.75rem;
      color: #8e929b;
      background: #f2f4f8;
      padding: 5px 14px;
      border-radius: 40px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .conclusion-block {{
      margin-bottom: 26px;
    }}
    .file-title {{
      font-size: 1.55rem;
      font-weight: 700;
      color: #141518;
      line-height: 1.34;
      margin-bottom: 8px;
      overflow-wrap: anywhere;
    }}
    .file-sub {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 7px 14px;
      font-size: 0.93rem;
      color: #5a5e66;
      line-height: 1.5;
    }}
    .version-tag {{
      background: #f0f2f5;
      padding: 3px 12px;
      border-radius: 20px;
      font-size: 0.8rem;
      font-weight: 600;
      color: #3e4046;
    }}
    .divider-light {{
      margin: 24px 0 28px;
      border: 0;
      height: 1px;
      background: linear-gradient(to right, #e6e9ef, #ffffff);
    }}
    .action-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 28px;
    }}
    .action-item {{
      background: #f7f9fc;
      border-radius: 18px;
      padding: 18px 20px 20px;
      border: 1px solid #edf0f5;
    }}
    .action-label {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.85rem;
      font-weight: 700;
      color: #2d2f34;
      margin-bottom: 9px;
    }}
    .icon-dot {{
      width: 18px;
      height: 18px;
      border-radius: 50%;
      display: inline-block;
      background: #dbe3ee;
      border: 5px solid #eef2f7;
      flex: 0 0 auto;
    }}
    .action-desc {{
      font-size: 0.9rem;
      line-height: 1.58;
      color: #3e4149;
      overflow-wrap: anywhere;
    }}
    .tag-safe,
    .tag-warning {{
      display: inline-block;
      margin-top: 10px;
      padding: 3px 12px;
      border-radius: 40px;
      font-size: 0.72rem;
      font-weight: 700;
    }}
    .tag-safe {{
      background: #e3f0ea;
      color: #1e6f4f;
    }}
    .tag-warning {{
      background: #fef1e6;
      color: #b45a2c;
    }}
    .evidence {{
      background: #f7f9fc;
      border-radius: 20px;
      padding: 18px 22px 22px;
      border: 1px solid #eaedf2;
    }}
    .evidence-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      font-size: 0.86rem;
      font-weight: 700;
      color: #3b3e45;
      margin-bottom: 14px;
    }}
    .evidence-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .evidence-row {{
      display: grid;
      grid-template-columns: 84px minmax(0, 1fr);
      gap: 10px;
      align-items: start;
      font-size: 0.9rem;
      color: #2d3037;
      line-height: 1.5;
    }}
    .label {{
      font-weight: 600;
      color: #6b707a;
      font-size: 0.8rem;
    }}
    .value {{
      color: #1e1f22;
      font-weight: 500;
      overflow-wrap: anywhere;
    }}
    .muted {{
      color: #7c818c;
      font-weight: 400;
    }}
    .confidence-tag {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      background: #eef1f6;
      padding: 5px 14px 5px 12px;
      border-radius: 40px;
      font-size: 0.75rem;
      font-weight: 600;
      color: #3c4049;
      margin-top: 18px;
      max-width: 100%;
    }}
    .bar {{
      display: inline-block;
      width: 48px;
      height: 4px;
      background: #d0d6e0;
      border-radius: 10px;
      overflow: hidden;
      flex: 0 0 auto;
    }}
    .fill {{
      display: block;
      height: 100%;
      width: 62%;
      background: #8b9bb5;
      border-radius: 10px;
    }}
    .confidence-high .fill {{
      width: 88%;
      background: #2e9b6b;
    }}
    .confidence-medium .fill {{
      width: 65%;
      background: #d69a2d;
    }}
    .confidence-low .fill {{
      width: 38%;
      background: #8b9bb5;
    }}
    .card-footer-note {{
      margin-top: 16px;
      font-size: 0.7rem;
      color: #9398a3;
      text-align: right;
      border-top: 1px solid #f0f2f6;
      padding-top: 16px;
    }}
    @media (max-width: 680px) {{
      .card {{
        padding: 26px 20px 30px;
        border-radius: 24px;
      }}
      .action-grid {{
        grid-template-columns: 1fr;
      }}
      .file-title {{
        font-size: 1.35rem;
      }}
      .status-header {{
        align-items: flex-start;
        flex-direction: column;
      }}
      .file-path-mini {{
        margin-left: 0;
        max-width: 100%;
      }}
      .evidence-row {{
        grid-template-columns: 1fr;
        gap: 2px;
      }}
      .confidence-tag {{
        align-items: flex-start;
        flex-wrap: wrap;
      }}
    }}
  </style>
</head>
<body>
  <article class="card">
    <header class="status-header {escape(answer["status_class"])}">
      <span class="status-badge"><span class="dot"></span>{escape(answer["status"])}</span>
      <span class="file-path-mini" title="{escape(answer["full_path"])}">{escape(answer["mini_path"])}</span>
    </header>

    <section class="conclusion-block">
      <h1 class="file-title">{escape(answer["summary"])}</h1>
      <div class="file-sub">
        <span>{escape(answer["file_name"])}</span>
        <span class="version-tag">{escape(answer["product"])}</span>
        <span>{escape(answer["company"])}</span>
        <span class="muted">{escape(answer["version"])}</span>
      </div>
    </section>

    <hr class="divider-light">

    <section class="action-grid">
      <div class="action-item">
        <div class="action-label"><span class="icon-dot"></span>这个文件可能是做什么的</div>
        <div class="action-desc">{escape(answer["purpose"])}</div>
        <span class="tag-safe">用途概括</span>
      </div>
      <div class="action-item">
        <div class="action-label"><span class="icon-dot"></span>你现在该怎么处理</div>
        <div class="action-desc">{escape(answer["advice"])}</div>
        <span class="tag-warning">删除建议</span>
      </div>
    </section>

    <section class="evidence">
      <div class="evidence-header">
        <span>判断依据</span>
        <span class="muted">仅保留用户需要的信息</span>
      </div>
      <div class="evidence-list">
        <div class="evidence-row"><span class="label">风险判断</span><span class="value">{escape(answer["risk"])}</span></div>
        <div class="evidence-row"><span class="label">发布方</span><span class="value">{escape(answer["company"])}</span></div>
        <div class="evidence-row"><span class="label">产品描述</span><span class="value">{escape(answer["description"])}</span></div>
      </div>
      <div class="confidence-tag {escape(answer["confidence_class"])}">
        <span>置信度</span>
        <span class="bar"><span class="fill"></span></span>
        <span>{escape(answer["confidence"])}</span>
      </div>
    </section>

    <footer class="card-footer-note">分析基于本地文件信息和模型判断，重要系统文件请谨慎处理</footer>
  </article>
</body>
</html>
"""


def _dict_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _try_parse_json(content: str) -> dict[str, Any] | None:
    if not content:
        return None

    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        fragment = _extract_json_fragment(content)
        if fragment is None:
            return None
        try:
            value = json.loads(fragment)
        except json.JSONDecodeError:
            return None

    return value if isinstance(value, dict) else None

# 标签文本解析
def _parse_labeled_text(text: str) -> dict[str, str] | None:
    if not text:
        return None

    label_map = {
        "summary": ("summary", "概要", "总结", "结论","文件简介"),
        "purpose": ("purpose", "用途", "文件用途", "作用","主要作用"),
        "risk": ("risk", "风险", "风险判断", "安全性"),
        "advice": ("advice", "删除建议", "建议", "deletion advice","处理建议"),
        "confidence": ("confidence", "置信度", "可信度","自信度"),
    }
    labels = [label for values in label_map.values() for label in values]
    label_pattern = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    # 正则表达式匹配标签和对应的值，支持多行文本
    pattern = re.compile(
        rf"(?im)^\s*(?:[-*]\s*)?(?P<label>{label_pattern})\s*[:：]\s*(?P<value>.*?)(?=^\s*(?:[-*]\s*)?(?:{label_pattern})\s*[:：]|\Z)",
        re.DOTALL,
    )

    result: dict[str, str] = {}
    for match in pattern.finditer(text):
        raw_label = match.group("label").casefold()
        value = match.group("value").strip()
        for key, possible_labels in label_map.items():
            if raw_label in [label.casefold() for label in possible_labels]:
                result[key] = value
                break

    if result:
        return result

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {"summary": lines[0]} if lines else None


def _extract_json_fragment(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]

# 清理模型输出
def _clean_model_text(content: object) -> str:
    text = str(content or "").strip()
    if not text:
        return ""

    text = _extract_cached_message_content(text) or text
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    return text.replace("```", "").strip()


def _extract_cached_message_content(text: str) -> str | None:
    """恢复被缓存的消息内容，通常是一个字符串字面量"""

    match = re.search(r"\bcontent=(?P<quote>['\"])", text)
    if match is None:
        return None

    quote = match.group("quote")
    start = match.start("quote")
    index = start + 1
    escaped = False
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            literal = text[start : index + 1]
            try:
                value = ast.literal_eval(literal)
            except (SyntaxError, ValueError):
                return None
            return str(value).strip()
        index += 1

    return None


def _text_or(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _is_uncertain_text(text: object) -> bool:
  normalized = str(text or "").strip().casefold()
  return normalized in {"不确定", "unknown", "uncertain", "n/a", "na", "null", "none"}


def _fallback_summary(file_name: str, company: str, risk_level: str) -> str:
    return f"{file_name} 来自 {company}，当前风险判断为 {risk_level}"


def _fallback_advice(risk_level: str, rule_reason: str) -> str:
    normalized = risk_level.casefold()
    if "高风险" in normalized or "danger" in normalized:
        return f"暂不建议直接删除。{rule_reason}"
    if "低风险" in normalized or "safe" in normalized:
        return f"通常可以删除，但请先确认它不是你正在使用的软件组件。{rule_reason}"
    return f"建议先保留，确认来源和用途后再处理。{rule_reason}"


def _fallback_purpose(description: str) -> str:
  text = str(description or "").strip()
  if not text:
    return "不确定"

  normalized = text.casefold()
  if normalized in {"unknown", "uncertain", "n/a", "na", "null", "none"}:
    return "不确定"

  return text


def _status_text(advice: object, risk_level: str) -> str:
    combined = f"{advice or ''} {risk_level}"
    if "删除" in combined or "delete" in combined.casefold():
        return "可以考虑清理"
    if "保留" in combined or "keep" in combined.casefold():
        return "建议先保留"
    if "high" in combined or "danger" in combined.casefold():
        return "谨慎处理"
    return "需要确认"


def _status_class(advice: object, risk_level: str) -> str:
    combined = f"{advice or ''} {risk_level}"
    if "删除" in combined or "delete" in combined.casefold() or "低风险" in combined or "safe" in combined.casefold():
        return "status-safe"
    if "高风险" in combined or "danger" in combined.casefold() or "谨慎" in combined:
        return "status-risk"
    return "status-unknown"


def _confidence_class(confidence: object) -> str:
    text = str(confidence or "").strip()
    if any(token in text for token in ("高", "high", "90", "95","98")):
        return "confidence-high"
    if any(token in text for token in ("低", "low", "50", "60","30")):
        return "confidence-low"
    return "confidence-medium"


def _compact_path(path: str) -> str:
    normalized = path.replace("/", "\\")
    parts = [part for part in normalized.split("\\") if part]
    if len(parts) >= 2:
        return "\\".join(parts[-2:])
    return normalized
