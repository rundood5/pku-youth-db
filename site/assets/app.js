/* ==========================================================================
   重要讲话与最新提法数据库 —— 公共交互
   依赖：window.DSH_DB（由 data/db.js 提供）
   说明：全站纯静态、零依赖、可离线打开；所有页面逻辑都由这里统一渲染，
        因此新增一期只要重新运行 tools/extract.py 并重新生成 db.js 即可。
   ========================================================================== */
(function () {
  "use strict";

  var DB = window.DSH_DB || { issues: [], leaders: [], stats: {}, site: {} };

  /* ---------------- 基础工具 ---------------- */
  var esc = function (s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  var $ = function (sel, root) {
    return (root || document).querySelector(sel);
  };
  var $$ = function (sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  };

  /** 把连续多个换行/空格压平，用于渲染段落 */
  var flat = function (s) {
    return String(s == null ? "" : s).replace(/\s*\n\s*/g, "\n").trim();
  };

  var CN_DIGITS = "零一二三四五六七八九";
  function cnNum(n) {
    if (n <= 10) return n === 10 ? "十" : CN_DIGITS[n];
    if (n < 20) return "十" + CN_DIGITS[n - 10];
    if (n < 100) {
      var t = Math.floor(n / 10),
        o = n % 10;
      return CN_DIGITS[t] + "十" + (o ? CN_DIGITS[o] : "");
    }
    return String(n);
  }

  /** 2026-08-23 -> 2026年8月23日 */
  function prettyDate(iso) {
    if (!iso) return "";
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    if (m) return m[1] + "年" + (+m[2]) + "月" + (+m[3]) + "日";
    m = /^(\d{4})-(\d{2})$/.exec(iso);
    if (m) return m[1] + "年" + (+m[2]) + "月";
    return iso;
  }

  /** 查询串里的高亮 */
  function highlight(text, q) {
    var safe = esc(text);
    if (!q) return safe;
    var tokens = q
      .split(/\s+/)
      .filter(function (t) {
        return t.length >= 1;
      })
      .map(function (t) {
        return t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      });
    if (!tokens.length) return safe;
    try {
      return safe.replace(new RegExp("(" + tokens.join("|") + ")", "gi"), "<mark>$1</mark>");
    } catch (e) {
      return safe;
    }
  }

  function truncate(s, n) {
    s = String(s || "");
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
  }

  /* ---------------- URL 参数 ---------------- */
  function param(name, fallback) {
    var m = new RegExp("[?&]" + name + "=([^&#]*)").exec(location.search);
    if (!m) return fallback;
    try {
      return decodeURIComponent(m[1].replace(/\+/g, " "));
    } catch (e) {
      return fallback;
    }
  }

  /* ---------------- 数据查找 ---------------- */
  function getIssue(no) {
    no = parseInt(no, 10);
    for (var i = 0; i < DB.issues.length; i++) {
      if (DB.issues[i].issue === no) return DB.issues[i];
    }
    return null;
  }

  function issueIndex(no) {
    for (var i = 0; i < DB.issues.length; i++) {
      if (DB.issues[i].issue === no) return i;
    }
    return -1;
  }

  /** 全库条目展平，附上所属期次信息，供检索用 */
  function allItems() {
    var out = [];
    DB.issues.forEach(function (it) {
      (it.entries || []).forEach(function (e, i) {
        out.push({
          issue: it.issue,
          issueLabel: it.label,
          issueDate: it.date,
          seq: i + 1,
          title: e.title,
          // summary 全文用于检索与详情，summaryShort 用于卡片列表
          summary: e.summary || e.summaryShort || "",
          summaryShort: e.summaryShort || e.summary || "",
          source: e.source || "",
          pubdate: e.pubdate || "",
          pubISO: e.pubISO || "",
          url: e.url || "",
          keywords: e.keywords || [],
          category: e.category || "其他",
          section: e.section || ""
        });
      });
    });
    return out;
  }

  function itemHaystack(it) {
    return [
      it.title,
      it.summary,
      it.source,
      it.pubdate,
      it.category,
      it.section,
      it.issueLabel,
      (it.keywords || []).join(" ")
    ]
      .join(" ")
      .toLowerCase();
  }

  function matchItem(it, q) {
    if (!q) return true;
    var tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
    var hay = itemHaystack(it);
    return tokens.every(function (t) {
      return hay.indexOf(t) !== -1;
    });
  }

  /* ---------------- 组件：期次卡片 ---------------- */
  function issueCard(it, opt) {
    opt = opt || {};
    var overview = (it.overview || []).slice(0, opt.max || 3);
    var rest = (it.overview || []).length - overview.length;
    var chips = (it.categories || []).slice(0, 3);

    var li = overview
      .map(function (t) {
        return (
          '<li><span class="dot"></span><span>' +
          esc(truncate(flat(t), opt.clamp || 74)) +
          "</span></li>"
        );
      })
      .join("");
    if (rest > 0) {
      li +=
        '<li class="more">另有 ' +
        rest +
        " 条内容，点击查看全部 →</li>";
    }

    var iso = /^\d{2}$/.test(String(it.issue)) ? it.issue : ("0" + it.issue).slice(-2);
    var noHtml = it.issue
      ? esc(it.issue) + "<i>期</i>"
      : '<span style="font-size:19px">待补</span>';

    return (
      '<a class="issue-card reveal" href="issue.html?no=' +
      it.issue +
      '">' +
      '<div class="issue-top">' +
      '<span class="issue-no">' +
      noHtml +
      "</span>" +
      '<span class="issue-date">' +
      icon("calendar") +
      esc(prettyDate(it.date) || it.dateText) +
      "</span>" +
      "</div>" +
      '<div><span class="mini-chip">' +
      esc(it.label) +
      "</span>" +
      (it.needsReview
        ? ' <span class="tag tag-amber" title="' + esc((it.notes || []).join("；")) + '">期号待核</span>'
        : (it.notes && it.notes.length
            ? ' <span class="tag tag-navy" title="' + esc(it.notes.join("；")) + '">源文件期号差异</span>'
            : "")) +
      "</div>" +
      '<ul class="issue-overview">' +
      (li || '<li><span class="dot"></span><span>本期暂无概览</span></li>') +
      "</ul>" +
      '<div class="issue-foot">' +
      '<span class="chips-inline">' +
      chips
        .map(function (c) {
          return '<span class="mini-chip">' + esc(c) + "</span>";
        })
        .join("") +
      "</span>" +
      '<span class="issue-go">查看本期 ' +
      esc(it.entryCount) +
      " 条 " +
      icon("arrow-right") +
      "</span>" +
      "</div>" +
      "</a>"
    );
  }

  /* ---------------- 组件：条目卡 ---------------- */
  function itemCard(it, q, opt) {
    opt = opt || {};
    var kw = (it.keywords || [])
      .slice(0, 8)
      .map(function (k) {
        return '<span class="kw">' + highlight(k, q) + "</span>";
      })
      .join("");

    var link = it.url
      ? '<a class="link-out" href="' +
        esc(it.url) +
        '" target="_blank" rel="noopener noreferrer">' +
        icon("external") +
        '<span class="url">' +
        esc(it.url.replace(/^https?:\/\//, "")) +
        "</span></a>"
      : '<span class="tag">未提供原文链接</span>';

    var issueLink = opt.showIssue
      ? '<a class="tag tag-navy" href="issue.html?no=' +
        it.issue +
        '">' +
        icon("layers") +
        esc(it.issueLabel) +
        "</a>"
      : "";

    var summary = it.summary || it.summaryShort || "";
    var shown = opt.full ? summary : it.summaryShort || summary;
    var clipped = shown.length < summary.length;

    return (
      '<article class="item reveal">' +
      '<span class="item-accent"></span>' +
      '<div class="item-head">' +
      (it.category ? '<span class="tag tag-red">' + esc(it.category) + "</span>" : "") +
      (it.section ? '<span class="tag">' + esc(it.section) + "</span>" : "") +
      issueLink +
      "</div>" +
      '<h3 class="item-title">' +
      (it.url
        ? '<a href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">' + highlight(it.title, q) + "</a>"
        : highlight(it.title, q)) +
      "</h3>" +
      '<div class="item-meta">' +
      (it.pubdate ? "<span>" + icon("calendar") + highlight(it.pubdate, q) + "</span>" : "") +
      (it.source ? "<span>" + icon("source") + highlight(it.source, q) + "</span>" : "") +
      (opt.showIssue && it.issueDate
        ? "<span>" + icon("clock") + esc(prettyDate(it.issueDate)) + " 收录</span>"
        : "") +
      "</div>" +
      '<p class="item-summary">' + highlight(shown, q) + (clipped ? " …" : "") + "</p>" +
      (kw ? '<div class="kw-row">' + kw + "</div>" : "") +
      '<div class="item-actions">' + link + "</div>" +
      "</article>"
    );
  }

  /* ---------------- 图标 ---------------- */
  var ICONS = {
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    layers: '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
    quote: '<path d="M9 7H5a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h2v1a3 3 0 0 1-3 3"/><path d="M19 7h-4a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h2v1a3 3 0 0 1-3 3"/>',
    book: '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 0 4 22.5Z"/><path d="M8 7h8M8 11h6"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    source: '<path d="M4 19.5V6a2 2 0 0 1 2-2h9l5 5v10.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1Z"/><path d="M14 4v6h6"/>',
    external: '<path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M18 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    "arrow-left": '<path d="M19 12H5"/><path d="m11 18-6-6 6-6"/>',
    "arrow-up": '<path d="M12 19V5"/><path d="m6 11 6-6 6 6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    close: '<path d="M18 6 6 18M6 6l12 12"/>',
    filter: '<path d="M3 5h18l-7 8v6l-4-2v-4Z"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    alert: '<path d="M10.3 3.6 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
    check: '<path d="m4 12 5 5L20 6"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    star: '<path d="m12 3 2.6 5.6 6.1.8-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6L3.3 9.4l6.1-.8Z"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M17 5.2a3.5 3.5 0 0 1 0 6.6M18.5 20a6.5 6.5 0 0 0-2-4.7"/>',
    upload: '<path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    db: '<ellipse cx="12" cy="6" rx="8" ry="3.2"/><path d="M4 6v12c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2V6"/><path d="M4 12c0 1.8 3.6 3.2 8 3.2s8-1.4 8-3.2"/>'
  };

  function icon(name, cls) {
    var path = ICONS[name] || ICONS.info;
    return (
      '<svg class="ic ' +
      (cls || "") +
      '" viewBox="0 0 24 24" aria-hidden="true">' +
      path +
      "</svg>"
    );
  }

  /* ---------------- 页面装配 ---------------- */
  function initNav() {
    var nav = $(".nav");
    var toggle = $(".nav-toggle");
    var links = $(".nav-links");
    if (toggle && links) {
      toggle.addEventListener("click", function () {
        var open = links.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
      $$(".nav-link", links).forEach(function (a) {
        a.addEventListener("click", function () {
          links.classList.remove("is-open");
          toggle.setAttribute("aria-expanded", "false");
        });
      });
    }
    if (nav) {
      var onScroll = function () {
        nav.classList.toggle("is-scrolled", window.scrollY > 8);
      };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }

    // 返回顶部
    var top = $(".to-top");
    if (top) {
      window.addEventListener(
        "scroll",
        function () {
          top.classList.toggle("is-visible", window.scrollY > 520);
        },
        { passive: true }
      );
      top.addEventListener("click", function () {
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }

    // 当前页高亮
    var here = location.pathname.split("/").pop() || "index.html";
    $$(".nav-link").forEach(function (a) {
      var href = (a.getAttribute("href") || "").split("?")[0];
      if (href === here) a.setAttribute("aria-current", "page");
    });
  }

  /** 滚动入场 */
  function initReveal(root) {
    var nodes = $$(".reveal", root || document);
    if (!nodes.length) return;
    if (!("IntersectionObserver" in window)) {
      nodes.forEach(function (n) {
        n.classList.add("is-in");
      });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            en.target.classList.add("is-in");
            io.unobserve(en.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.04 }
    );
    nodes.forEach(function (n, i) {
      n.style.transitionDelay = Math.min(i % 6, 5) * 45 + "ms";
      io.observe(n);
    });
  }

  function fillStats() {
    var s = DB.stats || {};
    $$("[data-stat]").forEach(function (el) {
      var key = el.getAttribute("data-stat");
      var v = s[key];
      if (v == null) return;
      if (key === "dateRange") {
        el.textContent = (v[0] || "") + " — " + (v[1] || "");
      } else {
        el.textContent = v;
      }
    });
  }

  function fillYear() {
    $$("[data-year]").forEach(function (el) {
      el.textContent = new Date().getFullYear();
    });
  }

  function fillCount() {
    $$("[data-count]").forEach(function (el) {
      var key = el.getAttribute("data-count");
      var v = (DB.stats || {})[key];
      el.textContent = v == null ? "" : v;
    });
  }

  /* ---------------- 页面：首页 ---------------- */
  function pageHome() {
    var host = $("#latestIssue");
    if (host) {
      var last = DB.issues[DB.issues.length - 1];
      if (last) {
        var list = (last.overview || [])
          .slice(0, 4)
          .map(function (t, i) {
            return (
              '<li><span class="idx">' +
              (i + 1) +
              "</span><span>" +
              esc(truncate(flat(t), 76)) +
              "</span></li>"
            );
          })
          .join("");
        host.innerHTML =
          '<div class="hero-card reveal">' +
          '<span class="hero-card-tag">最新一期 · ' +
          esc(last.label) +
          "</span>" +
          "<h3>" +
          esc(last.title) +
          "</h3>" +
          '<div class="hero-card-date">' +
          icon("calendar") +
          " " +
          esc(prettyDate(last.date) || last.dateText) +
          " · 收录 " +
          esc(last.entryCount) +
          " 条</div>" +
          '<ul class="hero-card-list">' +
          (list || "<li>本期暂无概览</li>") +
          "</ul>" +
          '<a class="hero-card-more" href="issue.html?no=' +
          last.issue +
          '">阅读本期全文提要 ' +
          icon("arrow-right") +
          "</a>" +
          "</div>";
      }
    }

    var recent = $("#recentIssues");
    if (recent) {
      var items = DB.issues.slice(-4).reverse();
      recent.innerHTML = items
        .map(function (it) {
          return issueCard(it, { max: 2, clamp: 60 });
        })
        .join("");
    }

    var latestItems = $("#latestItems");
    if (latestItems) {
      var pool = allItems()
        .sort(function (a, b) {
          return (b.pubISO || "").localeCompare(a.pubISO || "") || b.issue - a.issue;
        })
        .slice(0, 6);
      latestItems.innerHTML = pool
        .map(function (it) {
          return itemCard(it, "", { showIssue: true });
        })
        .join("");
    }

    var kw = $("#kwCloud");
    if (kw) {
      var top = ((DB.stats || {}).topKeywords || []).slice(0, 26);
      // 关键词为空时把整块藏起来，否则页面上会留一大片空白
      var kwSec = $("#kwSection");
      if (kwSec) kwSec.hidden = top.length === 0;
      kw.innerHTML = top
        .map(function (pair) {
          return (
            '<a class="chip" href="search.html?q=' +
            encodeURIComponent(pair[0]) +
            '">' +
            esc(pair[0]) +
            '<span class="n">' +
            pair[1] +
            "</span></a>"
          );
        })
        .join("");
    }
  }

  /* ---------------- 页面：数据库总览 ---------------- */
  function pageDatabase() {
    var list = $("#issueList");
    if (!list) return;

    var state = {
      q: param("q", ""),
      cat: param("cat", ""),
      sort: "desc",
      page: 1,
      per: 6
    };

    var input = $("#dbSearch");
    var clearBtn = $("#dbClear");
    var catRow = $("#catRow");
    var sortSel = $("#sortSel");
    var countEl = $("#dbCount");
    var moreBtn = $("#dbMore");

    // 分类 chips（含"全部"）
    var cats = (DB.stats || {}).categories || [];
    catRow.innerHTML =
      '<button class="chip" data-cat="" aria-pressed="true">全部<span class="n">' +
      (DB.stats.issueCount || 0) +
      "</span></button>" +
      cats
        .map(function (pair) {
          return (
            '<button class="chip" data-cat="' +
            esc(pair[0]) +
            '" aria-pressed="false">' +
            esc(pair[0]) +
            '<span class="n">' +
            pair[1] +
            "</span></button>"
          );
        })
        .join("");

    function filtered() {
      var out = DB.issues.filter(function (it) {
        if (state.cat) {
          if ((it.categories || []).indexOf(state.cat) === -1) return false;
        }
        if (!state.q) return true;
        var hay = [
          it.label,
          it.dateText,
          it.date,
          (it.overview || []).join(" "),
          (it.keywords || []).join(" "),
          (it.entries || [])
            .map(function (e) {
              return [e.title, e.summaryShort, e.source, (e.keywords || []).join(" ")].join(" ");
            })
            .join(" ")
        ]
          .join(" ")
          .toLowerCase();
        return state.q
          .toLowerCase()
          .split(/\s+/)
          .filter(Boolean)
          .every(function (t) {
            return hay.indexOf(t) !== -1;
          });
      });
      out.sort(function (a, b) {
        var d = (a.date || "").localeCompare(b.date || "");
        return state.sort === "desc" ? -d : d;
      });
      return out;
    }

    function render() {
      var rows = filtered();
      var shown = rows.slice(0, state.page * state.per);
      list.innerHTML = shown.length
        ? shown
            .map(function (it) {
              return issueCard(it, { max: 3, clamp: 70 });
            })
            .join("")
        : '<div class="empty" style="grid-column:1/-1">' +
          icon("search") +
          "<h3>没有匹配的期次</h3><p>试试更换关键词，或清除分类筛选后重试。</p>" +
          '<button class="btn btn-outline" id="emptyReset">清除全部筛选</button></div>';

      countEl.innerHTML =
        "共 <b>" + rows.length + "</b> 期匹配 · 累计 " +
        rows.reduce(function (n, it) {
          return n + it.entryCount;
        }, 0) +
        " 条内容";

      var rest = rows.length - shown.length;
      moreBtn.hidden = rest <= 0;
      moreBtn.innerHTML = "加载更多（还有 " + rest + " 期）" + icon("chevron-down");

      var reset = $("#emptyReset");
      if (reset) {
        reset.onclick = function () {
          state.q = "";
          state.cat = "";
          if (input) input.value = "";
          syncChips();
          render();
        };
      }
      initReveal(list);
    }

    function syncChips() {
      $$(".chip", catRow).forEach(function (b) {
        b.setAttribute("aria-pressed", b.getAttribute("data-cat") === state.cat ? "true" : "false");
      });
    }

    if (input) {
      input.value = state.q;
      var box = input.closest(".search-box");
      if (box) box.classList.toggle("has-value", !!state.q);
      var timer = null;
      input.addEventListener("input", function () {
        var box2 = input.closest(".search-box");
        if (box2) box2.classList.toggle("has-value", !!input.value);
        clearTimeout(timer);
        timer = setTimeout(function () {
          state.q = input.value.trim();
          state.page = 1;
          render();
        }, 130);
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        if (input) input.value = "";
        state.q = "";
        state.page = 1;
        var box = input && input.closest(".search-box");
        if (box) box.classList.remove("has-value");
        render();
        if (input) input.focus();
      });
    }

    catRow.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".chip");
      if (!btn) return;
      state.cat = btn.getAttribute("data-cat") || "";
      state.page = 1;
      syncChips();
      render();
    });

    if (sortSel) {
      sortSel.addEventListener("change", function () {
        state.sort = sortSel.value;
        render();
      });
    }
    moreBtn.addEventListener("click", function () {
      state.page++;
      render();
    });

    if (state.cat) syncChips();
    render();
  }

  /* ---------------- 页面：单期详情 ---------------- */
  function pageIssue() {
    var host = $("#issueBody");
    if (!host) return;

    var no = parseInt(param("no", ""), 10);
    var idx = isNaN(no) ? DB.issues.length - 1 : issueIndex(no);
    if (idx < 0) {
      host.innerHTML =
        '<div class="empty">' +
        icon("search") +
        "<h3>没有找到这一期</h3><p>该期可能尚未入库。请返回数据库总览选择其他期次。</p>" +
        '<a class="btn btn-primary" href="database.html">返回数据库总览</a></div>';
      return;
    }
    var it = DB.issues[idx];
    var prev = DB.issues[idx - 1];
    var next = DB.issues[idx + 1];

    document.title = it.label + " · " + DB.site.title;

    // 侧栏期号列表
    var side = $("#issueSide");
    if (side) {
      side.innerHTML = DB.issues
        .slice()
        .reverse()
        .map(function (x) {
          return (
            '<a class="side-item" href="issue.html?no=' +
            x.issue +
            '"' +
            (x.issue === it.issue ? ' aria-current="true"' : "") +
            "><span>" +
            esc(x.label) +
            '</span><span class="d">' +
            esc((x.date || "").slice(5)) +
            "</span></a>"
          );
        })
        .join("");
    }

    // 文档头
    var head = $("#issueHead");
    if (head) {
      head.innerHTML =
        '<div class="crumb"><a href="index.html">首页</a><span class="sep">/</span>' +
        '<a href="database.html">重要讲话数据库</a><span class="sep">/</span>' +
        "<span>" +
        esc(it.label) +
        "</span></div>" +
        "<h1>" +
        esc(it.title) +
        " · " +
        esc(it.label) +
        "</h1>" +
        '<p class="lede">' +
        esc(prettyDate(it.date) || it.dateText) +
        " 期次，共收录 " +
        esc(it.entryCount) +
        " 条重要文章、政策文件与提法，按原文来源逐条整理，可点击标题跳转原文。" +
        "</p>" +
        '<div class="doc-head-meta">' +
        "<span>" +
        icon("calendar") +
        esc(prettyDate(it.date) || it.dateText) +
        "</span>" +
        "<span>" +
        icon("layers") +
        esc(it.entryCount) +
        " 条内容</span>" +
        "<span>" +
        icon("filter") +
        ((it.categories || []).join(" / ") || "—") +
        "</span>" +
        "<span>" +
        icon("source") +
        esc(it.docx) +
        "</span>" +
        "</div>";
    }

    // 导读（概览）
    var overview = $("#issueOverview");
    if (overview) {
      if ((it.overview || []).length) {
        overview.innerHTML =
          '<div class="notice notice-info">' +
          icon("info") +
          "<div><strong>本期概览 · " +
          esc(it.overview.length) +
          " 条</strong><ol style=\"margin-top:8px\">" +
          it.overview
            .map(function (t, i) {
              return (
                '<li style="display:flex;gap:9px;margin-top:6px"><span style="font-family:var(--font-mono);opacity:.7">' +
                (i + 1) +
                ".</span><span>" +
                esc(flat(t)) +
                "</span></li>"
              );
            })
            .join("") +
          "</ol></div>";
      } else {
        overview.innerHTML = "";
      }
    }

    // 期号待核提示
    var notesHost = $("#issueNotes");
    if (notesHost) {
      notesHost.innerHTML = (it.notes || []).length
        ? '<div class="notice">' +
          icon("alert") +
          "<div><strong>该期期号/日期需要核对</strong><br>" +
          esc(it.notes.join("；")) +
          "。本页按报头内容如实展示，未做自动改写。<a href=\"about.html#quality\">查看数据说明</a></div></div>"
        : "";
    }

    // 条目列表
    var body = $("#entryList");
    if (body) {
      body.innerHTML = (it.entries || [])
        .map(function (e) {
          return itemCard(
            {
              issue: it.issue,
              issueLabel: it.label,
              issueDate: it.date,
              title: e.title,
              summary: e.summary || "",
              summaryShort: e.summaryShort || "",
              source: e.source,
              pubdate: e.pubdate,
              pubISO: e.pubISO,
              url: e.url,
              keywords: e.keywords,
              category: e.category,
              section: e.section
            },
            "",
            { showIssue: false, full: false }
          );
        })
        .join("");
    }

    // 上/下一期（只有一期时没有“上/下一期”的概念，只留返回总览）
    var pager = $("#issuePager");
    if (pager && DB.issues.length <= 1) {
      pager.innerHTML =
        '<a class="btn btn-outline" href="database.html">' + icon("grid") + "全部期次</a>";
    } else if (pager) {
      pager.innerHTML =
        (prev
          ? '<a class="btn btn-outline" href="issue.html?no=' +
            prev.issue +
            '">' +
            icon("arrow-left") +
            esc(prev.label) +
            "</a>"
          : '<span class="btn btn-outline" style="opacity:.45;pointer-events:none">' +
            icon("arrow-left") +
            "已是第一期</span>") +
        '<a class="btn btn-outline" href="database.html">' +
        icon("grid") +
        "全部期次</a>" +
        (next
          ? '<a class="btn btn-outline" href="issue.html?no=' +
            next.issue +
            '">' +
            esc(next.label) +
            icon("arrow-right") +
            "</a>"
          : '<span class="btn btn-outline" style="opacity:.45;pointer-events:none">已是最后一期' +
            icon("arrow-right") +
            "</span>");
    }

    // 本期出处
    if (it.footer && it.footer.length) {
      var foot = $("#issueFooter");
      if (foot) {
        foot.innerHTML =
          '<div class="notice notice-info">' +
          icon("users") +
          "<div><strong>本期编辑信息</strong><br>" +
          it.footer.map(esc).join("<br>") +
          "</div></div>";
      }
    }
  }

  /* ---------------- 页面：领导人论述库 ---------------- */
  function pageLeaders() {
    var host = $("#leaderBody");
    if (!host) return;

    var state = { q: param("q", ""), leader: param("leader", ""), sort: "time", page: 1, per: 12 };
    var input = $("#ldSearch");
    var clearBtn = $("#ldClear");
    var leaderRow = $("#leaderRow");
    var sortSel = $("#ldSort");
    var countEl = $("#ldCount");
    var moreBtn = $("#ldMore");

    var byLeader = {};
    DB.leaders.forEach(function (r) {
      byLeader[r.leader] = (byLeader[r.leader] || 0) + 1;
    });
    var order = ["毛泽东", "邓小平", "江泽民", "胡锦涛", "习近平"];
    var names = Object.keys(byLeader).sort(function (a, b) {
      var ia = order.indexOf(a),
        ib = order.indexOf(b);
      if (ia === -1) ia = 99;
      if (ib === -1) ib = 99;
      return ia - ib || a.localeCompare(b);
    });

    leaderRow.innerHTML =
      '<button class="chip" data-leader="" aria-pressed="true">全部领导人<span class="n">' +
      DB.leaders.length +
      "</span></button>" +
      names
        .map(function (n) {
          return (
            '<button class="chip" data-leader="' +
            esc(n) +
            '" aria-pressed="false">' +
            esc(n) +
            '<span class="n">' +
            byLeader[n] +
            "</span></button>"
          );
        })
        .join("");

    function pillClass(name) {
      return (
        { 毛泽东: "l-mao", 邓小平: "l-deng", 江泽民: "l-jiang", 胡锦涛: "l-hu", 习近平: "l-xi" }[name] || ""
      );
    }

    function filtered() {
      var rows = DB.leaders.filter(function (r) {
        if (state.leader && r.leader !== state.leader) return false;
        if (!state.q) return true;
        var hay = [r.leader, r.time, r.occasion, r.nature, r.quote].join(" ").toLowerCase();
        return state.q
          .toLowerCase()
          .split(/\s+/)
          .filter(Boolean)
          .every(function (t) {
            return hay.indexOf(t) !== -1;
          });
      });
      rows.sort(function (a, b) {
        if (state.sort === "leader") {
          var ia = names.indexOf(a.leader),
            ib = names.indexOf(b.leader);
          return ia - ib || (a.timeISO || "").localeCompare(b.timeISO || "");
        }
        if (state.sort === "occasion") return (a.occasion || "").localeCompare(b.occasion || "", "zh");
        return (a.timeISO || "9999").localeCompare(b.timeISO || "9999");
      });
      return rows;
    }

    // 引用句可能多段，用空行分条展示
    function quoteHtml(q) {
      return flat(q)
        .split(/\n+/)
        .filter(Boolean)
        .map(function (line) {
          return '<span class="q">' + highlight(line, state.q) + "</span>";
        })
        .join("");
    }

    function render() {
      var rows = filtered();
      var shown = rows.slice(0, state.page * state.per);
      host.innerHTML = shown.length
        ? shown
            .map(function (r, i) {
              return (
                "<tr>" +
                '<td class="c-leader"><span class="leader-pill ' +
                pillClass(r.leader) +
                '">' +
                esc(r.leader) +
                "</span></td>" +
                '<td class="c-time">' +
                highlight(r.time, state.q) +
                "</td>" +
                '<td class="c-occasion">' +
                highlight(r.occasion, state.q) +
                "</td>" +
                '<td class="c-occasion">' +
                highlight(r.nature, state.q) +
                "</td>" +
                '<td class="c-quote">' +
                quoteHtml(r.quote || "—") +
                "</td>" +
                "</tr>"
              );
            })
            .join("")
        : '<tr><td colspan="5"><div class="empty" style="border:0;background:none">' +
          icon("search") +
          "<h3>没有匹配的论述</h3><p>换个关键词，或点击“全部领导人”查看完整 42 条论述。</p></div></td></tr>";

      countEl.innerHTML = "共 <b>" + rows.length + "</b> 条论述";
      var rest = rows.length - shown.length;
      moreBtn.hidden = rest <= 0;
      moreBtn.innerHTML = "加载更多（还有 " + rest + " 条）" + icon("chevron-down");
    }

    function syncChips() {
      $$(".chip", leaderRow).forEach(function (b) {
        b.setAttribute("aria-pressed", b.getAttribute("data-leader") === state.leader ? "true" : "false");
      });
    }

    if (input) {
      input.value = state.q;
      var box = input.closest(".search-box");
      if (box) box.classList.toggle("has-value", !!state.q);
      var timer = null;
      input.addEventListener("input", function () {
        var b2 = input.closest(".search-box");
        if (b2) b2.classList.toggle("has-value", !!input.value);
        clearTimeout(timer);
        timer = setTimeout(function () {
          state.q = input.value.trim();
          state.page = 1;
          render();
        }, 130);
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        if (input) input.value = "";
        state.q = "";
        state.page = 1;
        var box = input && input.closest(".search-box");
        if (box) box.classList.remove("has-value");
        render();
      });
    }
    leaderRow.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".chip");
      if (!btn) return;
      state.leader = btn.getAttribute("data-leader") || "";
      state.page = 1;
      syncChips();
      render();
    });
    if (sortSel) {
      sortSel.addEventListener("change", function () {
        state.sort = sortSel.value;
        render();
      });
    }
    moreBtn.addEventListener("click", function () {
      state.page++;
      render();
    });

    if (state.leader) syncChips();
    render();

    // 习近平文章 + 青春寄语
    var artHost = $("#xiArticles");
    if (artHost) {
      artHost.innerHTML = (DB.xiArticles.items || [])
        .map(function (a, i) {
          var paras = flat(a.body)
            .split(/\n+/)
            .filter(Boolean)
            .map(function (p) {
              return "<p>" + esc(p) + "</p>";
            })
            .join("");
          return (
            '<div class="acc reveal">' +
            '<button class="acc-head" aria-expanded="false">' +
            '<span class="lead"><span class="idx">' +
            (i + 1) +
            "</span><span>" +
            esc(a.title) +
            '<span class="cnt">' +
            esc(a.dateISO) +
            " · " +
            a.chars +
            " 字</span></span></span>" +
            icon("chevron-down") +
            "</button>" +
            '<div class="acc-body" hidden>' +
            '<div class="article-body is-open">' +
            paras +
            "</div>" +
            "</div>" +
            "</div>"
          );
        })
        .join("");
    }

    var qHost = $("#xiQuotes");
    if (qHost) {
      qHost.innerHTML = (DB.xiQuotes.parts || [])
        .map(function (part) {
          var topics = (part.topics || [])
            .map(function (t) {
              return (
                '<h3 class="section-title" style="font-size:18px;margin:26px 0 16px">' +
                esc(t.title) +
                '<span class="mini-chip">' +
                t.quotes.length +
                " 条</span></h3>" +
                '<div class="quote-grid">' +
                t.quotes
                  .map(function (q) {
                    return (
                      '<figure class="quote-card reveal" style="margin:0">' +
                      "<p>" +
                      highlight(q.text, "") +
                      "</p>" +
                      (q.cite ? '<figcaption class="quote-cite">' + esc(q.cite) + "</figcaption>" : "") +
                      "</figure>"
                    );
                  })
                  .join("") +
                "</div>"
              );
            })
            .join("");
          return (
            '<div style="margin-bottom:30px">' +
            '<h2 class="section-title">' +
            esc(part.title) +
            '<span class="mini-chip">' +
            part.count +
            " 条</span></h2>" +
            topics +
            "</div>"
          );
        })
        .join("");
    }
  }

  /* ---------------- 页面：全库检索 ---------------- */
  function pageSearch() {
    var host = $("#searchResults");
    if (!host) return;

    var state = { q: param("q", ""), cat: "", sort: "date", page: 1, per: 8 };
    var input = $("#gsSearch");
    var clearBtn = $("#gsClear");
    var catRow = $("#gsCats");
    var sortSel = $("#gsSort");
    var countEl = $("#gsCount");
    var moreBtn = $("#gsMore");
    var pool = allItems();

    var cats = (DB.stats || {}).categories || [];
    catRow.innerHTML =
      '<button class="chip" data-cat="" aria-pressed="true">全部<span class="n">' +
      pool.length +
      "</span></button>" +
      cats
        .map(function (p) {
          return (
            '<button class="chip" data-cat="' +
            esc(p[0]) +
            '" aria-pressed="false">' +
            esc(p[0]) +
            '<span class="n">' +
            p[1] +
            "</span></button>"
          );
        })
        .join("");

    function filtered() {
      var rows = pool.filter(function (it) {
        if (state.cat && it.category !== state.cat) return false;
        return matchItem(it, state.q);
      });
      rows.sort(function (a, b) {
        if (state.sort === "issue") return b.issue - a.issue || a.seq - b.seq;
        if (state.sort === "source") return (a.source || "").localeCompare(b.source || "", "zh");
        return (b.pubISO || "").localeCompare(a.pubISO || "") || b.issue - a.issue;
      });
      return rows;
    }

    function render() {
      var rows = filtered();
      var shown = rows.slice(0, state.page * state.per);
      host.innerHTML = shown.length
        ? shown
            .map(function (it) {
              return itemCard(it, state.q, { showIssue: true });
            })
            .join("")
        : '<div class="empty">' +
          icon("search") +
          "<h3>没有找到匹配的内容</h3><p>当前库内共 " +
          pool.length +
          " 条记录。可尝试更短的关键词，例如“青年”“共青团”“条例”。</p>" +
          '<button class="btn btn-outline" id="gsReset">清除筛选</button></div>';

      countEl.innerHTML = state.q
        ? "关键词 “<b>" + esc(state.q) + "</b>” 命中 <b>" + rows.length + "</b> 条"
        : "全库共 <b>" + rows.length + "</b> 条";

      var rest = rows.length - shown.length;
      moreBtn.hidden = rest <= 0;
      moreBtn.innerHTML = "加载更多（还有 " + rest + " 条）" + icon("chevron-down");

      var reset = $("#gsReset");
      if (reset) {
        reset.onclick = function () {
          if (input) input.value = "";
          state.q = "";
          state.cat = "";
          syncChips();
          render();
        };
      }
      initReveal(host);
    }

    function syncChips() {
      $$(".chip", catRow).forEach(function (b) {
        b.setAttribute("aria-pressed", b.getAttribute("data-cat") === state.cat ? "true" : "false");
      });
    }

    if (input) {
      input.value = state.q;
      input.focus();
      var box = input.closest(".search-box");
      if (box) box.classList.toggle("has-value", !!state.q);
      var timer = null;
      input.addEventListener("input", function () {
        var b2 = input.closest(".search-box");
        if (b2) b2.classList.toggle("has-value", !!input.value);
        clearTimeout(timer);
        timer = setTimeout(function () {
          state.q = input.value.trim();
          state.page = 1;
          render();
        }, 120);
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        if (input) input.value = "";
        state.q = "";
        state.page = 1;
        var box = input && input.closest(".search-box");
        if (box) box.classList.remove("has-value");
        render();
        if (input) input.focus();
      });
    }
    catRow.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".chip");
      if (!btn) return;
      state.cat = btn.getAttribute("data-cat") || "";
      state.page = 1;
      syncChips();
      render();
    });
    if (sortSel) {
      sortSel.addEventListener("change", function () {
        state.sort = sortSel.value;
        render();
      });
    }
    moreBtn.addEventListener("click", function () {
      state.page++;
      render();
    });

    // 热门关键词
    var hot = $("#gsHot");
    if (hot) {
      var hotList = (DB.stats || {}).topKeywords || [];
      // 关键词为空时把整块藏起来，避免出现空白的“热门关键词”标题
      var hotWrap = hot.parentElement;
      if (hotWrap) hotWrap.hidden = hotList.length === 0;
      hot.innerHTML = hotList
        .slice(0, 14)
        .map(function (p) {
          return (
            '<button class="chip" data-q="' +
            esc(p[0]) +
            '">' +
            esc(p[0]) +
            '<span class="n">' +
            p[1] +
            "</span></button>"
          );
        })
        .join("");
      hot.addEventListener("click", function (ev) {
        var b = ev.target.closest(".chip");
        if (!b) return;
        var q = b.getAttribute("data-q");
        if (input) input.value = q;
        state.q = q;
        state.page = 1;
        var box = input && input.closest(".search-box");
        if (box) box.classList.add("has-value");
        render();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }

    render();
  }

  /* ---------------- 页面：关于 ---------------- */
  function pageAbout() {
    var host = $("#qualityBody");
    if (!host) return;
    var q = (DB.quality || { problems: [] }).problems || [];
    host.innerHTML = q.length
      ? q
          .map(function (p) {
            return (
              "<tr>" +
              '<td><span class="tag ' +
              (p.severe ? "tag-amber" : "tag-navy") +
              '">' +
              esc(p.kind) +
              "</span></td>" +
              "<td>" +
              esc(p.label) +
              "</td>" +
              "<td>" +
              esc(p.date || "—") +
              "</td>" +
              '<td style="font-family:var(--font-mono);font-size:12.5px">' +
              esc(p.file) +
              "</td>" +
              "<td>" +
              esc(p.detail) +
              "</td>" +
              "</tr>"
            );
          })
          .join("")
      : '<tr><td colspan="5" style="text-align:center;padding:34px">未发现期号问题</td></tr>';
  }

  /* ---------------- 问答窗口（库内检索问答） ----------------
     纯静态站无法运行大模型，因此这里做的是“检索式问答”：
     把问题拆成关键词 → 在站内已收录的全部资料里检索 → 按相关度排序 → 给出原文与出处。
     答案只来自库内数据，不联网、不编造；查不到就如实说明查不到。
  */
  var QA = {
    STOP: ("的 了 是 有 和 与 及 在 对 从 到 为 以 把 被 这 那 什么 哪些 如何 怎么 怎样 请问 关于 " +
           "重要 论述 讲话 精神 指出 强调 要求 我们 你们 他们 一个 进行 开展 以及 并且 而且 " +
           "a an the of and or to in on for is are what how").split(/\s+/),

    /** 把问题切成关键词
     *  先剥掉疑问语气与助词，再补 3/4 字片段。
     *  不用 2 字片段：实测会产生“记关”“人的”这类噪音，把无关长文排到前面。
     */
    keywords: function (q) {
      var raw = String(q || "")
        .replace(/[？?！!。，,、；;：:“”"'（）()《》〈〉\[\]【】\s]+/g, " ")
        .trim();
      if (!raw) return [];
      var base = [];
      raw.split(/\s+/).forEach(function (p) {
        // 去掉疑问词、助词、以及“总书记关于…的重要论述”这类套话
        p = p
          .replace(/^(请问|请|我想问|想问)/, "")
          .replace(/(有哪些|是什么|怎么样|怎么办|怎么|如何|哪些|什么|关于|对于|的重要论述|重要论述|的论述|论述|讲话|精神)$/g, "")
          .replace(/^(总书记|习近平总书记|习近平)/, "")
          .replace(/[的了呢吗]/g, "");
        if (!p || p.length < 2) return;
        if (QA.STOP.indexOf(p) !== -1) return;
        base.push(p);
      });
      var extra = [];
      base.forEach(function (w) {
        if (/^[\u4e00-\u9fff]+$/.test(w) && w.length >= 3) {
          for (var len = 3; len <= 4; len++) {
            for (var i = 0; i + len <= w.length; i++) extra.push(w.substr(i, len));
          }
        }
      });
      return base.concat(extra).filter(function (v, i, a) {
        return a.indexOf(v) === i;
      });
    },

    /** 组装可检索的资料全集 */
    corpus: function () {
      var docs = [];
      (DB.leaders || []).forEach(function (r) {
        docs.push({
          text: r.quote, kind: "领导人论述",
          title: r.leader + "　" + (r.occasion || ""),
          meta: [r.leader, r.time, r.occasion].filter(Boolean).join(" · "),
          hay: [r.leader, r.time, r.occasion, r.nature, r.quote].join(" ").toLowerCase()
        });
      });
      ((DB.xiQuotes || {}).parts || []).forEach(function (p) {
        (p.topics || []).forEach(function (t) {
          (t.quotes || []).forEach(function (q) {
            docs.push({
              text: q.text, kind: "青春寄语", title: t.title || "寄语", meta: q.cite || "",
              hay: [q.text, q.cite, t.title].join(" ").toLowerCase()
            });
          });
        });
      });
      ((DB.xiArticles || {}).items || []).forEach(function (a) {
        var body = flat(a.body || "");
        docs.push({
          text: body.slice(0, 420), kind: "重要文章", title: a.title, meta: a.dateISO || "",
          hay: [a.title, body].join(" ").toLowerCase()
        });
      });
      allItems().forEach(function (it) {
        docs.push({
          text: it.summary || it.summaryShort || "", kind: "数据库条目", title: it.title,
          meta: [it.issueLabel, it.source, it.pubdate].filter(Boolean).join(" · "),
          hay: [it.title, it.summary, (it.keywords || []).join(" "), it.source].join(" ").toLowerCase()
        });
      });
      (((DB.awards || {}).items) || []).forEach(function (a) {
        docs.push({
          text: "课题名称：" + a.title + "　负责人：" + (a.owner || "—"),
          kind: "课题", title: a.title, meta: "特别贡献奖 · 序号 " + a.no,
          hay: [a.title, a.owner, "课题"].join(" ").toLowerCase()
        });
      });
      return docs.filter(function (d) {
        return d.text && d.text.length > 4;
      });
    },

    /** 检索并打分
     *  用 IDF 加权：越少见的词权重越高，这样“立德树人”比“青年”更能左右排序。
     *  否则任何含“青年”的长文都会压过真正切题的内容。
     */
    search: function (question, limit) {
      var kws = QA.keywords(question);
      if (!kws.length) return { kws: [], hits: [] };
      var docs = QA.corpus();

      // 先算每个关键词的文档频率，得到 IDF
      var df = {};
      kws.forEach(function (k) {
        var n = 0;
        docs.forEach(function (d) {
          if (d.hay.indexOf(k) !== -1) n++;
        });
        df[k] = n;
      });
      var total = docs.length;
      function idf(k) {
        return Math.log(1 + total / (1 + df[k]));
      }

      var hits = [];
      docs.forEach(function (d) {
        var score = 0, matched = 0, weightSum = 0;
        kws.forEach(function (k) {
          var n = d.hay.split(k).length - 1;
          if (n > 0) {
            matched++;
            var w = idf(k);
            weightSum += w;
            score += Math.min(n, 3) * w;
            // 命中标题额外加权：标题切题度最高
            if (d.title.toLowerCase().indexOf(k) !== -1) score += w * 2.5;
          }
        });
        if (matched > 0) {
          // 命中的“权重种类”越多越相关
          score += matched * 1.5 + weightSum;
          // 轻微偏好短文本（更聚焦），但不要过度惩罚长文
          score = score / (1 + Math.log(1 + d.text.length / 400));
          hits.push({ doc: d, score: score, matched: matched });
        }
      });
      hits.sort(function (a, b) {
        return b.score - a.score || b.matched - a.matched;
      });
      return { kws: kws, hits: hits.slice(0, limit || 5) };
    }
  };

  function pageQA() {
    var input = $("#qaInput");
    var host = $("#qaAnswer");
    if (!input || !host) return;

    var examples = $("#qaExamples");
    var askBtn = $("#qaAsk");
    var clearBtn = $("#qaClear");
    var box = input.closest(".search-box");

    function render(question) {
      var q = String(question || "").trim();
      if (!q) {
        host.hidden = true;
        host.innerHTML = "";
        return;
      }
      var res = QA.search(q, 5);
      host.hidden = false;

      if (!res.hits.length) {
        host.innerHTML =
          '<div class="qa-empty">在库内没有检索到与「' + esc(q) + "」直接相关的资料。<br>" +
          "可以换个说法，或试试上面推荐的问题。</div>";
        return;
      }

      var kwForMark = res.kws.filter(function (k) {
        return k.length >= 2;
      }).join(" ");

      var hits = res.hits
        .map(function (h) {
          var d = h.doc;
          var body = d.text.length > 320 ? d.text.slice(0, 320) + "……" : d.text;
          return (
            '<div class="qa-hit"><p>' + highlight(body, kwForMark) + "</p>" +
            '<div class="qa-hit-cite">' +
            "<span>" + icon("book") + esc(d.kind) + "</span>" +
            "<span>" + icon("source") + esc(d.title) + "</span>" +
            (d.meta ? "<span>" + icon("calendar") + esc(d.meta) + "</span>" : "") +
            "</div></div>"
          );
        })
        .join("");

      var first = res.hits[0].doc;
      host.innerHTML =
        '<div class="qa-answer-head">' + icon("info") +
        "<span>根据库内资料，与「<b>" + esc(q) + "</b>」最相关的是 <b>" + res.hits.length + "</b> 条，" +
        "首条出自" + esc(first.kind) + "《" + esc(first.title) + "》</span></div>" +
        hits +
        '<div class="qa-answer-head" style="margin-top:18px;margin-bottom:0">' + icon("alert") +
        "<span>说明：本站是静态资料库，此窗口在已收录资料中检索原文并给出出处，" +
        "不接入大模型、不联网、不做改写。需要完整上下文请查看对应页面或原文链接。</span></div>";
    }

    askBtn.addEventListener("click", function () {
      render(input.value);
    });
    input.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        render(input.value);
      }
    });
    input.addEventListener("input", function () {
      if (box) box.classList.toggle("has-value", !!input.value);
    });
    clearBtn.addEventListener("click", function () {
      input.value = "";
      if (box) box.classList.remove("has-value");
      host.hidden = true;
      host.innerHTML = "";
      input.focus();
    });
    if (examples) {
      examples.addEventListener("click", function (ev) {
        var b = ev.target.closest(".chip");
        if (!b) return;
        input.value = b.getAttribute("data-q") || b.textContent;
        if (box) box.classList.add("has-value");
        render(input.value);
      });
    }
  }

  /** 折叠面板（全站通用）
   *  注意：必须注册在 boot 里，不能放在某个页面的函数内。
   *  之前它被写在 pageLeaders() 里，而该函数在非论述库页面会提前 return，
   *  导致 awards.html 的课题简介点了打不开。
   */
  function initAccordions() {
    document.addEventListener("click", function (ev) {
      var head = ev.target.closest(".acc-head");
      if (!head) return;
      var body = head.nextElementSibling;
      var open = head.getAttribute("aria-expanded") === "true";
      head.setAttribute("aria-expanded", open ? "false" : "true");
      if (body) body.hidden = open;
    });
  }

  /* ---------------- 启动 ---------------- */
  function boot() {
    initNav();
    initAccordions();
    fillStats();
    fillYear();
    fillCount();
    pageHome();
    pageDatabase();
    pageIssue();
    pageLeaders();
    pageSearch();
    pageAbout();
    pageQA();
    initReveal(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  // 暴露给调试使用
  window.DSH = {
    DB: DB,
    getIssue: getIssue,
    allItems: allItems,
    icon: icon,
    esc: esc,
    // 问答检索逻辑对外暴露，便于 tools/verify-qa.js 直接做自检
    QA: QA
  };
})();
