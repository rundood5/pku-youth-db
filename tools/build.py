# -*- coding: utf-8 -*-
"""
重要讲话与最新提法数据库 —— 站点生成脚本

输入：site/data/content.json（由 tools/extract.py 生成）
输出：
  site/data/db.js     全站数据（window.DSH_DB），内嵌数据使网站可直接双击打开、离线可用
  site/*.html         首页 / 数据库总览 / 单期详情 / 领导人论述 / 全库检索 / 关于 / 404

为什么把数据内嵌成 db.js 而不是 fetch(content.json)：
  用 fetch 读本地 JSON 在 file:// 协议下会被浏览器的跨域策略拦掉，
  内嵌成一个 JS 变量后，双击 html 也能正常显示，部署到服务器同样可用。

用法：
  python build.py            # 生成全部页面
  python build.py --check    # 只校验 content.json 与页面数量
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS_DIR)
SITE = os.path.join(ROOT, "site")
DATA_JSON = os.path.join(SITE, "data", "content.json")
DATA_JS = os.path.join(SITE, "data", "db.js")

NAV_ITEMS = [
    ("index.html", "首页"),
    ("database.html", "重要讲话数据库"),
    ("leaders.html", "领导人论述库"),
    ("awards.html", "青年工作课题"),
    ("search.html", "全库检索"),
    ("about.html", "关于本库"),
]

# 网站图标：由 source/北大校徽.png 处理后生成（见 tools/prepare_logo.py）
# 用真实图片文件而不是内联 data URI，替换校徽时只需重跑一个脚本
FAVICON = "assets/favicon.png"

# 校徽图片资源（均由 tools/prepare_logo.py 生成）
#   pku-logo-white.png 白色版 —— 深藏青底的导航栏与页脚必须用白色版，
#                              红色版在深藏青上对比度过低（实测几乎看不清）
#   pku-emblem.png     红色版 —— 首屏水印用
LOGO_WHITE = "assets/pku-logo-white.png"
LOGO_EMBLEM = "assets/pku-emblem.png"

# 导航栏与页脚的校徽标记（白色版，放在深色底上）
BRAND_MARK = (
    '<span class="brand-mark" aria-hidden="true">'
    '<img src="%s" alt="" width="160" height="160" decoding="async">'
    "</span>" % LOGO_WHITE
)

# 网站名称（品牌）与其中的数据库模块名称，两者含义不同，不要混用：
#   SITE_NAME   —— 整个网站的名字，出现在导航栏、页脚、浏览器标签
#   DB_NAME     —— 站内"重要讲话与最新提法数据库"这个模块的名字，也是源 Word 文件的实际名称
SITE_NAME = "北大青年纵横"
DB_NAME = "重要讲话与最新提法数据库"
SITE_TAGLINE = "学习资料库"
# 不标注主办单位。本站是资料汇编性质的检索工具，不作为任何单位的官方发布渠道。
# 页脚只保留中立署名，避免造成“官方发布”的印象。
ORG_NAME = "北大青年纵横 · 学习资料库"

META_DESC = (
    "北大青年纵横：荟萃时代嘉言，拓思青年纵横。收录党和国家领导人关于青年和共青团工作的重要论述，"
    "以及《重要讲话与最新提法数据库》各期政策文件与权威文章，支持关键词检索与原文跳转。"
)

# --------------------------------------------------------------------------
# 「豆腐块」小栏目数据
#   三块横向小栏目，条目为真实可访问的中国共青团网栏目与权威来源链接。
#   栏目地址已逐个核实（见 tools/check_links.py 的输出）。
#   更新方式：直接增删下面的条目即可，不需要改动页面结构。
# --------------------------------------------------------------------------
DOUFU_BLOCKS = [
    {
        "title": "规范性文件",
        "more": "https://www.gqt.org.cn/xxgk/",
        "items": [
            {
                "text": "共青团中央 教育部印发《关于落实党建带团建制度机制 深化高校共青团工作的意见》的通知",
                "url": "https://www.gqt.org.cn/xxgk/tngz_gfwj/",
            },
            {
                "text": "共青团中央办公厅关于印发《深化新兴领域青年服务体系建设方案》的通知",
                "url": "https://www.gqt.org.cn/xxgk/tngz_gfwj/",
            },
            {
                "text": "团内规章和规范性文件（信息公开专栏）",
                "url": "https://www.gqt.org.cn/xxgk/",
            },
        ],
    },
    {
        "title": "青年发展",
        "more": "https://www.gqt.org.cn/sylm/qnfzgh/",
        "items": [
            {
                "text": "《中长期青年发展规划（2016—2025年）》",
                "url": "https://www.gov.cn/gongbao/content/2017/content_5189005.htm",
            },
            {
                "text": "中长期青年发展规划实施情况",
                "url": "https://www.gqt.org.cn/sylm/qnfzgh/",
            },
            {
                "text": "青年发展统计监测情况",
                "url": "https://www.gqt.org.cn/sylm/qnfzgh/",
            },
        ],
    },
    {
        "title": "全团要讯",
        "more": "https://www.gqt.org.cn/tngz/",
        "items": [
            {
                "text": "全团要讯（共青团中央工作动态）",
                "url": "https://www.gqt.org.cn/tngz/",
            },
            {
                "text": "共青团中央工作动态与调研报道",
                "url": "https://qnzz.youth.cn/gzdt/",
            },
            {
                "text": "中国共青团网 · 共青团中央网站",
                "url": "https://www.gqt.org.cn/",
            },
        ],
    },
]


def doufu_html() -> str:
    """生成「豆腐块」小栏目的 HTML（放在首页右侧栏，尺寸较小）。"""
    cards = []
    for blk in DOUFU_BLOCKS:
        lis = "\n".join(
            '            <li><a href="%s" target="_blank" rel="noopener noreferrer">%s</a></li>'
            % (it["url"], it["text"])
            for it in blk["items"]
        )
        cards.append(
            '        <div class="doufu">\n'
            '          <h3 class="doufu-title">%s</h3>\n'
            '          <ul class="doufu-list">\n%s\n          </ul>\n'
            '          <a class="doufu-more" href="%s" target="_blank" rel="noopener noreferrer">'
            "查看更多 <svg class=\"ic\" viewBox=\"0 0 24 24\"><path d=\"M5 12h14\"/><path d=\"m13 6 6 6-6 6\"/></svg></a>\n"
            "        </div>" % (blk["title"], lis, blk["more"])
        )
    return (
        '      <aside class="home-side">\n'
        '        <div class="side-block-head">\n'
        '          <h2 class="side-title">共青团青年发展</h2>\n'
        '          <p class="side-desc">规范性文件、调研信息与全团要讯，一键直达权威来源</p>\n'
        "        </div>\n" + "\n".join(cards) + "\n"
        '        <a class="side-all" href="https://www.gqt.org.cn/" target="_blank" rel="noopener noreferrer">'
        '访问中国共青团网 <svg class="ic" viewBox="0 0 24 24"><path d="M14 4h6v6"/><path d="M20 4 11 13"/>'
        '<path d="M18 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5"/></svg></a>\n'
        "      </aside>"
    )


# --------------------------------------------------------------------------
# 公共片段
# --------------------------------------------------------------------------
def cn_date(iso: str) -> str:
    """2026-08-10 -> 2026年8月10日，用于静态文案里的日期区间。"""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", iso or "")
    if m:
        return "%s年%d月%d日" % (m.group(1), int(m.group(2)), int(m.group(3)))
    return iso or ""


def cn_range(a: str, b: str) -> str:
    """2026-08-10 ~ 2026-08-31 -> 2026年8月10日 — 8月31日（同年时省略重复年份）"""
    ma = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", a or "")
    mb = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", b or "")
    if not ma or not mb:
        return "%s — %s" % (a, b)
    if ma.group(1) == mb.group(1):
        return "%s年%d月%d日 — %d月%d日" % (
            ma.group(1), int(ma.group(2)), int(ma.group(3)), int(mb.group(2)), int(mb.group(3)))
    return "%s — %s" % (cn_date(a), cn_date(b))


def qa_html(data: dict) -> str:
    """问答窗口模块。

    设计说明：本站是纯静态站点，无法运行大模型，因此这里做的是
    “库内检索问答”——把问题拆成关键词，在站内已收录的资料里检索原文，
    按相关度排序后给出答案片段与出处。答案全部来自库内，不联网、不编造。
    """
    s = data.get("stats", {})
    scope = "数据范围：领导人论述 %d 条 · 重要文章 %d 篇 · 青春寄语 %d 条 · 课题 %d 项 · 数据库条目 %d 条" % (
        s.get("leaderCount", 0), s.get("xiArticleCount", 0), s.get("quoteCount", 0),
        len(data.get("awards", {}).get("items", [])), s.get("entryCount", 0))
    examples = [
        "总书记关于立德树人的重要论述",
        "青年要如何树立理想信念",
        "共青团工作的政治性、先进性、群众性",
        "青年和共青团工作的重要论述有哪些",
        "中长期青年发展规划",
    ]
    chips = "\n".join(
        '            <button class="chip" type="button" data-q="%s">%s</button>' % (e, e)
        for e in examples
    )
    return """
  <section class="section" id="qa">
    <div class="wrap">
      <div class="section-head">
        <div>
          <h2 class="section-title">问答窗口</h2>
          <p class="section-desc">
            输入问题，系统在<strong>本站已收录的资料</strong>中检索原文并给出出处。只查库内内容，不联网、不编造。
          </p>
        </div>
      </div>

      <div class="qa-panel">
        <div class="qa-head">
          <svg class="ic ic-lg" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
          <span>库内检索问答</span>
          <small>%s</small>
        </div>
        <div class="qa-body">
          <div class="qa-input-row">
            <div class="search-box">
              <svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
              <label class="sr-only" for="qaInput">输入问题</label>
              <input id="qaInput" type="search" placeholder="例如：总书记关于立德树人的重要论述有哪些？" autocomplete="off">
              <button class="search-clear" id="qaClear" type="button" aria-label="清空">
                <svg class="ic" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>
              </button>
            </div>
            <button class="btn btn-primary" id="qaAsk" type="button">
              <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
              查一下
            </button>
          </div>
          <div class="qa-examples" id="qaExamples">
