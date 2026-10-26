#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic PDF preparation, HTML rendering and artifact checks; no prose writer."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import fitz
    from bs4 import BeautifulSoup
except ImportError as exc:
    raise SystemExit('Missing dependency: install requirements.txt in the chosen Python environment.') from exc

SKILL = Path(__file__).resolve().parents[1]
ASSETS = SKILL / 'assets'
ARTICLE_STYLE = "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;color:#252a30;background:#fff;max-width:560px;margin:0 auto;padding:0;box-sizing:border-box;text-align:left;"
P_STYLE = 'margin:0 0 20px;font-size:16px;line-height:1.9;letter-spacing:.3px;text-align:left;overflow-wrap:anywhere;'
PAGE_STYLE = 'display:inline-block;width:92%;height:auto;vertical-align:top;margin-right:10px;border:1px solid #e5e8eb;box-sizing:border-box;scroll-snap-align:start;background:#fff;'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def esc(value):
    return html.escape(str(value), quote=True)


def formatted(value):
    # Only **bold** and *italic* are accepted; raw HTML is never interpolated.
    text = esc(value)
    text = re.sub(r'\*\*([^*\n]+)\*\*', r'<strong style="font-weight:600;color:#365982;">\1</strong>', text)
    return re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em style="font-style:italic;">\1</em>', text)


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


def data_uri(path):
    path = Path(path)
    kinds = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.pdf': 'application/pdf'}
    if path.suffix.lower() not in kinds:
        raise ValueError('Unsupported embedded asset: ' + str(path))
    return 'data:' + kinds[path.suffix.lower()] + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def save_image(path, out, label):
    if path is None:
        return ''
    dest = out / 'assets' / (label + path.suffix.lower())
    if path.resolve() != dest.resolve():
        shutil.copyfile(path, dest)
    return data_uri(dest)


def heading(text, key):
    return '<section data-section="' + esc(key) + '" style="margin:42px 0 22px;"><h2 style="color:#365982;font-size:20px;line-height:1.5;font-weight:600;margin:0;"><span aria-hidden="true" style="display:inline-block;position:relative;width:34px;height:26px;vertical-align:middle;margin-right:10px;"><span style="position:absolute;left:0;top:1px;width:24px;height:24px;border:1.5px solid #365982;border-radius:50%;"></span><span style="position:absolute;left:17px;top:6px;width:18px;height:18px;border:2px solid #fff;border-radius:50%;background:#EEAA91;"></span></span><span style="vertical-align:middle;">' + edit(text) + '</span></h2></section>'


