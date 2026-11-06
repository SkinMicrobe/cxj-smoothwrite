#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""smoothwrite v3: PDF preparation, figure extraction, WeChat-safe HTML rendering and checks.

The script never writes prose. The agent reads the paper and authors content.json;
this script turns it into one offline, editable preview.html whose article body
survives a paste into the WeChat Official Account editor.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    from bs4 import BeautifulSoup
    from PIL import Image
except ImportError as exc:
    raise SystemExit('Missing dependency: install requirements.txt (PyMuPDF, beautifulsoup4, Pillow).') from exc

VERSION = '3.0.0'
SKILL = Path(__file__).resolve().parents[1]
ASSETS = SKILL / 'assets'

# ---------------------------------------------------------------------------
# WeChat-safe style constants. Rules (learned from real pastes):
#  * inline styles only; no display:table/flex/grid, position, object-fit,
#    scroll-snap, calc(), <svg>, <button>, ids or classes in the copied body;
#  * tiny images and images inside table cells were dropped by the editor, so
#    icons are drawn with CSS and logo/QR are embedded at >=200px natural size;
#  * horizontal swipe = nowrap + overflow-x:auto box with inline-block cells.
# ---------------------------------------------------------------------------
BLUE, ORANGE = '#365982', '#EEAA91'
ARTICLE_STYLE = ("font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;"
                 "color:#252a30;background:#fff;max-width:560px;margin:0 auto;padding:0;box-sizing:border-box;text-align:left;")
P_STYLE = 'margin:0 0 20px;font-size:16px;line-height:1.9;letter-spacing:.3px;text-align:left;overflow-wrap:anywhere;'
MARK = ('<span style="display:inline-block;width:22px;height:22px;border:2.5px solid ' + BLUE + ';border-radius:50%;'
        'box-sizing:border-box;vertical-align:middle;"></span>'
        '<span style="display:inline-block;width:15px;height:15px;background:' + ORANGE + ';border:2px solid #fff;border-radius:50%;'
        'box-sizing:border-box;vertical-align:middle;margin:6px 10px 0 -8px;"></span>')
FIG_CELL = ('display:inline-block;width:{w};vertical-align:top;margin-right:{mr};white-space:normal;box-sizing:border-box;'
            'background:#fff;border-radius:6px;padding:10px 10px 12px;font-size:13px;line-height:1.7;')
FIG_IMG = 'display:block;width:100%;height:auto;margin:0;border:1px solid #e5e8eb;box-sizing:border-box;background:#fff;'
FORBIDDEN_STYLE = re.compile(r'display\s*:\s*(table|flex|grid)|position\s*:|object-fit|scroll-snap|calc\(', re.I)
KEEP_ATTRS = ('style', 'src', 'href', 'alt')
MAX_ARTICLE_BYTES = 5 * 1024 * 1024


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def esc(value):
    return html.escape(str(value), quote=True)


def formatted(value):
    # Only **bold** and *italic* are accepted; raw HTML is always escaped.
    text = esc(value)
    text = re.sub(r'\*\*([^*\n]+)\*\*', r'<strong style="font-weight:600;color:' + BLUE + r';">\1</strong>', text)
    return re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em style="font-style:italic;">\1</em>', text)


def plain(value):
    return BeautifulSoup(formatted(value), 'html.parser').get_text()


def edit(value):
    return '<span data-edit="">' + formatted(value) + '</span>'


def checked_url(value, required=False):
    if not value and not required:
        return ''
    if not isinstance(value, str) or urlparse(value).scheme not in ('http', 'https') or not urlparse(value).netloc:
        raise ValueError('Expected an http(s) URL: ' + str(value))
    return value


def asset_path(value, base):
    if not value:
        return None
    path = Path(value).expanduser()
    path = path if path.is_absolute() else Path(base) / path
    if not path.is_file():
        raise ValueError('Asset not found: ' + str(path))
    return path.resolve()


def flatten(im):
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, 'white')
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert('RGB')


def save_image(src, dest, max_width=1200, min_width=0, quality=88, fmt='JPEG', nearest=False):
    """Normalise an image for WeChat: bounded width, small file, never tiny."""
    im = flatten(Image.open(src))
    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    if min_width and im.width < min_width:
        im = im.resize((min_width, round(im.height * min_width / im.width)), Image.NEAREST if nearest else Image.LANCZOS)
    dest = Path(dest).with_suffix('.png' if fmt == 'PNG' else '.jpg')
    dest.parent.mkdir(parents=True, exist_ok=True)
    if fmt == 'PNG':
        im.save(dest, 'PNG', optimize=True)
    else:
        im.save(dest, 'JPEG', quality=quality, optimize=True, progressive=True)
    return dest


def data_uri(path):
    path = Path(path)
    kinds = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.pdf': 'application/pdf'}
    if path.suffix.lower() not in kinds:
        raise ValueError('Unsupported embedded asset: ' + str(path))
    return 'data:' + kinds[path.suffix.lower()] + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def zh_date(value):
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', value.strip())
    return f'{int(m[1])}年{int(m[2])}月{int(m[3])}日' if m else value


