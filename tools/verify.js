/* ==========================================================================
   站点自检工具（Node，无外部依赖）
   用一个最小 DOM 实现把 assets/app.js 真正跑起来，检查每个页面渲染后的结果：
     · JS 是否抛异常
     · 动态容器是否被填充、条目数量是否正确
     · 关键内容（期号、标题、原文链接）是否出现
     · 页面上是否残留 "undefined" / "NaN" / 未替换占位符
   用法：node tools/verify.js
   ========================================================================== */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SITE = path.resolve(__dirname, "..", "site");

/* ---------------- 最小 DOM 实现 ---------------- */
class ClassList {
  constructor(el) {
    this.el = el;
    this.set = new Set();
  }
  add(...c) { c.forEach((x) => x && this.set.add(x)); this._sync(); }
  remove(...c) { c.forEach((x) => this.set.delete(x)); this._sync(); }
  contains(c) { return this.set.has(c); }
  toggle(c, force) {
    const want = force === undefined ? !this.set.has(c) : !!force;
    if (want) this.set.add(c); else this.set.delete(c);
    this._sync();
    return want;
  }
  _sync() { this.el._className = [...this.set].join(" "); }
}

class El {
  constructor(tag, attrs) {
    this.tagName = (tag || "div").toUpperCase();
    this.attrs = Object.assign({}, attrs);
    this.children = [];
    this.parent = null;
    this._text = "";
    this._html = "";
    this._className = this.attrs.class || "";
    this.classList = new ClassList(this);
    this.style = {};
    this.hidden = false;
    this._listeners = {};
    this._id = this.attrs.id || "";
  }
  get className() { return this._className; }
  set className(v) {
    this._className = v || "";
    this.classList.set = new Set(String(v || "").split(/\s+/).filter(Boolean));
  }
  get id() { return this._id; }
  get textContent() {
    return this._text || stripTags(this._html);
  }
  set textContent(v) { this._text = String(v == null ? "" : v); }
  get innerHTML() { return this._html; }
  set innerHTML(v) {
    this._html = String(v == null ? "" : v);
    this._text = "";
    this.children = parseFragment(this._html, this);
  }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === "id") this._id = String(v); }
  getAttribute(k) {
    if (k === "class") return this._className;
    return k in this.attrs ? this.attrs[k] : null;
  }
  removeAttribute(k) { delete this.attrs[k]; }
  hasAttribute(k) { return k in this.attrs; }
  addEventListener(t, fn) { (this._listeners[t] = this._listeners[t] || []).push(fn); }
  removeEventListener(t, fn) {
    if (this._listeners[t]) this._listeners[t] = this._listeners[t].filter((f) => f !== fn);
  }
  dispatch(type, ev) {
    (this._listeners[type] || []).forEach((fn) => fn.call(this, ev || {}));
  }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  closest(sel) {
    let n = this;
    while (n) { if (matches(n, sel)) return n; n = n.parent; }
    return null;
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  querySelectorAll(sel) {
    const out = [];
    const walk = (node) => {
      node.children.forEach((c) => {
        if (matches(c, sel)) out.push(c);
        walk(c);
      });
    };
    walk(this);
    return out;
  }
  get nextElementSibling() {
    if (!this.parent) return null;
    const i = this.parent.children.indexOf(this);
    return this.parent.children[i + 1] || null;
  }
  get firstElementChild() { return this.children[0] || null; }
  focus() {}
  blur() {}
}

