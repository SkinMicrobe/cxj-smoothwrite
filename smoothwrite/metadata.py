"""Conservative local metadata extraction from parsed PDF text."""

from __future__ import annotations

import re

from .io_utils import load_journal_style, model_to_json_file, read_json
from .models import PaperMetadata, ParsedPDF

_DOI_PATTERN = re.compile(
    r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b",
    flags=re.IGNORECASE,
)
_YEAR_PATTERN = re.compile(r"\b20\d{2}\b")
_MONTH_PATTERN = re.compile(
    r"\b("
    r"January|February|March|April|May|June|July|August|"
    r"September|October|November|December"
    r")\b",
    flags=re.IGNORECASE,
)
_JOURNALS = tuple(load_journal_style()["journals"].values())
_TITLE_EXCLUSION_PATTERN = re.compile(
    r"""
    ^\s*(
        doi\b
        |https?://
        |www\.
        |copyright\b
        |©
        |all\ rights\ reserved
        |received\b
        |accepted\b
        |published\b
        |volume\b
        |issue\b
        |page\b
        |pages\b
        |abstract\b
        |research\ article\b
        |original\ article\b
        |article\b
        |open\ access\b
    )
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)
_AFFILIATION_PATTERN = re.compile(
    r"\b("
    r"university|institute|institution|department|laboratory|lab\b|"
    r"school of|college of|faculty of|hospital|academy|center for|centre for|"
    r"correspondence|email|e-mail|orcid"
    r")\b",
    flags=re.IGNORECASE,
)
_SECTION_PATTERN = re.compile(
    r"^(abstract|introduction|results?|methods?|discussion|references)\b",
    flags=re.IGNORECASE,
)
_AUTHOR_NAME_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z'’-]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z'’-]+)+\b"
)


def _nonempty_lines(text: str) -> list[str]:
    """Return normalized nonempty lines."""
    return [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]


def _looks_like_journal(line: str) -> bool:
    """Return whether a line primarily identifies a known journal."""
    normalized = re.sub(r"\s+", " ", line).strip(" .|").casefold()
    for journal in _JOURNALS:
        journal_name = journal.casefold()
        if normalized == journal_name:
            return True
        if normalized.startswith(journal_name) and re.search(
            r"\b(volume|vol\.?|issue|doi|20\d{2}|www\.|https?://)\b",
            normalized,
        ):
            return True
    return False


def _is_title_candidate(line: str) -> bool:
    """Apply conservative exclusions to a possible title line."""
    if len(line) < 12 or len(line) > 300:
        return False
    if _TITLE_EXCLUSION_PATTERN.search(line):
        return False
    if _AFFILIATION_PATTERN.search(line):
        return False
    if _SECTION_PATTERN.search(line):
        return False
    if _DOI_PATTERN.search(line) or _looks_like_journal(line):
        return False
    if re.fullmatch(r"[\d\s./-]+", line):
        return False
    if len(re.findall(r"[A-Za-z]", line)) < 8:
        return False
    return True


def _extract_title(first_page_text: str) -> tuple[str | None, int | None]:
    """Infer a title and its line index from the early first-page text."""
    lines = _nonempty_lines(first_page_text)
    for index, line in enumerate(lines[:15]):
        if _is_title_candidate(line):
            return line, index
    return None, None


def _is_author_candidate(line: str) -> bool:
    """Return whether a line has strong signs of being an author list."""
    if len(line) > 400:
        return False
    if _AFFILIATION_PATTERN.search(line) or _DOI_PATTERN.search(line):
        return False
    if _SECTION_PATTERN.search(line) or _looks_like_journal(line):
        return False

    lowered = line.casefold()
    has_list_separator = "," in line or ";" in line or " and " in lowered
    names = _AUTHOR_NAME_PATTERN.findall(line)
    return "et al" in lowered or (has_list_separator and len(names) >= 2)


def _extract_authors(first_page_text: str, title_index: int | None) -> list[str]:
    """Extract a conservative author list from lines following the title."""
    if title_index is None:
        return []

    lines = _nonempty_lines(first_page_text)
    for line in lines[title_index + 1 : title_index + 7]:
        if not _is_author_candidate(line):
            continue

        cleaned = re.sub(r"[*†‡§¶#\d]+", "", line)
        cleaned = re.sub(r"\bet\s+al\.?", "", cleaned, flags=re.IGNORECASE)
        parts = re.split(r"\s*(?:,|;|\band\b)\s*", cleaned)
        authors = [part.strip(" .") for part in parts if part.strip(" .")]
        return authors

    return []


def _find_known_journal(text: str) -> str | None:
    """Find the first known journal name in text."""
    for journal in _JOURNALS:
        if re.search(rf"\b{re.escape(journal)}\b", text, flags=re.IGNORECASE):
            return journal
    return None


def _find_first(pattern: re.Pattern[str], primary: str, fallback: str) -> str | None:
    """Search primary text first, then fallback text."""
    match = pattern.search(primary) or pattern.search(fallback)
    return match.group(0) if match else None


def extract_metadata(
    parsed_pdf: ParsedPDF,
    url: str | None = None,
    journal_hint: str | None = None,
    year_hint: str | None = None,
    month_hint: str | None = None,
) -> PaperMetadata:
    """Extract paper metadata locally using conservative text heuristics."""
    notes: list[str] = []
    first_page_text = parsed_pdf.pages[0].text if parsed_pdf.pages else ""
    full_text = parsed_pdf.full_text

    title, title_index = _extract_title(first_page_text)
    if title is None:
        notes.append("Title could not be inferred reliably from the first page.")
    else:
        notes.append("Title was inferred heuristically from an early first-page line.")

    doi_match = _DOI_PATTERN.search(first_page_text) or _DOI_PATTERN.search(full_text)
    doi = doi_match.group(0).rstrip(".,;:)") if doi_match else None
    if doi is None:
        notes.append("DOI was not found in the parsed PDF text.")

    if journal_hint is not None:
        journal = journal_hint
    else:
        journal = _find_known_journal(first_page_text)
        if journal is None:
            notes.append("Journal could not be identified from the supported journal list.")
        else:
            notes.append("Journal was inferred heuristically from the first page.")

    if year_hint is not None:
        year = year_hint
    else:
        year = _find_first(_YEAR_PATTERN, first_page_text, full_text)
        if year is None:
            notes.append("Publication year could not be identified from the parsed text.")
        else:
            notes.append("Publication year was inferred heuristically from the parsed text.")

    if month_hint is not None:
        month = month_hint
    else:
        month_match = _MONTH_PATTERN.search(first_page_text) or _MONTH_PATTERN.search(
            full_text
        )
        month = month_match.group(1).title() if month_match else None
        if month is None:
            notes.append("Publication month could not be identified from the parsed text.")
        else:
            notes.append("Publication month was inferred heuristically from the parsed text.")

    authors = _extract_authors(first_page_text, title_index)
    if authors:
        notes.append("Authors were inferred heuristically from lines following the title.")
    else:
        notes.append("Authors could not be extracted reliably and require manual review.")

    if url is None:
        notes.append("Original paper URL was not provided.")

    notes.append("research_object and core_question require later manual or LLM enrichment.")

    return PaperMetadata(
        title=title,
        journal=journal,
        year=year,
        month=month,
        authors=authors,
        doi=doi,
        url=url,
        research_object=None,
        core_question=None,
        notes=notes,
    )


def save_metadata(
    parsed_pdf_json: str,
    output_path: str,
    url: str | None = None,
    journal_hint: str | None = None,
    year_hint: str | None = None,
    month_hint: str | None = None,
) -> PaperMetadata:
    """Load parsed PDF JSON, extract metadata, save it, and return the model."""
    parsed_pdf = ParsedPDF.model_validate(read_json(parsed_pdf_json))
    metadata = extract_metadata(
        parsed_pdf=parsed_pdf,
        url=url,
        journal_hint=journal_hint,
        year_hint=year_hint,
        month_hint=month_hint,
    )
    model_to_json_file(metadata, output_path)
    return metadata
