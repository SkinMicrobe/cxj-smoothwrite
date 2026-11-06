# content.json 输入约定（v3）

常规输入为本期论文 PDF、两条指定往期推荐及对应图片、本期期刊官网截图。本文件是代理的内部约定，不是给用户的表单。完整实例：[`examples/bjd-ljag463/content.json`](../examples/bjd-ljag463/content.json)；留空占位版：[`examples/blank-template/content.json`](../examples/blank-template/content.json)。

## 必填

```json
{
  "title": "期刊缩写｜本篇论文的核心对象与问题",
  "paper": {
    "english_title": "Verified paper title",
    "journal": "Journal full name",
    "journal_abbrev": "J Abbrev",
    "published": "2026-10-15",
    "authors_short": "Li Y, Wang Y, et al.",
    "doi": "10.xxxx/example",
    "url": "https://doi.org/10.xxxx/example",
    "article_type": "Review",
    "version_label": "Accepted manuscript"
  },
  "lead": "日期、团队与合作单位，在 *Journal name*（缩写）发表论文，梳理或发现……。",
  "overview": [
    {"heading": "01｜具体主题", "paragraphs": ["有原文支持的段落，支持 **加粗** 与 *斜体*。"]}
  ],
  "evidence": [
    {"section": 1, "claim": "正文中的关键主张", "pages": [3, 4], "note": "证据类型、模型或边界"}
  ]
}
```

- `published` 写 `YYYY-MM-DD` 时渲染为“2026年10月15日在线发表”。`journal_abbrev` 可选，用于图片来源行。
- `evidence.section` 是概述小节的 1 起始序号；`pages` 是 PDF 文件页码（不是印刷页码）。每节至少一个证据条目。
- **不允许 `authors` 字段**：v3 模板没有作者简介模块。

## 期刊截图

```json
"header": {
  "image": "journal-header.png",
  "caption": "期刊官网页面截图 · Accepted Manuscript",
  "alt": "截图内容说明",
  "source_url": "https://publisher.example/article"
}
```

缺失或 `image: null` 时省略头图，不生成冒充截图。渲染时自动缩到 1200px 宽 JPEG。

## 论文图示（横滑）

```json
"figures": [
  {
    "label": "Figure 1",
    "image": "figures/figure-1.png",
    "pages": [47, 37],
    "title_zh": "依据 legend 的中文标题",
    "description_zh": "依据 legend 翻译的中文说明，不扩写结论。",
    "caption_en": "Legend 的第一句英文原题."
  }
],
"figure_source": "图片来源：Li Y, et al. *Br J Dermatol* 2026. DOI: 10.1093/bjd/ljag463 · 点击图片可放大",
"figures_heading": "论文图示"
```

- `image` 通常来自 `prepare` 输出的 `figure-candidates/`，或 `crop` 渲染的矢量图区域。按 Figure 编号排序。
- `pages` 填图所在页和 legend 所在页。
- 2 张及以上自动做成横滑（卡片宽 86%，显示 `i / n` 与“← 左右滑动查看 Fig 1–n →”）；1 张时整宽显示；空数组或缺失时省略模块。
- `figure_source` 可省略，脚本按第一作者、期刊缩写、年份、DOI 自动生成；`figures_heading` 默认“论文图示”。
- 补充材料图（Fig. S1 等）默认不放，除非用户要求。

## 往期推荐

```json
"recommendations": [
  {"title": "已核实的标题", "kind": "公众号推文", "meta": "2026-09-12", "reason": "与本文的具体关联", "url": "https://mp.weixin.qq.com/s/..."},
  {"title": "相关论文标题", "kind": "相关论文", "meta_label": "团队相关论文原文 · JACI · 2025", "reason": "……", "url": "https://doi.org/..."}
]
```

- `kind` 只能是 `公众号推文`（显示“往期推文 · meta”和“阅读推文 ›”）或 `相关论文`（显示“相关论文原文 · meta”和“查看原文 ›”）。`meta_label` 可整体覆盖第二行。
- 不能把只有 DOI 的论文标成公众号推文。预览左侧“设置论文与往期链接”可在浏览器中替换链接。
- `recommendations_heading` 默认“往期推荐”。传入 `"recommendations": []` 时渲染标题和空行。省略此字段会隐藏整个模块。
- 常规做法是在每个推荐条目中设置 `wechat_image`（相对于内容 JSON 的图片路径）。每条单独成卡，保留期刊原文链接；图片跳转地址由用户在预览页按编号分别填写。用 `meta_label` 显示期刊全名和发表年份。
- 兼容已有单图片稿件。若使用顶层的推荐图片，填写 `recommendations`，并在顶层设置 `"reserve_wechat_card": true`。推荐条目下方会显示「阅读往期推文」。在预览的「设置论文与往期链接」中填入文章地址后复制，或粘贴正文后在公众号编辑器中给这行文字设置超链接。若同时提供顶层 `wechat_post_image`（相对于内容 JSON 的图片路径），则以图片替换文字入口，并在图下提示「点击图片查看往期推文」。同一设置项绑定图片的跳转地址。

## 其他可选字段

- `review_notes`：来源、未取得的素材、已完成的人工核对，写入 `review_notes.md`。
- `**...**`、`*...*` 是仅有的内联样式；原始 HTML 会被转义。

## 团队 profile

```json
{
  "account_name": "公众号名称",
  "logo": "logo.png",
  "qr": "qr.png",
  "group": {
    "brand": "团队名称",
    "english_lines": [],
    "paragraphs": ["用户确认的团队介绍原文"],
    "website": "https://example.org",
    "email": "lab@example.org"
  }
}
```

默认使用 `assets/smooth-profile.json`。logo 自动放大到 ≥200px、二维码 ≥300px 原始尺寸嵌入（微信会丢弃过小的粘贴图片）。没有团队资料时用 `{"account_name":"科研论文"}`，省略课题组模块，不套用 SMOOTH 资料。
