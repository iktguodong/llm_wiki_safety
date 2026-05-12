"""培训大纲生成。"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Optional

from backend.config import config
from backend.services.llm import llm_service
from .models import ContentPack, SourceRef, TrainingOutline, TrainingOutlineSection

ALLOWED_STYLES = {"standard_training", "management_briefing", "frontline_shift_training"}


def _coerce_style(value: str) -> str:
    return value if value in ALLOWED_STYLES else "standard_training"


def _as_dict(data: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        return dict(data.model_dump())
    if isinstance(data, dict):
        return dict(data)
    return dict(getattr(data, "__dict__", {}))


def _strip_fence(text: str) -> str:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    return cleaned


def _extract_json(text: str) -> dict[str, Any] | None:
    cleaned = _strip_fence(text)
    for start_char in ("{", "["):
        start = cleaned.find(start_char)
        if start == -1:
            continue
        try:
            value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    return None


def _default_sections(content_pack: ContentPack, settings: dict[str, Any]) -> list[TrainingOutlineSection]:
    refs = [ref for chunk in content_pack.chunks for ref in chunk.source_refs]
    if not refs and content_pack.sources and any(src.type == "prompt" for src in content_pack.sources):
        refs = []

    base_titles = [
        ("培训背景与目标", "明确培训的业务背景、风险场景和培训目标", ["为什么要学", "本次培训要解决什么问题"]),
        ("主要风险或管理要求", "说明关键风险、隐患和管理控制要求", ["重点风险点", "必须遵守的管理要求"]),
        ("关键制度/职责/流程", "梳理制度、职责分工和基本流程", ["谁负责", "按什么流程执行"]),
        ("作业或处置步骤", "讲清现场作业或应急处置步骤", ["先做什么", "遇到异常怎么办"]),
        ("管控措施与检查要点", "总结控制措施、检查清单和验证方法", ["工程/管理/个人防护", "检查什么"]),
        ("常见错误或典型情景", "展示常见误区、易错点和情景讨论", ["常见错误", "典型场景"]),
        ("测验与复盘", "通过测验检验掌握情况并复盘", ["核心知识点回顾", "小测验"]),
        ("行动清单", "形成培训后的行动清单和落实安排", ["培训后要落实什么", "行动清单"]),
    ]

    section_count = min(len(base_titles), max(4, int(settings.get("slide_count") or 8) // 2))
    minutes_each = max(1, int((content_pack.duration_minutes or 60) / max(1, section_count)))
    sections: list[TrainingOutlineSection] = []
    for idx, (title, goal, points) in enumerate(base_titles[:section_count]):
        section_refs = refs[idx::section_count][:3] if refs else []
        sections.append(
            TrainingOutlineSection(
                id=f"sec-{uuid.uuid4().hex[:8]}",
                title=title,
                goal=goal,
                key_points=points,
                estimated_minutes=minutes_each,
                source_refs=section_refs,
            )
        )
    return sections


def _build_prompt(content_pack: ContentPack, settings: dict[str, Any]) -> str:
    chunks_text = []
    for chunk in content_pack.chunks[:8]:
        refs = ", ".join((ref.title or ref.source_id or ref.source_type) for ref in chunk.source_refs[:3])
        chunks_text.append(f"### {chunk.title}\n来源：{refs}\n{chunk.text[:1500]}")
    content_preview = "\n\n".join(chunks_text)[:12000]
    return f"""
请基于以下输入材料生成安全生产培训大纲，输出严格 JSON，不要 Markdown，不要代码块。

要求：
- 优先依据输入材料，不编造企业事实
- 如果只有提示词，可以扩展通用培训结构，但不得伪造法规条款、企业制度、岗位职责或来源
- 大纲适合后续转成 PPT
- sections 至少 4 个，尽量与时长、页数匹配

输入设置：
{json.dumps(settings, ensure_ascii=False, indent=2)}

输入材料：
{content_preview}

