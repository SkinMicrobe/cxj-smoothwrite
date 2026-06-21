"""Extract reusable writing signals from a reference Word article."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from docx import Document

from .models import ReferenceProfile

_SECTION_PATTERN = re.compile(r"^[一二三四五六七八九十百]+、.+")


def extract_reference_profile(docx_path: str) -> ReferenceProfile:
    """Read reference prose and lightweight structure without copying its layout."""
    source = Path(docx_path)
    if not source.is_file():
        raise FileNotFoundError(f"Reference DOCX does not exist: {source}")

    document = Document(str(source))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    nonempty = [text for text in paragraphs if text]
    text = "\n\n".join(nonempty)
    headings = [text for text in nonempty if _SECTION_PATTERN.match(text)]

    with zipfile.ZipFile(source) as archive:
        image_count = sum(
            1 for name in archive.namelist() if name.startswith("word/media/")
        )

    return ReferenceProfile(
        source_docx=str(source),
        text=text,
        character_count=len(text),
        paragraph_count=len(nonempty),
        section_headings=headings,
        image_count=image_count,
    )