def heading(text, key):
    return ('<section data-section="' + esc(key) + '" style="margin:42px 0 22px;"><h2 style="color:' + BLUE +
            ';font-size:20px;line-height:1.5;letter-spacing:.6px;font-weight:600;margin:0;">' + MARK +
            '<span style="vertical-align:middle;">' + edit(text) + '</span></h2></section>')


# ---------------------------------------------------------------------------
# prepare / crop
# ---------------------------------------------------------------------------
def extract_figure_candidates(doc, target, min_side):
    out_dir = target / 'figure-candidates'
    out_dir.mkdir(exist_ok=True)
    seen, rows = set(), []
    for page in doc:
        for info in page.get_images(full=True):
            xref, smask, w, h = info[0], info[1], info[2], info[3]
            if xref in seen or min(w, h) < min_side:
                continue
            seen.add(xref)
            pix = fitz.Pixmap(doc, xref)
            if pix.n - pix.alpha >= 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            if pix.alpha:
                pix = fitz.Pixmap(pix, 0)
            mode = 'L' if pix.n == 1 else 'RGB'
            im = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
            if smask:
                mask = fitz.Pixmap(doc, smask)
                m = Image.frombytes('L', (mask.width, mask.height), mask.samples).resize(im.size)
                bg = Image.new('RGB', im.size, 'white')
                bg.paste(im.convert('RGB'), mask=m)
                im = bg
            name = f'p{page.number+1:03}-x{xref}.png'
            im.convert('RGB').save(out_dir / name)
            rows.append({'page': page.number + 1, 'path': 'figure-candidates/' + name, 'width': im.width, 'height': im.height})
    return rows


def figure_mentions(texts):
    """Pages whose text has a 'Figure N' / 'Fig. N' label (legends or figure pages)."""
    found = {}
    for index, text in enumerate(texts, 1):
        for m in re.finditer(r'\b(?:Figure|Fig\.?)\s*(\d{1,2})\b', text):
            found.setdefault(int(m[1]), set()).add(index)
    return {str(k): sorted(v) for k, v in sorted(found.items())}


def prepare(args):
    source = Path(args.pdf).expanduser().resolve()
    target = Path(args.workdir).expanduser().resolve()
    if not source.is_file():
        raise ValueError('PDF not found: ' + str(source))
    if (target / 'source_manifest.json').exists():
        raise ValueError('Prepared work already exists; reuse it or choose a new workdir.')
    doc = fitz.open(source)
    if doc.needs_pass or not len(doc):
        raise ValueError('PDF is encrypted or contains no pages.')
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target / 'source.pdf')
    pages_dir = target / 'page-previews'
    pages_dir.mkdir(exist_ok=True)
    texts = []
    for page in doc:
        texts.append(page.get_text(sort=True))
        # Low-resolution page previews: for locating figures, not for publishing.
        zoom = 900 / page.rect.width
        page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(pages_dir / f'page-{page.number+1:03}.png')
    (target / 'paper_text.md').write_text('\n\n'.join(f'## PDF FILE PAGE {i}\n\n{t}' for i, t in enumerate(texts, 1)), encoding='utf-8')
    candidates = extract_figure_candidates(doc, target, args.min_figure_side)
    manifest = {
        'skill_version': VERSION, 'pdf': 'source.pdf', 'pdf_sha256': digest(source), 'page_count': len(doc),
        'pdf_metadata_unverified': doc.metadata,
        'figure_mentions': figure_mentions(texts),
        'figure_candidates': candidates,
        'low_text_pages': [i for i, t in enumerate(texts, 1) if len(t.strip()) < 40],
    }
    write_json(target / 'source_manifest.json', manifest)
    print(json.dumps({'prepared': str(target), 'pages': len(doc), 'figure_candidates': len(candidates),
                      'figure_mentions': manifest['figure_mentions']}, ensure_ascii=False))


def crop(args):
    """Render a page region (for vector figures that have no embedded raster)."""
    prepared = Path(args.prepared).resolve()
    doc = fitz.open(prepared / 'source.pdf')
    if not 1 <= args.page <= len(doc):
        raise ValueError('Page outside the PDF.')
    page = doc[args.page - 1]
    box = [float(x) for x in args.bbox.split(',')]
    if len(box) != 4:
        raise ValueError('bbox needs x0,y0,x1,y1')
    if all(0 <= v <= 1 for v in box):  # fractions of the page
        r = page.rect
        box = [r.x0 + box[0] * r.width, r.y0 + box[1] * r.height, r.x0 + box[2] * r.width, r.y0 + box[3] * r.height]
    clip = fitz.Rect(*box)
    zoom = args.dpi / 72
    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False).save(out)
    print(json.dumps({'figure': str(out), 'page': args.page, 'bbox_points': [round(v, 1) for v in box]}))


