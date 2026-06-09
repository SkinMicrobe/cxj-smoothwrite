---
name: smoothwrite
description: Generate a structured Chinese WeChat research interpretation package and editable Word document from a scientific paper PDF. Use when Codex needs to run or extend a local life-science paper parsing, figure extraction, fallback writing, review, and Word rendering workflow.
---

# smoothwrite

## 目标

从科研论文 PDF 生成适合微信公众号编辑流程的中文科研解读初稿，并交付包含正文、配图和论文信息的可编辑 Word 文档。

保持各处理阶段解耦，将中间结果保存为 JSON 或 Markdown，方便开发者和编辑人员检查、修订与调试。

当前初版使用本地 fallback 逻辑生成文章计划、配图计划和正文，不调用真实 LLM。将所有生成内容视为待人工核查的科研传播初稿。

## 输入

### 必需输入

- **论文 PDF**：用于解析正文、元信息、Figure caption 和 Figure 页面图。

### 可选输入

- **原文 URL**：用于补充论文信息，并在文末提供原文链接。
- **配图数量**：用于控制进入公众号正文的 Figure 数量。

参考范文和目标字数已预留在 prompt 与配置结构中，但当前 CLI 尚未提供对应参数。

缺少可选输入时，依据论文内容和默认配置继续工作。无法可靠确认的信息必须标记为待人工核查，不得编造。

## 输出

最终输出目录必须包含：

- `article.md`：公众号正文 Markdown。
- `final.docx`：包含正文、配图和论文信息的 Word 成品。
- `parsed_pdf.json`：逐页文本、全文文本和 Figure captions。
- `paper_metadata.json`：论文标题、作者、期刊、发表时间、DOI 和原文链接等元信息。
- `article_plan.json`：文章逻辑骨架和各节写作计划。
- `figure_plan.json`：配图选择、顺序、用途、来源和图注计划。
- `output_manifest.json`：全部输出文件及生成状态清单。
- `review_notes.md`：事实、结构、写作规范和配图质检报告。
- `figures/`：导出的 Figure 页面图、粗裁剪图和 `figure_manifest.json`。

## smoothwrite 使用后的固定回复规则

只要调用或运行了 `smoothwrite` skill，无论是完整成功、部分成功，还是 fallback 生成，最终回复都必须包含一段中文输出说明。

说明必须以以下句式开头：

```text
在使用 smoothwrite skill 之后，我为你输出了：
```

随后使用中文编号列出实际已经生成的文件或目录。不得声称不存在的文件已经生成。完整成功时使用以下标准格式：

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

部分文件未生成时，必须另行列出：

```text
以下文件未能生成，需要检查：
1、final.docx
2、figures/
```

如果正文由 fallback 逻辑生成，必须补充：

```text
需要注意：当前正文为 fallback 版本，主要用于验证流程和 Word 渲染，正式发布前仍需要使用完整写作模型生成或人工修订。
```

如果 Figure 自动裁剪失败或置信度较低，必须补充：

```text
需要注意：部分 Figure 可能使用的是整页截图或低置信度裁剪图，建议发布前人工核对图片位置和清晰度。
```

如果元信息存在不确定字段，必须补充：

```text
需要注意：论文标题、期刊、作者、年份、DOI 或原文链接中存在未能自动确认的信息，建议根据原文人工核对。
```

路径尽量使用相对输出目录的形式，并始终保留 `review_notes.md` 作为人工检查入口。

## 核心流程

按以下顺序执行，并保存可人工检查的中间产物：