%s
          </div>
          <div class="qa-answer" id="qaAnswer" hidden></div>
        </div>
      </div>
    </div>
  </section>
""" % (scope, chips)


def nav_html(active: str) -> str:
    links = "\n".join(
        '        <a class="nav-link" href="%s"%s>%s</a>'
        % (href, ' aria-current="page"' if href == active else "", label)
        for href, label in NAV_ITEMS
    )
    return """  <a class="skip-link" href="#main">跳到主要内容</a>
  <header class="nav">
    <div class="wrap nav-inner">
      <a class="brand" href="index.html">
        <span class="brand-mark" aria-hidden="true">
          <img src="assets/pku-logo-white.png" alt="" width="160" height="160" decoding="async">
        </span>
        <span class="brand-text">
          <span class="brand-name">北大青年纵横</span>
          <span class="brand-sub">学习资料库</span>
        </span>
      </a>
      <button class="nav-toggle" type="button" aria-label="展开导航菜单" aria-expanded="false">
        <svg class="ic ic-lg" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
      </button>
      <nav class="nav-links" aria-label="主导航">
%s
        <a class="nav-cta" href="search.html">
          <svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
          检索
        </a>
      </nav>
    </div>
  </header>""" % links


def footer_html(site_meta: dict) -> str:
    links = site_meta.get("footerLinks", [])
    link_items = "\n".join(
        """            <a class="footer-link" href="%s" target="_blank" rel="noopener noreferrer">
              <svg class="ic" viewBox="0 0 24 24"><path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M18 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5"/></svg>
              <span>%s<small>%s</small></span>
            </a>"""
        % (l["url"], l["name"], l.get("desc", ""))
        for l in links
    )
    return """  <footer class="footer">
    <div class="wrap">
      <div class="footer-grid">
        <div class="footer-brand">
          <div class="brand">
            <span class="brand-mark" aria-hidden="true">
              <img src="assets/pku-logo-white.png" alt="" width="160" height="160" decoding="async">
            </span>
            <span class="brand-text">
              <span class="brand-name">北大青年纵横</span>
              <span class="brand-sub">学习资料库</span>
            </span>
          </div>
          <p class="footer-couplet">荟萃时代嘉言<span class="cp-dot-sm" aria-hidden="true"></span>拓思青年纵横</p>
          <p>系统整理党和国家领导人关于青年和共青团工作的重要论述、最新重要讲话与政策文件，
             按期次归档、逐条著录，供团学工作与理论学习检索使用。</p>
        </div>
        <div>
          <h4>站内导航</h4>
          <div class="footer-links">
            <a class="footer-link" href="database.html">
              <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
              <span>重要讲话数据库</span>
            </a>
            <a class="footer-link" href="leaders.html">
              <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
              <span>领导人论述库</span>
            </a>
            <a class="footer-link" href="search.html">
              <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
              <span>全库检索</span>
            </a>
            <a class="footer-link" href="about.html">
              <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
              <span>关于本库与数据说明</span>
            </a>
          </div>
        </div>
        <div>
          <h4>友情链接</h4>
          <div class="footer-links">
