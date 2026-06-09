# smoothwrite 文章逻辑规划

根据 PDF 解析文本和论文元信息，生成适合微信公众号科研解读文章的逻辑骨架。

遵循 `system_style.md` 的总写作规范。

## 输入

### 论文元信息

{{paper_metadata_json}}

### PDF 解析文本

{{parsed_pdf_json}}

### 可选写作要求

{{writing_requirements}}

## 规划要求

- 围绕论文的核心研究问题和主要证据组织文章。
- 清楚呈现“旧认知—新证据—新模型/新理解”的推进。
- 不要机械照搬论文 Results 的顺序。
- 将论文内容重组为适合微信公众号阅读的叙事逻辑。
- 优先安排能够帮助读者理解研究问题、关键证据、机制解释和结论边界的章节。
- 小标题必须短。
- 小标题必须是判断句，而不是“研究背景”“实验结果”等关键词。
- 不得加入论文没有支持的机制、结论或意义。
- 无法从输入确认的信息使用 `null`，不要编造。

## 输出要求

只输出一个合法 JSON 对象，不要输出 Markdown 代码块、解释文字或额外前后缀。

JSON 必须包含以下字段：

- `title`
- `main_thesis`
- `old_model`
- `new_evidence`
- `new_model`
- `sections`

每个 `sections` 项必须包含：

- `heading`
- `core_point`
- `figure_label`

输出结构：

```json
{
  "title": "期刊｜研究对象/核心发现：机制概括/意义总结",
  "main_thesis": "文章希望读者理解的核心判断",
  "old_model": "研究前的主要认知或解释框架；无法确认时为 null",
  "new_evidence": "论文提供的关键新证据；无法确认时为 null",
  "new_model": "新模型或新理解；无法确认时为 null",
  "sections": [
    {
      "heading": "一、短判断句",
      "core_point": "本节要建立的核心判断及其证据",
      "figure_label": "配图1或null"
    }
  ]
}
```