请输出 JSON 对象，结构示例：
{{
  "title": "培训标题",
  "topic": "主题",
  "audience": "受众",
  "duration_minutes": 30,
  "style": "standard_training",
  "sections": [
    {{
      "title": "章节标题",
      "goal": "章节目标",
      "key_points": ["要点1", "要点2"],
      "estimated_minutes": 5
    }}
  ],
  "warnings": ["可选警告"]
}}
""".strip()


def _fallback_outline(content_pack: ContentPack, settings: dict[str, Any]) -> TrainingOutline:
    sections = _default_sections(content_pack, settings)
    warnings = list(content_pack.warnings)
    if not any(ref.source_type != "prompt" for chunk in content_pack.chunks for ref in chunk.source_refs):
        warnings.append("该内容主要由模型生成，未绑定企业原文来源")
    return TrainingOutline(
        id=f"ol-{uuid.uuid4().hex[:10]}",
        title=str(settings.get("topic") or content_pack.topic),
        topic=str(settings.get("topic") or content_pack.topic),
        audience=str(settings.get("audience") or content_pack.audience),
        duration_minutes=int(settings.get("duration_minutes") or content_pack.duration_minutes or 60),
        style=_coerce_style(str(settings.get("style") or "standard_training")),  # type: ignore[arg-type]
        sections=sections,
        warnings=warnings,
    )


async def generate_outline(content_pack: ContentPack, settings: Any, llm_client=llm_service) -> TrainingOutline:
    settings_dict = _as_dict(settings)
    style = str(settings_dict.get("style") or "standard_training")
    topic = str(settings_dict.get("topic") or content_pack.topic)
    audience = str(settings_dict.get("audience") or content_pack.audience)
    duration_minutes = int(settings_dict.get("duration_minutes") or content_pack.duration_minutes or 60)
    slide_count = int(settings_dict.get("slide_count") or 12)

    model_roles = config.get("models", {}).get("model_roles", {})
    model_id = model_roles.get("ppt_gen") or config.get("current_model_id")
    providers = config.get("models", {}).get("providers", [])
    model_available = False
    if model_id:
        for provider in providers:
            if any(model.get("id") == model_id for model in provider.get("models", [])) and provider.get("api_key"):
                model_available = True
                break

    if model_available:
        try:
            prompt = _build_prompt(content_pack, settings_dict)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是安全生产培训课程设计专家。请基于输入材料生成企业安全培训大纲。"
                        "要求：优先依据输入材料，不编造企业事实；如果只有用户主题提示，可以扩展通用培训结构，"
                        "但不得伪造法规条款、企业制度、岗位职责或来源；输出严格 JSON；适合后续转成 PPT。"
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            response = await llm_client.chat_sync(messages, model_id=model_id, temperature=0.2)
            data = _extract_json(response or "")
            if data:
                sections = []
                raw_sections = data.get("sections") or []
                source_refs = [ref for chunk in content_pack.chunks for ref in chunk.source_refs]
                for idx, section in enumerate(raw_sections):
                    if not isinstance(section, dict):
                        continue
                    refs = source_refs[idx::max(1, len(raw_sections))][:3]
                    sections.append(
                        TrainingOutlineSection(
                            id=f"sec-{uuid.uuid4().hex[:8]}",
                            title=str(section.get("title") or f"章节 {idx + 1}"),
                            goal=str(section.get("goal") or ""),
                            key_points=[str(p) for p in section.get("key_points", []) if str(p).strip()][:5],
                            estimated_minutes=int(section.get("estimated_minutes") or max(1, duration_minutes // max(1, len(raw_sections) or 1))),
                            source_refs=refs,
                        )
                    )
                if len(sections) >= 4:
                    warnings = list(content_pack.warnings) + [str(w) for w in data.get("warnings", []) if str(w).strip()]
                    if not any(ref.source_type != "prompt" for chunk in content_pack.chunks for ref in chunk.source_refs):
                        warnings.append("该内容主要由模型生成，未绑定企业原文来源")
                    return TrainingOutline(
                        id=f"ol-{uuid.uuid4().hex[:10]}",
                        title=str(data.get("title") or topic),
                        topic=str(data.get("topic") or topic),
                        audience=str(data.get("audience") or audience),
                        duration_minutes=int(data.get("duration_minutes") or duration_minutes),
                        style=_coerce_style(str(data.get("style") or style)),  # type: ignore[arg-type]
                        sections=sections,
                        warnings=warnings,
                    )
        except Exception as exc:
            content_pack.warnings.append(f"LLM 大纲生成失败，已回退到规则大纲：{str(exc)[:200]}")

    return _fallback_outline(content_pack, settings_dict)
