"""Command-line interface for the smoothwrite pipeline."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .io_utils import load_default_config, read_text
from .models import OutputManifest

_SUMMARY_OUTPUTS = (
    ("公众号科研解读正文", "article_md", "article.md", False),
    ("Word 成品文档", "final_docx", "final.docx", False),
    ("论文元信息", "metadata_json", "paper_metadata.json", False),
    ("PDF 解析结果", "parsed_pdf_json", "parsed_pdf.json", False),
    ("文章结构规划", "article_plan_json", "article_plan.json", False),
    ("配图方案", "figure_plan_json", "figure_plan.json", False),
    ("Figure 图片目录", "figures_dir", "figures/", True),
    ("输出清单", "output_manifest_json", "output_manifest.json", False),
    ("人工检查提示", "review_notes_md", "review_notes.md", False),
)


def _summary_path(
    output_dir: Path,
    manifest: OutputManifest | None,
    manifest_field: str,
    relative_path: str,
) -> Path:
    """Resolve one summary artifact from the manifest or output directory."""
    manifest_value = getattr(manifest, manifest_field, None) if manifest else None
    if manifest_value:
        return Path(manifest_value)
    return output_dir / relative_path.rstrip("/")


def _review_signals(
    output_dir: Path,
    manifest: OutputManifest | None,
) -> tuple[bool, bool, bool]:
    """Detect fallback, crop-risk, and metadata-risk signals."""
    notes = list(manifest.review_notes) if manifest else []
    review_path = _summary_path(
        output_dir, manifest, "review_notes_md", "review_notes.md"
    )
    if review_path.is_file():
        try:
            notes.append(read_text(review_path))
        except OSError:
            pass

    text = "\n".join(notes).casefold()
    fallback = "fallback" in text
    crop_risk = (
        "crop confidence is failed" in text
        or "crop confidence is low" in text
        or ": failed。" in text
        or ": low。" in text
    )
    metadata_risk = any(
        marker in text
        for marker in (
            "uncertain or missing",
            "could not be",
            "was not found",
            "was not provided",
            "require manual review",
        )
    )
    return fallback, crop_risk, metadata_risk


def build_completion_summary(
    output_dir: str,
    manifest: OutputManifest | None = None,
) -> str:
    """Build the required Chinese summary from actual output artifacts."""
    output_path = Path(output_dir).resolve()
    generated: list[tuple[str, str]] = []
    missing: list[str] = []

    for description, field, relative_path, is_directory in _SUMMARY_OUTPUTS:
        path = _summary_path(output_path, manifest, field, relative_path)
        exists = path.is_dir() if is_directory else path.is_file()
        if exists:
            generated.append((description, relative_path))
        else:
            missing.append(relative_path)

    lines = ["在使用 smoothwrite skill 之后，我为你输出了：", ""]
    if generated:
        lines.extend(
            f"{index}、{description}：{relative_path}"
            for index, (description, relative_path) in enumerate(generated, start=1)
        )
    else:
        lines.append("当前没有确认已生成的输出文件。")

    if missing:
        lines.extend(["", "以下文件未能生成，需要检查："])
        lines.extend(
            f"{index}、{relative_path}"
            for index, relative_path in enumerate(missing, start=1)
        )

    fallback, crop_risk, metadata_risk = _review_signals(output_path, manifest)
    if fallback:
        lines.extend(
            [
                "",
                "需要注意：当前正文为 fallback 版本，主要用于验证流程和 Word 渲染，"
                "正式发布前仍需要使用完整写作模型生成或人工修订。",
            ]
        )
    if crop_risk:
        lines.extend(
            [
                "",
                "需要注意：部分 Figure 可能使用的是整页截图或低置信度裁剪图，"
                "建议发布前人工核对图片位置和清晰度。",
            ]
        )
    if metadata_risk:
        lines.extend(
            [
                "",
                "需要注意：论文标题、期刊、作者、年份、DOI 或原文链接中存在未能自动"
                "确认的信息，建议根据原文人工核对。",
            ]
        )

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build the smoothwrite command-line parser."""
    config = load_default_config()
    default_figure_count = int(config["article"]["default_figure_count"])
    parser = argparse.ArgumentParser(
        prog="smoothwrite",
        description=(
            "Prepare evidence for a Codex-assisted Chinese research interpretation "
            "and render the reviewed result as an editable Word document."
        ),
        epilog=(
            "Example:\n"
            "  smoothwrite run --pdf input/paper.pdf --url "
            "\"https://doi.org/xxxxx\" --output output/\n\n"
            "Use 'prepare', let Codex author the JSON/Markdown intermediates, then "
            "use 'finalize'. The legacy 'run' command remains for smoke tests only."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="{prepare,finalize,run}")

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Parse the paper and reference article for Codex-assisted writing.",
    )
    prepare_parser.add_argument("--pdf", required=True, help="Path to the input paper PDF.")
    prepare_parser.add_argument("--output", default="output", help="Output directory.")
    prepare_parser.add_argument("--reference-docx", help="Reference WeChat article DOCX.")
    prepare_parser.add_argument("--url", help="Original paper or DOI URL.")
    prepare_parser.add_argument("--journal", help="Journal name hint for metadata.")
    prepare_parser.add_argument("--year", help="Publication year hint.")
    prepare_parser.add_argument("--month", help="English publication month hint.")
    prepare_parser.add_argument(
        "--target-word-count",
        type=int,
        default=int(config["article"]["default_target_word_count"]),
    )
    prepare_parser.add_argument(
        "--target-section-count",
        type=int,
        default=int(config["article"]["default_section_count"]),
    )
    prepare_parser.add_argument(
        "--figure-count", type=int, default=default_figure_count
    )
    prepare_parser.add_argument("--no-crop", action="store_true")

    finalize_parser = subparsers.add_parser(
        "finalize",
        help="Validate agent-authored intermediates and render final.docx.",
    )
    finalize_parser.add_argument("--output", default="output", help="Prepared output directory.")
    run_parser = subparsers.add_parser(
        "run",
        help="Run the complete local fallback pipeline.",
        description=(
            "Generate parsed PDF data, metadata, figure assets, fallback plans, "
            "article.md, final.docx, review notes, and an output manifest."
        ),
        epilog=(
            "Example:\n"
            "  smoothwrite run --pdf input/paper.pdf --output output/ "
            "--journal \"Nature Microbiology\" --year 2026 --month June"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument("--pdf", required=True, help="Path to the input paper PDF.")
    run_parser.add_argument(
        "--output",
        default="output",
        help="Directory for all generated artifacts (default: output).",
    )
    run_parser.add_argument("--url", help="Original paper or DOI URL.")
    run_parser.add_argument("--journal", help="Journal name hint for metadata.")
    run_parser.add_argument("--year", help="Publication year hint.")
    run_parser.add_argument("--month", help="English publication month hint.")
    run_parser.add_argument(
        "--figure-count",
        type=int,
        default=default_figure_count,
        help=f"Maximum figures selected by fallback planning (default: {default_figure_count}).",
    )
    run_parser.add_argument(
        "--no-crop",
        action="store_true",
        help="Export full pages only; disable caption-position rough cropping.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the smoothwrite CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "prepare":
        try:
            from .pipeline import prepare_pipeline

            brief = prepare_pipeline(
                pdf_path=args.pdf,
                output_dir=args.output,
                reference_docx=args.reference_docx,
                target_word_count=args.target_word_count,
                target_section_count=args.target_section_count,
                figure_count=args.figure_count,
                url=args.url,
                journal_hint=args.journal,
                year_hint=args.year,
                month_hint=args.month,
                attempt_crop=not args.no_crop,
            )
        except Exception as exc:
            print(f"smoothwrite prepare failed: {exc}", file=sys.stderr)
            return 1
        print(
            "Preparation complete. Codex should now author article_plan.json, "
            "figure_plan.json, and article.md before running finalize."
        )
        print(
            f"Targets: {brief.target_word_count} Chinese characters, "
            f"{brief.target_section_count} sections, {brief.target_figure_count} figures."
        )
        return 0

    if args.command == "finalize":
        try:
            from .pipeline import finalize_pipeline

            manifest = finalize_pipeline(args.output)
        except Exception as exc:
            print(f"smoothwrite finalize failed: {exc}", file=sys.stderr)
            print(build_completion_summary(args.output))
            return 1
        print(build_completion_summary(manifest.output_dir, manifest))
        return 0

    if args.command == "run":
        if args.figure_count < 0:
            parser.error("--figure-count must be zero or greater.")

        try:
            from .pipeline import run_pipeline

            manifest = run_pipeline(
                pdf_path=args.pdf,
                output_dir=args.output,
                url=args.url,
                journal_hint=args.journal,
                year_hint=args.year,
                month_hint=args.month,
                figure_count=args.figure_count,
                attempt_crop=not args.no_crop,
            )
        except Exception as exc:
            print(f"smoothwrite failed: {exc}", file=sys.stderr)
            print(build_completion_summary(args.output))
            return 1

        print(build_completion_summary(manifest.output_dir, manifest))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
