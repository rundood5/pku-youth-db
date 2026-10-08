# -*- coding: utf-8 -*-
"""
重要讲话与最新提法数据库 —— 数据提取脚本

把 source/ 目录下的 Word 文件解析成网站唯一数据源 site/data/content.json。

数据模型（目录级 + 单期摘要）：
  {
    "site":    站点元信息 / 页脚友情链接,
    "stats":   首页统计数字,
    "issues":  每期一条记录（数据库主表）+ 该期条目摘要（详情页用）,
    "leaders": 历届党和国家领导人关于共青团及青年工作重要论述（43 条表格）,
    "articles":习近平总书记重要文章汇总、青春寄语（按篇/主题分组）
  }

用法：
  python extract.py                 # 解析 source/ -> site/data/content.json
  python extract.py --check         # 只做自检，不写文件
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from datetime import date

from docx import Document
from docx.oxml.ns import qn

# --------------------------------------------------------------------------
# 路径
# --------------------------------------------------------------------------
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS_DIR)
SOURCE_DIR = os.path.join(ROOT, "source")
OUT_FILE = os.path.join(ROOT, "site", "data", "content.json")

ISSUE_DIR = os.path.join(SOURCE_DIR, "2.北大青年纵横", "主文件")
FILTER_FILE = os.path.join(TOOLS_DIR, "filter-list.txt")
AWARD_XLSX = os.path.join(SOURCE_DIR, "特别贡献奖", "特别贡献奖", "特别贡献奖申报", "理论研究室.xlsx")
LEADER_DOC = os.path.join(
    SOURCE_DIR,
    "1.党和国家领导人关于共青团及青年工作重要论述",
    "3历届党和国家领导人关于共青团及青年工作重要论述.docx",
)
XI_DIR = os.path.join(
    SOURCE_DIR, "1.党和国家领导人关于共青团及青年工作重要论述", "习近平总书记"
)

# 字段标签 -> 键名
FIELD_LABELS = {
    "标题": "title",
    "发布时间": "pubdate",
    "发布来源": "source",
    "文章来源": "source",
    "会议来源": "meeting",
    "原文链接": "url",
    "关键词": "keywords",
    "观点速览": "summary",
}

CN_NUM = "一二三四五六七八九十"

# 大分类：用于 database.html 的分类 chips
CATEGORY_RULES = [
    ("习近平", ("习近平总书记", "习近平")),
    ("共青团与青年", ("共青团", "青年", "团中央", "少先队")),
    ("党中央国务院", ("中共中央", "国务院", "中办", "国办", "中央纪委", "全国人大", "全国政协")),
    ("政策文件", ("政策文件", "国务院公报", "政策解读", "部委", "通知", "指导意见", "条例", "办法", "规划")),
    ("党报党刊", ("人民日报", "求是", "光明日报", "经济日报")),
    ("权威发布", ("新华社", "中国政府网", "新华网", "人民网")),
]


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def norm(text: str) -> str:
    """把 Word 里的软换行、不间断空格统一掉，便于检索与匹配。"""
    if not text:
        return ""
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = text.replace("\u2028", "\n").replace("\v", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def body_blocks(doc: Document):
    """按文档真实顺序产出 ('p', text) / ('t', table)。"""
    paras = doc.paragraphs
    tables = doc.tables
    pi = ti = 0
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            if pi < len(paras):
                text = norm(paras[pi].text)
                pi += 1
                if text:
                    yield ("p", text)
        elif child.tag == qn("w:tbl"):
            if ti < len(tables):
                yield ("t", tables[ti])
                ti += 1


def table_text(table) -> str:
    return norm("\n".join(c.text for row in table.rows for c in row.cells))


def parse_date(text: str) -> str:
    """从任意文本里抽出日期，返回可排序的 ISO 串。

    支持到"日"的精度时返回 YYYY-MM-DD；只有年到月返回 YYYY-MM；只有年返回 YYYY。
    若文本里没有任何 20 世纪/21 世纪年份，返回空串。
    """
    if not text:
        return ""
    m = re.search(r"(1[89]\d{2}|20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(1[89]\d{2}|20\d{2})\s*年\s*(\d{1,2})\s*月", text)
    if m:
        return "%s-%02d" % (m.group(1), int(m.group(2)))
    m = re.search(r"(1[89]\d{2}|20\d{2})", text)
    if m:
        return m.group(1)
    return ""


def cn_to_int(token: str):
    """把 一/二/…/二十 这类中文数字转成 int；失败返回 None。"""
    token = token.strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token == "十":
        return 10
    if token.startswith("十"):
        rest = token[1:]
        return 10 + (CN_NUM.index(rest) + 1 if rest in CN_NUM else 0)
    if "十" in token:
        a, _, b = token.partition("十")
        tens = CN_NUM.index(a) + 1 if a in CN_NUM else 1
        ones = CN_NUM.index(b) + 1 if b in CN_NUM else 0
        return tens * 10 + ones
    if token in CN_NUM:
        return CN_NUM.index(token) + 1
    return None


def cut_summary(text: str, limit: int = 320) -> str:
    """观点速览做摘要化，保留完整句子以免读起来断裂。"""
    text = norm(text)
    if len(text) <= limit:
        return text
    window = text[: limit + 60]
    for mark in ("。", "；", "！", "？"):
        idx = window.rfind(mark)
        if idx >= limit * 0.6:
            return text[: idx + 1]
    return text[:limit] + "……"


def tidy_paragraph(text: str) -> str:
    """修掉 Word 里常见的排版残留：中文后多余空格、"好3." 这类断行粘连。"""
    if not text:
        return ""
    # 中文/标点 与 数字 之间被换行截断时补一个空格或直接读通：这里统一加空格更自然
    text = re.sub(r"([\u4e00-\u9fff；。，、）])(\d+[.．、])", r"\1 \2", text)
    # 中文字符之间多余的空格（Word 里常因加粗/换行产生）
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    # 全角/半角冒号前多余空格
    text = re.sub(r"\s+([：；。，、）])", r"\1", text)
    return text.strip()


def guess_category(*texts) -> str:
    blob = " ".join(texts)
    for label, keys in CATEGORY_RULES:
        for k in keys:
            if k in blob:
                return label
    return "其他"


# --------------------------------------------------------------------------
# 解析：重要讲话与最新提法数据库（当期）
# --------------------------------------------------------------------------
SECTION_RE = re.compile(r"^\s*([%s]+)\s*[、.．]\s*(.+?)\s*$" % CN_NUM)
SUB_RE = re.compile(r"^\s*[（(]\s*([%s]+)\s*[)）]\s*(.*?)\s*$" % CN_NUM)


def split_section_title(raw: str):
    """'一、政策文件' -> (1, '政策文件')；不匹配返回 (None, raw)。"""
    m = SECTION_RE.match(raw)
    if not m:
        return None, raw
    num = cn_to_int(m.group(1))
    title = m.group(2).strip()
    if num is None or len(raw) > 40:
        return None, raw
    return num, title


def load_relevance_rules(path: str) -> dict:
    """读取 filter-list.txt 的收录规则。

    返回 {"enabled": bool, "include": [...], "exclude": [...]}。
    默认 enabled = False，即不做过筛、保留全部内容；
    只有显式写 enabled = yes 才启用白名单过滤。这样能避免规则文件缺失或写坏
    导致数据库被意外清空。
    """
    rules = {"enabled": False, "include": [], "exclude": []}
    if not os.path.isfile(path):
        return rules
    section = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("[") and s.endswith("]"):
                key = s[1:-1].strip().lower()
                section = key if key in ("include", "exclude", "options") else None
                continue
            if section == "options":
                if s.lower().replace(" ", "").startswith("enabled="):
                    val = s.split("=", 1)[1].strip().lower()
                    rules["enabled"] = val in ("yes", "true", "on", "1")
                continue
            if section in ("include", "exclude"):
                rules[section].append(s.lower())
    return rules


def is_relevant(title: str, summary: str, rules: dict) -> bool:
    """判断条目是否收录。

    过滤未启用（默认）时一律收录，即“保留原样”；
    启用后按 [include] 白名单收录、[exclude] 例外剔除。
    """
    if not rules.get("enabled"):
        return True
    inc, exc = rules["include"], rules["exclude"]
    if not inc:
        return True
    hay = ("%s %s" % (title or "", summary or "")).lower()
    if any(k in hay for k in exc):
        return False
    return any(k in hay for k in inc)


# 课题简介生成规则：源数据只有“序号/题目/负责人”，没有摘要字段，
# 因此按题目关键词归纳研究方向，生成一句简要介绍（不是原文摘要，勿当作内容概述引用）。
AWARD_THEME_RULES = [
    ("青年理想信念", "围绕青年理想信念教育展开，研究其常态化、制度化建设的路径与机制。"),
    ("理想信念", "聚焦青年理想信念教育，探讨如何把教育要求落到日常、形成长效机制。"),
    ("国际青年", "比较研究国际青年发展与人文交流，为青年外事与青年发展政策提供参照。"),
    ("青年发展", "以青年发展政策为对象，梳理政策供给与青年需求之间的匹配关系与改进方向。"),
    ("生育", "关注当代青年家庭与生育观念的变化趋势，分析其成因及对青年政策的影响。"),
    ("消费", "研究当代青年消费行为与圈层文化消费特征，为引导青年理性消费提供依据。"),
    ("文旅", "考察青年文旅消费的行为特征与趋势，提出面向青年群体的服务优化建议。"),
    ("价值观", "分析青年价值观的生成机理，探讨更具针对性的培育策略。"),
    ("志愿服务", "研究志愿服务对青年政治认同的影响，评估志愿育人的实际成效。"),
    ("养老", "从银发经济视角观察青年养老观念的变化，讨论青年责任与制度衔接。"),
    ("基层团组织", "以基层团组织为切入点，研究共青团动员青年参与乡村振兴的实践机制。"),
    ("乡村振兴", "研究青年助力乡村振兴的路径与成效，总结可复制的实践经验。"),
    ("红色资源", "探讨高校红色资源融入思想政治教育的应用方式与实际效果。"),
    ("共青团", "聚焦高校共青团工作，研究其高质量发展的机理、困境与优化路径。"),
    ("网络思政", "研究全媒体环境下高校共青团网络思政引领的创新机制。"),
    ("思政", "围绕高校思想政治教育，研究育人体系构建与实效提升的路径。"),
    ("实习", "研究大学生实习见习的行为模式与长效机制，分析其对成长成才的影响。"),
    ("心理健康", "研究家庭、学校、社会协同育人对学生心理健康的作用机制。"),
    ("学生权益", "关注学生权益意识与校园服务保障，提出改进校园治理的建议。"),
    ("学生社团", "研究公益类学生社团的实践模式与发展策略，总结社团育人经验。"),
    ("理论宣讲", "评估青年理论宣讲组织的成效，探讨提升宣讲感染力的创新路径。"),
    ("榜样", "研究青年榜样宣传教育的范式转变，探讨如何实现价值共鸣。"),
    ("文化遗产", "研究校园文化遗产的创造性转化及其育人机制。"),
    ("口述史", "以口述史方法记录重大志愿活动，梳理志愿精神的传承脉络。"),
    ("留学生", "面向高校留学生群体，研究阐释中国道路与中国理论的路径与机制。"),
    ("自媒体", "考察平台自媒体人的群体特征，分析其对青年认知的影响。"),
    ("教育振兴", "研究高校青年助力县域教育振兴的路径与实际成效。"),
    ("教师培训", "从教师培训切入，探讨教育帮扶由“输血”转向“造血”的机制。"),
    ("在线学习", "研究智媒环境下青年学生的学习行为模式及其对网络育人的启示。"),
    ("国际传播", "研究中国青年国际传播能力的结构特征与现实困境。"),
    ("外交", "分析青年群体国际关系取向的形成因素，为青年外事工作提供参考。"),
    ("戏曲", "以戏曲遗产保护为例，研究传统文化的当代传承与经验再造。"),
    ("绿色循环", "以快递包装循环为例，研究青年参与绿色低碳实践的可行路径。"),
]


def award_intro(title: str) -> str:
    """按题目关键词生成一句简要介绍。"""
    for key, text in AWARD_THEME_RULES:
        if key in title:
            return text
    return "本课题为该批次特别贡献奖立项课题，研究方向见课题名称。"


def award_files(no: int, title: str, base_dir: str) -> list:
    """定位该课题序号对应的申报材料，返回可下载的文件列表。

    源目录里每个课题有两类文件：作品提交、附件一。文件名形如
    “28特贡+李思诺+作品提交.pdf”。这里按序号前缀匹配，返回
    site/awards.html 可用的相对路径（../source/...）并做 URL 编码。
    """
    if not os.path.isdir(base_dir):
        return []
    out = []
    for name in sorted(os.listdir(base_dir)):
        if name.startswith("._") or not re.match(r"^%d特贡" % no, name):
            continue
        if name.lower().endswith((".pdf", ".docx", ".doc")):
            kind = "作品提交" if "作品提交" in name else ("附件一" if "附件一" in name else "材料")
            rel = "../source/" + os.path.relpath(
                os.path.join(base_dir, name), SOURCE_DIR).replace("\\", "/")
            out.append({"name": "%s（%s）" % (kind, os.path.splitext(name)[1].lstrip(".").upper()),
                        "path": urllib.parse.quote(rel)})
    return out


def load_summaries() -> dict:
    """读取 tools/summaries.json（由 tools/extract_summaries.py 从源文件提取的摘要）。

    返回 {序号字符串: 摘要文本}。文件不存在时返回空字典，
    此时课题简介会退回按题目关键词自动生成。
    """
    path = os.path.join(TOOLS_DIR, "summaries.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for k, v in (raw or {}).items():
        if isinstance(v, dict):
            s = (v.get("summary") or "").strip()
            if s:
                out[str(k)] = s
    return out


def load_award_projects(path: str) -> dict:
    """读取「特别贡献奖」理论研究室课题清单（xlsx）。

    版式：第 1 行是部门名，第 2 行是表头（序号/作品题目/负责人），其后为数据行。
    """
    if not os.path.isfile(path):
        return {"title": "共青团与青年工作课题", "items": [], "source": ""}
    try:
        import openpyxl
    except ImportError:
        return {"title": "共青团与青年工作课题", "items": [], "source": "（缺少 openpyxl，未能解析）"}

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    items = []
    for row in ws.iter_rows(values_only=True):
        cells = ["" if c is None else str(c).strip() for c in row]
        if len(cells) < 3:
            continue
        no, title, owner = cells[0], cells[1], cells[2]
        # 跳过表头与说明行
        if no in ("序号", "") and title in ("作品题目", ""):
            continue
        if not title or title in ("作品题目",):
            continue
        if not no.isdigit():
            continue
        items.append({"no": int(no), "title": title, "owner": owner})
    items.sort(key=lambda x: x["no"])
    # 为每项课题补上简介与可下载材料。
    # 申报材料放在 xlsx 同级的“理论研究室”子目录里（文件名形如 28特贡+姓名+作品提交.pdf）。
    xlsx_dir = os.path.dirname(path)
    file_dir = os.path.join(xlsx_dir, "理论研究室")
    if not os.path.isdir(file_dir):
        file_dir = xlsx_dir  # 兜底：结构若是平铺的也能找到
    # 优先用从源文件提取的真实摘要；没有则退回按题目生成的介绍
    summaries = load_summaries()
    real = 0
    for it in items:
        s = summaries.get(str(it["no"]))
        if s:
            it["intro"] = s
            it["introSource"] = "source"      # 来自源文件
            real += 1
        else:
            it["intro"] = award_intro(it["title"])
            it["introSource"] = "generated"   # 按题目关键词生成
        it["files"] = award_files(it["no"], it["title"], file_dir)
    with_files = sum(1 for it in items if it["files"])
    return {
        "title": "共青团与青年工作课题",
        "subtitle": "北京大学“挑战杯”系列赛事·特别贡献奖（校团委理论研究室）",
        "items": items,
        "withFiles": with_files,
        "realIntros": real,
        "source": os.path.relpath(path, SOURCE_DIR).replace("\\", "/"),
    }


def parse_issue(path: str) -> dict:
    doc = Document(path)
    blocks = list(body_blocks(doc))
    file_issue = None
    _m = re.search(r"总第\s*(\d+)\s*期", os.path.basename(path))
    if _m:
        file_issue = int(_m.group(1))

    title = "重要讲话与最新提法数据库"
    issue_no = None
    issue_date = ""
    overview = []
    footer_meta = []
    entries = []
    sections = []

    if blocks and blocks[0][0] == "p":
        title = blocks[0][1] or title

    # ---- 报文头（表格） ----
    for kind, payload in blocks:
        if kind != "t":
            continue
        raw = table_text(payload)
        if "总第" in raw:
            m = re.search(r"总第\s*(\d+)\s*期", raw)
            if m:
                issue_no = int(m.group(1))
            # 报头日期可能是 "2026年X月X日" 占位符，此时留空由条目日期兜底
            head_date = raw.split("总第")[0]
            issue_date = parse_date(head_date) if "X" not in head_date and "x" not in head_date else ""
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("概览"):
                    rest = line.split("：", 1)[-1].strip()
                    if rest:
                        overview.append(rest)
                elif re.match(r"^\d+\s*[.．、]", line):
                    overview.append(re.sub(r"^\d+\s*[.．、]\s*", "", line))
        elif "审核" in raw or "编辑" in raw or "主编" in raw:
            footer_meta = [l.strip() for l in raw.split("\n") if l.strip()]
        break

    # ---- 正文：章节 -> 条目 ----
    current = None  # 当前条目
    current_section = None

    def flush():
        nonlocal current
        if current and (current.get("title") or current.get("summary")):
            entries.append(current)
        current = None

    started = False
    for kind, payload in blocks:
        if kind == "t":
            continue
        text = payload
        if not started:
            if text == title:
                started = True
                continue
            if text.startswith("重要讲话与最新提法数据库"):
                started = True
                continue

        num, sec_title = split_section_title(text)
        if num is not None and "：" not in text:
            flush()
            current_section = sec_title
            sections.append({"no": num, "title": sec_title})
            continue

        msub = SUB_RE.match(text)
        if msub and "：" not in text:
            flush()
            current_section = msub.group(2).strip() or current_section
            continue

        if text.startswith("标题："):
            flush()
            current = {"section": current_section, "title": text.split("：", 1)[1].strip()}
            continue

        key = None
        for label, field in FIELD_LABELS.items():
            if text.startswith(label + "：") or text == label + "：":
                key = (label, field)
                break
        if key:
            label, field = key
            value = text.split("：", 1)[1].strip() if "：" in text else ""
            if current is None:
                current = {"section": current_section, "title": ""}
            if field == "url" and not value:
                current["_want_url"] = True
                continue
            if field == "title" and not current.get("title"):
                current["title"] = value
            else:
                current[field] = value
            continue

        # 续行：链接或上一字段的接续文本
        if current is not None:
            if current.pop("_want_url", False):
                current["url"] = text
            elif current.get("summary"):
                current["summary"] = (current["summary"] + text)
            elif current.get("url") and text.startswith("http"):
                current["url"] = text
    flush()

    # ---- 条目后处理 ----
    for e in entries:
        e.pop("_want_url", None)
        for k in ("title", "pubdate", "source", "url", "keywords", "summary", "meeting"):
            if k in e:
                e[k] = norm(e[k])
        e["pubdate"] = e.get("pubdate", "")
        e["pubISO"] = parse_date(e.get("pubdate", ""))
        e["keywords"] = [k.strip() for k in re.split(r"[；;，,]", e.get("keywords", "")) if k.strip()]
        e["summary"] = tidy_paragraph(norm(e.get("summary", "")))
        e["summaryShort"] = cut_summary(e["summary"])
        e["category"] = guess_category(
            e.get("section") or "", e.get("title") or "", e.get("keywords") and "；".join(e["keywords"]) or ""
        )
        if not e.get("title"):
            e["title"] = e["summaryShort"][:40] or "（未命名条目）"

    # 概览兜底：用条目标题生成
    if not overview:
        overview = [e["title"] for e in entries[:5]]

    # ---- 期号核对：报头 vs 文件名 ----
    # 源文件中两者并不总是一致，因此两者都记录，把差异交给页面显示，而不是悄悄改成一致。
    # 区分严重程度很重要，否则 16 张卡片都会挂上警告：
    #   needsReview = True  -> 真正的数据缺陷（占位符、日期占位符），页面上打标记
    #   needsReview = False -> 文件名与报头期号相差 1 这类系统性偏差，只在数据质量页列出
    notes = []
    needs_review = False
    if issue_no is None:
        issue_no = file_issue
        if file_issue is not None:
            notes.append("报头期号为占位符“总第X期”，已采用文件名期号")
            needs_review = True
    elif file_issue is not None and file_issue != issue_no:
        notes.append("报头期号（总第%d期）与文件名（总第%d期）不一致" % (issue_no, file_issue))
        needs_review = False

    if issue_date:
        y = re.match(r"^(\d{4})", issue_date)
        if y and int(y.group(1)) > date.today().year:
            notes.append("报头日期为占位符（%s），已采用条目日期" % issue_date)
            issue_date = ""
            needs_review = True

    date_for_sort = issue_date
    if not date_for_sort:
        for e in entries:
            if e.get("pubISO"):
                date_for_sort = e["pubISO"]
                break

    return {
        "issue": issue_no or 0,
        "fileIssue": file_issue,
        "label": "总第%d期" % issue_no if issue_no else "期号待补",
        "date": date_for_sort,
        "dateText": issue_date,
        "title": title,
        "overview": overview,
        "sections": sections,
        "footer": footer_meta,
        "entries": entries,
        "entryCount": len(entries),
        "sources": sorted({e.get("source", "") for e in entries if e.get("source")}),
        "keywords": sorted({k for e in entries for k in e.get("keywords", [])}),
        "categories": sorted({e.get("category", "") for e in entries if e.get("category")}),
        "notes": notes,
        "needsReview": needs_review,
        "docx": os.path.relpath(path, SOURCE_DIR).replace("\\", "/"),
    }


# --------------------------------------------------------------------------
# 解析：历届党和国家领导人关于共青团及青年工作重要论述（表格）
# --------------------------------------------------------------------------
def parse_leaders(path: str) -> list:
    """读取"历届党和国家领导人"表格。

    直接按 XML 行遍历：python-docx 的 row.cells 在合并单元格时会重复计数，
    用 tc 逐个取可以保证一行一格，避免漏行。
    """
    doc = Document(path)
    if not doc.tables:
        return []
    table = doc.tables[0]
    rows = []
    last_leader = ""
    for tr in table._tbl.tr_lst:
        cells = []
        for tc in tr.tc_lst:
            text = norm("".join(node.text or "" for node in tc.iter(qn("w:t"))))
            cells.append(text)
        if not any(cells):
            continue
        joined = " ".join(cells)
        if not rows and ("领导人" in cells[0] or "对应原句" in joined):
            continue
        if len(cells) < 5:
            cells += [""] * (5 - len(cells))
        leader, when, occasion, nature, quote = cells[:5]
        if not leader and not when and not occasion:
            continue
        # 同一领导人的多行在 Word 中是纵向合并单元格：续行 leader 为空，需要向下填充
        if leader:
            last_leader = leader
        else:
            leader = last_leader
        rows.append(
            {
                "leader": leader,
                "time": when,
                "timeISO": parse_date(when),
                "occasion": tidy_paragraph(occasion),
                "nature": tidy_paragraph(nature),
                "quote": tidy_paragraph(quote),
            }
        )
    rows.sort(key=lambda r: (r["timeISO"] or "9999", r["leader"]))
    return rows


def parse_xi_articles(path: str) -> dict:
    """习近平总书记关于共青团与青年工作重要文章汇总。

    版式：封面标题若干行 -> [文章标题行, 日期行(2013年05月04日), 正文...] 循环。
    因此先定位全部日期行，再把每个日期行之前最近的一行作为文章标题。
    """
    doc = Document(path)
    paras = [norm(p.text) for p in doc.paragraphs if norm(p.text)]
    if not paras:
        return {"title": os.path.basename(path), "items": []}

    date_line_re = re.compile(r"^(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(.*)$")
    marks = [i for i, t in enumerate(paras) if date_line_re.match(t)]
    if not marks:
        return {"title": paras[0], "items": []}

    items = []
    for order, idx in enumerate(marks):
        m = date_line_re.match(paras[idx])
        raw_title = paras[idx - 1] if idx > 0 else ""
        # 标题行可能是破折号开头的引题（如 "——同团中央新一届领导班子成员集体谈话"），
        # 也可能本身就是日期行或过长段落，这些情况都不作为标题
        title = re.sub(r"^[—–\-]{1,3}\s*", "", raw_title).strip()
        if date_line_re.match(raw_title) or len(raw_title) > 70:
            title = ""
        end = marks[order + 1] - 1 if order + 1 < len(marks) else len(paras)
        body = norm("\n".join(paras[idx + 1 : end]))
        items.append(
            {
                "no": order + 1,
                "title": title or "（标题缺失·以日期代称）",
                "date": paras[idx],
                "dateISO": "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3))),
                "venue": m.group(4).strip(),
                "body": body,
                "chars": len(body),
            }
        )
    return {
        "title": "".join(paras[:4]).strip() or paras[0],
        "source": os.path.relpath(path, SOURCE_DIR).replace("\\", "/"),
        "items": items,
    }


def parse_xi_quotes(path: str) -> dict:
    """习近平总书记对青年的青春寄语。

    版式：“一 寄语篇” -> “一、谈理想：…” -> 若干语录行 + 一行 ——出处。
    一条语录可能由多个段落组成，因此按“出处行”来切分，未带出处的行并入当前语录。
    """
    doc = Document(path)
    paras = [norm(p.text) for p in doc.paragraphs if norm(p.text)]
    if not paras:
        return {"title": os.path.basename(path), "parts": []}

    part_re = re.compile(r"^([%s]+)\s+(\S*?篇)\s*$" % CN_NUM)
    topic_re = re.compile(r"^([%s]+)\s*[、.．]\s*(.+)$" % CN_NUM)

    parts = []
    cur_part = None
    cur_topic = None
    buf = []

    def flush(cite=""):
        nonlocal buf
        if cur_topic is not None and buf:
            text = norm(" ".join(buf))
            if text:
                cur_topic["quotes"].append(
                    {"text": text, "cite": cite, "dateISO": parse_date(cite)}
                )
        buf = []

    for text in paras:
        mp = part_re.match(text)
        if mp:
            flush()
            cur_part = {"title": text, "topics": []}
            parts.append(cur_part)
            cur_topic = None
            continue
        if cur_part is None:
            # 跳过封面标题行，等到第一个“篇”
            continue
        mt = topic_re.match(text)
        if mt and len(text) <= 40 and not text.startswith("——"):
            flush()
            cur_topic = {"title": mt.group(2).strip(), "name": mt.group(2).strip(), "quotes": []}
            if mt.group(1) == "一" and text.startswith("一、") and cur_topic["title"].startswith("寄语"):
                pass
            cur_part["topics"].append(cur_topic)
            continue
        if cur_topic is None:
            continue
        if text.startswith("——") or text.startswith("—"):
            flush(norm(text.lstrip("—－-").strip()))
            continue
        buf.append(text)
    flush()

    for part in parts:
        for topic in part["topics"]:
            for q in topic["quotes"]:
                q["cite"] = q.get("cite", "")
        part["count"] = sum(len(t["quotes"]) for t in part["topics"])
    parts = [p for p in parts if p["count"]]

    return {
        "title": "".join(paras[:2]).strip() or paras[0],
        "source": os.path.relpath(path, SOURCE_DIR).replace("\\", "/"),
        "parts": parts,
    }


# --------------------------------------------------------------------------
# 站点元信息
# --------------------------------------------------------------------------
FOOTER_LINKS = [
    {
        "name": "习近平讲话数据库",
        "url": "http://jhsjk.people.cn/",
        "desc": "人民网·习近平系列重要讲话数据库",
    },
    {
        "name": "人民日报数据库",
        "url": "http://paper.people.com.cn/",
        "desc": "《人民日报》图文数据库",
    },
    {
        "name": "共青团中央",
        "url": "https://www.gqt.org.cn/",
        "desc": "中国共产主义青年团中央委员会",
    },
]


def build_index(issues, leaders, xi_articles, xi_quotes):
    all_entries = [e for it in issues for e in it["entries"]]
    keywords = {}
    for e in all_entries:
        for k in e.get("keywords", []):
            keywords[k] = keywords.get(k, 0) + 1
    sources = {}
    for e in all_entries:
        s = e.get("source") or ""
        if s:
            sources[s] = sources.get(s, 0) + 1
    categories = {}
    for it in issues:
        for e in it["entries"]:
            c = e.get("category") or "其他"
            categories[c] = categories.get(c, 0) + 1
    dates = sorted([it["date"] for it in issues if it.get("date")])
    return {
        "issueCount": len(issues),
        "entryCount": len(all_entries),
        "leaderCount": len(leaders),
        "quoteCount": sum(len(t["quotes"]) for p in xi_quotes.get("parts", []) for t in p["topics"]),
        "xiArticleCount": len(xi_articles.get("items", [])),
        "dateRange": (dates[0], dates[-1]) if dates else ("", ""),
        "issueRange": (
            min([it["issue"] for it in issues] or [0]),
            max([it["issue"] for it in issues] or [0]),
        ),
        "topKeywords": sorted(keywords.items(), key=lambda kv: (-kv[1], kv[0]))[:40],
        "topSources": sorted(sources.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "categories": sorted(categories.items(), key=lambda kv: (-kv[1], kv[0])),
    }


def data_quality(issues) -> dict:
    """检查源文件里的期号问题，生成数据质量报告。

    源文件中确实存在三类状况，都是真实存在的、不能由脚本擅自"修正"的：
      1. 报头期号是 "总第X期" 占位符；
      2. 报头期号与文件名期号不一致（多为差 1）；
      3. 期号重复或跳号。
    脚本只如实记录并把问题交给页面展示与人工确认。
    """
    by_no = {}
    for it in issues:
        by_no.setdefault(it["issue"], []).append(it["docx"])

    problems = []
    for it in issues:
        if it.get("notes"):
            severe = bool(it.get("needsReview"))
            problems.append(
                {
                    "kind": "期号/日期占位符待补" if severe else "报头与文件名期号不一致",
                    "severe": severe,
                    "issue": it["issue"],
                    "label": it["label"],
                    "date": it["date"],
                    "file": it["docx"],
                    "detail": "；".join(it["notes"]),
                }
            )

    dup = []
    for no, files in sorted(by_no.items()):
        if len(files) > 1:
            dup.append({"issue": no, "files": files})
            problems.append(
                {
                    "kind": "期号重复",
                    "severe": True,
                    "issue": no,
                    "label": "总第%d期" % no,
                    "date": "",
                    "file": "、".join(os.path.basename(f) for f in files),
                    "detail": "有 %d 个文件使用同一期号，需要人工确认其中一期的正式期号" % len(files),
                }
            )

    nums = sorted(by_no)
    gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in by_no] if nums else []
    if gaps:
        problems.append(
            {
                "kind": "期号跳号",
                "severe": True,
                "issue": 0,
                "label": "—",
                "date": "",
                "file": "—",
                "detail": "总第 %s 期在数据源中缺少对应文件（可能尚未出版，或报头期号填错）"
                % "、".join(str(g) for g in gaps),
            }
        )

    return {
        "checked": len(issues),
        "problemCount": len(problems),
        "severeCount": sum(1 for p in problems if p.get("severe")),
        "duplicates": dup,
        "gaps": gaps,
        "problems": problems,
        "note": "以上问题来自源 Word 文件的报头/文件名，脚本未做任何自动改写，请在源文件中确认后重新运行 tools/extract.py。",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只自检，不写文件")
    args = ap.parse_args()

    if not os.path.isdir(SOURCE_DIR):
        print("找不到数据源目录：%s" % SOURCE_DIR)
        return 1

    # ---- 20 期 ----
    issues = []
    if os.path.isdir(ISSUE_DIR):
        for name in os.listdir(ISSUE_DIR):
            if not name.lower().endswith(".docx") or name.startswith("~$"):
                continue
            path = os.path.join(ISSUE_DIR, name)
            try:
                issues.append(parse_issue(path))
            except Exception as exc:  # noqa: BLE001
                print("解析失败 %s: %s" % (name, exc))
    issues.sort(key=lambda it: it["issue"])

    # ---- 按相关性过滤（默认关闭，保留原样）----
    rules = load_relevance_rules(FILTER_FILE)
    dropped_entries = 0
    for it in issues:
        # 先记住过滤前的条数，否则后面无从统计剔除了多少
        it["origEntryCount"] = len(it["entries"])
        if rules.get("enabled"):
            kept = []
            for e in it["entries"]:
                if is_relevant(e.get("title", ""), e.get("summaryShort", ""), rules):
                    kept.append(e)
                else:
                    dropped_entries += 1
            it["entries"] = kept
        it["entryCount"] = len(it["entries"])
        it["droppedCount"] = it["origEntryCount"] - it["entryCount"]

    # 条目被全部剔除的期次不再展示（过滤关闭时不会发生）
    dropped_issues = [it["label"] for it in issues if it["entryCount"] == 0]
    issues = [it for it in issues if it["entryCount"] > 0]
    # 若发生过过滤，各字段需要重算，否则卡片上的分类标签会残留已删除条目的内容
    if dropped_entries:
        for it in issues:
            it["categories"] = sorted({e.get("category", "") for e in it["entries"] if e.get("category")})
            it["keywords"] = sorted({k for e in it["entries"] for k in e.get("keywords", [])})
            it["sources"] = sorted({e.get("source", "") for e in it["entries"] if e.get("source")})

    # ---- 领导人论述 ----
    leaders = parse_leaders(LEADER_DOC) if os.path.isfile(LEADER_DOC) else []

    # ---- 特别贡献奖课题 ----
    awards = load_award_projects(AWARD_XLSX)

    # ---- 习近平文章 / 寄语 ----
    xi_articles = {"title": "习近平总书记关于共青团与青年工作重要文章汇总", "items": []}
    xi_quotes = {"title": "习近平总书记对青年的青春寄语", "parts": []}
    if os.path.isdir(XI_DIR):
        for name in os.listdir(XI_DIR):
            if not name.lower().endswith(".docx") or name.startswith("~$"):
                continue
            path = os.path.join(XI_DIR, name)
            try:
                if "寄语" in name or "指示" in name:
                    xi_quotes = parse_xi_quotes(path)
                else:
                    xi_articles = parse_xi_articles(path)
            except Exception as exc:  # noqa: BLE001
                print("解析失败 %s: %s" % (name, exc))

    stats = build_index(issues, leaders, xi_articles, xi_quotes)
    quality = data_quality(issues)

    data = {
        "site": {
            # title 是网站名称（品牌），subtitle 是站内数据库模块的名称；
            # 两者含义不同，页面上的导航栏/页脚用 title，数据库模块用 subtitle。
            "title": "北大青年纵横",
            "subtitle": "重要讲话与最新提法数据库",
            # 不标注主办单位：本站是资料汇编性质的检索工具，
            # 不作为任何单位的官方发布渠道。
            "org": "北大青年纵横 · 学习资料库",
            "official": False,
            "generated": date.today().isoformat(),
            "footerLinks": FOOTER_LINKS,
        },
        "stats": stats,
        "quality": quality,
        "issues": issues,
        "awards": awards,
        "filterInfo": {
            "enabled": rules.get("enabled", False),
            "rules": rules["include"],
            "droppedEntries": dropped_entries,
            "droppedIssues": dropped_issues,
            "keptEntries": sum(it["entryCount"] for it in issues),
        },
        "leaders": leaders,
        "xiArticles": xi_articles,
        "xiQuotes": xi_quotes,
    }

    print("=" * 70)
    print("解析结果自检")
    print("=" * 70)
    print("期次总数        : %d  (总第%d期 — 总第%d期)" % (stats["issueCount"], *stats["issueRange"]))
    print("条目总数        : %d" % stats["entryCount"])
    print("时间跨度        : %s ~ %s" % stats["dateRange"])
    print("领导人论述      : %d 条" % stats["leaderCount"])
    print("习近平文章      : %d 篇" % stats["xiArticleCount"])
    print("青春寄语        : %d 条" % stats["quoteCount"])
    print("分类分布        : %s" % ", ".join("%s×%d" % kv for kv in stats["categories"]))
    print("-" * 70)
    for it in issues:
        flag = "OK " if it["entryCount"] else "空!"
        note = ("  ← " + it["notes"][0]) if it.get("notes") else ""
        print(
            "  %s 总第%-3d期 %-11s 条目%-2d %s%s"
            % (flag, it["issue"], it["dateText"] or it["date"], it["entryCount"],
               (it["overview"][0][:26] if it["overview"] else ""), note)
        )
    empty = [it["issue"] for it in issues if not it["entryCount"]]
    if empty:
        print("警告：以下期次未解析出条目 -> %s" % empty)

    print("-" * 70)
    print(
        "数据质量报告：%d 处需要人工确认（其中 %d 处为占位符/重复/跳号）"
        % (quality["problemCount"], quality["severeCount"])
    )
    for p in quality["problems"]:
        print("  · [%s] %s" % (p["kind"], p["detail"]))

    if args.check:
        return 0

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    size = os.path.getsize(OUT_FILE) / 1024.0
    print("-" * 70)
    print("已写入 %s (%.1f KB)" % (OUT_FILE, size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
