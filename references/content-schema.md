# content.json 输入约定

用户只需提供论文 PDF 和期刊截图。本文件是代理的内部输入约定，不是要求用户提交的表单。由代理阅读论文后直接撰写 JSON，将用户截图路径填入 `header.image`，不是让脚本自行“生成结论”。完整实例在 `examples/bjd-content.json`；它没有包含原始PDF或BJD截图，需要在实际任务中对应到用户提供的文件。

## 必填

```json
{
  "title": "期刊缩写｜本篇论文的核心对象与问题",
  "paper": {
    "english_title": "Verified paper title",
    "journal": "Journal name",
    "published": "2026-10-15",
    "authors_short": "Li Y, Wang Y, et al.",
    "doi": "10.xxxx/example",
    "url": "https://doi.org/10.xxxx/example",
    "article_type": "Review",
    "version_label": "接收稿"
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

`section` 是概述小节的1起始序号。`pages` 是PDF文件页码，不是原文印刷页码，必须在实际页数范围内；每节至少有一个证据条目，关键数字/因果表述另行逐条核对。

`published`、`article_type`、`version_label` 由核对资料填写。信息缺失时先在工作稿标明缺口并继续可完成部分，不能编造以通过渲染校验。脚本会拒绝缺少这些字段的正式交付稿。

## 可选素材与模块

```json
{
  "header": {
    "image": "journal-header.png",
    "caption": "期刊官网页面截图 · Accepted Manuscript",
    "alt": "真实截图的内容说明",
    "source_url": "https://publisher.example/article",
    "verified_on": "2026-10-26"
  },
  "authors": [
    {
      "name": "Gaofeng Wang",
      "role": "通讯作者",
      "profile_name": "Gaofeng Wang",
      "bullets": ["已核对的单位与职务。", "与本篇相关的研究方向。"],
      "source_url": "https://skinmicrobe.github.io/team/Gaofeng-Wang"
    }
  ],
  "recommendations": [
    {
      "title": "已核实的推荐标题",
      "kind": "相关论文",
      "meta": "期刊 · 年份",
      "reason": "具体关联",
      "url": "https://doi.org/10.xxxx/example"
    }
  ],
  "review_notes": ["需要说明的来源、未取得素材和实际已完成的人工核对。"]
}
```

- `header.image` 缺失或为null时省略头图，核对记录注明，不能生成冒充截图的头图。
- `authors` 缺失或空数组时省略作者模块。`profile_name` 只取内置头像，不自动证明该作者参与当前论文；角色必须逐篇确认。其他作者可直接提供 `photo` 路径而不使用 `profile_name`。缺照片时显示明确待补位置。
- `recommendations` 缺失或空数组时省略该模块。`kind` 仅支持 `公众号推文` 或 `相关论文`，渲染后据此显示“往期推文”或“相关论文原文”。
- 资源文件路径相对 `content.json` 所在目录；profile里的资源相对profile文件所在目录。也可用绝对路径执行本次任务，但打包共享前应改为携带素材的相对路径。
- `**...**` 和 `*...*` 是支持的内联样式；原始HTML会转义，不用于复杂排版。摘要正文不插图；原图在完整页图中保留。

## 其他团队 profile

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
  },
  "author_profiles": []
}
```

没有团队资料时使用如 `{"account_name":"科研论文"}` 的profile，省略团队介绍，不套用SMOOTH固定资料。默认SMOOTH资料中与时间相关的研究规模、服务器数量和职务是用户提供版本，用户要求保留时不得自行更新；如需核实，先提出具体来源差异。