%s
          </div>
        </div>
      </div>
      <div class="footer-bottom">
        <span>© <span data-year>2026</span> 北大青年纵横 · 本站为学习资料汇编，内容整理自公开来源，<strong>非任何单位官方发布</strong></span>
        <span class="tag">数据更新：%s</span>
      </div>
    </div>
  </footer>

  <button class="to-top" type="button" aria-label="返回顶部">
    <svg class="ic" viewBox="0 0 24 24"><path d="M12 19V5"/><path d="m6 11 6-6 6 6"/></svg>
  </button>""" % (link_items, site_meta.get("generated", ""))


def shell(title: str, desc: str, active: str, body: str, site_meta: dict, path_prefix: str = "") -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<meta name="theme-color" content="#0f1b33">
<link rel="icon" href="%s">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
%s

<main id="main">
%s
</main>

%s

<script src="data/db.js"></script>
<script src="assets/app.js"></script>
</body>
</html>
""" % (title, desc, FAVICON, nav_html(active), body, footer_html(site_meta))


# --------------------------------------------------------------------------
# 首页
# --------------------------------------------------------------------------
def page_index(data: dict) -> str:
    s = data["stats"]
    # 注意：这里拼接了 doufu_html()，所以整段必须用括号包起来，
    # 否则 % 只会作用于最后一段字符串（曾因此导致占位符 %(issueCount)d 原样输出）。
    body = """  <section class="hero">
    <img class="hero-emblem" src="assets/pku-emblem.png" alt="" aria-hidden="true" decoding="async">
    <div class="wrap hero-grid">
      <div>
        <span class="eyebrow"><span class="eyebrow-dot"></span>数据持续更新 · 已归档 %(issueCount)d 期</span>
        <h1>北大青年纵横</h1>
        <p class="hero-couplet"><span>荟萃时代嘉言</span><i class="cp-dot" aria-hidden="true"></i><span>拓思青年纵横</span></p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="database.html">
            <svg class="ic" viewBox="0 0 24 24"><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/></svg>
            进入重要讲话数据库
          </a>
          <a class="btn btn-ghost" href="leaders.html">
            <svg class="ic" viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M17 5.2a3.5 3.5 0 0 1 0 6.6M18.5 20a6.5 6.5 0 0 0-2-4.7"/></svg>
            领导人重要论述
          </a>
          <a class="btn btn-ghost" href="search.html">
            <svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
            全库检索
          </a>
        </div>
        <div class="hero-facts">
          <span class="hero-fact"><b>%(issueCount)d</b> 期已归档</span>
          <span class="hero-fact"><b>%(entryCount)d</b> 条著录内容</span>
          <span class="hero-fact"><b>%(leaderCount)d</b> 条领导人论述</span>
          <span class="hero-fact"><b>%(dateRangeText)s</b></span>
        </div>
      </div>
      <div id="latestIssue">
        <div class="hero-card">
          <span class="hero-card-tag">正在载入最新一期…</span>
          <h3>重要讲话与最新提法数据库</h3>
          <div class="hero-card-date">数据载入中</div>
        </div>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <div class="stats">
        <div class="stat">
          <div class="stat-num" data-stat="issueCount">%(issueCount)d<small>期</small></div>
          <div class="stat-label">已归档期次</div>
        </div>
        <div class="stat">
          <div class="stat-num" data-stat="entryCount">%(entryCount)d<small>条</small></div>
          <div class="stat-label">著录内容条目</div>
        </div>
        <div class="stat">
          <div class="stat-num" data-stat="leaderCount">%(leaderCount)d<small>条</small></div>
          <div class="stat-label">领导人重要论述</div>
        </div>
        <div class="stat">
          <div class="stat-num" data-stat="quoteCount">%(quoteCount)d<small>条</small></div>
          <div class="stat-label">青年寄语与指示</div>
        </div>
      </div>
    </div>
  </section>

  <section class="section section-alt">
    <div class="wrap">
      <div class="section-head">
        <div>
          <h2 class="section-title">四大内容板块</h2>
          <p class="section-desc">库内所有内容都按统一字段著录，点进去即可看到摘要与原文入口。</p>
        </div>
      </div>
      <div class="entry-grid entry-grid-2">
        <a class="entry reveal" href="database.html">
          <span class="entry-icon">
            <svg class="ic" viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="8" ry="3.2"/><path d="M4 6v12c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2V6"/><path d="M4 12c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2"/></svg>
          </span>
          <h3>重要讲话数据库</h3>
          <p>《重要讲话与最新提法数据库》按期次归档，每期含概览目录、著录条目与原文链接，
             可按分类、关键词、时间筛选定位。</p>
          <span class="entry-foot">
            <span>%(issueCount)d 期 · %(entryCount)d 条</span>
            <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
          </span>
        </a>
        <a class="entry reveal" href="leaders.html">
          <span class="entry-icon">
            <svg class="ic" viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M17 5.2a3.5 3.5 0 0 1 0 6.6M18.5 20a6.5 6.5 0 0 0-2-4.7"/></svg>
          </span>
          <h3>领导人论述库</h3>
          <p>历届党和国家领导人关于<b>青年和共青团工作</b>的重要论述汇总，
             按领导人、时间、场合、性质与完整原句著录，另附青年寄语分主题语录，
             可检索具体提法的出处。</p>
          <span class="entry-foot">
            <span>%(leaderCount)d 条论述 · %(quoteCount)d 条寄语</span>
            <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
          </span>
        </a>
        <a class="entry reveal" href="awards.html">
          <span class="entry-icon">
            <svg class="ic" viewBox="0 0 24 24"><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 0 4 22.5Z"/><path d="M8 7h8M8 11h6"/><path d="m9 16 1.4 1.4L13 15"/></svg>
          </span>
          <h3>青年工作特别贡献课题</h3>
          <p>北京大学“挑战杯”系列赛事特别贡献奖立项课题，聚焦<b>青年和共青团工作</b>；
             每项可展开查看<b>源文件摘要</b>与申报材料下载。</p>
          <span class="entry-foot">
            <span>%(awardCount)d 项课题</span>
            <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
          </span>
        </a>
        <a class="entry reveal" href="search.html">
          <span class="entry-icon">
            <svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
          </span>
          <h3>全库检索</h3>
          <p>在全部期次的著录条目中一次性检索标题、观点速览、关键词与来源，
             命中结果高亮显示并可跳转原文，适合找提法、找出处、找依据。</p>
          <span class="entry-foot">
            <span>覆盖数据库全部 %(entryCount)d 条</span>
            <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
          </span>
        </a>
      </div>
    </div>
  </section>
"""

    body += """
  <section class="section section-alt" id="tianSection">
    <div class="wrap">
      <div class="tian-grid">
        <div class="tian-cell" id="recentSection">
          <div class="section-head">
            <div>
              <h2 class="section-title">最新收录内容</h2>
              <p class="section-desc">
                跨期次汇总最近收录的条目，按发布时间倒序排列；
                点击标题直达原文，或进入数据库按整期查看。共已归档 %(issueCount)d 期。
              </p>
            </div>
            <a class="section-link" href="database.html">
              按整期浏览 %(issueCount)d 期
              <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
            </a>
          </div>
          <div class="entry-list" id="latestItems"></div>
          <div class="more-wrap">
            <a class="btn btn-outline" href="database.html">
              <svg class="ic" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>
              进入重要讲话数据库
            </a>
          </div>
        </div>
        <div class="tian-cell tian-cell-qa">
""" + qa_html(data) + """
        </div>
        <div class="tian-cell">
""" + doufu_html() + """
        </div>
      </div>
    </div>
  </section>

  <section class="section" id="kwSection">
    <div class="wrap">
      <div class="section-head">
        <div>
          <h2 class="section-title">高频关键词</h2>
          <p class="section-desc">点击任一关键词即可在全库中检索相关内容。</p>
        </div>
      </div>
      <div class="chip-row" id="kwCloud"></div>
    </div>
  </section>
""" 
    # 关键：% 只能作用于紧邻的一个字符串字面量，
    # 因此这里先把 body 整体赋回，再统一做一次格式化，
    # 否则前面拼接进来的段落里的 %(xxx)d 不会被替换。
    body = body % {
        "issueCount": s["issueCount"],
        "entryCount": s["entryCount"],
        "leaderCount": s["leaderCount"],
        "quoteCount": s["quoteCount"],
        "dateRangeText": cn_range(s["dateRange"][0], s["dateRange"][1]),
        "awardCount": len((data.get("awards") or {}).get("items", [])),
    }

    # 注意：问答窗口只在田字格右列出现一次（见上面的 qa_html 调用），
    # 不要在页面底部再接一次，否则会出现两个一模一样的问答模块。

    # 自检：占位符必须全部替换完成，否则页面上会出现 %(xxx)d 这样的字样
    if re.search(r"%\([a-zA-Z]+\)[ds]", body):
        raise SystemExit("首页生成失败：存在未替换的格式占位符，请检查 body 的 % 作用范围")

    return shell(
        "北大青年纵横 · 学习资料库",
        META_DESC,
        "index.html",
        body,
        data["site"],
    )


