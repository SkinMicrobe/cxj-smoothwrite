"""Lightweight validation for smoothwrite articles and output artifacts."""

from __future__ import annotations

import re
from pathlib import Path

from .io_utils import load_default_config, read_json, read_text, write_text
from .models import FigurePlan

_TITLE_PATTERN = re.compile(r"^#\s+.+｜.+：.+$")
_SECTION_PATTERN = re.compile(r"^(?:#{1,6}\s*)?[一二三四五六七八九十百]+、.+$")
_FIGURE_MARKER_PATTERN = re.compile(
    r"^配图\d+\s*｜\s*(?:Figure|Fig\.?)\s*\d+",
    flags=re.IGNORECASE,
)
_PAPER_INFO_PATTERN = re.compile(r"^论文信息：", flags=re.MULTILINE)
_SOURCE_LINK_PATTERN = re.compile(r"^原文链接：", flags=re.MULTILINE)
_BAD_MARKERS = (
    (re.compile(r"-turn\d+`?", flags=re.IGNORECASE), "检测到内部网页引用标记，如 -turn0`。"),
    (re.compile(r"\[\d+\]"), "检测到论文引用编号，如 [1]。"),
    (re.compile(r"^\s*References\s*$", flags=re.IGNORECASE | re.MULTILINE), "检测到 References 标记。"),
)
_MARKETING_TERMS = ("震惊", "重磅", "颠覆", "太强了", "不看后悔")


def _nonempty_lines(article_md: str) -> list[str]:
    """Return stripped nonempty Markdown lines."""
    return [line.strip() for line in article_md.splitlines() if line.strip()]


def validate_article(article_md: str) -> list[str]:
    """Return basic structural and style issues found in article Markdown."""
    notes: list[str] = []
    lines = _nonempty_lines(article_md)

    if not lines or not lines[0].startswith("# "):
        notes.append("文章缺少第一行 Markdown 标题。")
    elif not _TITLE_PATTERN.match(lines[0]):
        notes.append("标题未大致符合“期刊｜...：...”格式。")

    first_section_index = next(
        (index for index, line in enumerate(lines) if _SECTION_PATTERN.match(line)),
        None,
    )
    introduction_lines = (
        lines[1:first_section_index]
        if first_section_index is not None
        else lines[1:]
    )
    introduction_lines = [
        line
        for line in introduction_lines
        if not _FIGURE_MARKER_PATTERN.match(line)
    ]
    if not introduction_lines:
        notes.append("文章缺少标题后的引言段落。")

    sections = [line for line in lines if _SECTION_PATTERN.match(line)]
    if not sections:
        notes.append("文章未使用中文数字分节。")
    for section in sections:
        heading = re.sub(r"^#{1,6}\s*", "", section)
        if len(heading) > 30:
            notes.append(f"小标题可能过长：{heading}")

    if not any(_FIGURE_MARKER_PATTERN.match(line) for line in lines):
        notes.append("文章未包含配图标记。")
    if not _PAPER_INFO_PATTERN.search(article_md):
        notes.append("文章缺少文末论文信息。")
    if not _SOURCE_LINK_PATTERN.search(article_md):
        notes.append("文章缺少原文链接。")

    for pattern, message in _BAD_MARKERS:
        if pattern.search(article_md):
            notes.append(message)

    for term in _MARKETING_TERMS:
        if term in article_md:
            notes.append(f"检测到营销化表达：{term}")

    return notes


def validate_outputs(output_dir: str) -> list[str]:
    """Validate required output files and FigurePlan image references."""
    output_path = Path(output_dir)
    output_config = load_default_config()["output"]
    notes: list[str] = []
    required_files = {
        output_config["article_md"]: "文章 Markdown",
        output_config["final_docx"]: "Word 成品",
        output_config["metadata_json"]: "论文元信息",
        output_config["figure_plan_json"]: "配图计划",
    }

    for filename, description in required_files.items():
        path = output_path / filename
        if not path.is_file():
            notes.append(f"缺少{description}文件：{path}")

    article_path = output_path / output_config["article_md"]
    if article_path.is_file():
        try:
            notes.extend(validate_article(read_text(article_path)))
        except Exception as exc:
            notes.append(f"无法读取 {output_config['article_md']}：{exc}")

    figure_plan_path = output_path / output_config["figure_plan_json"]
    if figure_plan_path.is_file():
        try:
            figure_plan = FigurePlan.model_validate(read_json(figure_plan_path))
        except Exception as exc:
            notes.append(
                f"无法读取或验证 {output_config['figure_plan_json']}：{exc}"
            )
        else:
            for figure in figure_plan.figures:
                if not figure.image_path:
                    notes.append(f"{figure.label} 未设置 image_path。")
                    continue
                image_path = Path(figure.image_path)
                if not image_path.is_absolute():
                    image_path = output_path / image_path
                if not image_path.is_file():
                    notes.append(
                        f"{figure.label} 引用的图片不存在：{image_path}"
                    )

    return notes


def write_review_notes(output_dir: str, notes: list[str]) -> str:
    """Append basic validation notes to review_notes.md and return its path."""
    output_path = Path(output_dir)
    review_name = load_default_config()["output"]["review_notes_md"]
    review_path = output_path / review_name
    existing = read_text(review_path).rstrip() if review_path.is_file() else ""

    section_lines = ["## 基础自动质检", ""]
    if notes:
        section_lines.extend(f"- {note}" for note in notes)
    else:
        section_lines.append("- 未发现基础结构或输出文件问题。")

    section = "\n".join(section_lines)
    if existing:
        content = existing + "\n\n" + section + "\n"
    else:
        content = "# smoothwrite 质量检查报告\n\n" + section + "\n"

    write_text(review_path, content)
    return str(review_path)
