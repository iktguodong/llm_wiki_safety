"""内置安全生产 PPT 模板。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SafetyTemplate:
    template_id: str
    name: str
    theme_colors: dict[str, str]
    font_family_cn: str
    font_family_en: str
    title_size: int
    body_size: int
    footer_style: str
    slide_layout_rules: dict[str, str]
    warning_colors: dict[str, str]


TEMPLATES: dict[str, SafetyTemplate] = {
    "standard_training": SafetyTemplate(
        template_id="standard_training",
        name="标准安全培训",
        theme_colors={
            "bg": "#FFFFFF",
            "title": "#0F172A",
            "body": "#334155",
            "accent": "#F97316",
            "primary": "#1D4ED8",
            "success": "#16A34A",
            "danger": "#DC2626",
            "border": "#E2E8F0",
        },
        font_family_cn="Microsoft YaHei",
        font_family_en="Arial",
        title_size=28,
        body_size=16,
        footer_style="由安牛生成",
        slide_layout_rules={"density": "medium", "emphasis": "clear", "tone": "professional"},
        warning_colors={"normal": "#1D4ED8", "attention": "#F97316", "warning": "#DC2626", "critical": "#991B1B"},
    ),
    "management_briefing": SafetyTemplate(
        template_id="management_briefing",
        name="管理层汇报",
        theme_colors={
            "bg": "#FFFFFF",
            "title": "#0F172A",
            "body": "#334155",
            "accent": "#2563EB",
            "primary": "#0F172A",
            "success": "#16A34A",
            "danger": "#DC2626",
            "border": "#CBD5E1",
        },
        font_family_cn="Microsoft YaHei",
        font_family_en="Arial",
        title_size=30,
        body_size=15,
        footer_style="安牛安全汇报",
        slide_layout_rules={"density": "low", "emphasis": "conclusion_cards", "tone": "executive"},
        warning_colors={"normal": "#2563EB", "attention": "#D97706", "warning": "#B91C1C", "critical": "#7F1D1D"},
    ),
    "frontline_shift_training": SafetyTemplate(
        template_id="frontline_shift_training",
        name="班组宣贯",
        theme_colors={
            "bg": "#FFFFFF",
            "title": "#0F172A",
            "body": "#334155",
            "accent": "#EA580C",
            "primary": "#1D4ED8",
            "success": "#16A34A",
            "danger": "#DC2626",
            "border": "#E2E8F0",
        },
        font_family_cn="PingFang SC",
        font_family_en="Arial",
        title_size=32,
        body_size=18,
        footer_style="安牛班组培训",
        slide_layout_rules={"density": "low", "emphasis": "one_action_per_slide", "tone": "actionable"},
        warning_colors={"normal": "#1D4ED8", "attention": "#EA580C", "warning": "#DC2626", "critical": "#991B1B"},
    ),
}


def get_template(template_id: str | None) -> SafetyTemplate:
    if template_id and template_id in TEMPLATES:
        return TEMPLATES[template_id]
    return TEMPLATES["standard_training"]