# --------------------------------------------------------------------------
# 数据库总览
# --------------------------------------------------------------------------
def page_database(data: dict) -> str:
    s = data["stats"]
    body = """  <section class="doc-head">
    <div class="wrap">
      <div class="crumb">
        <a href="index.html">首页</a><span class="sep">/</span><span>重要讲话数据库</span>
      </div>
      <h1>重要讲话与最新提法数据库</h1>
      <p class="lede">
        按期次归档的政策文件、党报党刊文章与权威发布，每期包含概览目录与逐条著录内容。
        支持按分类筛选、关键词检索与时间排序，点击任一期次可查看完整条目与原文链接。
      </p>
      <div class="doc-head-meta">
        <span><svg class="ic" viewBox="0 0 24 24"><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/></svg>%(issueCount)d 期已归档</span>
        <span><svg class="ic" viewBox="0 0 24 24"><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 0 4 22.5Z"/><path d="M8 7h8M8 11h6"/></svg>%(entryCount)d 条著录内容</span>
        <span><svg class="ic" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>%(from)s 至 %(to)s</span>
      </div>
    </div>
  </section>

  <div class="wrap" style="padding-top:30px">
    <div class="notice notice-info">
      <svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>
      <div><strong>著录规范</strong>：每条内容均记录 标题 / 发布时间 / 发布来源 / 原文链接 / 关键词 / 观点速览，
        与源 Word 文件字段一一对应。<a href="about.html#fields">查看字段说明</a></div>
    </div>
  </div>

  <section class="section-tight">
    <div class="wrap">
      <div class="toolbar" style="position:static;background:none;border:0;padding:0;margin-bottom:22px">
        <div class="toolbar-row">
          <div class="search-box">
            <svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
            <label class="sr-only" for="dbSearch">检索期次</label>
            <input id="dbSearch" type="search" placeholder="检索期次：标题、关键词、来源、观点速览…" autocomplete="off">
            <button class="search-clear" id="dbClear" type="button" aria-label="清除检索词">
              <svg class="ic" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
          </div>
          <span class="select-wrap">
            <label class="sr-only" for="sortSel">排序方式</label>
            <select id="sortSel">
              <option value="desc">时间倒序（最新在前）</option>
              <option value="asc">时间正序（最早在前）</option>
            </select>
            <svg class="ic" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>
          </span>
        </div>
        <div class="toolbar-row" style="margin-top:14px">
          <div class="chip-row" id="catRow"></div>
        </div>
      </div>

      <div class="result-bar">
        <span id="dbCount">正在统计…</span>
      </div>

      <div class="issue-grid" id="issueList"></div>

      <div class="more-wrap">
        <button class="btn btn-outline" id="dbMore" type="button" hidden>加载更多</button>
      </div>
    </div>
  </section>
""" % {
        "issueCount": s["issueCount"],
        "entryCount": s["entryCount"],
        "from": cn_date(s["dateRange"][0]),
        "to": cn_date(s["dateRange"][1]),
    }
    return shell(
        "重要讲话数据库 · 北大青年纵横",
        "按期次浏览《重要讲话与最新提法数据库》全部内容，支持分类筛选、关键词检索与时间排序。",
        "database.html",
        body,
        data["site"],
    )