# ---------------------------------------------------------------------------
# content checks
# ---------------------------------------------------------------------------
def check_content(content, count):
    for key in ('title', 'lead'):
        if not isinstance(content.get(key), str) or not content[key].strip():
            raise ValueError('Missing text: ' + key)
    paper = content.get('paper', {})
    for key in ('english_title', 'journal', 'published', 'authors_short', 'article_type', 'version_label'):
        if not isinstance(paper.get(key), str) or not paper[key].strip():
            raise ValueError('Missing verified paper field: ' + key)
    checked_url(paper.get('url'), required=True)
    sections = content.get('overview', [])
    if not sections:
        raise ValueError('An agent-authored overview is required; no automatic prose fallback exists.')
    for section in sections:
        if not section.get('heading') or not section.get('paragraphs') or not all(isinstance(x, str) and x.strip() for x in section['paragraphs']):
            raise ValueError('Overview headings and nonempty paragraphs are required.')
    evidence = content.get('evidence', [])
    for item in evidence:
        if not item.get('claim') or not item.get('pages') or not isinstance(item.get('section'), int) or not 1 <= item['section'] <= len(sections):
            raise ValueError('Evidence needs claim, section (1-based) and pages.')
        if not all(isinstance(n, int) and 1 <= n <= count for n in item['pages']):
            raise ValueError('Evidence page outside the source PDF.')
    if set(x['section'] for x in evidence) != set(range(1, len(sections) + 1)):
        raise ValueError('Every overview section needs at least one PDF evidence entry.')
    if content.get('authors'):
        raise ValueError('v3 template has no author module; remove "authors" from content.json.')
    figures = content.get('figures', [])
    for fig in figures:
        for key in ('label', 'image', 'title_zh', 'description_zh', 'caption_en'):
            if not isinstance(fig.get(key), str) or not fig[key].strip():
                raise ValueError('Figure needs label, image, title_zh, description_zh, caption_en: ' + str(fig.get('label')))
        if not fig.get('pages') or not all(isinstance(n, int) and 1 <= n <= count for n in fig['pages']):
            raise ValueError('Figure pages must be PDF file pages: ' + fig['label'])
    for rec in content.get('recommendations', []):
        checked_url(rec.get('url'), required=True)
        if rec.get('kind') not in ('公众号推文', '相关论文') or not rec.get('title'):
            raise ValueError('Recommendation needs kind (公众号推文/相关论文) and title.')
    header = content.get('header') or {}
    checked_url(header.get('source_url'))


# ---------------------------------------------------------------------------
# article blocks
# ---------------------------------------------------------------------------
def header_html(content, base, out):
    header = content.get('header') or {}
    src = asset_path(header.get('image'), base)
    if not src:
        return ''
    dest = save_image(src, out / 'assets' / 'journal-header', max_width=1200, quality=86)
    result = ('<section id="journal-header" style="margin:0 0 23px;"><img data-zoom src="' + data_uri(dest) + '" alt="' +
              esc(header.get('alt', '期刊官网论文页截图')) + '" style="display:block;width:100%;height:auto;margin:0;border:1px solid #e5e8eb;box-sizing:border-box;">')
    if header.get('caption'):
        result += '<p style="margin:7px 0 0;font-size:11px;line-height:1.7;color:#8a929b;">' + edit(header['caption']) + '</p>'
    return result + '</section>'


def paper_html(content):
    paper = content['paper']
    result = ('<section id="paper-info" style="margin:0;padding:0;overflow-wrap:anywhere;">'
              '<p style="margin:0 0 8px;font-size:14px;font-weight:600;color:' + BLUE + ';">论文信息</p>'
              '<p style="margin:0 0 9px;font-size:14px;line-height:1.8;color:#3e4854;">' + edit(paper['english_title']) + '</p>'
              '<p style="margin:0 0 5px;font-size:12px;line-height:1.9;color:#78828e;">' +
              edit('*' + paper['journal'] + '* · ' + zh_date(paper['published']) + '在线发表') + '<br>' + edit(paper['authors_short']))
    if paper.get('doi'):
        result += '<br>DOI：' + edit(paper['doi'])
    result += ('</p><p style="margin:8px 0 0;font-size:12px;line-height:1.7;"><a data-link="paper" href="' + esc(paper['url']) +
               '" style="color:' + BLUE + ';text-decoration:underline;">查看期刊原文</a></p>')
    result += ('<p id="takeaway" style="margin:18px 0 0;border-left:2px solid ' + ORANGE + ';padding-left:12px;font-size:15px;'
               'line-height:1.85;color:' + BLUE + ';overflow-wrap:anywhere;">' + edit(content['lead']) + '</p></section>')
    return result


def overview_html(content):
    result = heading('论文概述', 'reading') + '<section id="overview">'
    for section in content['overview']:
        result += '<h3 style="margin:22px 0 10px;font-size:16px;font-weight:600;line-height:1.5;color:' + BLUE + ';">' + edit(section['heading']) + '</h3>'
        result += ''.join('<p style="' + P_STYLE + '">' + edit(p) + '</p>' for p in section['paragraphs'])
    return result + '</section>'