def prepare(args):
    source = Path(args.pdf).expanduser().resolve()
    target = Path(args.workdir).expanduser().resolve()
    if not source.is_file():
        raise ValueError('PDF not found: ' + str(source))
    if (target / 'source_manifest.json').exists():
        raise ValueError('Prepared work already exists; reuse it or choose a new workdir.')
    if not 600 <= args.page_width <= 4000:
        raise ValueError('page-width must be between 600 and 4000.')
    doc = fitz.open(source)
    if doc.needs_pass or not len(doc):
        raise ValueError('PDF is encrypted or contains no pages.')
    target.mkdir(parents=True, exist_ok=True)
    pages_dir = target / 'paper-pages'
    pages_dir.mkdir(exist_ok=True)
    if source != target / 'source.pdf':
        shutil.copyfile(source, target / 'source.pdf')
    pages, texts = [], []
    for index, page in enumerate(doc):
        path = pages_dir / f'page-{index+1:03}.jpg'
        pix = page.get_pixmap(matrix=fitz.Matrix(args.page_width / page.rect.width, args.page_width / page.rect.width), alpha=False)
        path.write_bytes(pix.tobytes('jpeg', jpg_quality=87))
        text = page.get_text(sort=True)
        texts.append(f'## PDF FILE PAGE {index+1}\n\n{text}')
        pages.append({'page': index+1, 'path': str(path.relative_to(target)), 'width': pix.width, 'height': pix.height, 'sha256': digest(path), 'text_chars': len(text.strip())})
    (target / 'paper_text.md').write_text('\n\n'.join(texts), encoding='utf-8')
    manifest = {'pdf': 'source.pdf', 'pdf_sha256': digest(source), 'page_count': len(doc), 'pdf_metadata_unverified': doc.metadata, 'pages': pages, 'low_text_pages': [p['page'] for p in pages if p['text_chars'] < 40]}
    write_json(target / 'source_manifest.json', manifest)
    print(json.dumps({'prepared': str(target), 'pages': len(doc), 'low_text_pages': manifest['low_text_pages']}, ensure_ascii=False))


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
    if set(x['section'] for x in evidence) != set(range(1, len(sections)+1)):
        raise ValueError('Every overview section needs at least one PDF evidence entry.')
    for author in content.get('authors', []):
        if not author.get('name') or not author.get('role') or not author.get('bullets'):
            raise ValueError('Each author needs verified name, role and bullets.')
        if author.get('profile_name') and author['role'] != '通讯作者':
            raise ValueError('Built-in author profile requires verified corresponding-author role.')
    for rec in content.get('recommendations', []):
        checked_url(rec.get('url'), required=True)
        if rec.get('kind') not in ('公众号推文', '相关论文') or not rec.get('title'):
            raise ValueError('Recommendation needs an explicit kind and title.')
    header = content.get('header') or {}
    checked_url(header.get('source_url'))


def group_html(profile, profile_base, out):
    group = profile.get('group')
    if not group:
        return ''
    paragraphs = group.get('paragraphs', [])
    if not paragraphs:
        raise ValueError('Group profile requires supplied introduction paragraphs.')
    logo = save_image(asset_path(profile.get('logo'), profile_base), out, 'lab-logo')
    qr = save_image(asset_path(profile.get('qr'), profile_base), out, 'group-qr')
    left = '<section style="display:table-cell;width:58px;vertical-align:middle;"><img src="' + logo + '" alt="课题组标志" style="display:block;width:52px;height:67px;object-fit:contain;"></section>' if logo else ''
    brand = '<p style="margin:0 0 3px;font-size:18px;font-weight:700;line-height:1.45;color:#78735e;">' + edit(group.get('brand', profile.get('account_name', ''))) + '</p>'
    english = ''.join('<p style="margin:1px 0;font-size:14px;font-weight:600;line-height:1.45;color:#8b9291;">' + edit(line) + '</p>' for line in group.get('english_lines', []))
    result = heading('关于课题组', 'group') + '<section id="group-profile"><section style="display:table;width:100%;table-layout:fixed;padding-bottom:17px;border-bottom:1px solid #e4e8ee;margin-bottom:20px;">' + left + '<section style="display:table-cell;vertical-align:middle;padding-left:7px;">' + brand + english + '</section></section>'
    result += ''.join('<p data-group-paragraph style="margin:0 0 19px;font-size:14px;line-height:1.95;overflow-wrap:anywhere;color:#4d5660;">' + edit(p) + '</p>' for p in paragraphs)
    result += '<section style="border-top:1px solid #c9c9bf;padding-top:15px;">'
    if qr:
        result += '<section class="photo-slot" data-photo="qr" style="width:76px;height:76px;margin:0 auto 14px;"><img src="' + qr + '" alt="课题组二维码" style="display:block;width:100%;height:100%;object-fit:contain;"></section>'
    for key, default_label in [('website', '实验室网站：'), ('email', '联系邮箱：')]:
        value = group.get(key)
        if not value:
            continue
        if key == 'website':
            href = checked_url(value, required=True)
        else:
            if not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', value):
                raise ValueError('Invalid group email.')
            href = 'mailto:' + value
        result += '<p style="margin:0 0 6px;font-size:12px;line-height:1.8;text-align:center;overflow-wrap:anywhere;color:#78735e;">' + edit(group.get(key + '_label', default_label)) + '<a href="' + esc(href) + '" style="color:#365982;text-decoration:none;">' + edit(value) + '</a></p>'
    return result + '</section></section>'


