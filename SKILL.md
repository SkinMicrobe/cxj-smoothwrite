---
name: smoothwrite
description: 接收用户提供的一篇论文 PDF 和一张期刊截图，按已确认的 SMOOTH 蓝橙模板、写法和文风，生成可编辑、可离线分享、可一键复制粘贴进微信公众号编辑器的 HTML。适用于“按模板做这篇论文”“PDF和截图生成公众号”“SMOOTH成果推送”及现有推文修改。
metadata:
  version: "3.0.0"
---

# smoothwrite

## 成品与范围

**固定工作流：用户提供论文 PDF ＋期刊截图（＋可选的往期推文链接）→ 阅读论文并按范文文风撰写 → 从 PDF 提取 Fig → 渲染单文件 HTML → 用户点“复制到公众号”直接粘贴。** 不要求用户另写正文、填写 JSON 或重新提供已内置的团队资料；`content.json`、图片和核对记录由代理在内部生成。

交付**可编辑单文件 `preview.html`**：所有图片内嵌，接收者离线用电脑浏览器打开即可阅读、编辑、放大图片、下载草稿；左侧“复制到公众号”按钮输出微信编辑器能保留的正文。默认不是 Word、全文翻译或长篇解读。

**固定模块顺序（v3 最终版）：期刊截图 → 论文信息 → 橙色竖线团队导语 → 论文概述 → 论文图示（Fig 横滑）→ 往期推荐 → 关于课题组。**

- **没有作者简介模块**（已由用户删除）；`content.json` 出现 `authors` 时脚本会报错，不得恢复。
- **不再嵌入 PDF 逐页页图**。原文区改为“论文图示”：Fig 1、Fig 2……按顺序排成横向滑动卡片，每张卡片含图、中文图题、中文说明、英文原题。
- **往期推荐是模板固定模块**。用户给了往期推文链接就用；没给时用已核实的团队相关论文（标“相关论文原文”），并在交付时提醒用户可替换为公众号往期推文链接；确实没有素材才省略。
- 不设置 SMOOTH 点评、招聘或第一作者模块。除非用户要求，不重新设计模板。

## 写作约定

- 概述通常约 **800–1,100 个可见字符**，约 3 个小节；纯文字、短段落、少量加粗；用具体结论取代设问铺垫和泛化总结。
- 标题有吸引力，但核心对象和问题优先。已确认例子：`BJD｜健康、湿疹、痤疮：你的皮肤微生物到底在代谢什么？`（仅为例子，每篇重新确定关键词）。
- 发表团队信息放在**概述之前的橙色导语**，不在概述内重复。英文期刊名斜体、不加书名号，缩写正体。
- 推文统称“论文”；按真实类型使用“梳理、总结”或“发现、验证”，不把综述中引用的既有研究写成团队新实验。
- 图题：中文标题＋中文说明依据 PDF 的 Figure legends 忠实翻译，不扩写结论；英文原题保留 legend 第一句。
- 新稿先读 [references/writing.md](references/writing.md)。只改标题、字句或删模块时，直接改现有稿及 `content.json`，不重跑整篇写作。

## 工作流程

1. **提取。** 运行 `prepare`：复制 PDF，导出全文文本 `paper_text.md`、低清页面预览 `page-previews/`，并把 PDF 内嵌的大尺寸位图提取到 `figure-candidates/`（已去透明遮罩、无水印行号），`source_manifest.json` 列出候选图和 “Figure N” 出现的页码。
2. **阅读与核对。** 读主文、结论、Figure legends 和关键图表；核对题名、DOI、日期、署名、通讯单位、版本。不能只读摘要。
3. **确定 Fig。** 打开 `figure-candidates/` 与对应页预览，确认每张候选图对应 Figure 几、没有漏图或拼错。图是矢量绘制、没有候选时，用 `crop` 按页面区域渲染（先看页面预览定框）。把选定图片放到工作目录，写入 `content.json` 的 `figures`。
4. **期刊截图。** 核对截图中的期刊、题名、版本与 PDF 一致后写入 `header.image`；不另找封面、不拼造官网截图。缺图时先完成其余部分并说明待补。
5. **写稿。** 参照 `examples/bjd-ljag463/content.json` 的标题思路、导语句式和信息密度，依据当前 PDF 撰写 `content.json`；每个概述小节给出 PDF 页码证据。字段见 [references/content-schema.md](references/content-schema.md)。
6. **渲染与检查。** `render` 生成全部文件并自动执行 `validate`。浏览器工具可用时，检查桌面与约 390px 手机宽度、Fig 横滑、点图放大、编辑、复制按钮。检查要求见 [references/delivery.md](references/delivery.md)。
7. **交付。** 把 `preview.html` 发给用户，一句话说明：用 Chrome/Edge 打开，点“复制到公众号”，在后台正文区粘贴，等图片上传完再保存，用手机预览看横滑。只在有实际缺口时列待补项（如往期推文链接）。

## 脚本

依赖 PyMuPDF、Beautiful Soup、Pillow；先检查现有环境，需要时按 `requirements.txt` 装进隔离环境，不擅自改系统 Python。

```bash
S=/path/to/smoothwrite/scripts/smoothwrite.py

python3 $S prepare --pdf paper.pdf --workdir work/paper
# 矢量图（无候选位图）时：按 PDF 点坐标或 0–1 页面比例裁切
python3 $S crop --prepared work/paper --page 12 --bbox 0.08,0.10,0.92,0.62 --output work/fig2.png
python3 $S render --prepared work/paper --content work/content.json --output outputs/paper
python3 $S validate --output outputs/paper
```

`render --profile other-team.json` 可替换团队资料；`--no-pdf` 不在工具栏内嵌原文 PDF 下载；`--overwrite` 覆盖已有输出（先确认人工改动已同步回 `content.json`）。素材路径相对各自 JSON 文件解析。

## 微信兼容规则（脚本已内置，修改模板时必须遵守）

实际粘贴测试中，微信编辑器会丢掉下列写法，导致乱码、图片不显示或排版散开：

- 不用 `display:table/flex/grid`、`position`、`object-fit`、`scroll-snap`、`calc()`、`<svg>`、`<button>`；复制内容不带 id、class、data-*。
- **小图会被丢弃**：标题前的双圆标记用 CSS 画，logo/二维码嵌入时原始尺寸 ≥200px，`validate` 拒绝短边 <150px 的图片。
- 图片放在表格单元格里会丢；左右并排一律用 `display:inline-block` 的 section。
- 横滑 = 外层 `white-space:nowrap; overflow-x:auto`，内层 `display:inline-block` 卡片（宽 86%，露出下一张提示可滑）。
- 图片压缩到宽 ≤1200px 的 JPEG，正文复制体积控制在 5MB 以内（BJD 范例约 0.8MB）。

## 现有稿修改与发布边界

- 局部修改优先改 `content.json` 后 `render --overwrite`，或直接改用户正在看的 HTML；不要让已删除模块（作者简介、页图翻阅）在重渲染时复活。
- 课题组介绍沿用 `assets/smooth-profile.json` 原文，不擅自压缩、更新数字或加招聘。其他团队用自己的 profile。
- 生成推文不代表授权登录公众号、导入、群发或推送 GitHub；这些由用户另行指定。