def figures_html(content, base, out):
    figures = content.get('figures', [])
    if not figures:
        return ''
    n = len(figures)
    cells = []
    for i, fig in enumerate(figures, 1):
        dest = save_image(asset_path(fig['image'], base), out / 'assets' / 'figures' / f'figure-{i}', max_width=1200, quality=88)
        style = FIG_CELL.format(w='86%' if n > 1 else '100%', mr='10px' if i < n else '0')
        counter = ('<span style="color:#9aa3ad;font-weight:400;font-size:12px;padding-left:8px;">' + f'{i} / {n}</span>') if n > 1 else ''
        short = re.sub(r'^(Figure|Fig\.?)\s*', '图 ', fig['label'])
        cells.append(
            '<section data-figure style="' + style + '">'
            '<p style="margin:0 0 8px;font-size:13px;line-height:1.6;font-weight:600;letter-spacing:.5px;">'
            '<span style="display:inline-block;padding:1px 8px;border-radius:2px;background:' + BLUE + ';color:#fff;">' + esc(fig['label']) + '</span>' + counter + '</p>'
            '<img data-zoom src="' + data_uri(dest) + '" alt="论文 ' + esc(fig['label']) + '" style="' + FIG_IMG + '">'
            '<p style="margin:10px 0 0;font-size:14px;line-height:1.75;font-weight:600;color:#252a30;">' + edit(short + '｜' + fig['title_zh']) + '</p>'
            '<p style="margin:4px 0 0;font-size:13px;line-height:1.8;color:#4d5660;text-align:justify;overflow-wrap:anywhere;">' + edit(fig['description_zh']) + '</p>'
            '<p style="margin:4px 0 0;font-size:12px;line-height:1.7;color:#8a929b;font-style:italic;overflow-wrap:anywhere;">' + edit(fig['label'] + '. ' + fig['caption_en']) + '</p>'
            '</section>')
    if n > 1:
        body = ('<section id="fig-strip" style="width:100%;overflow-x:auto;overflow-y:hidden;white-space:nowrap;'
                '-webkit-overflow-scrolling:touch;box-sizing:border-box;padding:0 0 6px;">' + ''.join(cells) + '</section>'
                '<p style="margin:8px 0 0;font-size:12px;line-height:1.8;text-align:center;color:#647080;">← 左右滑动查看 '
                + esc(figures[0]['label'].replace('Figure', 'Fig')) + '–' + esc(re.sub(r'^(Figure|Fig\.?)\s*', '', figures[-1]['label'])) + ' →</p>')
    else:
        body = cells[0]
    paper = content['paper']
    year = paper['published'][:4]
    source = content.get('figure_source') or ('图片来源：' + paper['authors_short'].replace(', et al.', ' et al.').split(',')[0] +
                                              ', et al. *' + paper.get('journal_abbrev', paper['journal']) + '* ' + year +
                                              ('. DOI: ' + paper['doi'] if paper.get('doi') else '') + ' · 点击图片可放大')
    return ('<section id="figures">' + heading(content.get('figures_heading', '论文图示'), 'figures') +
            '<section style="background:#f4f6f8;border-radius:8px;padding:14px 12px 12px;">' + body +
            '<p style="margin:2px 0 0;font-size:11px;line-height:1.8;text-align:center;color:#89939e;overflow-wrap:anywhere;">' + edit(source) + '</p>'
            '</section></section>')


def wechat_post_image_html(image_path, output_path, link_key):
    image = save_image(image_path, output_path, max_width=1200)
    return ('<p style="margin:10px 0 0;border:1px solid #dce5ef;">'
            '<a data-link="' + link_key + '" style="display:block;text-decoration:none;">'
            '<img src="' + data_uri(image) + '" alt="往期推文配图" '
            'style="display:block;width:100%;height:auto;margin:0;">'
            '<span style="display:block;padding:8px 6px;text-align:center;font-size:13px;line-height:1.6;'
            'font-weight:600;background-color:#eaf1f8;color:' + BLUE + ';">点击图片查看往期推文</span></a></p>')