# --------------------------------------------------------------------------
# 单期详情
# --------------------------------------------------------------------------
def page_issue(data: dict) -> str:
    body = """  <section class="doc-head">
    <div class="wrap" id="issueHead"></div>
  </section>

  <section class="section-tight">
    <div class="wrap">
      <div class="issue-layout">
        <aside class="side-sticky">
          <nav class="side-card" aria-label="期次导航">
            <div class="side-head">期次导航（%(n)d 期）</div>
            <div class="side-list" id="issueSide"></div>
          </nav>
          <div style="margin-top:16px">
            <a class="btn btn-outline" href="database.html" style="width:100%%">
              <svg class="ic" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>
              返回总览
            </a>
          </div>
        </aside>

        <div>
          <div id="issueBody">
            <div id="issueHead"></div>
            <div id="issueNotes" style="margin-bottom:20px"></div>
            <div id="issueOverview" style="margin-bottom:26px"></div>

            <div class="row-between" style="margin-bottom:18px">
              <h2 class="section-title" style="font-size:20px">本期著录条目</h2>
            </div>

            <div class="entry-list" id="entryList"></div>

            <div id="issueFooter" style="margin-top:26px"></div>

            <div class="row" id="issuePager" style="margin-top:32px;justify-content:space-between;flex-wrap:wrap;gap:12px"></div>
          </div>
        </div>
      </div>
    </div>
  </section>
""" % {"n": data["stats"]["issueCount"]}
    return shell(
        "期次详情 · 北大青年纵横",
        "查看该期《重要讲话与最新提法数据库》的概览目录、著录条目与原文链接。",
        "database.html",
        body,
        data["site"],
    )


# --------------------------------------------------------------------------
# 领导人论述库
# --------------------------------------------------------------------------
def page_leaders(data: dict) -> str:
    s = data["stats"]
    body = """  <section class="doc-head">
    <div class="wrap">
      <div class="crumb">
        <a href="index.html">首页</a><span class="sep">/</span><span>领导人论述库</span>
      </div>
      <h1>历届党和国家领导人关于青年和共青团工作的重要论述汇总</h1>
      <p class="lede">
        汇总历届党和国家领导人在重要会议、座谈、回信与文章中关于青年和共青团工作的论述，
        按 领导人 / 时间 / 场合 / 性质 / 完整原句 逐条著录，可检索具体提法的出处。
        以青春之视角，读懂党对青年的殷切期望。
      </p>
      <div class="doc-head-meta">
        <span><svg class="ic" viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M17 5.2a3.5 3.5 0 0 1 0 6.6M18.5 20a6.5 6.5 0 0 0-2-4.7"/></svg>%(leaderCount)d 条论述</span>
        <span><svg class="ic" viewBox="0 0 24 24"><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 0 4 22.5Z"/><path d="M8 7h8M8 11h6"/></svg>%(xiArticleCount)d 篇重要文章</span>
        <span><svg class="ic" viewBox="0 0 24 24"><path d="M9 7H5a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h2v1a3 3 0 0 1-3 3"/><path d="M19 7h-4a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h2v1a3 3 0 0 1-3 3"/></svg>%(quoteCount)d 条青春寄语</span>
      </div>
      <div class="row" style="margin-top:20px;flex-wrap:wrap;gap:10px">
        <a class="btn btn-ghost btn-sm" href="#leadersTable">重要论述表格</a>
        <a class="btn btn-ghost btn-sm" href="#xiArticlesSec">重要文章汇总</a>
        <a class="btn btn-ghost btn-sm" href="#xiQuotesSec">青春寄语（分主题）</a>
      </div>
    </div>
  </section>

  <section class="section-tight" id="leadersTable">
    <div class="wrap">
      <div class="toolbar" style="position:static;background:none;border:0;padding:0;margin-bottom:22px">
        <div class="toolbar-row">
          <div class="search-box">
            <svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
            <label class="sr-only" for="ldSearch">检索论述</label>
            <input id="ldSearch" type="search" placeholder="检索论述：提法、场合、原句…（如“政治性、先进性、群众性”）" autocomplete="off">
            <button class="search-clear" id="ldClear" type="button" aria-label="清除检索词">
              <svg class="ic" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
          </div>
          <span class="select-wrap">
            <label class="sr-only" for="ldSort">排序方式</label>
            <select id="ldSort">
              <option value="time">按时间排序</option>
              <option value="leader">按领导人排序</option>
              <option value="occasion">按场合排序</option>
            </select>
            <svg class="ic" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>
          </span>
        </div>
        <div class="toolbar-row" style="margin-top:14px">
          <div class="chip-row" id="leaderRow"></div>
        </div>
      </div>

      <div class="result-bar">
        <span id="ldCount">正在统计…</span>
      </div>

      <div class="table-wrap">
        <div class="table-scroll">
          <table class="data">
            <thead>
              <tr>
                <th scope="col">领导人</th>
                <th scope="col">时间</th>
                <th scope="col">场合</th>
                <th scope="col">性质 / 主要提法</th>
                <th scope="col">对应原句（完整）</th>
              </tr>
            </thead>
            <tbody id="leaderBody"></tbody>
          </table>
        </div>
      </div>

      <div class="more-wrap">
        <button class="btn btn-outline" id="ldMore" type="button" hidden>加载更多</button>
      </div>
    </div>
  </section>

  <section class="section section-alt" id="xiArticlesSec">
    <div class="wrap">
      <div class="section-head">
        <div>
          <h2 class="section-title">习近平总书记重要文章汇总</h2>
          <p class="section-desc">点击标题展开文章全文提要。</p>
        </div>
      </div>
      <div id="xiArticles"></div>
    </div>
  </section>

  <section class="section" id="xiQuotesSec">
    <div class="wrap">
      <div class="section-head">
        <div>
          <h2 class="section-title">习近平总书记对青年的青春寄语</h2>
          <p class="section-desc">按“谈理想、谈学习、谈价值观、谈创新、谈笃实”等主题分组，每条均标注出处。</p>
        </div>
      </div>
      <div id="xiQuotes"></div>
    </div>
  </section>
""" % {
        "leaderCount": s["leaderCount"],
        "xiArticleCount": s["xiArticleCount"],
        "quoteCount": s["quoteCount"],
    }
    return shell(
        "领导人论述库 · 北大青年纵横",
        "历届党和国家领导人关于青年和共青团工作的重要论述汇总，按领导人、时间、场合、性质与原句著录，可检索具体提法出处。",
        "leaders.html",
        body,
        data["site"],
    )


