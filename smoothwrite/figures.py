"""Export full PDF pages containing figure captions."""

from __future__ import annotations

import re
from pathlib import Path

import fitz

from .io_utils import ensure_dir, read_json, write_json
from .models import FigureAsset, ParsedPDF


def _figure_stem(figure_id: str) -> str:
    """Convert a figure identifier into a stable filename stem."""
    normalized = re.sub(r"(?i)^fig(?:ure)?\.?\s*", "Figure_", figure_id.strip())
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized).strip("_")
    return normalized or "Figure"


def _figure_filename(figure_id: str, kind: str) -> str:
    """Return a stable page or crop image filename."""
    return f"{_figure_stem(figure_id)}_{kind}.png"


def _normalize_search_text(text: str) -> str:
    """Normalize extracted PDF text for approximate caption matching."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def _find_caption_block(page: object, figure_asset: FigureAsset) -> tuple[float, ...] | None:
    """Find the text block most likely to contain a figure caption."""
    figure_id = _normalize_search_text(figure_asset.figure_id)
    caption_prefix = _normalize_search_text(figure_asset.caption or "")[:80]
    figure_id_candidates: list[tuple[float, ...]] = []

    for block in page.get_text("blocks"):
        if len(block) < 5:
            continue
        block_text = _normalize_search_text(str(block[4]))
        if caption_prefix and len(caption_prefix) >= 15 and caption_prefix in block_text:
            return tuple(float(value) for value in block[:4])
        if figure_id and block_text.startswith(figure_id):
            figure_id_candidates.append(tuple(float(value) for value in block[:4]))

    return figure_id_candidates[0] if figure_id_candidates else None


def _save_manifest(assets: list[FigureAsset], figures_path: Path) -> None:
    """Save figure assets as a human-readable JSON manifest."""
    write_json(
        figures_path / "figure_manifest.json",
        [asset.model_dump(mode="json") for asset in assets],
    )


def crop_figure_from_page(
    pdf_path: str,
    figure_asset: FigureAsset,
    output_dir: str,
    zoom: float = 2.5,
) -> FigureAsset:
    """Attempt a conservative crop above a figure caption text block.

    The full-page image recorded on the asset is left untouched. Failures are
    returned on the asset as notes rather than raised, except for invalid input
    PDF paths or zoom values.
    """
    source_path = Path(pdf_path)
    output_path = ensure_dir(output_dir)
    asset = figure_asset.model_copy(deep=True)

    if zoom <= 0:
        raise ValueError(f"Zoom must be greater than zero, received: {zoom}")
    if not source_path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"PDF path is not a file: {source_path}")
    if asset.page_number is None:
        asset.crop_image = None
        asset.crop_confidence = "failed"
        asset.notes.append("Crop failed because page_number is missing.")
        return asset

    try:
        document = fitz.open(str(source_path))
    except Exception as exc:
        raise ValueError(f"Unable to open or read PDF: {source_path}") from exc

    try:
        if document.needs_pass:
            raise ValueError(f"PDF is encrypted and cannot be read: {source_path}")
        if asset.page_number < 1 or asset.page_number > document.page_count:
            asset.crop_image = None
            asset.crop_confidence = "failed"
            asset.notes.append(
                "Crop failed because page_number "
                f"{asset.page_number} is outside the PDF page range."
            )
            return asset

        try:
            page = document.load_page(asset.page_number - 1)
            caption_block = _find_caption_block(page, asset)
        except Exception as exc:
            asset.crop_image = None
            asset.crop_confidence = "failed"
            asset.notes.append(f"Crop failed while reading page text blocks: {exc}")
            return asset

        if caption_block is None:
            asset.crop_image = None
            asset.crop_confidence = "failed"
            asset.notes.append("Crop failed because the caption text block was not found.")
            return asset

        page_rect = page.rect
        caption_top = caption_block[1]
        if caption_top <= page_rect.height * 0.2:
            asset.crop_image = None
            asset.crop_confidence = "failed"
            asset.notes.append(
                "Crop failed because the caption is too close to the top of the page."
            )
            return asset

        # Keep a broad region above the caption to reduce the risk of cutting panels.
        crop_top = max(page_rect.y0, caption_top - page_rect.height * 0.65)
        crop_bottom = min(page_rect.y1, caption_top + page_rect.height * 0.015)
        side_margin = page_rect.width * 0.025
        clip = fitz.Rect(
            page_rect.x0 + side_margin,
            crop_top,
            page_rect.x1 - side_margin,
            crop_bottom,
        )
        if clip.width <= 0 or clip.height <= page_rect.height * 0.1:
            asset.crop_image = None
            asset.crop_confidence = "failed"
            asset.notes.append("Crop failed because the inferred crop region is invalid.")
            return asset

        crop_path = output_path / _figure_filename(asset.figure_id, "crop")
        try:
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(zoom, zoom),
                clip=clip,
                alpha=False,
            )
            pixmap.save(str(crop_path))
        except Exception as exc:
            asset.crop_image = None
            asset.crop_confidence = "failed"
            asset.notes.append(f"Crop rendering failed: {exc}")
            return asset

        asset.crop_image = str(crop_path)
        asset.crop_confidence = (
            "medium" if caption_top >= page_rect.height * 0.55 else "low"
        )
        asset.notes.append(
            "Generated a conservative crop from the region above the caption block."
        )
        return asset
    finally:
        document.close()


def export_figure_pages(
    pdf_path: str,
    parsed_pdf: ParsedPDF,
    figures_dir: str,
    zoom: float = 2.5,
    attempt_crop: bool = True,
) -> list[FigureAsset]:
    """Render the full PDF page associated with each figure caption.

    Captions without a usable page number remain in the returned manifest with
    a note and no page image.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the PDF cannot be read or zoom is not positive.
    """
    source_path = Path(pdf_path)
    figures_path = ensure_dir(figures_dir)

    if zoom <= 0:
        raise ValueError(f"Zoom must be greater than zero, received: {zoom}")
    if not source_path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"PDF path is not a file: {source_path}")

    try:
        document = fitz.open(str(source_path))
    except Exception as exc:
        raise ValueError(f"Unable to open or read PDF: {source_path}") from exc

    assets: list[FigureAsset] = []

    try:
        if document.needs_pass:
            raise ValueError(f"PDF is encrypted and cannot be read: {source_path}")
        if document.page_count == 0:
            raise ValueError(f"PDF contains no pages: {source_path}")

        matrix = fitz.Matrix(zoom, zoom)

        for caption in parsed_pdf.figure_captions:
            notes: list[str] = []
            page_image: str | None = None

            if caption.page_number is None:
                notes.append("Figure page was not exported because page_number is missing.")
            elif caption.page_number < 1 or caption.page_number > document.page_count:
                notes.append(
                    "Figure page was not exported because page_number "
                    f"{caption.page_number} is outside the PDF page range."
                )
            else:
                output_path = figures_path / _figure_filename(caption.figure_id, "page")
                try:
                    page = document.load_page(caption.page_number - 1)
                    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                    pixmap.save(str(output_path))
                except Exception as exc:
                    raise ValueError(
                        f"Unable to render page {caption.page_number} for "
                        f"{caption.figure_id}: {source_path}"
                    ) from exc

                page_image = str(output_path)
                notes.append(
                    f"Exported full PDF page at {zoom:g}x zoom."
                )

            asset = FigureAsset(
                figure_id=caption.figure_id,
                caption=caption.caption,
                page_number=caption.page_number,
                page_image=page_image,
                crop_image=None,
                crop_confidence="not_attempted",
                notes=notes,
            )
            if attempt_crop:
                asset = crop_figure_from_page(
                    pdf_path=pdf_path,
                    figure_asset=asset,
                    output_dir=str(figures_path),
                    zoom=zoom,
                )
            else:
                asset.notes.append("Cropping was not attempted.")

            assets.append(asset)
    finally:
        document.close()

    _save_manifest(assets, figures_path)
    return assets


def save_figure_assets(
    pdf_path: str,
    parsed_pdf_json: str,
    figures_dir: str,
) -> list[FigureAsset]:
    """Load ParsedPDF JSON and export its figure-caption pages."""
    parsed_pdf = ParsedPDF.model_validate(read_json(parsed_pdf_json))
    return export_figure_pages(
        pdf_path=pdf_path,
        parsed_pdf=parsed_pdf,
        figures_dir=figures_dir,
    )
