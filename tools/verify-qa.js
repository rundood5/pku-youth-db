/* 问答窗口功能自检
   用最小 DOM 执行 assets/app.js，然后直接调用内部的 QA 检索逻辑，
   检查典型问题能否检索到库内资料、命中是否正确、是否会出现空结果。

   用法：node tools/verify-qa.js
*/
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SITE = path.resolve(__dirname, "..", "site");

/* ---- 最小 DOM（只要够 app.js 初始化不报错即可） ---- */
function El(tag) {
  this.tagName = (tag || "div").toUpperCase();
  this.attrs = {}; this.children = []; this.parent = null;
  this._text = ""; this._html = ""; this._className = "";
  this.style = {}; this.hidden = false; this._listeners = {};
  const self = this;
  this.classList = {
    add() {}, remove() {}, toggle() { return false; }, contains() { return false; }
  };
}
El.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
El.prototype.getAttribute = function (k) { return this.attrs[k] !== undefined ? this.attrs[k] : null; };
El.prototype.hasAttribute = function (k) { return k in this.attrs; };
El.prototype.removeAttribute = function (k) { delete this.attrs[k]; };
El.prototype.addEventListener = function () {};
El.prototype.removeEventListener = function () {};
El.prototype.appendChild = function (c) { return c; };
El.prototype.closest = function () { return null; };
El.prototype.querySelector = function () { return null; };
El.prototype.querySelectorAll = function () { return []; };
El.prototype.focus = function () {};
Object.defineProperty(El.prototype, "innerHTML", {
  get() { return this._html; }, set(v) { this._html = String(v == null ? "" : v); }
});
Object.defineProperty(El.prototype, "textContent", {
  get() { return this._text; }, set(v) { this._text = String(v == null ? "" : v); }
});
Object.defineProperty(El.prototype, "nextElementSibling", { get() { return null; } });

const root = new El("html");
const document = {
  readyState: "complete",
  title: "",
  documentElement: root,
  body: root,
  querySelector: () => null,
  querySelectorAll: () => [],
  getElementById: () => null,
  addEventListener: () => {},
  createElement: (t) => new El(t)
};

const sandbox = {
  document,
  location: { pathname: "/index.html", search: "", href: "file:///index.html" },
  console, Date, Math, JSON, RegExp, parseInt, parseFloat, isNaN,
  encodeURIComponent, decodeURIComponent, Promise, Array, Object, String, Number, Boolean, Error,
  setTimeout: (fn) => { try { fn(); } catch (e) {} return 0; },
  clearTimeout: () => {},
  IntersectionObserver: class { observe() {} unobserve() {} disconnect() {} }
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.addEventListener = () => {};
sandbox.window.scrollTo = () => {};
sandbox.window.scrollY = 0;

const ctx = vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(SITE, "data", "db.js"), "utf8"), ctx, { filename: "db.js" });
try {
  vm.runInContext(fs.readFileSync(path.join(SITE, "assets", "app.js"), "utf8"), ctx, { filename: "app.js" });
} catch (e) {
  console.log("app.js 执行失败:", e.message);
  process.exit(1);
}

const DSH = sandbox.window.DSH || {};
if (!DSH.QA || typeof DSH.QA.search !== "function") {
  console.log("window.DSH.QA 未暴露，无法自检问答逻辑。");
  process.exit(1);
}
const QA = DSH.QA;

console.log("=".repeat(70));
console.log("问答窗口自检（库内检索问答）");
console.log("=".repeat(70));

const corpus = QA.corpus();
const byKind = {};
corpus.forEach((d) => (byKind[d.kind] = (byKind[d.kind] || 0) + 1));
console.log("可检索资料总量: " + corpus.length + " 条");
Object.keys(byKind).forEach((k) => console.log("   " + k + ": " + byKind[k]));

const QUESTIONS = [
  ["总书记关于立德树人的重要论述", ["立德", "树人"]],
  ["青年要如何树立理想信念", ["理想", "信念", "青年"]],
  ["共青团工作的政治性、先进性、群众性", ["政治性", "先进性", "群众性"]],
  ["中长期青年发展规划", ["青年发展规划", "中长期"]],
  ["青年和共青团工作的重要论述有哪些", ["青年", "共青团"]],
  ["四个意识四个自信", []],
  ["完全不相关的问题zzzqqq", []]
];

let fail = 0;
console.log("\n" + "-".repeat(70));
for (const [q, expectAny] of QUESTIONS) {
  const res = QA.search(q, 5);
  const kws = res.kws.join("/");
  const top = res.hits[0];
  const ok = expectAny.length === 0 ? true : expectAny.some((k) =>
    res.hits.some((h) => h.doc.hay.indexOf(k.toLowerCase()) !== -1));
  if (!ok) fail++;
  console.log("\n问题: " + q);
  console.log("  关键词: " + (kws || "(无)"));
  console.log("  命中数: " + res.hits.length + (expectAny.length ? (ok ? "  [OK]" : "  [FAIL 未命中预期内容]") : ""));
  if (top) {
    console.log("  首条  : [" + top.doc.kind + "] " + top.doc.title.slice(0, 40));
    console.log("  片段  : " + top.doc.text.slice(0, 62).replace(/\s+/g, " ") + "…");
  } else {
    console.log("  首条  : （无命中）");
  }
}

console.log("\n" + "=".repeat(70));
console.log(fail === 0 ? "问答检索自检通过 ✓" : fail + " 个问题未检索到预期内容 ✗");
process.exit(fail === 0 ? 0 : 1);