# --------------------------------------------------------------------------
# 全库检索
# --------------------------------------------------------------------------
def page_search(data: dict) -> str:
    s = data["stats"]
    body = """  <section class="doc-head">
    <div class="wrap">
      <div class="crumb">
        <a href="index.html">首页</a><span class="sep">/</span><span>全库检索</span>
      </div>
      <h1>全库检索</h1>
      <p class="lede">
        在全部 %(issueCount)d 期、%(entryCount)d 条著录内容中检索标题、观点速览、关键词与发布来源，
        命中处高亮显示，可直接跳转原文。
      </p>    </div>
  </section>

  <section class="section-tight">
    <div class="wrap">
      <div class="toolbar" style="position:static;background:none;border:0;padding:0;margin-bottom:22px">
        <div class="toolbar-row">
          <div class="search-box" style="flex:1 1 420px">
            <svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
            <label class="sr-only" for="gsSearch">全库检索</label>
            <input id="gsSearch" type="search" placeholder="输入关键词，例如：青年、共青团、全面从严治党、住房公积金…" autocomplete="off">
            <button class="search-clear" id="gsClear" type="button" aria-label="清除检索词">
              <svg class="ic" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
          </div>
          <span class="select-wrap">
            <label class="sr-only" for="gsSort">排序方式</label>
            <select id="gsSort">
              <option value="date">按发布时间排序</option>
              <option value="issue">按所属期次排序</option>
              <option value="source">按发布来源排序</option>
            </select>
            <svg class="ic" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>
          </span>
        </div>
        <div class="toolbar-row" style="margin-top:14px">
          <div class="chip-row" id="gsCats"></div>
        </div>
      </div>

      <div style="margin-bottom:24px">
        <div style="font-size:13px;color:var(--ink-3);margin-bottom:9px">热门关键词</div>
        <div class="chip-row" id="gsHot"></div>
      </div>

      <div class="result-bar">
        <span id="gsCount">正在统计…</span>
      </div>

      <div class="entry-list" id="searchResults"></div>

      <div class="more-wrap">
        <button class="btn btn-outline" id="gsMore" type="button" hidden>加载更多</button>
      </div>
    </div>
  </section>
""" % {"issueCount": s["issueCount"], "entryCount": s["entryCount"]}
    return shell(
        "全库检索 · 北大青年纵横",
        "在所有期次的著录内容中检索重要讲话、政策文件与重要提法，支持关键词高亮与原文跳转。",
        "search.html",
        body,
        data["site"],
    )


# --------------------------------------------------------------------------
# 关于本库
# --------------------------------------------------------------------------
def page_awards(data: dict) -> str:
    """共青团与青年工作课题栏目：特别贡献奖课题清单。

    每项课题点击可展开，显示简要介绍与下载链接。
    介绍文字由课题名称自动生成（源数据只有“序号/题目/负责人”，没有摘要字段），
    可下载的申报材料从 source 目录定位，按课题序号匹配。
    """
    a = data.get("awards", {}) or {}
    items = a.get("items", []) or []

    cards = []
    for it in items:
        title = it["title"]
        owner = it.get("owner") or "—"
        # 简介由 extract.py 生成并存在数据里，这里直接取用
        intro = it.get("intro") or "本课题为该批次特别贡献奖立项课题。"
        # 下载链接：把课题序号对应的申报材料列出来（本地文件，随 source 目录一起分发）
        files = it.get("files") or []
        if files:
            links = "\n".join(
                '                <li><a class="dl" href="%s" download>%s'
                '<svg class="ic" viewBox="0 0 24 24"><path d="M12 4v12"/><path d="m7 11 5 5 5-5"/>'
                '<path d="M4 20h16"/></svg></a></li>' % (f["path"], f["name"])
                for f in files
            )
            dl = '<ul class="dl-list">\n%s\n            </ul>' % links
        else:
            dl = '<p class="dl-none">暂无可下载的申报材料</p>'

        cards.append(
            '      <div class="acc reveal">\n'
            '        <button class="acc-head" type="button" aria-expanded="false">\n'
            '          <span class="lead"><span>%s</span>'
            '<span class="cnt">负责人：%s</span></span>\n'
            '          <svg class="ic" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>\n'
            "        </button>\n"
            '        <div class="acc-body" hidden>\n'
            '          <p class="award-intro">%s</p>\n'
            '          <div class="award-dl"><div class="award-dl-title">申报材料下载</div>%s</div>\n'
            "        </div>\n"
            "      </div>" % (title, owner, intro, dl)
        )

    body = """  <section class="doc-head">
    <div class="wrap">
      <div class="crumb">
        <a href="index.html">首页</a><span class="sep">/</span><span>共青团与青年工作课题</span>
      </div>
      <h1>共青团与青年工作课题</h1>
      <p class="lede">
        %(subtitle)s。共 %(n)d 项课题，涵盖青年理想信念、青年发展政策、共青团工作、
        思政育人、乡村振兴等方向。点击任一课题可展开查看简要介绍与申报材料下载。
      </p>
      <div class="doc-head-meta">
        <span><svg class="ic" viewBox="0 0 24 24"><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 0 4 22.5Z"/><path d="M8 7h8M8 11h6"/></svg>%(n)d 项课题</span>
        <span><svg class="ic" viewBox="0 0 24 24"><path d="M4 19.5V6a2 2 0 0 1 2-2h9l5 5v10.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1Z"/><path d="M14 4v6h6"/></svg>来源：%(source)s</span>
      </div>
    </div>
  </section>

  <section class="section-tight">
    <div class="wrap wrap-narrow">
%(cards)s
    </div>
  </section>
""" % {
        "subtitle": a.get("subtitle", "共青团与青年工作课题"),
        "n": len(items),
        "source": a.get("source", "—"),
        "cards": "\n".join(cards),
    }
    return shell(
        "共青团与青年工作课题 · 北大青年纵横",
        "北京大学“挑战杯”系列赛事特别贡献奖（校团委理论研究室）课题清单，含简要介绍与申报材料下载。",
        "awards.html",
        body,
        data["site"],
    )


