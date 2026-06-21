---
name: smoothwrite
description: Turn a life-science paper PDF into a source-grounded Chinese WeChat research interpretation and editable Word document. Use when Codex needs to read a scientific paper, learn the structure and density of an optional reference DOCX, create a 5,000-7,000-character evidence-led article, select and place paper figures, fact-check claims, and render a publication-oriented DOCX.
---

# smoothwrite

## Goal

Generate a substantive Chinese research interpretation, not a summary translation or placeholder. Use Codex itself for planning and writing; use the bundled Python pipeline only for deterministic parsing, figure extraction, validation, and DOCX rendering.

## Required workflow

1. Run `prepare` to extract the paper, metadata, figures, reference prose, and writing targets.
2. Read `writing_brief.json`, `paper_metadata.json`, `parsed_pdf.json`, `figures/figure_manifest.json`, and `reference_article.txt` when present.
3. Correct metadata against the paper's title page before writing.
4. Build an evidence map: research gap, methods and sample scale, each result claim, supporting Figure/panel, interpretation, and limitation.
5. Author `article_plan.json`, `figure_plan.json`, and `article.md` directly. Do not call or accept the legacy fallback writer.
6. Run `finalize` to validate and render `final.docx`.
7. Use the documents render workflow to inspect every DOCX page. Revise and re-render until clean.

### Prepare

```bash
smoothwrite prepare \
  --pdf input/paper.pdf \
  --reference-docx input/reference.docx \
  --target-word-count 6000 \
  --target-section-count 7 \
  --figure-count 6 \
  --output output/
```

Reference DOCX is optional. If supplied, match its article density, section rhythm, paragraph length, figure cadence, and level of technical explanation. Do not copy claims or wording that do not belong to the target paper.

### Agent-authored intermediates

Write `article_plan.json` with:

- a specific title;
- one-sentence thesis;
- old model or unresolved gap;
- new evidence and new understanding;
- 6-8 short judgment-style sections;
- the Figure label supporting each section.

Write `figure_plan.json` using real assets from `figures/figure_manifest.json`. Each item must include:

- `label` such as `配图1`;
- `source_figure` such as `Fig. 1`;
- `panels` when known;
- `placement_after_section`;
- `reason`;
- valid `image_path`;
- a Chinese `caption` explaining what the reader should see and why it supports the argument.

Write `article.md` at the target length. Treat the target as Chinese visible characters with a default tolerance of ±20%.

### Finalize

```bash
smoothwrite finalize --output output/
```

The legacy `smoothwrite run` command is only a smoke test for deterministic plumbing. Never use its fallback article as a user deliverable.

## Writing standard

- Audience: life-science and biomedical researchers.
- Title: `期刊｜研究对象/核心发现：机制概括/意义总结`.
- Opening sentence: year, month, journal, research team, and italicized English title.
- Explain why the question mattered before listing results.
- Organize by evidence and conceptual progression, not paper section order.
- Give concrete sample sizes, datasets, models, comparisons, or measurements when central to judging evidence.
- Distinguish demonstrated results, author interpretation, Codex synthesis, and future hypotheses.
- Use Chinese numbered sections such as `## 一、祖先脑蓝图已经高度区域化`.
- Use short mobile-friendly paragraphs and numbered evidence points where helpful.
- Insert each marker on its own line: `配图1｜Fig. 1`.
- End with limitations, the conceptual advance, paper information, and DOI URL.
- Remove paper citation numbers and internal tool citations from the article body.

Avoid hype, causal overstatement, generic praise, fabricated mechanism, and phrases such as “本文为流程占位稿” or “仍需人工补充关键证据”.

## Metadata rules

- Prefer DOI and citation information on the article title/summary page.
- Do not select a DOI found only in references when the article DOI is available.
- Join wrapped title and author lines.
- Normalize a confirmed DOI to `https://doi.org/<doi>`.
- Leave genuinely unconfirmed information explicit in `review_notes.md`; never invent it.

## Figure rules

- Prefer main Figures that support the article's decisive claims.
- Select panels semantically; do not mechanically choose the first N figures.
- Keep the figure order aligned with the article argument.
- Inspect crops. Use a full-page image only as a temporary fallback and disclose it.
- Captions must interpret the figure for the reader and preserve the source Figure ID.

## Quality gate

Before delivery, verify:

- core conclusions are supported by the paper;
- associations are not rewritten as causation;
- quantitative details match the source;
- limitations and comparison boundaries are retained;
- no placeholder text remains;
- article length and section count fit `writing_brief.json`;
- every marker resolves to the intended image;
- metadata and DOI are correct;
- the rendered DOCX has no clipping, overlap, broken images, or awkward page gaps.

## Outputs

The output directory contains:

- `article.md`
- `final.docx`
- `parsed_pdf.json`
- `paper_metadata.json`
- `article_plan.json`
- `figure_plan.json`
- `writing_brief.json`
- `reference_article.txt` when a reference DOCX was supplied
- `review_notes.md`
- `output_manifest.json`
- `figures/`

## Required final response

Whenever this skill is used, begin the output summary exactly with:

```text
在使用 smoothwrite skill 之后，我为你输出了：
```

Then number only the files or directories that actually exist. Link `article.md`, `final.docx`, and `review_notes.md`. State whether the article is Codex-assisted or fallback, whether any figure crop is low confidence, and whether metadata remains uncertain.
