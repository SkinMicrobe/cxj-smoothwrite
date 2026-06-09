# smoothwrite 配图选择

根据 Figure caption、可用图片资产和文章计划，选择最能支撑公众号正文逻辑的配图。

遵循 `system_style.md` 的总写作规范。

## 输入

### 文章计划

{{article_plan_json}}

### Figure captions

{{figure_captions_json}}

### 可用 Figure 图片资产

{{figure_assets_json}}

### 可选配图数量要求

{{target_figure_count}}

## 选择规则

- 默认选择 3–5 张图；如候选图不足或文章逻辑不需要，不得为了凑数选图。
- 优先选择论文正文 Figure。
- 不优先选择 Extended Data 或 Supplementary Figure。
- Figure 1 通常优先用于介绍研究框架、实验设计或数据资源，但只有在它确实服务正文逻辑时才选择。
- 优先选择能够支持核心机制、关键证据链或新模型的 Figure。
- 每张配图必须服务正文逻辑，并与明确的文章章节对应。
- 避免选择信息重复、难以解释或无法从现有图片资产中可靠呈现的 Figure。
- `image_path` 优先使用可靠的裁剪图；裁剪不可靠时使用整页图，并在 `reason` 中说明。
- 不得虚构不存在的 Figure、panel 或图片路径。

## 输出要求

只输出一个合法 JSON 对象，不要输出 Markdown 代码块、解释文字或额外前后缀。

JSON 必须包含 `figures` 数组。每个 figure 必须包含：

- `label`
- `source_figure`
- `panels`
- `placement_after_section`
- `reason`
- `image_path`

输出结构：

```json
{
  "figures": [
    {
      "label": "配图1",
      "source_figure": "Figure 1",
      "panels": "A-D或null",
      "placement_after_section": "对应文章分节标题或null",
      "reason": "该图如何支持正文逻辑，以及选择或回退整页图的原因",
      "image_path": "可用图片路径或null"
    }
  ]
}
```