def page_about(data: dict) -> str:
    s = data["stats"]
    q = data.get("quality", {})
    body = """  <section class="doc-head">
    <div class="wrap">
      <div class="crumb">
        <a href="index.html">首页</a><span class="sep">/</span><span>关于本库</span>
      </div>
      <h1>关于本库与数据说明</h1>
      <p class="lede">
        本库由《重要讲话与最新提法数据库》各期 Word 文件与领导人论述汇总表自动解析生成，
        字段、期号与原文链接均来自源文件，未作改写。
      </p>
    </div>
  </section>

  <section class="section-tight">
    <div class="wrap wrap-narrow">
      <h2 class="section-title" id="fields">一、著录字段</h2>
      <p class="section-desc">每条内容固定著录以下字段，与源 Word 文件中的“标题：/ 发布时间：”等标签一一对应。</p>
      <div class="table-wrap" style="margin-top:20px">
        <div class="table-scroll">
          <table class="data" style="min-width:0">
            <thead>
              <tr><th scope="col">字段</th><th scope="col">说明</th></tr>
            </thead>
            <tbody>
              <tr><td>标题</td><td>文章或文件的正式标题</td></tr>
              <tr><td>发布时间</td><td>原文发布时间，用于时间排序与筛选</td></tr>
              <tr><td>发布来源</td><td>发布机关或媒体，如新华社、中国政府网、《求是》</td></tr>
              <tr><td>原文链接</td><td>指向原文的官方网址，可直接跳转</td></tr>
              <tr><td>关键词</td><td>便于检索的提法标签，分号分隔</td></tr>
              <tr><td>观点速览</td><td>该条内容的核心观点摘要</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <h2 class="section-title" id="quality" style="margin-top:48px">二、数据质量核对</h2>
      <p class="section-desc">
        脚本在解析时发现以下 %(problemCount)d 处需要人工确认的问题，其中
        <span class="tag tag-amber">%(severeCount)d 处</span>属于占位符、期号重复或跳号，
        <span class="tag tag-navy">%(softCount)d 处</span>属于报头期号与文件名期号相差 1 的系统性偏差。
        这些问题来自源 Word 文件的报头或文件名本身，脚本<strong>未做任何自动改写</strong>，仅如实记录；
        建议在源文件中确认后重新生成。
      </p>
      <div class="table-wrap" style="margin-top:20px">
        <div class="table-scroll">
          <table class="data" style="min-width:820px">
            <thead>
              <tr>
                <th scope="col">类型</th><th scope="col">期次</th><th scope="col">日期</th>
                <th scope="col">源文件</th><th scope="col">说明</th>
              </tr>
            </thead>
            <tbody id="qualityBody"></tbody>
          </table>
        </div>
      </div>

      <h2 class="section-title" id="update" style="margin-top:48px">三、如何新增一期</h2>
      <p class="section-desc">本库是“丢文件即入库”的结构，新出一期时不需要改任何代码。</p>
      <div class="acc" style="margin-top:20px">
        <button class="acc-head" aria-expanded="true">
          <span class="lead"><span class="idx">1</span><span>把新的 Word 文件放进 source 目录</span></span>
          <svg class="ic" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>
        </button>
        <div class="acc-body">
          <p>新一期的《重要讲话与最新提法数据库》Word 文件放入
            <code>source/2.北大青年纵横/主文件/</code>，命名保持与现有文件一致即可
            （如 <code>重要讲话与最新提法数据库-总第23期.docx</code>）。
            领导人论述、重要文章如有更新，也按原文件名替换 <code>source/1.党和国家领导人…</code> 下的文件。</p>
        </div>
      </div>
      <div class="acc" style="margin-top:14px">
        <button class="acc-head" aria-expanded="true">
          <span class="lead"><span class="idx">2</span><span>重新运行解析与生成脚本</span></span>
          <svg class="ic" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>
        </button>
        <div class="acc-body">
          <p>在项目根目录执行两条命令，网站就会自动多出新的一期：</p>
          <pre style="background:var(--navy-900);color:#e8eefc;padding:16px 18px;border-radius:10px;overflow-x:auto;font-size:13px;line-height:1.8;font-family:var(--font-mono)">python tools/extract.py
python tools/build.py</pre>
          <p style="margin-top:12px">第一条解析 Word 生成 <code>site/data/content.json</code>，
            第二条把它写成网站数据与新页面。脚本会打印解析自检表，逐期显示条目数与数据质量提示。</p>
        </div>
      </div>
      <div class="acc" style="margin-top:14px">
        <button class="acc-head" aria-expanded="true">
          <span class="lead"><span class="idx">3</span><span>本地预览</span></span>
          <svg class="ic" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>
        </button>
        <div class="acc-body">
          <p>直接双击 <code>site/index.html</code> 即可离线浏览；
            也可以在本项目根目录启动一个本地服务后访问 <code>http://127.0.0.1:8123/</code>：</p>
          <pre style="background:var(--navy-900);color:#e8eefc;padding:16px 18px;border-radius:10px;overflow-x:auto;font-size:13px;line-height:1.8;font-family:var(--font-mono)">python -m http.server 8123 --directory site</pre>
        </div>
      </div>

      <h2 class="section-title" id="tech" style="margin-top:48px">四、技术说明</h2>
      <div class="stats" style="margin-top:20px;grid-template-columns:repeat(3,minmax(0,1fr))">
        <div class="stat">
          <div class="stat-num" style="font-size:26px">纯静态</div>
          <div class="stat-label">HTML + CSS + 原生 JS，无框架、无构建依赖</div>
        </div>
        <div class="stat">
          <div class="stat-num" style="font-size:26px">可离线</div>
          <div class="stat-label">数据内嵌于 data/db.js，双击即可打开</div>
        </div>
        <div class="stat">
          <div class="stat-num" style="font-size:26px">零外链</div>
          <div class="stat-label">不依赖任何外部字体、图片或 CDN</div>
        </div>
      </div>

      <div class="notice notice-info" style="margin-top:32px">
        <svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>
        <div><strong>版权与使用</strong>：本库内容整理自公开权威来源（中国政府网、新华社、《人民日报》《求是》、
          共青团中央等），原文著作权归原作者与发布机构所有，本站仅作学习研究与工作参考使用。</div>
      </div>
    </div>
  </section>
""" % {
        "problemCount": q.get("problemCount", 0),
        "severeCount": q.get("severeCount", 0),
        "softCount": q.get("problemCount", 0) - q.get("severeCount", 0),
    }
    return shell(
        "关于本库 · 北大青年纵横",
        "著录字段说明、数据质量核对结果、新增期次的操作步骤与技术说明。",
        "about.html",
        body,
        data["site"],
    )