def build_article(content, content_base, profile, profile_base, manifest, prepared, out):
    paper = content['paper']
    result = ''
    header = content.get('header') or {}
    header_image = asset_path(header.get('image'), content_base)
    if header_image:
        uri = save_image(header_image, out, 'journal-header')
        result += '<section id="journal-header" style="margin:0 0 23px;"><img data-zoom tabindex="0" role="button" src="' + uri + '" alt="' + esc(header.get('alt', '期刊官网或论文首页截图')) + '" style="display:block;width:100%;height:auto;border:1px solid #e5e8eb;cursor:zoom-in;">'
        if header.get('caption'):
            result += '<p style="margin:7px 0 0;font-size:11px;line-height:1.7;color:#8a929b;">' + edit(header['caption']) + '</p>'
        result += '</section>'
    result += '<section id="paper-info"><p style="margin:0 0 8px;font-size:14px;font-weight:600;color:#365982;">论文信息</p><p style="margin:0 0 9px;font-size:14px;line-height:1.8;color:#3e4854;">' + edit(paper['english_title']) + '</p>'
    result += '<p style="margin:0 0 5px;font-size:12px;line-height:1.9;color:#78828e;">' + edit('*' + paper['journal'] + '* · ' + paper['published'] + ' 在线发表') + '<br>' + edit(paper['authors_short'])
    if paper.get('doi'):
        result += '<br>DOI：' + edit(paper['doi'])
    result += '</p><p style="margin:8px 0 0;font-size:12px;"><a data-link="paper" href="' + esc(paper['url']) + '" target="_blank" rel="noopener noreferrer" style="color:#365982;">查看期刊原文</a></p>'
    result += '<p id="takeaway" style="margin:18px 0 0;border-left:2px solid #EEAA91;padding-left:12px;font-size:15px;line-height:1.85;color:#365982;overflow-wrap:anywhere;">' + edit(content['lead']) + '</p></section>'
    result += heading('论文概述', 'reading') + '<section id="overview">'
    for section in content['overview']:
        result += '<h3 style="margin:22px 0 10px;font-size:16px;font-weight:600;line-height:1.5;color:#365982;">' + edit(section['heading']) + '</h3>'
        result += ''.join('<p style="' + P_STYLE + '">' + edit(p) + '</p>' for p in section['paragraphs'])
    result += '</section><section id="original">' + heading('论文原文', 'original') + '<section style="background:#f0f4f6;padding:14px 12px;border-radius:8px;"><section id="page-strip" role="region" aria-label="论文原文页图，左右滑动翻页" tabindex="0" style="width:100%;overflow-x:auto;white-space:nowrap;scroll-snap-type:x mandatory;scrollbar-width:none;box-sizing:border-box;padding-bottom:8px;">'
    for page in manifest['pages']:
        source = prepared / page['path']
        target = out / 'assets/paper-pages' / source.name
        shutil.copyfile(source, target)
        result += '<img class="paper-page" data-zoom tabindex="0" src="' + data_uri(target) + '" alt="论文原文第' + str(page['page']) + '页，共' + str(manifest['page_count']) + '页" width="' + str(page['width']) + '" height="' + str(page['height']) + '" loading="lazy" decoding="async" style="' + PAGE_STYLE + '">'
    result += '</section><section class="page-nav" data-editor-only style="display:flex;align-items:center;justify-content:space-between;padding-top:10px;"><button id="prev-page" class="action" aria-label="上一页">‹</button><p style="font-size:12px;color:#78828e;"><span id="page-number">01</span> / <span id="page-total">' + str(manifest['page_count']).zfill(2) + '</span></p><button id="next-page" class="action" aria-label="下一页">›</button></section><p style="margin:8px 0 0;text-align:center;font-size:11px;line-height:1.8;color:#8a929b;">左右滑动翻阅原文 · 点击页图放大 · ' + esc(paper['version_label']) + ' ' + str(manifest['page_count']) + '页</p></section></section>'
    authors = content.get('authors', [])
    if authors:
        result += heading('作者简介', 'authors') + '<section id="authors" style="background:#f4f6f8;border-radius:8px;padding:18px 16px;">'
        profiles = {p['name']: p for p in profile.get('author_profiles', [])}
        for index, author in enumerate(authors):
            entry = profiles.get(author.get('profile_name'), {})
            if author.get('profile_name') and not entry:
                raise ValueError('Unknown built-in author profile: ' + author['profile_name'])
            photo = asset_path(author.get('photo'), content_base) if author.get('photo') else asset_path(entry.get('photo'), profile_base)
            uri = save_image(photo, out, f'author-{index+1}')
            image = '<img src="' + uri + '" alt="' + esc(author['name']) + '" style="display:block;width:100%;height:100%;object-fit:cover;object-position:center top;">' if uri else '<p style="font-size:12px;line-height:1.7;padding-top:30px;margin:0;">作者照片<br>待补充</p>'
            result += '<section style="display:table;table-layout:fixed;width:100%;margin:' + ('20px' if index else '0') + ' 0 0;"><section style="display:table-cell;width:84px;vertical-align:top;"><section class="photo-slot" data-photo="author-' + str(index+1) + '" style="width:84px;height:112px;background:#e5e9ef;color:#7e8894;text-align:center;border-radius:16px 16px 4px 4px;border-bottom:4px solid #EEAA91;overflow:hidden;">' + image + '</section></section><section style="display:table-cell;vertical-align:top;padding-left:16px;"><p style="margin:0 0 3px;font-size:12px;line-height:1.6;color:#7d8791;">' + edit(author['role']) + '</p><h3 style="margin:0 0 9px;font-size:16px;line-height:1.5;">' + edit(author['name']) + '</h3>'
            result += ''.join('<p style="margin:0 0 5px;font-size:13px;line-height:1.8;color:#4d5660;"><span aria-hidden="true" style="color:#EEAA91;padding-right:6px;">•</span>' + edit(b) + '</p>' for b in author['bullets']) + '</section></section>'
        result += '</section>'
    recs = content.get('recommendations', [])
    if recs:
        result += heading('往期推荐', 'recommendations')
        for index, rec in enumerate(recs):
            result += '<a data-link="rec' + str(index+1) + '" href="' + esc(rec['url']) + '" target="_blank" rel="noopener noreferrer" style="display:block;margin:0 0 26px;text-decoration:none;color:#252a30;"><p style="margin:0 0 5px;font-size:15px;font-weight:600;line-height:1.7;">' + edit(rec['title']) + '</p><p style="margin:0 0 8px;font-size:12px;line-height:1.8;color:#7d8791;">' + edit(('相关论文原文' if rec['kind'] == '相关论文' else '往期推文') + (' · ' + rec['meta'] if rec.get('meta') else '')) + '</p><p style="margin:0;font-size:13px;line-height:1.9;color:#4d5660;">' + edit(rec.get('reason', '')) + '</p></a>'
    return result + group_html(profile, profile_base, out)


