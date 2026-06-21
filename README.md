# cxj-smoothwrite

`cxj-smoothwrite` 是一个面向生命科学论文的 Codex Skill：它把论文 PDF 转换为有证据约束的中文微信公众号科研解读，并生成可编辑、带原论文配图的 Word 文档。

新版不再把本地 fallback 草稿当作最终成品。标准流程分为两个阶段：

1. `prepare` 解析论文、提取元信息和 Figure，并分析参考公众号文章。
2. Codex 基于论文证据完成文章规划、配图方案和实质正文写作。
3. `finalize` 校验中间产物，渲染 `final.docx`，生成质检报告和输出清单。

## 环境要求

- Python 3.10 或更高版本
- Windows、macOS 或 Linux
- Codex（用于标准的实质写作阶段）

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
smoothwrite --help
```

Windows PowerShell 激活命令：

```powershell
.\.venv\Scripts\Activate.ps1
```

## 推荐用法

通常直接在 Codex 中调用 Skill，并提供论文 PDF；如有示范公众号 Word 文档，也一并提供。Skill 会自行执行完整流程。

手动执行第一阶段：

```bash
smoothwrite prepare \
  --pdf input/paper.pdf \
  --reference-docx input/reference.docx \
  --url "https://doi.org/xxxxx" \
  --output output/
```

`prepare` 会生成论文解析结果、元信息、Figure 资产、参考文章纯文本和写作 brief。Codex 随后据此完成：

- `article_plan.json`
- `figure_plan.json`
- `article.md`

完成实质写作后执行：

```bash
smoothwrite finalize --output output/
```

`run` 命令仅保留用于本地 smoke test；其 fallback 正文不得作为交付成品：

```bash
smoothwrite run --pdf input/paper.pdf --output output/
```

## 输出目录

```text
output/
├── parsed_pdf.json
├── paper_metadata.json
├── writing_brief.json
├── reference_article.txt
├── article_plan.json
├── figure_plan.json
├── article.md
├── final.docx
├── review_notes.md
├── output_manifest.json
└── figures/
    ├── figure_manifest.json
    └── Figure_*.png
```

默认目标为约 6000 字、7 个主体章节和 6 幅配图；实际结构应服从论文论证链和用户提供的参考文章风格。正文必须区分论文直接证据、作者解释和编辑性概括，避免把相关性改写为因果性。

## 主要改进

- 引入 `prepare → Codex 写作 → finalize` 两阶段工作流。
- 支持从参考 DOCX 提取篇幅、结构和媒体特征。
- 改进 Science 等期刊 PDF 的标题、作者和 DOI 抽取。
- 改进跨页 Figure 识别，减少只截到图注或残缺 panel 的情况。
- Word 使用 A4 中文公众号排版，并支持中文图注和行内 Markdown 样式。
- 校验正文目标长度、占位符、Figure 引用和必需中间文件。
- 将运行所需配置与 prompt 打包进 Python wheel，支持非 editable 安装。

## 发布前检查

请优先阅读 `review_notes.md`，并核查：

- 标题、作者、期刊、日期与 DOI。
- 关键事实、因果表述和结论边界。
- 图片是否对应正确 Figure，panel 是否完整。
- `final.docx` 是否存在分页、缺图或文字溢出。

完整工作约束与 Codex 执行规则见 [`SKILL.md`](SKILL.md)。