# --------------------------------------------------------------------------
# 404
# --------------------------------------------------------------------------
def page_404(data: dict) -> str:
    body = """  <section class="section" style="padding:90px 0">
    <div class="wrap">
      <div class="empty">
        <svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <h3>没有找到这个页面</h3>
        <p>页面可能已被移动或地址输入有误。你可以回到首页，或直接进入数据库总览。</p>
        <div class="row" style="justify-content:center;flex-wrap:wrap">
          <a class="btn btn-primary" href="index.html">返回首页</a>
          <a class="btn btn-outline" href="database.html">重要讲话数据库</a>
          <a class="btn btn-outline" href="search.html">全库检索</a>
        </div>
      </div>
    </div>
  </section>
"""
    return shell(
        "页面未找到 · 北大青年纵横",
        "页面未找到。",
        "",
        body,
        data["site"],
    )


# --------------------------------------------------------------------------
# 生成
# --------------------------------------------------------------------------
def write_db_js(data: dict) -> None:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    js = (
        "/* 本文件由 tools/build.py 自动生成，请勿手工修改。\n"
        "   数据来源：tools/extract.py 解析 source/ 下的 Word 文件。\n"
        "   生成时间：%s */\n" % date.today().isoformat()
        + "window.DSH_DB = " + payload + ";\n"
    )
    with open(DATA_JS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(js)


def check_html(paths) -> list:
    """基础结构自检：标签闭合、必备元素、内部链接可达、属性引号完整。"""
    problems = []
    # 属性值必须带引号。曾经因为脚本写文件时把引号吞掉，生成出
    # <p class=hero-couplet> 这种不合法 HTML，浏览器虽能容错但不可接受，
    # 因此在这里做硬性检查。
    unquoted = re.compile(r'\s(?:class|id|href|src|alt|aria-hidden|aria-label|rel|style|width|height)=[^"\'\s>]')
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            html = fh.read()
        name = os.path.relpath(p, SITE)
        for tag in ("html", "head", "body"):
            if "<%s" % tag not in html or "</%s>" % tag not in html:
                problems.append("%s: 缺少 <%s> 标签" % (name, tag))
        for needle in ("assets/style.css", "assets/app.js", "data/db.js", "id=\"main\""):
            if needle not in html:
                problems.append("%s: 缺少 %s" % (name, needle))
        if "nav-toggle" not in html:
            problems.append("%s: 缺少移动端导航按钮" % name)
        hits = unquoted.findall(html)
        if hits:
            problems.append("%s: 有 %d 处属性值未加引号 -> %s" % (name, len(hits), hits[:3]))
        # 内部链接可达性
        for href in set(re.findall(r'href="([^"#:?]+\.html)"', html)):
            if not os.path.isfile(os.path.join(SITE, href)):
                problems.append("%s: 链接目标不存在 -> %s" % (name, href))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = ap.parse_args()

    if not os.path.isfile(DATA_JSON):
        print("找不到 %s，请先运行 python tools/extract.py" % DATA_JSON)
        return 1
    with open(DATA_JSON, encoding="utf-8") as fh:
        data = json.load(fh)

    print("=" * 70)
    print("站点生成")
    print("=" * 70)

    if args.check:
        print("数据：%d 期 / %d 条条目 / %d 条论述" % (
            data["stats"]["issueCount"], data["stats"]["entryCount"], data["stats"]["leaderCount"]))
        print("数据质量待确认问题：%d 处" % data.get("quality", {}).get("problemCount", 0))
        return 0

    write_db_js(data)
    print("已生成 site/data/db.js  (%.1f KB)" % (os.path.getsize(DATA_JS) / 1024.0))

    pages = {
        "index.html": page_index(data),
        "database.html": page_database(data),
        "issue.html": page_issue(data),
        "leaders.html": page_leaders(data),
        "awards.html": page_awards(data),
        "search.html": page_search(data),
        "about.html": page_about(data),
        "404.html": page_404(data),
    }
    for name, html in pages.items():
        path = os.path.join(SITE, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(html)
        print("已生成 %-16s (%.1f KB)" % ("site/" + name, os.path.getsize(path) / 1024.0))

    problems = check_html([os.path.join(SITE, n) for n in pages])
    print("-" * 70)
    if problems:
        print("结构自检发现问题：")
        for p in problems:
            print("  ! " + p)
    else:
        print("结构自检通过：页面标签完整、资源引用与内部链接均可达。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