def tools_html(content, manifest, pdf_uri):
    pairs = [('paper', '论文原文', content['paper']['url'])] + [('rec'+str(i+1), '推荐'+str(i+1), r['url']) for i, r in enumerate(content.get('recommendations', []))]
    inputs = ''.join('<label>' + label + '<input type="url" data-link-input="' + key + '" value="' + esc(url) + '"></label>' for key, label, url in pairs)
    options = ''.join('<option value="' + str(i) + '">第 ' + str(i+1) + ' 页</option>' for i in range(manifest['page_count']))
    return '<span class="brand-rule"></span><h1>SMOOTH 论文推文</h1><p class="lead">蓝橙色模板 · 可编辑离线预览</p><section class="buttons"><button id="edit" class="action primary" aria-pressed="false">编辑文字与照片</button><button id="choose-pages" class="action">替换原文页图</button><button id="copy" class="action">复制正文排版</button><button id="save" class="action">下载可编辑草稿</button><button id="export" class="action">下载正文排版</button></section><p id="status" role="status"></p><details><summary>设置论文与往期链接</summary>' + inputs + '</details><details><summary>原文快速定位与下载</summary><label>跳转至原文页码<select id="jump-page" style="display:block;width:100%;padding:9px;">' + options + '</select></label><p><a download="original-paper.pdf" href="' + pdf_uri + '">下载原始 PDF</a></p></details><details><summary>在公众号后台使用</summary><p>正文复制后需重新上传图片；原文滑动请在微信支持的组件或排版工具中配置，最后用手机预览。</p></details><p class="tip">本地编辑后请下载草稿保存。<br>浏览器效果与微信实际效果需分别检查。</p>'