1. **解析 PDF**：提取逐页文本、全文文本和 Figure captions，保存 `parsed_pdf.json`。
2. **提取元信息**：整理标题、作者、期刊、发表时间、DOI 和原文 URL，保存 `paper_metadata.json`。
3. **导出 Figure 资产**：导出包含 Figure caption 的整页 PNG，并尝试生成 caption 上方区域的粗裁剪图。
4. **生成文章逻辑骨架**：当前由 fallback 逻辑生成 `article_plan.json`。
5. **选择正文配图**：当前由 fallback 逻辑优先选择正文 Figure，生成 `figure_plan.json`。
6. **生成公众号正文**：当前由 fallback 逻辑生成结构完整但内容简略的 `article.md`。
7. **渲染 Word**：将正文和可用配图渲染为 `final.docx`。
8. **生成质检报告**：记录元信息不确定性、裁剪风险、fallback 状态和基础结构问题，输出 `review_notes.md`。
9. **记录输出清单**：将输入、输出目录、关键产物路径和质检 notes 写入 `output_manifest.json`。

## 运行方式

安装项目后运行：

```bash
smoothwrite run --pdf input/paper.pdf --url "https://doi.org/xxxxx" --output output/
```

也可从源码目录运行：

```bash
python scripts/smoothwrite_run.py run --pdf input/paper.pdf --output output/
```

## 写作定位

面向生命科学、基础医学、生物信息学、微生物学、遗传学、演化生物学、生态学等领域科研人员。

- 不是新闻快讯。
- 不是摘要翻译。
- 不是面向普通读者的大众科普。
- 需要解释研究问题、证据链、方法价值和结论边界。
- 需要体现“旧认知—新证据—新模型/新理解”的推进。
- 将论文明确证明的内容与作者推测、文章解读和未来问题区分开。

## 标题格式

使用以下格式：

`期刊｜研究对象/核心发现：机制概括/意义总结`

标题应准确概括研究对象、核心发现和意义，不使用夸张、悬念或营销表达。

## 引言格式

- 第一句必须包含年份、月份、期刊、团队和英文论文标题。
- 英文论文标题必须使用斜体。
- 引言应迅速交代研究背景、旧认知中的关键缺口，以及本研究试图回答的问题。

推荐句式：

`年份年月份，团队在《期刊》发表题为 *English Paper Title* 的研究论文，……`

## 正文格式

- 使用中文数字编号分节，例如“一、”“二、”“三、”。
- 小标题必须是短判断句，直接表达该节结论或推进。
- 段落应适合微信公众号手机端阅读，避免连续的大段文字。
- 各节围绕一项明确判断展开，并说明支撑判断的实验、数据或分析。
- 重点解释证据如何改变旧认知，而不是按论文段落顺序复述结果。
- 对关键方法、样本、模型和限制提供足够信息，使科研读者可以判断证据强度。

## 配图规则

- 优先使用正文 Figure。
- 不优先使用 Extended Data 或 Supplementary Figure；仅在正文 Figure 无法支撑关键论点时考虑使用。
- 配图必须服务于正文证据链，不为装饰而插图。
- 配图顺序应与正文论证顺序一致。
- 配图标记格式统一为：`配图1｜Figure 1`。
- 图注应说明读者需要从图中看到什么，并保留准确的 Figure 来源信息。

## 文末格式

文章末尾必须包含：

`论文信息：作者 et al., 期刊, 年份。`

`原文链接：...`

原文 URL 未提供或无法确认时，不得编造链接。当前 fallback 正文会省略该行，并由 `review_notes.md` 提示人工补充。

## 质检要求

生成 `review_notes.md`，至少检查：

- 核心结论是否得到论文证据支持。
- 是否将相关性写成因果关系，或扩大论文结论适用范围。
- 是否遗漏关键限制、反例或不确定性。
- “旧认知—新证据—新模型/新理解”的推进是否清晰。
- 标题、引言、分节、小标题、配图标记和文末信息是否符合规范。
- 配图与正文论点是否匹配，Figure 来源是否准确。
- 文中是否残留论文引用编号或文件引用标记。

## 禁止事项

- 不要营销号表达。
- 不要震惊体。
- 不要编造论文未证明的机制。
- 不要保留论文引用编号或文件引用标记。
- 不要过度口语化。
- 不要将作者推测或文章解读写成已证实事实。
- 不要为了流畅而删除影响结论边界的限定条件。