def recommendations_html(content, base, out):
    if 'recommendations' not in content:
        return ''
    recs = content['recommendations']
    cover = asset_path(content.get('wechat_post_image'), base) if recs and content.get('reserve_wechat_card') else None
    card_style = 'padding:14px;border:1px solid #dce5ef;border-radius:8px;background-color:#f8fafc;'
    outer_style = ' style="' + card_style + '"' if cover else ''
    result = heading(content.get('recommendations_heading', '往期推荐'), 'recommendations') + '<section id="recommendations"' + outer_style + '>'
    if not recs:
        return result + '<p style="margin:0;line-height:1.75;"><br></p></section>'
    for i, rec in enumerate(recs, 1):
        key = 'rec' + str(i)
        last = i == len(recs)
        kind = '往期推文' if rec['kind'] == '公众号推文' else '相关论文原文'
        meta = rec.get('meta_label') or (kind + (' · ' + rec['meta'] if rec.get('meta') else ''))
        rec_cover = asset_path(rec.get('wechat_image'), base)
        spacing = 'margin:0 0 ' + ('6px' if last else '20px') + ';'
        layout = card_style if rec_cover else ('' if last else 'padding:0 0 18px;border-bottom:1px solid #e9edf1;')
        result += ('<section data-rec style="' + spacing + layout + '">'
                   '<p style="margin:0 0 4px;font-size:15px;font-weight:600;line-height:1.75;"><a data-link="' + key + '" href="' + esc(rec['url']) +
                   '" style="color:#252a30;text-decoration:none;">' + edit(rec['title']) + '</a></p>'
                   '<p style="margin:0;font-size:12px;line-height:1.75;color:#8a929b;">' + edit(meta) + '</p>')
        if rec.get('reason'):
            result += '<p style="margin:8px 0 0;font-size:13px;line-height:1.8;color:#6f7c8a;">' + edit(rec['reason']) + '</p>'
        result += ('<p style="margin:6px 0 0;font-size:12px;line-height:1.7;"><a data-link="' + key + '" href="' + esc(rec['url']) +
                   '" style="color:' + BLUE + ';text-decoration:none;">' + ('阅读推文 ›' if rec['kind'] == '公众号推文' else '查看原文 ›') + '</a></p>')
        if rec_cover:
            result += wechat_post_image_html(rec_cover, out / 'assets' / ('wechat-post-' + str(i)), 'wechat-post-' + key)
        result += '</section>'
    if content.get('reserve_wechat_card'):
        if cover:
            result += wechat_post_image_html(cover, out / 'assets' / 'wechat-post', 'wechat-post')
        else:
            result += ('<p style="margin:12px 0 0;background-color:#f2f6fa;border:1px solid #dce5ef;">'
                       '<a data-link="wechat-post" style="display:block;padding:10px 12px;font-size:14px;line-height:1.6;'
                       'font-weight:600;color:' + BLUE + ';text-decoration:none;">阅读往期推文 ›</a></p>')
    return result + '</section>'


def group_html(profile, base, out):
    group = profile.get('group')
    if not group:
        return ''
    paragraphs = group.get('paragraphs', [])
    if not paragraphs:
        raise ValueError('Group profile requires supplied introduction paragraphs.')
    logo_src, qr_src = asset_path(profile.get('logo'), base), asset_path(profile.get('qr'), base)
    result = heading('关于课题组', 'group') + '<section id="group-profile">'
    result += '<section style="padding:0 0 17px;border-bottom:1px solid #e4e8ee;margin:0 0 20px;">'
    if logo_src:
        logo = save_image(logo_src, out / 'assets' / 'lab-logo', max_width=240, min_width=200, quality=90)
        result += ('<section style="display:inline-block;width:56px;vertical-align:middle;"><img src="' + data_uri(logo) +
                   '" alt="课题组标志" style="display:block;width:52px;height:auto;margin:0;"></section>')
    result += '<section style="display:inline-block;width:' + ('75%' if logo_src else '100%') + ';vertical-align:middle;padding-left:' + ('8px' if logo_src else '0') + ';box-sizing:border-box;">'
    result += '<p style="margin:0 0 3px;font-size:18px;font-weight:700;line-height:1.45;color:#78735e;">' + edit(group.get('brand', profile.get('account_name', ''))) + '</p>'
    result += ''.join('<p style="margin:1px 0 0;font-size:14px;font-weight:600;line-height:1.45;color:#8b9291;">' + edit(x) + '</p>' for x in group.get('english_lines', []))
    result += '</section></section>'
    result += ''.join('<p data-group-paragraph style="margin:0 0 19px;font-size:14px;line-height:1.95;letter-spacing:.1px;text-align:left;'
                      'overflow-wrap:anywhere;color:#4d5660;">' + edit(p) + '</p>' for p in paragraphs)
    result += '<section style="border-top:1px solid #c9c9bf;padding-top:15px;margin-top:4px;">'
    if qr_src:
        qr = save_image(qr_src, out / 'assets' / 'group-qr', max_width=600, min_width=300, fmt='PNG', nearest=True)
        result += ('<section class="photo-slot" data-photo="qr" style="width:120px;margin:0 auto 14px;"><img src="' + data_uri(qr) +
                   '" alt="课题组二维码" style="display:block;width:120px;height:auto;margin:0;"></section>')
    for key, default_label in (('website', '实验室网站：'), ('email', '联系邮箱：')):
        value = group.get(key)
        if not value:
            continue
        if key == 'website':
            href = checked_url(value, required=True)
        else:
            if not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', value):
                raise ValueError('Invalid group email.')
            href = 'mailto:' + value
        result += ('<p style="margin:0 0 6px;font-size:12px;line-height:1.8;text-align:center;overflow-wrap:anywhere;color:#78735e;">' +
                   edit(group.get(key + '_label', default_label)) + '<a href="' + esc(href) + '" style="color:' + BLUE +
                   ';text-decoration:none;">' + edit(value) + '</a></p>')
    return result + '</section></section>'


def build_article(content, content_base, profile, profile_base, out):
    return (header_html(content, content_base, out) + paper_html(content) + overview_html(content) +
            figures_html(content, content_base, out) + recommendations_html(content, content_base, out) + group_html(profile, profile_base, out))


