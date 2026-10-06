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
    ("search.html", "全库检索"),
    ("about.html", "关于本库"),
]

FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='7' fill='%230f1b33'/%3E"
    "%3Crect x='0' y='0' width='4' height='32' fill='%23b11d24'/%3E"
    "%3Ctext x='17' y='23' font-size='18' font-family='serif' font-weight='bold'"
    " fill='%23ffffff' text-anchor='middle'%3E论%3C/text%3E%3C/svg%3E"
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
          <svg class="ic" viewBox="0 0 24 24"><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/></svg>
        </span>
        <span class="brand-text">
          <span class="brand-name">重要讲话与最新提法数据库</span>
          <span class="brand-sub">北大青年纵横 · 学习资料库</span>
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
              <svg class="ic" viewBox="0 0 24 24"><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/></svg>
            </span>
            <span class="brand-text">
              <span class="brand-name">重要讲话与最新提法数据库</span>
              <span class="brand-sub">北大青年纵横</span>
            </span>
          </div>
          <p>系统整理党和国家领导人关于共青团及青年工作的重要论述、最新重要讲话与政策文件，
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
        <span>© <span data-year>2026</span> %s · 数据整理自公开权威来源，仅供学习研究使用</span>
        <span class="tag">数据更新：%s</span>
      </div>
    </div>
  </footer>

  <button class="to-top" type="button" aria-label="返回顶部">
    <svg class="ic" viewBox="0 0 24 24"><path d="M12 19V5"/><path d="m6 11 6-6 6 6"/></svg>
  </button>""" % (link_items, site_meta.get("org", ""), site_meta.get("generated", ""))


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
    body = """  <section class="hero">
    <div class="wrap hero-grid">
      <div>
        <span class="eyebrow"><span class="eyebrow-dot"></span>数据持续更新 · 已归档 %(issueCount)d 期</span>
        <h1>把党和国家领导人的<br><em>重要讲话与最新提法</em><br>整理成一座可检索的库</h1>
        <p class="hero-lede">
          收录习近平总书记及历届党和国家领导人关于共青团与青年工作的重要论述，
          按期次归档《重要讲话与最新提法数据库》所涉政策文件、党报党刊文章与权威发布，
          逐条著录标题、时间、来源、原文链接、关键词与观点速览。
        </p>
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
          <h2 class="section-title">三大内容板块</h2>
          <p class="section-desc">库内所有内容都按统一字段著录，点进去即可看到摘要与原文入口。</p>
        </div>
      </div>
      <div class="entry-grid">
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
          <p>历届党和国家领导人关于共青团及青年工作的重要论述汇总，
             按领导人、时间、场合、性质与完整原句著录，另附青年寄语分主题语录。</p>
          <span class="entry-foot">
            <span>%(leaderCount)d 条论述 · %(quoteCount)d 条寄语</span>
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

  <section class="section">
    <div class="wrap">
      <div class="section-head">
        <div>
          <h2 class="section-title">最新归档期次</h2>
          <p class="section-desc">按发布时间倒序排列，点击卡片查看该期完整概览与著录条目。</p>
        </div>
        <a class="section-link" href="database.html">
          查看全部 %(issueCount)d 期
          <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
        </a>
      </div>
      <div class="issue-grid" id="recentIssues"></div>
    </div>
  </section>

  <section class="section section-alt">
    <div class="wrap">
      <div class="section-head">
        <div>
          <h2 class="section-title">最近更新的内容</h2>
          <p class="section-desc">跨期次抽取的最新条目，标题可直接跳转原文。</p>
        </div>
        <a class="section-link" href="search.html">
          去检索
          <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
        </a>
      </div>
      <div class="entry-list" id="latestItems"></div>
    </div>
  </section>

  <section class="section">
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
""" % {
        "issueCount": s["issueCount"],
        "entryCount": s["entryCount"],
        "leaderCount": s["leaderCount"],
        "quoteCount": s["quoteCount"],
        "dateRangeText": cn_range(s["dateRange"][0], s["dateRange"][1]),
    }
    return shell(
        "重要讲话与最新提法数据库 · 北大青年纵横",
        "收录党和国家领导人关于共青团与青年工作的重要论述，以及《重要讲话与最新提法数据库》全部期次的政策文件与权威文章，支持关键词检索与原文跳转。",
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
        "重要讲话数据库 · 重要讲话与最新提法数据库",
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
        "期次详情 · 重要讲话与最新提法数据库",
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
      <h1>党和国家领导人关于共青团及青年工作重要论述</h1>
      <p class="lede">
        汇总历届党和国家领导人在重要会议、座谈、回信与文章中关于共青团和青年工作的论述，
        按 领导人 / 时间 / 场合 / 性质 / 完整原句 逐条著录，可检索具体提法的出处。
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
        "领导人论述库 · 重要讲话与最新提法数据库",
        "历届党和国家领导人关于共青团及青年工作的重要论述汇总，按领导人、时间、场合、性质与原句著录。",
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
        "全库检索 · 重要讲话与最新提法数据库",
        "在所有期次的著录内容中检索重要讲话、政策文件与重要提法，支持关键词高亮与原文跳转。",
        "search.html",
        body,
        data["site"],
    )


# --------------------------------------------------------------------------
# 关于本库
# --------------------------------------------------------------------------
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
        "关于本库 · 重要讲话与最新提法数据库",
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
        "页面未找到 · 重要讲话与最新提法数据库",
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
    """基础结构自检：标签闭合、必备元素、内部链接可达。"""
    problems = []
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
