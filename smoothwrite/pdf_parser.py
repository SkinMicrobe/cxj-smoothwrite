"""Extract page text and figure captions from research paper PDFs."""

from __future__ import annotations

import re
from pathlib import Path

import fitz

from .io_utils import model_to_json_file
from .models import FigureCaption, PDFPage, ParsedPDF

_FIGURE_CAPTION_PATTERN = re.compile(
    r"""
    ^[ \t]*
    (?P<figure_id>(?:figure|fig\.?)[ \t]+\d+[A-Za-z]?)
    (?P<caption_start>[^\n]*)
    (?P<caption_continuation>
        (?:
            \n
            (?![ \t]*\n)
            (?![ \t]*(?:figure|fig\.?)[ \t]+\d+[A-Za-z]?)
            [^\n]*
        )*
    )
    """,
    flags=re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)


def _extract_figure_captions(text: str, page_number: int) -> list[FigureCaption]:
    """Extract basic multiline figure captions from one page of text."""
    captions: list[FigureCaption] = []

    for match in _FIGURE_CAPTION_PATTERN.finditer(text):
        figure_id = re.sub(r"\s+", " ", match.group("figure_id")).strip()
        caption_text = (
            figure_id
            + match.group("caption_start")
            + match.group("caption_continuation")
        )
        caption_text = re.sub(r"[ \t]*\n[ \t]*", " ", caption_text)
        caption_text = re.sub(r"[ \t]+", " ", caption_text).strip()

        captions.append(
            FigureCaption(
                figure_id=figure_id,
                caption=caption_text,
                page_number=page_number,
            )
        )

    return captions


def parse_pdf(pdf_path: str) -> ParsedPDF:
    """Parse a PDF into page text, full text, and basic figure captions.

    Raises:
        FileNotFoundError: If the input path does not exist.
        ValueError: If the path is not a file, or the PDF is empty, encrypted,
            damaged, or otherwise unreadable.
    """
    source_path = Path(pdf_path)

    if not source_path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"PDF path is not a file: {source_path}")

    try:
        document = fitz.open(str(source_path))
    except Exception as exc:
        raise ValueError(f"Unable to open or read PDF: {source_path}") from exc

    try:
        if document.needs_pass:
            raise ValueError(f"PDF is encrypted and cannot be read: {source_path}")
        if document.page_count == 0:
            raise ValueError(f"PDF contains no pages: {source_path}")

        pages: list[PDFPage] = []
        figure_captions: list[FigureCaption] = []

        for page_index in range(document.page_count):
            page_number = page_index + 1
            try:
                page_text = document.load_page(page_index).get_text("text")
            except Exception as exc:
                raise ValueError(
                    f"Unable to read page {page_number} from PDF: {source_path}"
                ) from exc

            pages.append(PDFPage(page_number=page_number, text=page_text))
            figure_captions.extend(
                _extract_figure_captions(page_text, page_number)
            )

        if not any(page.text.strip() for page in pages):
            raise ValueError(
                f"PDF contains no extractable text: {source_path}"
            )

        full_text = "\n\n".join(page.text for page in pages)
        return ParsedPDF(
            source_pdf=str(source_path),
            pages=pages,
            full_text=full_text,
            figure_captions=figure_captions,
        )
    finally:
        document.close()


def save_parsed_pdf(pdf_path: str, output_path: str) -> ParsedPDF:
    """Parse a PDF, save the result as JSON, and return the parsed model."""
    parsed_pdf = parse_pdf(pdf_path)
    model_to_json_file(parsed_pdf, output_path)
    return parsed_pdf
