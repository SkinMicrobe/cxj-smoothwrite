"""Model-independent prompt assembly and article generation interfaces."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ArticlePlan, ArticleSection, FigurePlan, PaperMetadata, ParsedPDF

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_CHINESE_NUMERALS = (
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "九",
    "十",
)


class LLMClient:
    """Minimal interface implemented by any future LLM provider adapter."""

    def generate(self, prompt: str) -> str:
        """Generate text from a fully assembled prompt."""
        raise NotImplementedError


class EchoLLMClient(LLMClient):
    """Placeholder client that returns recognizable non-production content."""

    def generate(self, prompt: str) -> str:
        """Return a deterministic placeholder response."""
        return (
            "# EchoLLMClient 占位输出\n\n"
            "当前使用 EchoLLMClient，未调用真实语言模型。\n\n"
            f"已接收 prompt，共 {len(prompt)} 个字符。"
        )


def load_prompt_template(name: str) -> str:
    """Load a Markdown prompt template from the project prompts directory."""
    prompt_name = name if name.endswith(".md") else f"{name}.md"
    prompt_path = (_PROMPTS_DIR / prompt_name).resolve()

    if prompt_path.parent != _PROMPTS_DIR.resolve():
        raise ValueError(f"Invalid prompt template name: {name}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template does not exist: {prompt_path}")
    if not prompt_path.is_file():
        raise ValueError(f"Prompt template path is not a file: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")


def _model_json(model: object) -> str:
    """Serialize a Pydantic model as readable JSON for prompt injection."""
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )


def build_article_writer_prompt(
    metadata: PaperMetadata,
    parsed_pdf: ParsedPDF,
    article_plan: ArticlePlan,
    figure_plan: FigurePlan,
) -> str:
    """Build the complete prompt used to generate article Markdown."""
    template = (
        load_prompt_template("system_style")
        + "\n\n---\n\n"
        + load_prompt_template("article_writer")
    )
    return (
        template.replace("{{paper_metadata_json}}", _model_json(metadata))
        .replace("{{article_plan_json}}", _model_json(article_plan))
        .replace("{{figure_plan_json}}", _model_json(figure_plan))
        .replace("{{parsed_pdf_json}}", _model_json(parsed_pdf))
        .replace("{{reference_article}}", "未提供参考范文。")
        .replace("{{target_word_count}}", "未指定目标字数。")
    )


def _section_heading(index: int, heading: str) -> str:
    """Ensure fallback section headings use Chinese numeral prefixes."""
    stripped = heading.strip()
    if stripped.startswith(tuple(f"{number}、" for number in _CHINESE_NUMERALS)):
        return stripped
    numeral = _CHINESE_NUMERALS[index] if index < len(_CHINESE_NUMERALS) else str(index + 1)
    return f"{numeral}、{stripped}"


def _figure_marker(label: str, source_figure: str) -> str:
    """Build a standard smoothwrite figure marker."""
    return f"{label}｜{source_figure}"


def _fallback_article_markdown(
    metadata: PaperMetadata,
    article_plan: ArticlePlan,
    figure_plan: FigurePlan,
) -> str:
    """Create a structurally complete, deliberately brief fallback article."""
    title = article_plan.title.strip() or "待补充期刊｜待补充研究对象：待补充核心发现"
    year = metadata.year or "待核查年份"
    month = metadata.month or "待核查月份"
    journal = metadata.journal or "待核查期刊"
    team = f"{metadata.authors[0]}团队" if metadata.authors else "待核查团队"
    paper_title = metadata.title or "待核查英文论文标题"

    lines = [
        f"# {title}",
        "",
        (
            f"{year}年{month}，{team}在《{journal}》发表题为 "
            f"*{paper_title}* 的研究论文。本文为流程占位稿，具体事实、"
            "证据强度和结论边界仍需依据原论文人工核查。"
        ),
        "",
    ]

    sections = article_plan.sections or [
        ArticleSection(
            heading="核心证据仍需补充",
            core_point=article_plan.main_thesis,
            figure_label=None,
        )
    ]

    used_labels: set[str] = set()
    for index, section in enumerate(sections):
        heading = _section_heading(index, section.heading)
        lines.extend(
            [
                f"## {heading}",
                "",
                section.core_point,
                "",
                "1）本节内容根据文章逻辑骨架生成，需补充论文中的关键证据。",
                "",
                "2）涉及机制与因果关系的表述需结合原文进一步核查。",
                "",
            ]
        )

        for figure in figure_plan.figures:
            matches_label = section.figure_label and figure.label == section.figure_label
            matches_section = figure.placement_after_section in {section.heading, heading}
            if figure.label not in used_labels and (matches_label or matches_section):
                lines.extend(
                    [
                        _figure_marker(figure.label, figure.source_figure),
                        "",
                    ]
                )
                used_labels.add(figure.label)

    for figure in figure_plan.figures:
        if figure.label not in used_labels:
            lines.extend(
                [
                    _figure_marker(figure.label, figure.source_figure),
                    "",
                ]
            )

    authors = metadata.authors[0] if metadata.authors else "待核查作者"
    lines.extend(
        [
            "## 总结",
            "",
            article_plan.main_thesis,
            "",
            (
                "这项研究的价值需要放回其证据链和适用边界中理解。"
                "当前占位稿仅提供完整文章结构，发布前仍需补充细节并完成事实核查。"
            ),
            "",
            f"论文信息：{authors} et al., {journal}, {year}。",
        ]
    )
    if metadata.url:
        lines.extend(["", f"原文链接：{metadata.url}"])

    return "\n".join(lines).rstrip() + "\n"


def generate_article_markdown(
    metadata: PaperMetadata,
    parsed_pdf: ParsedPDF,
    article_plan: ArticlePlan,
    figure_plan: FigurePlan,
    llm_client: LLMClient,
) -> str:
    """Generate article Markdown with an LLM client or deterministic fallback."""
    if llm_client is None or isinstance(llm_client, EchoLLMClient):
        return _fallback_article_markdown(metadata, article_plan, figure_plan)

    prompt = build_article_writer_prompt(
        metadata=metadata,
        parsed_pdf=parsed_pdf,
        article_plan=article_plan,
        figure_plan=figure_plan,
    )
    article = llm_client.generate(prompt)
    if not article or not article.strip():
        return _fallback_article_markdown(metadata, article_plan, figure_plan)
    return article.strip() + "\n"