def wechat_body(article_html):
    """Python twin of editor.js sanitize(): what the copy button puts on the clipboard."""
    soup = BeautifulSoup('<section style="' + ARTICLE_STYLE + '">' + article_html + '</section>', 'html.parser')
    for el in soup.select('[data-editor-only], button, svg, script, input, dialog'):
        el.decompose()
    for el in soup.find_all(True):
        el.attrs = {k: v for k, v in el.attrs.items() if k in KEEP_ATTRS}
        if el.name == 'img':
            el['style'] = el.get('style', '').rstrip(';') + ';max-width:100%;'
    return str(soup)


def tools_html(content, pdf_uri, figure_count):
    pairs = [('paper', '论文原文地址', content['paper']['url'])] + [
        ('rec' + str(i + 1), '往期推荐 ' + str(i + 1).zfill(2), r['url']) for i, r in enumerate(content.get('recommendations', []))]
    pairs.extend(('wechat-post-rec' + str(i), f'往期推荐 {i:02d} 的公众号文章链接', '')
                 for i, rec in enumerate(content.get('recommendations', []), 1) if rec.get('wechat_image'))
    if content.get('reserve_wechat_card') and content.get('recommendations'):
        pairs.append(('wechat-post', '往期公众号文章链接', ''))
    inputs = ''.join('<label>' + esc(label) + '<input type="url" data-link-input="' + key + '" value="' + esc(url) + '"></label>' for key, label, url in pairs)
    pdf = ('<details><summary>原文 PDF</summary><p><a download="original-paper.pdf" href="' + pdf_uri + '">下载完整原文 PDF</a></p></details>') if pdf_uri else ''
    return ('<span class="brand-rule"></span><h1>SMOOTH 论文推文</h1><p class="lead">蓝橙色模板 · 论文图示 Fig 1–' + str(figure_count) +
            ' 横滑<br>往期推荐 · 课题组介绍</p><section class="buttons">'
            '<button id="edit" class="action primary" aria-pressed="false">编辑文字与二维码</button>'
            '<button id="copy" class="action">复制到公众号</button>'
            '<button id="save" class="action">下载可编辑草稿</button>'
            '<button id="export" class="action">下载纯正文 HTML</button></section><p id="status" role="status" aria-live="polite"></p>'
            '<details><summary>设置论文与往期链接</summary>' + inputs + '</details>' + pdf +
            '<details><summary>在公众号后台使用</summary>'
            '<p>1. 点“复制到公众号”，在公众号后台正文区直接粘贴；标题填在后台标题栏。</p>'
            '<p>2. 粘贴后等待图片全部上传完成再保存。</p>'
            '<p>3. 论文图示为横向滑动结构，电脑端编辑器里可能显示为一行，以手机预览为准。</p>'
            '<p>4. 未认证公众号的正文外链可能无法点击，可把论文链接填到“阅读原文”。</p></details>'
            '<p class="tip">点“复制到公众号”后直接粘贴即可。<br>修改后请下载草稿保存。</p>')


