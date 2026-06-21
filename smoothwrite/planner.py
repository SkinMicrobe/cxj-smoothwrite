"""Build model-independent prompts for article and figure planning."""

from __future__ import annotations

import json

from .models import ArticlePlan, FigureAsset, PaperMetadata, ParsedPDF
from .writer import load_prompt_template


def _model_json(model: object) -> str:
    """Serialize a Pydantic model as readable JSON for prompt injection."""
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )


def _models_json(models: list[object]) -> str:
    """Serialize a list of Pydantic models as readable JSON."""
    return json.dumps(
        [model.model_dump(mode="json") for model in models],
        ensure_ascii=False,
        indent=2,
    )


def build_article_plan_prompt(
    metadata: PaperMetadata,
    parsed_pdf: ParsedPDF,
    writing_requirements: str | None = None,
) -> str:
    """Build the prompt used to generate an ArticlePlan JSON object."""
    template = (
        load_prompt_template("system_style")
        + "\n\n---\n\n"
        + load_prompt_template("article_planner")
    )
    return (
        template.replace("{{paper_metadata_json}}", _model_json(metadata))
        .replace("{{parsed_pdf_json}}", _model_json(parsed_pdf))
        .replace("{{writing_requirements}}", writing_requirements or "未提供额外写作要求。")
    )


def build_figure_selection_prompt(
    article_plan: ArticlePlan,
    figure_assets: list[FigureAsset],
) -> str:
    """Build the prompt used to generate a FigurePlan JSON object."""
    template = (
        load_prompt_template("system_style")
        + "\n\n---\n\n"
        + load_prompt_template("figure_selector")
    )
    captions = [
        {
            "figure_id": asset.figure_id,
            "caption": asset.caption,
            "page_number": asset.page_number,
        }
        for asset in figure_assets
    ]
    return (
        template.replace("{{article_plan_json}}", _model_json(article_plan))
        .replace(
            "{{figure_captions_json}}",
            json.dumps(captions, ensure_ascii=False, indent=2),
        )
        .replace("{{figure_assets_json}}", _models_json(figure_assets))
        .replace("{{target_figure_count}}", "默认选择 3–5 张图。")
    )
