"""Pydantic models for smoothwrite intermediate and output artifacts."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class PDFPage(BaseModel):
    """Text extracted from one PDF page."""

    page_number: int
    text: str


class FigureCaption(BaseModel):
    """A figure identifier and caption found in the paper."""

    figure_id: str
    caption: str
    page_number: int | None = None


class ParsedPDF(BaseModel):
    """Structured text and figure captions extracted from a PDF."""

    source_pdf: str
    pages: list[PDFPage] = Field(default_factory=list)
    full_text: str
    figure_captions: list[FigureCaption] = Field(default_factory=list)


class PaperMetadata(BaseModel):
    """Normalized bibliographic and research metadata for a paper."""

    title: str | None = None
    journal: str | None = None
    year: str | None = None
    month: str | None = None
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    url: str | None = None
    research_object: str | None = None
    core_question: str | None = None
    notes: list[str] = Field(default_factory=list)


class FigureAsset(BaseModel):
    """A candidate figure asset and its extraction status."""

    figure_id: str
    caption: str | None = None
    page_number: int | None = None
    page_image: str | None = None
    crop_image: str | None = None
    crop_confidence: str
    notes: list[str] = Field(default_factory=list)


class FigurePlanItem(BaseModel):
    """One selected figure and its intended article placement."""

    label: str
    source_figure: str
    panels: str | None = None
    placement_after_section: str | None = None
    reason: str
    image_path: str | None = None
    caption: str | None = None


class FigurePlan(BaseModel):
    """Selected figures for the article."""

    figures: list[FigurePlanItem] = Field(default_factory=list)


class ArticleSection(BaseModel):
    """One planned article section."""

    heading: str
    core_point: str
    figure_label: str | None = None


class ArticlePlan(BaseModel):
    """Logical structure for the research interpretation article."""

    title: str
    main_thesis: str
    old_model: str | None = None
    new_evidence: str | None = None
    new_model: str | None = None
    sections: list[ArticleSection] = Field(default_factory=list)


class OutputManifest(BaseModel):
    """Paths and review notes for a smoothwrite output directory."""

    pdf_path: str
    output_dir: str
    parsed_pdf_json: str | None = None
    article_md: str | None = None
    final_docx: str | None = None
    metadata_json: str | None = None
    article_plan_json: str | None = None
    figure_plan_json: str | None = None
    figures_dir: str | None = None
    figure_manifest_json: str | None = None
    review_notes_md: str | None = None
    output_manifest_json: str | None = None
    reference_article_txt: str | None = None
    writing_brief_json: str | None = None
    review_notes: list[str] = Field(default_factory=list)


class ReferenceProfile(BaseModel):
    """Text and structural signals extracted from a reference DOCX."""

    source_docx: str
    text: str
    character_count: int
    paragraph_count: int
    section_headings: list[str] = Field(default_factory=list)
    image_count: int = 0
    page_count_hint: int | None = None


class WritingBrief(BaseModel):
    """Deterministic inputs for the Codex-assisted writing stage."""

    target_word_count: int
    target_section_count: int
    target_figure_count: int
    reference_profile: ReferenceProfile | None = None
    instructions: list[str] = Field(default_factory=list)


class PipelineInputs(BaseModel):
    """Inputs accepted by the future pipeline."""

    pdf_path: Path
    output_dir: Path
    source_url: str | None = None