def render(args):
    prepared, input_path, out = Path(args.prepared).resolve(), Path(args.content).resolve(), Path(args.output).resolve()
    if (out / 'preview.html').exists() and not args.overwrite:
        raise ValueError('Output exists. Reconcile manual edits, then use --overwrite if authorized.')
    manifest = read_json(prepared / 'source_manifest.json')
    if digest(prepared / manifest['pdf']) != manifest['pdf_sha256']:
        raise ValueError('Prepared PDF hash mismatch.')
    content = read_json(input_path)
    check_content(content, manifest['page_count'])
    profile_path = Path(args.profile).resolve() if args.profile else ASSETS / 'smooth-profile.json'
    profile = read_json(profile_path)
    if out.exists() and args.overwrite:
        shutil.rmtree(out / 'assets', ignore_errors=True)
    (out / 'assets').mkdir(parents=True, exist_ok=True)
    article = build_article(content, input_path.parent, profile, profile_path.parent, out)
    pdf_uri = ''
    if not args.no_pdf:
        shutil.copyfile(prepared / manifest['pdf'], out / 'original-paper.pdf')
        pdf_uri = data_uri(out / 'original-paper.pdf')
    native = ('<h1>' + edit(content['title']) + '</h1><p><span class="account">' + edit(profile.get('account_name', '科研论文')) +
              '</span>　·　样稿预览</p><p class="native-note">此处模拟微信标题区，不包含在复制正文内</p>')
    values = {'TITLE': esc(content['title']), 'CSS': (ASSETS / 'preview.css').read_text(encoding='utf-8'),
              'TOOLS': tools_html(content, pdf_uri, len(content.get('figures', []))), 'NATIVE_HEAD': native,
              'ARTICLE_STYLE': ARTICLE_STYLE, 'ARTICLE': article, 'SCRIPT': (ASSETS / 'editor.js').read_text(encoding='utf-8')}
    template = (ASSETS / 'preview-template.html').read_text(encoding='utf-8')
    (out / 'preview.html').write_text(re.sub(r'@@([A-Z_]+)@@', lambda m: values[m[1]], template), encoding='utf-8')
    (out / 'body-article.html').write_text(
        '<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' +
        esc(content['title']) + '</title><body style="margin:0;padding:16px;">' + wechat_body(article) + '</body></html>', encoding='utf-8')
    md = '# ' + content['title'] + '\n\n' + content['lead'] + '\n\n'
    for section in content['overview']:
        md += '## ' + section['heading'] + '\n\n' + '\n\n'.join(section['paragraphs']) + '\n\n'
    for fig in content.get('figures', []):
        md += '**' + fig['label'] + '｜' + fig['title_zh'] + '**  \n' + fig['description_zh'] + '\n\n'
    for rec in content.get('recommendations', []):
        md += '- 往期推荐：[' + rec['title'] + '](' + rec['url'] + ')\n'
    md += '\n原文：' + content['paper']['english_title'] + '\n\n*' + content['paper']['journal'] + '*，' + zh_date(content['paper']['published']) + '在线发表\n\n' + content['paper']['url'] + '\n'
    (out / 'article.md').write_text(md, encoding='utf-8')
    write_json(out / 'paper_metadata.json', dict(content['paper'], pdf_sha256=manifest['pdf_sha256'], pdf_pages=manifest['page_count']))
    tsv = 'section\tclaim\tsource_pdf_pages\tnote\n'
    for row in content['evidence']:
        tsv += '\t'.join(str(x).replace('\t', ' ').replace('\n', ' ') for x in (row['section'], row['claim'], ','.join(map(str, row['pages'])), row.get('note', ''))) + '\n'
    (out / 'evidence-map.tsv').write_text(tsv, encoding='utf-8')
    contract = {
        'skill_version': VERSION, 'page_count': manifest['page_count'], 'pdf_sha256': manifest['pdf_sha256'], 'pdf_embedded': bool(pdf_uri),
        'title': content['title'], 'lead_text': plain(content['lead']),
        'overview_text': [[plain(p) for p in s['paragraphs']] for s in content['overview']],
        'figure_count': len(content.get('figures', [])), 'recommendation_count': len(content.get('recommendations', [])),
        'group_paragraphs': (profile.get('group') or {}).get('paragraphs', []),
        'header_present': bool((content.get('header') or {}).get('image')),
    }
    write_json(out / 'content-contract.json', contract)
    notes = ['# 内容核对与交付记录', '', '正文由代理阅读论文后撰写；渲染脚本不生成 fallback 正文。', '',
             '- smoothwrite 版本：' + VERSION, '- PDF 文件页数：' + str(manifest['page_count']), '- PDF SHA-256：' + manifest['pdf_sha256'],
             '- 真实文章类型：' + content['paper']['article_type'], '- PDF 版本：' + content['paper']['version_label'],
             '- 论文图示：' + str(contract['figure_count']) + ' 张；往期推荐：' + str(contract['recommendation_count']) + ' 条',
             '- 默认未完成微信后台粘贴与手机预览。']
    if not contract['header_present']:
        notes.append('- 期刊头图未提供，未模拟生成。')
    if not contract['figure_count']:
        notes.append('- 未提供论文图示，页面省略该模块。')
    if not contract['recommendation_count']:
        if 'recommendations' in content:
            notes.append('- 往期推荐已留空，由用户在公众号后台添加。')
        else:
            notes.append('- 未提供往期推荐，页面省略该模块。')
    notes += ['', '## 本稿核对备注', ''] + ['- ' + str(x) for x in content.get('review_notes', [])]
    (out / 'review_notes.md').write_text('\n'.join(notes) + '\n', encoding='utf-8')
    errors = validate_output(out)
    if errors:
        raise ValueError('Rendered artifact failed checks: ' + '; '.join(errors))
    files = [{'path': str(p.relative_to(out)), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'output_manifest.json']
    write_json(out / 'output_manifest.json', {'skill_version': VERSION, 'automatic_checks_passed': True, 'visual_check': 'not_run', 'wechat_paste_check': 'not_run', 'files': files})
    body_kb = (out / 'body-article.html').stat().st_size // 1024
    print(json.dumps({'preview': str(out / 'preview.html'), 'figures': contract['figure_count'], 'recommendations': contract['recommendation_count'], 'wechat_body_kb': body_kb}, ensure_ascii=False))


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
def check_wechat_markup(root, name, errors):
    for el in root.find_all(True):
        if el.name in ('svg', 'button', 'script', 'iframe', 'table', 'input', 'video'):
            errors.append(f'{name}: <{el.name}> is not kept by the WeChat editor')
        style = el.get('style', '')
        if FORBIDDEN_STYLE.search(style):
            errors.append(f'{name}: WeChat-unsafe style "{FORBIDDEN_STYLE.search(style)[0]}" on <{el.name}>')
    for img in root.find_all('img'):
        src = img.get('src', '')
        if not src.startswith('data:image/'):
            errors.append(f'{name}: image is not embedded')
            continue
        im = Image.open(io.BytesIO(base64.b64decode(src.split(',', 1)[1])))
        if min(im.size) < 150:
            errors.append(f'{name}: image {im.size} is too small; WeChat drops tiny pasted images')


def validate_output(out):
    errors = []
    try:
        contract = read_json(out / 'content-contract.json')
        if contract['pdf_embedded'] and digest(out / 'original-paper.pdf') != contract['pdf_sha256']:
            errors.append('Original PDF hash mismatch')
        prev = BeautifulSoup((out / 'preview.html').read_text(encoding='utf-8'), 'html.parser')
        art = prev.select_one('#article')
        if art is None:
            return ['preview.html: missing #article']
        if prev.title is None or prev.title.get_text() != contract['title']:
            errors.append('preview.html: document title mismatch')
        h1 = prev.select_one('.native-head h1')
        if h1 is None or h1.get_text() != contract['title']:
            errors.append('preview.html: visible title mismatch')
        if art.select_one('[data-section="authors"]'):
            errors.append('preview.html: author module must not exist in v3')
        if len(art.select('[data-figure]')) != contract['figure_count']:
            errors.append('preview.html: figure count mismatch')
        if len(art.select('[data-rec]')) != contract['recommendation_count']:
            errors.append('preview.html: recommendation count mismatch')
        if bool(art.select_one('#journal-header')) != contract['header_present']:
            errors.append('preview.html: header presence mismatch')
        if art.select_one('#takeaway').get_text() != contract['lead_text']:
            errors.append('preview.html: lead mismatch')
        overview = art.select_one('#overview').get_text()
        if any(p not in overview for s in contract['overview_text'] for p in s):
            errors.append('preview.html: overview mismatch')
        if [p.get_text() for p in art.select('[data-group-paragraph]')] != contract['group_paragraphs']:
            errors.append('preview.html: supplied group copy mismatch')
        order = [s['data-section'] for s in art.select('[data-section]')]
        expected = [k for k in ('reading', 'figures', 'recommendations', 'group') if k in order]
        if order != expected:
            errors.append('preview.html: module order ' + str(order))
        ids = [el['id'] for el in prev.select('[id]')]
        if len(ids) != len(set(ids)):
            errors.append('preview.html: duplicate DOM IDs')
        if contract['pdf_embedded']:
            link = prev.select_one('a[download="original-paper.pdf"]')
            if link is None or base64.b64decode(link['href'].split(',', 1)[1]) != (out / 'original-paper.pdf').read_bytes():
                errors.append('preview.html: embedded PDF mismatch')
        check_wechat_markup(art, 'preview.html#article', errors)
        body_raw = (out / 'body-article.html').read_text(encoding='utf-8')
        body = BeautifulSoup(body_raw, 'html.parser').body
        check_wechat_markup(body, 'body-article.html', errors)
        if any(el.get('id') or el.get('class') for el in body.find_all(True)):
            errors.append('body-article.html: ids/classes must be stripped')
        if len(body.find_all('img')) != len(art.find_all('img')):
            errors.append('body-article.html: image count differs from preview')
        if contract['lead_text'] not in body.get_text():
            errors.append('body-article.html: lead missing')
        if len(body_raw.encode()) > MAX_ARTICLE_BYTES:
            errors.append('body-article.html: over 5 MB; WeChat paste may fail')
        for link in prev.select('a[href]'):
            if urlparse(link['href']).scheme not in ('http', 'https', 'mailto', 'data', ''):
                errors.append('unsafe link scheme')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(str(exc))
    return sorted(set(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', action='version', version='smoothwrite ' + VERSION)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare', help='Copy the PDF, extract text, page previews and figure candidates.')
    p.add_argument('--pdf', required=True)
    p.add_argument('--workdir', required=True)
    p.add_argument('--min-figure-side', type=int, default=300, help='Smallest embedded image side kept as a figure candidate.')
    c = commands.add_parser('crop', help='Render a page region to PNG (vector figures).')
    c.add_argument('--prepared', required=True)
    c.add_argument('--page', type=int, required=True, help='PDF file page, 1-based.')
    c.add_argument('--bbox', required=True, help='x0,y0,x1,y1 in PDF points, or 0-1 fractions of the page.')
    c.add_argument('--output', required=True)
    c.add_argument('--dpi', type=int, default=220)
    r = commands.add_parser('render', help='Render an agent-authored content JSON into preview.html and body-article.html.')
    r.add_argument('--prepared', required=True)
    r.add_argument('--content', required=True)
    r.add_argument('--output', required=True)
    r.add_argument('--profile')
    r.add_argument('--no-pdf', action='store_true', help='Do not embed the original PDF download in the tools panel.')
    r.add_argument('--overwrite', action='store_true')
    v = commands.add_parser('validate', help='Structural and WeChat-markup checks; not a scientific or visual review.')
    v.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            prepare(args)
        elif args.command == 'crop':
            crop(args)
        elif args.command == 'render':
            render(args)
        else:
            errors = validate_output(Path(args.output).resolve())
            print(json.dumps({'valid': not errors, 'errors': errors}, ensure_ascii=False))
            return 1 if errors else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