def render(args):
    prepared, input_path, out = Path(args.prepared).resolve(), Path(args.content).resolve(), Path(args.output).resolve()
    if (out / 'preview.html').exists() and not args.overwrite:
        raise ValueError('Output exists. Reconcile manual edits, then use --overwrite if authorized.')
    manifest = read_json(prepared / 'source_manifest.json')
    if digest(prepared / manifest['pdf']) != manifest['pdf_sha256']:
        raise ValueError('Prepared PDF hash mismatch.')
    if len(manifest['pages']) != manifest['page_count']:
        raise ValueError('Prepared page count mismatch.')
    for page in manifest['pages']:
        path = (prepared / page['path']).resolve()
        if prepared not in path.parents or digest(path) != page['sha256']:
            raise ValueError('Prepared page hash or path mismatch.')
    content = read_json(input_path)
    check_content(content, manifest['page_count'])
    profile_path = Path(args.profile).resolve() if args.profile else ASSETS / 'smooth-profile.json'
    profile = read_json(profile_path)
    (out / 'assets/paper-pages').mkdir(parents=True, exist_ok=True)
    article = build_article(content, input_path.parent, profile, profile_path.parent, manifest, prepared, out)
    shutil.copyfile(prepared / manifest['pdf'], out / 'original-paper.pdf')
    native = '<h1>' + edit(content['title']) + '</h1><p><span class="account">' + edit(profile.get('account_name', '科研论文')) + '</span> · 样稿预览</p><p class="native-note">此处模拟微信标题区，不包含在复制正文内</p>'
    values = {'TITLE': esc(content['title']), 'CSS': (ASSETS / 'preview.css').read_text(encoding='utf-8'), 'TOOLS': tools_html(content, manifest, data_uri(out / 'original-paper.pdf')), 'NATIVE_HEAD': native, 'ARTICLE': article, 'SCRIPT': (ASSETS / 'editor.js').read_text(encoding='utf-8')}
    template = (ASSETS / 'preview-template.html').read_text(encoding='utf-8')
    rendered = re.sub(r'@@([A-Z_]+)@@', lambda m: values[m[1]], template)
    (out / 'preview.html').write_text(rendered, encoding='utf-8')
    soup = BeautifulSoup('<section id="article" style="' + ARTICLE_STYLE + '">' + article + '</section>', 'html.parser')
    for el in soup.select('[data-editor-only]'):
        el.decompose()
    for el in soup.find_all(True):
        for key in ('contenteditable', 'data-edit', 'data-photo', 'data-zoom', 'tabindex', 'role'):
            el.attrs.pop(key, None)
    (out / 'body-article.html').write_text('<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(content['title']) + '</title><body style="margin:0;padding:24px;">' + str(soup) + '</body></html>', encoding='utf-8')
    markdown = '# ' + content['title'] + '\n\n' + content['lead'] + '\n\n'
    for section in content['overview']:
        markdown += '## ' + section['heading'] + '\n\n' + '\n\n'.join(section['paragraphs']) + '\n\n'
    markdown += '原文：' + content['paper']['english_title'] + '\n\n*' + content['paper']['journal'] + '*，' + content['paper']['published'] + '\n\n' + content['paper']['url'] + '\n'
    (out / 'article.md').write_text(markdown, encoding='utf-8')
    write_json(out / 'paper_metadata.json', dict(content['paper'], pdf_sha256=manifest['pdf_sha256'], pdf_pages=manifest['page_count']))
    write_json(out / 'evidence.json', content['evidence'])
    tsv = 'section\tclaim\tsource_pdf_pages\tnote\n'
    for row in content['evidence']:
        tsv += '\t'.join(str(x).replace('\t', ' ').replace('\n', ' ') for x in (row['section'], row['claim'], ','.join(map(str, row['pages'])), row.get('note', ''))) + '\n'
    (out / 'evidence-map.tsv').write_text(tsv, encoding='utf-8')
    contract = {'page_count': manifest['page_count'], 'pdf_sha256': manifest['pdf_sha256'], 'title': content['title'], 'lead_text': BeautifulSoup(formatted(content['lead']), 'html.parser').get_text(), 'overview_text': [[BeautifulSoup(formatted(p), 'html.parser').get_text() for p in s['paragraphs']] for s in content['overview']], 'group_paragraphs': (profile.get('group') or {}).get('paragraphs', []), 'author_count': len(content.get('authors', [])), 'recommendation_count': len(content.get('recommendations', [])), 'header_present': bool((content.get('header') or {}).get('image'))}
    write_json(out / 'content-contract.json', contract)
    notes = ['# 内容核对与交付记录', '', '正文由 Codex 辅助撰写；渲染脚本不生成 fallback 正文。', '', '- PDF 文件页数：' + str(manifest['page_count']), '- PDF SHA-256：' + manifest['pdf_sha256'], '- 真实文章类型：' + content['paper']['article_type'], '- PDF 版本：' + content['paper']['version_label'], '- 自动检查与人工事实核对分别记录；默认未完成浏览器视觉验收与微信手机预览。']
    if not contract['header_present']:
        notes += ['- 期刊头图未提供，未模拟生成；正文部分可先审阅。']
    if not content.get('authors'):
        notes += ['- 未提供已核实作者简介，页面省略作者模块。']
    if not content.get('recommendations'):
        notes += ['- 未提供往期或相关论文素材，页面省略推荐模块。']
    for author in content.get('authors', []):
        if not author.get('photo') and not author.get('profile_name'):
            notes += ['- ' + author['name'] + '照片待补。']
    if content.get('header'):
        notes += ['- 期刊头图来源：' + str(content['header'].get('source_url', '用户提供；未额外指定网址'))]
    notes += ['', '## 本稿核对备注', ''] + ['- ' + str(x) for x in content.get('review_notes', [])]
    (out / 'review_notes.md').write_text('\n'.join(notes) + '\n', encoding='utf-8')
    errors = validate_output(out)
    if errors:
        raise ValueError('Rendered artifact failed checks: ' + '; '.join(errors))
    files = [{'path': str(p.relative_to(out)), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'output_manifest.json']
    write_json(out / 'output_manifest.json', {'automatic_checks_passed': True, 'visual_check': 'not_run', 'wechat_mobile_check': 'not_run', 'files': files})
    print(json.dumps({'preview': str(out / 'preview.html'), 'pages': manifest['page_count'], 'embedded_assets': True}, ensure_ascii=False))


def validate_output(out):
    errors = []
    try:
        contract = read_json(out / 'content-contract.json')
        if digest(out / 'original-paper.pdf') != contract['pdf_sha256']:
            errors.append('Original PDF hash mismatch')
        doc = fitz.open(out / 'original-paper.pdf')
        if len(doc) != contract['page_count']:
            errors.append('Original PDF page count mismatch')
        if len(list((out / 'assets/paper-pages').glob('page-*.jpg'))) != contract['page_count']:
            errors.append('Exported page image count mismatch')
        for name in ('preview.html', 'body-article.html'):
            soup = BeautifulSoup((out / name).read_text(encoding='utf-8'), 'html.parser')
            article = soup.select_one('#article')
            if article is None:
                errors.append(name + ': missing article'); continue
            if soup.title is None or soup.title.get_text() != contract['title']:
                errors.append(name + ': document title mismatch')
            if name == 'preview.html':
                title = soup.select_one('.native-head h1')
                if title is None or title.get_text() != contract['title']:
                    errors.append(name + ': visible title mismatch')
                pdf_link = soup.select_one('a[download="original-paper.pdf"]')
                if pdf_link is None or base64.b64decode(pdf_link['href'].split(',', 1)[1]) != (out / 'original-paper.pdf').read_bytes():
                    errors.append(name + ': embedded PDF mismatch')
            if len(soup.select('#page-strip img')) != contract['page_count']:
                errors.append(name + ': carousel count mismatch')
            if soup.select_one('#takeaway').get_text() != contract['lead_text']:
                errors.append(name + ': lead content mismatch')
            if bool(soup.select_one('#journal-header')) != contract['header_present']:
                errors.append(name + ': header presence mismatch')
            if len(soup.select('#authors .photo-slot')) != contract['author_count']:
                errors.append(name + ': author count mismatch')
            if len(soup.select('a[data-link^="rec"]')) != contract['recommendation_count']:
                errors.append(name + ': recommendation count mismatch')
            actual = [p.get_text() for p in soup.select('[data-group-paragraph]')]
            if actual != contract['group_paragraphs']:
                errors.append(name + ': supplied group copy mismatch')
            overview = soup.select_one('#overview').get_text()
            for paragraphs in contract['overview_text']:
                if any(p not in overview for p in paragraphs):
                    errors.append(name + ': overview mismatch')
            ids = [el['id'] for el in soup.select('[id]')]
            if len(ids) != len(set(ids)):
                errors.append(name + ': duplicate DOM IDs')
            for image in soup.select('img[src]'):
                uri = image['src']
                if not uri.startswith('data:image/'):
                    errors.append(name + ': external image dependency'); continue
                raw = base64.b64decode(uri.split(',', 1)[1], validate=True)
                with fitz.open(stream=raw) as image_doc:
                    if not len(image_doc):
                        errors.append(name + ': empty image')
            for link in soup.select('a[href]'):
                if urlparse(link['href']).scheme not in ('http', 'https', 'mailto', 'data', ''):
                    errors.append(name + ': unsafe link scheme')
            for image, page in zip(soup.select('#page-strip img'), range(1, contract['page_count']+1)):
                path = out / 'assets/paper-pages' / f'page-{page:03}.jpg'
                if base64.b64decode(image['src'].split(',', 1)[1]) != path.read_bytes():
                    errors.append(name + ': embedded page differs from exported page')
        evidence = read_json(out / 'evidence.json')
        if any(not 1 <= p <= contract['page_count'] for row in evidence for p in row['pages']):
            errors.append('Invalid evidence page')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(str(exc))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare', help='Extract the entire PDF and all page images.')
    prep.add_argument('--pdf', required=True)
    prep.add_argument('--workdir', required=True)
    prep.add_argument('--page-width', type=int, default=1700)
    render_p = commands.add_parser('render', help='Render an agent-authored content JSON into a standalone HTML.')
    render_p.add_argument('--prepared', required=True)
    render_p.add_argument('--content', required=True)
    render_p.add_argument('--output', required=True)
    render_p.add_argument('--profile')
    render_p.add_argument('--overwrite', action='store_true')
    valid = commands.add_parser('validate', help='Check artifacts; does not claim visual or scientific validation.')
    valid.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            prepare(args)
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
