# smoothwrite

`smoothwrite` 将生命科学科研论文 PDF 转换为适合微信公众号编辑流程的结构化产物，并生成包含正文和配图的 Word 文档。

当前初版已经支持完整本地流程：PDF 文本解析、基础元信息抽取、Figure caption 识别、Figure 页面导出与粗裁剪、fallback 文章规划与写作、Word 渲染、基础质检和输出清单生成。当前流程不联网，也不调用真实 LLM。

## 环境要求

- Python 3.10 或更高版本
- Windows、macOS 或 Linux

## 安装

在项目目录创建虚拟环境并安装：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

macOS 或 Linux：

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

安装完成后检查命令：

```bash
smoothwrite --help
smoothwrite run --help
```

## 运行

安装后运行完整流程：

```bash
smoothwrite run \
  --pdf input/paper.pdf \
  --url "https://doi.org/xxxxx" \
  --output output/
```

也可以直接从源码目录运行：

```bash
python scripts/smoothwrite_run.py run \
  --pdf input/paper.pdf \
  --url "https://doi.org/xxxxx" \
  --output output/
```

提供元信息提示并关闭粗裁剪：

```bash
smoothwrite run \
  --pdf input/paper.pdf \
  --output output/ \
  --journal "Nature Microbiology" \
  --year 2026 \
  --month June \
  --figure-count 4 \
  --no-crop
```

主要参数：

- `--pdf`：必需，输入论文 PDF。
- `--output`：输出目录，默认 `output`。
- `--url`：可选，论文原文或 DOI URL。
- `--journal`、`--year`、`--month`：可选元信息提示。
- `--figure-count`：fallback 配图计划最多选择的图片数量。
- `--no-crop`：关闭基于 caption 位置的粗裁剪。

## 当前流程

1. 解析 PDF 页面文本和 Figure caption。
2. 抽取基础论文元信息。
3. 导出包含 Figure caption 的整页 PNG，并尝试粗裁剪。
4. 生成 fallback 文章计划和配图计划。
5. 生成结构完整但内容简略的 fallback Markdown 正文。
6. 渲染 `final.docx`。
7. 生成自动质检报告与输出清单。

## 输出目录

默认输出目录结构：

```text
output/
├── parsed_pdf.json
├── paper_metadata.json
├── article_plan.json
├── figure_plan.json
├── article.md
├── final.docx
├── review_notes.md
├── output_manifest.json
└── figures/
    ├── figure_manifest.json
    ├── Figure_1_page.png
    └── Figure_1_crop.png
```

- `parsed_pdf.json`：逐页文本、全文文本和 Figure captions。
- `paper_metadata.json`：启发式抽取的论文元信息及不确定性 notes。
- `article_plan.json`：fallback 文章逻辑骨架。
- `figure_plan.json`：fallback 配图选择和图片路径。
- `article.md`：结构完整的 fallback 公众号正文。
- `final.docx`：可继续人工编辑的 Word 文档。
- `review_notes.md`：元信息、裁剪、文章生成方式和基础结构质检结果。
- `output_manifest.json`：输入路径、输出目录、关键产物路径和质检 notes。
- `figures/figure_manifest.json`：全部 Figure 资产及裁剪状态。

## 运行完成后的回复格式

CLI 会根据输出目录中的实际文件生成中文完成摘要。摘要不会硬编码声称所有文件均已成功生成。

完整成功时，输出格式如下：

```text
在使用 smoothwrite skill 之后，我为你输出了：

1、公众号科研解读正文：article.md
2、Word 成品文档：final.docx
3、论文元信息：paper_metadata.json
4、PDF 解析结果：parsed_pdf.json
5、文章结构规划：article_plan.json
6、配图方案：figure_plan.json
7、Figure 图片目录：figures/
8、输出清单：output_manifest.json
9、人工检查提示：review_notes.md
```

如果部分产物缺失，CLI 会在“以下文件未能生成，需要检查”部分单独列出。摘要还会根据实际结果提示：

- 正文是否由 fallback 逻辑生成。
- Figure 是否存在裁剪失败或低置信度情况。
- 论文元信息是否存在未能自动确认的字段。

无论摘要是否提示问题，发布前都应优先阅读 `review_notes.md`。

## 配置与模板

- `config/default.yaml`：文章、图片和输出文件默认参数。
- `config/journal_style.yaml`：常见期刊显示名称。
- `prompts/`：未来接入真实 LLM 时使用的模型无关 prompt 模板。
- `templates/`：文章结构和图注风格模板。
- `schemas/`：中间数据与输出数据的 JSON Schema。

## 当前限制

- 当前文章计划、配图计划和正文由 fallback 逻辑生成，不代表可直接发布的高质量科研解读。
- Figure caption 识别基于基础正则，复杂排版可能漏检或误识别。
- Figure 自动裁剪基于 caption 上方区域，可能包含正文、漏掉 panel 或无法裁剪。
- 元信息抽取为本地启发式规则，可能需要人工补充。
- 扫描版 PDF 或没有文本层的 PDF 当前无法解析。
- 生成文章后仍建议人工核查事实、结论边界、原文链接和图像。

## 发布前检查

优先阅读 `review_notes.md`，并人工核查：

- 标题、作者、期刊、年月和 DOI。
- 文章中的事实、因果判断和结论边界。
- 配图是否对应正确 Figure，裁剪是否完整。
- `final.docx` 中的排版和缺图提示。
