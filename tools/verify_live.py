# -*- coding: utf-8 -*-
"""部署后验证：检查 GitHub Pages 上的网站是否真的可用

用法：
    python tools/verify_live.py                          # 用默认网址
    python tools/verify_live.py https://xxx.github.io/repo/

检查项（这些都是"页面返回 200 但其实是坏的"的常见情况）：
  1. 首页、各子页面、资源文件是否都能取到
  2. 页面里引用的资源路径是否真的是相对路径（部署到子目录时最容易出错）
  3. 数据文件是否被替换成了 GitHub 的 404 页面（路径写错时表现为 HTTP 200 + HTML）
  4. 数据是否完整（期次、条目、论述数量）
  5. 关键中文内容是否正常（编码没坏）
  6. 缓存响应头是否合理（避免更新后别人看到旧内容）
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "https://rundood5.github.io/pku-youth-db/"

PAGES = [
    "index.html",
    "database.html",
    "issue.html",
    "leaders.html",
    "search.html",
    "about.html",
    "404.html",
]
ASSETS = ["assets/style.css", "assets/app.js", "data/db.js", ".nojekyll"]


def get(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers={"User-Agent": "site-verify/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()
    except Exception as e:  # noqa: BLE001
        return None, {}, str(e).encode()


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    if not base.endswith("/"):
        base += "/"

    print("=" * 70)
    print("线上网站验证")
    print("=" * 70)
    print("网址: %s" % base)
    print()

    fails, warns = [], []

    # ---- 1. 可达性 ----
    print("[1/6] 页面与资源可达性")
    results = {}
    for path in PAGES + ASSETS:
        status, headers, body = get(base + path)
        results[path] = (status, headers, body)
        mark = "OK " if status == 200 else "XX "
        print("   %s %-20s HTTP %s  %8s bytes" % (mark, path, status, len(body) if status else "-"))
        if status != 200:
            fails.append("%s 返回 %s（不是 200）" % (path, status))

    if all(results[p][0] is None for p in results):
        print("\n[FAIL] 完全无法连接。可能原因：仓库还没推送、Pages 还没开启、或网址写错了。")
        print("       如果刚开启 Pages，请再等 1-2 分钟重试。")
        return 1

    # ---- 2. 资源路径是否为相对路径 ----
    print()
    print("[2/6] 首页资源引用是否为相对路径（部署在子目录时最关键）")
    idx_status, _, idx_body = results["index.html"]
    idx = idx_body.decode("utf-8", "replace") if idx_status == 200 else ""
    refs = re.findall(r'(?:href|src)="([^"]*(?:\.css|\.js))"', idx)
    if not refs:
        fails.append("首页里没找到任何 css/js 引用，页面可能没取对")
    for r in refs:
        bad = r.startswith("/")
        print("   %s %s" % ("XX " if bad else "OK ", r))
        if bad:
            fails.append("资源路径以 / 开头（%s），部署在子目录时会 404" % r)

    # ---- 3. 数据文件是否真的是数据 ----
    print()
    print("[3/6] 数据文件内容是否为真实数据（防止拿到 404 页面）")
    db_status, db_headers, db_body = results["data/db.js"]
    db_text = db_body.decode("utf-8", "replace") if db_status == 200 else ""
    if "DSH_DB" not in db_text:
        fails.append("data/db.js 里没有 DSH_DB，可能被替换成了 404 页面")
        print("   XX  未找到 window.DSH_DB")
    else:
        print("   OK  找到 window.DSH_DB")
        if "404" in db_text[:300] and "Not Found" in db_text[:600]:
            fails.append("data/db.js 内容像 GitHub 的 404 页面")
            print("   XX  内容疑似 404 页面")

    # ---- 4. 数据完整性 ----
    print()
    print("[4/6] 数据完整性")
    data = None
    if "DSH_DB" in db_text:
        try:
            # db.js 结构为：/* 注释 */\nwindow.DSH_DB = {...};\n
            # 直接取第一个 "{" 到最后一个 "}" 之间的内容，避免注释或前缀干扰
            start = db_text.index("{", db_text.index("DSH_DB"))
            end = db_text.rindex("}")
            data = json.loads(db_text[start : end + 1])
        except Exception as e:  # noqa: BLE001
            fails.append("无法解析 db.js 里的 JSON: %s" % e)
            print("   XX  db.js 内容解析失败: %s" % e)

    if data:
        issues = data.get("issues", [])
        leaders = data.get("leaders", [])
        entries = sum(len(i.get("entries", [])) for i in issues)
        quotes = sum(
            len(t.get("quotes", []))
            for p in data.get("xiQuotes", {}).get("parts", [])
            for t in p.get("topics", [])
        )
        articles = len(data.get("xiArticles", {}).get("items", []))
        print("   期次        : %d" % len(issues))
        print("   著录条目    : %d" % entries)
        print("   领导人论述  : %d" % len(leaders))
        print("   重要文章    : %d" % articles)
        print("   青春寄语    : %d" % quotes)
        for label, got, want in [
            ("期次", len(issues), 20),
            ("著录条目", entries, 36),
            ("领导人论述", len(leaders), 42),
            ("重要文章", articles, 12),
            ("青春寄语", quotes, 64),
        ]:
            if got != want:
                warns.append("%s 为 %d，本地为 %d（若你更新过内容则正常）" % (label, got, want))

    # ---- 5. 中文与编码 ----
    print()
    print("[5/6] 中文内容与编码")
    if "北大青年纵横" in idx:
        print("   OK  首页含站名「北大青年纵横」，UTF-8 正常")
    else:
        fails.append("首页里找不到站名「北大青年纵横」，可能编码损坏或页面不对")
        print("   XX  未找到站名")
    if data:
        lead0 = (data.get("leaders") or [{}])[0]
        if lead0.get("leader") and lead0.get("quote"):
            print("   OK  论述数据含中文内容（%s）" % lead0["leader"])

    # ---- 6. 缓存头 ----
    print()
    print("[6/6] 缓存策略（避免更新后别人看到旧内容）")
    cc = db_headers.get("Cache-Control") or db_headers.get("cache-control") or "(未设置)"
    print("   data/db.js 的 Cache-Control: %s" % cc)
    if "max-age" in cc and "max-age=0" not in cc and "no-cache" not in cc:
        warns.append("db.js 被长期缓存（%s），更新内容后访问者可能看到旧数据" % cc)
    print("   说明: GitHub Pages 对静态文件会自行设置缓存，通常无需担心；")
    print("        若此值不理想，改用 Cloudflare Pages 可自定义（见 DEPLOY.md 第三节）。")

    # ---- 汇总 ----
    print()
    print("=" * 70)
    if fails:
        print("结果：部署未成功，发现 %d 个问题" % len(fails))
        for f in fails:
            print("   ! %s" % f)
        print()
        print("排查顺序：")
        print("   1) 仓库是否已推送成功？打开 https://github.com/rundood5/pku-youth-db 看有没有文件")
        print("   2) Settings -> Pages 的 Source 是否选成了 GitHub Actions")
        print("   3) Actions 标签里那次运行是绿勾还是红叉？红叉点进去看报错")
        print("   4) 刚开启 Pages 的话，等 1-2 分钟再跑一次本脚本")
        return 1

    print("结果：部署成功 ✓")
    for w in warns:
        print("   提示: %s" % w)
    print()
    print("可以把这个网址发给别人了：")
    print("   %s" % base)
    print()
    print("建议再手动确认一次：用手机流量（关掉 WiFi）打开该网址，确认外网访问正常。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