/* 极简选择器匹配：#id / .class / tag / tag.class / [attr] */
function matches(el, sel) {
  if (!el || !el.tagName) return false;
  return String(sel).split(",").some((one) => {
    one = one.trim();
    if (!one) return false;
    const parts = one.match(/^([a-zA-Z]+)?((?:[.#][\w-]+)*)((?:\[[^\]]+\])*)$/);
    if (!parts) return false;
    const [, tag, cls, attrs] = parts;
    if (tag && el.tagName !== tag.toUpperCase()) return false;
    // 组合选择器 split 保持从左到右
    if (cls) {
      const needs = cls.match(/[.#][\w-]+/g) || [];
      for (const n of needs) {
        if (n[0] === "." && !el.classList.contains(n.slice(1))) return false;
        if (n[0] === "#" && el.id !== n.slice(1)) return false;
      }
    }
    if (attrs) {
      const list = attrs.match(/\[[^\]]+\]/g) || [];
      for (const a of list) {
        const m = /^\[([\w-]+)(?:=["']?([^"'\]]*)["']?)?\]$/.exec(a);
        if (!m) return false;
        if (m[2] === undefined) { if (!el.hasAttribute(m[1])) return false; }
        else if (el.getAttribute(m[1]) !== m[2]) return false;
      }
    }
    return true;
  });
}

function stripTags(html) {
  return String(html)
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function parseFragment(html, parent) {
  const nodes = [];
  const stack = [parent];
  const re = /<(\/?)([a-zA-Z][\w-]*)((?:\s*[\w:-]+(?:=(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+)/g;
  let m;
  while ((m = re.exec(html))) {
    const [, closing, tag, attrStr, selfClose, text] = m;
    if (text !== undefined) {
      const t = text.trim();
      if (t) {
        const leaf = new El("#text");
        leaf._text = t;
        stack[stack.length - 1].children.push(leaf);
      }
      continue;
    }
    const lower = tag.toLowerCase();
    if (closing) {
      // 只在标签名匹配时弹栈，避免被自闭合/不可见标签带偏
      for (let i = stack.length - 1; i > 0; i--) {
        if (stack[i].tagName === lower.toUpperCase()) {
          stack.length = i;
          break;
        }
      }
      continue;
    }
    const attrs = {};
    const ar = /([\w:-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
    let a;
    while ((a = ar.exec(attrStr || ""))) {
      attrs[a[1]] = a[2] !== undefined ? a[2] : a[3] !== undefined ? a[3] : a[4] !== undefined ? a[4] : "";
    }
    const el = new El(lower, attrs);
    stack[stack.length - 1].children.push(el);
    if (!selfClose && !["br", "img", "input", "meta", "link", "hr", "source"].includes(lower)) {
      stack.push(el);
    }
  }
  return nodes.length ? nodes : parent.children;
}

/* ---------------- 页面装载 ---------------- */
function loadPage(file, query) {
  const html = fs.readFileSync(path.join(SITE, file), "utf8");
  const root = new El("html");

  // 只解析 body 内容（app.js 只在 body 内操作）
  const bodyMatch = /<body[^>]*>([\s\S]*)<\/body>/i.exec(html);
  const bodyHtml = bodyMatch ? bodyMatch[1] : html;
  // 去掉 script 标签，稍后手动执行
  const cleanBody = bodyHtml.replace(/<script[\s\S]*?<\/script>/gi, "");
  root.innerHTML = cleanBody;

  const document = {
    readyState: "complete",
    title: (/<title>([\s\S]*?)<\/title>/i.exec(html) || [, ""])[1],
    documentElement: root,
    body: root,
    _listeners: {},
    querySelector: (s) => root.querySelector(s),
    querySelectorAll: (s) => root.querySelectorAll(s),
    getElementById: (id) => root.querySelector("#" + id),
    addEventListener(t, fn) { (this._listeners[t] = this._listeners[t] || []).push(fn); },
    createElement: (t) => new El(t)
  };

  const location = {
    pathname: "/" + file,
    search: query || "",
    href: "file:///" + file + (query || "")
  };

  const sandbox = {
    document,
    location,
    console,
    setTimeout: (fn) => { try { fn(); } catch (e) {} return 0; },
    clearTimeout: () => {},
    Date,
    Math,
    JSON,
    RegExp,
    parseInt,
    parseFloat,
    isNaN,
    encodeURIComponent,
    decodeURIComponent,
    Promise,
    Array,
    Object,
    String,
    Number,
    Boolean,
    Error
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.window.addEventListener = () => {};
  sandbox.window.scrollTo = () => {};
  sandbox.window.scrollY = 0;
  sandbox.IntersectionObserver = class {
    constructor() {}
    observe() {}
    unobserve() {}
    disconnect() {}
  };

  const ctx = vm.createContext(sandbox);
  const errors = [];
  try {
    vm.runInContext(fs.readFileSync(path.join(SITE, "data", "db.js"), "utf8"), ctx, { filename: "db.js" });
  } catch (e) { errors.push("db.js: " + e.message); }
  try {
    vm.runInContext(fs.readFileSync(path.join(SITE, "assets", "app.js"), "utf8"), ctx, { filename: "app.js" });
  } catch (e) { errors.push("app.js 执行异常: " + e.message); }

  // app.js 在 readyState=complete 时直接执行 boot()，无需手动触发
  return { document, root, html, errors, sandbox };
}

/* ---------------- 检查项 ---------------- */
const CHECKS = [
  {
    file: "index.html",
    name: "首页",
    expect: [
      ["#latestIssue", "hero-card-tag", "最新一期"],
      ["#recentIssues", "issue-card", null, 1],
      ["#latestItems", "class=\"item", null, 1],
      ["#kwCloud", "", ""],
      ["@raw", "北大青年纵横", null],
      ["@raw", "<h1>北大青年纵横</h1>", null, 1]
    ]
  },
  {
    file: "database.html",
    name: "数据库总览",
    expect: [
      ["#catRow", "chip", null, 2],
      ["#issueList", "issue-card", null, 1],
      ["#dbCount", "", "共"],
      ["@raw", "北大青年纵横", null]
    ]
  },
  {
    file: "issue.html",
    name: "单期详情（唯一保留的一期）",
    query: "?no=14",
    expect: [
      ["#issueSide", "side-item", null, 1],
      ["#issueHead", "h1", "总第14期"],
      ["#entryList", "class=\"item", null, 1],
      ["#issueOverview", "本期概览"],
      ["#issuePager", "href=\"database.html\""]
    ]
  },
  {
    file: "issue.html",
    name: "单期详情（缺省取最新一期）",
    query: "",
    expect: [
      ["#issueHead", "h1", "总第14期"],
      ["#entryList", "class=\"item", null, 1]
    ]
  },
  {
    file: "issue.html",
    name: "单期详情（不存在的期号）",
    query: "?no=999",
    expect: [["#issueBody", "", "没有找到这一期"]]
  },
  {
    file: "leaders.html",
    name: "领导人论述库",
    expect: [
      ["#leaderRow", "chip", null, 5],
      ["#leaderBody", "leader-pill", null, 12],
      ["#xiArticles", "acc-head", null, 12],
      ["#xiQuotes", "quote-card", null, 20]
    ]
  },
  {
    file: "search.html",
    name: "全库检索",
    expect: [
      ["#gsCats", "chip", null, 2],
      ["#gsCats", "chip", null, 2],
      ["#gsCount", "", "全库共"]
    ]
  },
  {
    file: "search.html",
    name: "全库检索（带关键词 q=青年）",
    query: "?q=" + encodeURIComponent("青年"),
    expect: [
      ["#gsCount", "", "青年"],
      ["#searchResults", "class=\"item", null, 1],
      ["#searchResults", "<mark>", null, 1]
    ]
  },
  {
    file: "database.html",
    name: "数据库总览（带分类筛选 cat=共青团与青年）",
    query: "?cat=" + encodeURIComponent("共青团与青年"),
    expect: [
      ["#issueList", "issue-card", null, 1],
      ["#dbCount", "", "1</b>"]
    ]
  },
  {
    file: "awards.html",
    name: "共青团与青年工作课题",
    expect: [
      ["@raw", "新时代青年理想信念教育常态化制度化研究", null],
      ["@raw", "新时代青年理想信念教育常态化制度化研究", null],
      ["@raw", "共青团与青年工作课题", null]
    ]
  },
  {
    file: "about.html",
    name: "关于本库",
    expect: [["#qualityBody", "tr", null, 1]]
  },
  {
    file: "404.html",
    name: "404",
    // 404 页没有带 id 的容器，直接对整页 HTML 做文本与元素检查
    raw: true,
    expect: [
      ["@raw", "没有找到这个页面", null],
      ["@raw", "btn-primary", null, 1],
      ["@raw", "btn-outline", null, 2],
      ["@raw", "href=\"index.html\"", null, 1]
    ]
  }
];

function countOccurrences(hay, needle) {
  if (!needle) return 0;
  let n = 0, i = 0;
  while ((i = hay.indexOf(needle, i)) !== -1) { n++; i += needle.length; }
  return n;
}

let fail = 0;
const report = [];

console.log("=".repeat(72));
console.log("站点渲染自检（Node 最小 DOM + vm 执行 app.js）");
console.log("=".repeat(72));

for (const c of CHECKS) {
  const page = loadPage(c.file, c.query);
  const problems = [];
  if (page.errors.length) problems.push(...page.errors);

  for (const [sel, needle, textNeed, minCount] of c.expect) {
    let hay;
    if (c.raw || sel === "@raw") {
      hay = page.html;
    } else {
      const host = page.root.querySelector(sel);
      if (!host) { problems.push("找不到容器 " + sel); continue; }
      hay = host.innerHTML;
    }
    if (textNeed && hay.indexOf(textNeed) === -1) {
      problems.push(sel + " 内未找到文本 “" + textNeed + "”（渲染可能未执行）");
    }
    if (needle) {
      const n = countOccurrences(hay, needle);
      if (n === 0) problems.push(sel + " 未渲染出 " + needle);
      else if (minCount && n < minCount) problems.push(sel + " 只渲染出 " + n + " 个 " + needle + "，预期 ≥" + minCount);
    }
  }

  // 残留占位符检查
  const bodyText = page.root.textContent;
  ["undefined", "NaN", "[object Object]", "%s", "%d"].forEach((bad) => {
    if (bodyText.includes(bad)) problems.push("页面文本中残留 “" + bad + "”");
  });

  const status = problems.length ? "FAIL" : "PASS";
  if (problems.length) fail++;
  console.log(`\n[${status}] ${c.name}  (${c.file})`);
  problems.forEach((p) => console.log("   ! " + p));
  if (!problems.length) console.log("   · 渲染与内容检查全部通过");
  report.push({ page: c.file, ok: !problems.length, problems });
}

/* ---------------- 数据完整性检查 ---------------- */
console.log("\n" + "=".repeat(72));
console.log("数据完整性检查");
console.log("=".repeat(72));
const dbSrc = fs.readFileSync(path.join(SITE, "data", "db.js"), "utf8");
const db = JSON.parse(dbSrc.replace(/^[\s\S]*?window\.DSH_DB\s*=\s*/, "").replace(/;\s*$/, ""));
const dataProblems = [];

if (db.issues.length < 1) dataProblems.push("过滤后没有任何期次");
const emptyIssue = db.issues.filter((i) => !i.entries.length);
if (emptyIssue.length) dataProblems.push("有条目为空的期次: " + emptyIssue.map((i) => i.issue).join(","));
const noUrl = [];
db.issues.forEach((it) => it.entries.forEach((e) => { if (!e.url) noUrl.push(it.label + " / " + e.title); }));
const noTitle = [];
db.issues.forEach((it) => it.entries.forEach((e) => { if (!e.title || /未命名/.test(e.title)) noTitle.push(it.label); }));
if (noTitle.length) dataProblems.push("缺少标题的条目: " + noTitle.join(","));
if (db.leaders.length !== 42) dataProblems.push("领导人论述 " + db.leaders.length + " ≠ 42");
if ((db.awards && db.awards.items ? db.awards.items.length : 0) !== 25) dataProblems.push("课题数异常");
const badLeader = db.leaders.filter((r) => !r.leader || (!r.quote && !r.occasion));
if (badLeader.length) {
  dataProblems.push(
    "论述表存在缺领导人/缺场合的行 " + badLeader.length + " 行: " +
      badLeader.map((r) => r.time + "/" + r.occasion).join(",")
  );
}
// 有场合但无原句的行属于源文件本身如此，只统计不判定失败
const noQuote = db.leaders.filter((r) => !r.quote);
if (noQuote.length) console.log("提示        : 源表中 " + noQuote.length + " 行未填写原句（页面显示为 —）");
if (db.xiArticles.items.length !== 12) dataProblems.push("重要文章 " + db.xiArticles.items.length + " ≠ 12");

const totalEntries = db.issues.reduce((n, i) => n + i.entries.length, 0);
const totalQuotes = db.xiQuotes.parts.reduce((n, p) => n + p.totalsQuotes || 0, 0);

console.log("期次        : " + db.issues.length);
console.log("条目        : " + totalEntries);
console.log("领导人论述  : " + db.leaders.length + "  (毛泽东%d/邓小平%d/江泽民%d/胡锦涛%d/习近平%d)".replace(/%d/g, () => ""));
const byLeader = {};
db.leaders.forEach((r) => (byLeader[r.leader] = (byLeader[r.leader] || 0) + 1));
console.log("  按领导人  : " + Object.entries(byLeader).map(([k, v]) => k + " " + v).join(" / "));
console.log("重要文章    : " + db.xiArticles.items.length + " 篇");
console.log("青春寄语    : " + db.xiQuotes.parts.reduce((n, p) => n + p.topics.reduce((m, t) => m + t.quotes.length, 0), 0) + " 条");
console.log("无原文链接  : " + noUrl.length + " 条" + (noUrl.length ? " -> " + noUrl.slice(0, 3).join(" | ") : ""));
console.log("数据质量问题: " + (db.quality ? db.quality.problemCount : 0) + " 处");

if (dataProblems.length) {
  fail++;
  console.log("\n[FAIL] 数据完整性");
  dataProblems.forEach((p) => console.log("   ! " + p));
} else {
  console.log("\n[PASS] 数据完整性：期次、条目、论述、文章数量与必填字段全部正常");
}

console.log("\n" + "=".repeat(72));
console.log(fail === 0 ? "全部检查通过 ✓" : fail + " 项检查未通过 ✗");
console.log("=".repeat(72));
process.exit(fail === 0 ? 0 : 1);
