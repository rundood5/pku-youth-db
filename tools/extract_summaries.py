# -*- coding: utf-8 -*-
"""从特别贡献奖课题的源文件里提取真实摘要

背景
  《共青团与青年工作课题》栏目原先的“简介”是根据课题名称推测生成的，
  并非原文内容。本脚本改为直接从学生的申报材料里提取官方摘要：

    作品提交.docx / .pdf  ->  取“摘要：”“内容摘要：”段落
    附件一.*             ->  作为兜底来源

  支持格式：.docx（python-docx）、.pdf（pypdf）、.doc（LibreOffice 转 txt）

用法
    python tools/extract_summaries.py            # 提取并写入 tools/summaries.json
    python tools/extract_summaries.py --report   # 只打印统计，不写文件

之后执行 python tools/extract.py 会把摘要并入 site/data/content.json。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS_DIR)
SRC_DIR = os.path.join(
    ROOT, "source", "特别贡献奖", "特别贡献奖", "特别贡献奖申报", "理论研究室")
OUT_FILE = os.path.join(TOOLS_DIR, "summaries.json")

# 允许脚本从工作区安装的依赖目录里 import pypdf
sys.path.insert(0, os.path.join(ROOT, ".pylibs"))

LIBREOFFICE_NODE = r"D:\DSH\resources\runtime\primary-runtime\dependencies\node\bin\node.exe"
LIBREOFFICE_CLI = (r"D:\DSH\resources\app.asar.unpacked\dsh\node_modules"
                   r"\@deepseek-ai\libreoffice-kit\lib\cli.js")

# 摘要起始标记，按优先级排列
ABSTRACT_LABELS = [
    "摘要：", "摘要:", "内容摘要：", "内容摘要:", "【摘要】", "[摘要]",
    "论文摘要：", "研究摘要：",
]
# 摘要结束标记（出现即截断）
ABSTRACT_END = [
    "关键词：", "关键词:", "关键字：", "关键字:", "【关键词】",
    "目录", "第一章", "一、引言", "1 引言", "1.引言", "引言",
]
# 这些段落属于封面/表单，不作为摘要
JUNK_PATTERNS = [
    r"^北京大学第[三四五]+届", r"^“?挑战杯”，?$", r"^\d{4}\s*年\s*\d{1,2}\s*月$",
    r"^作品提交$", r"^附件[一二三四]$", r"^特别贡献奖", r"^团队负责人",
    r"^课题名称", r"^申报单位", r"^学号", r"^姓名", r"^联系方式", r"^\s*$",
]


def norm(s: str) -> str:
    s = (s or "").replace("\u3000", " ").replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def is_junk(par: str) -> bool:
    for pat in JUNK_PATTERNS:
        if re.search(pat, par):
            return True
    # 目录行：连续点号 + 页码，例如“摘要 ................. 1”
    if par.count(".") >= 6 or par.count("…") >= 6:
        return True
    if re.search(r"\.{4,}\s*\d+\s*$", par):
        return True
    # 纯编号小标题，例如“1.2 文献综述”
    if re.match(r"^\d+(\.\d+)*\s+\S{2,20}$", par) and len(par) < 30:
        return True
    return False


def label_position(par: str, lab: str) -> int:
    """返回“摘要：”这类标记作为段落开头出现的位置；不是开头则返回 -1。

    必须限制在开头，否则目录里的“摘要 ......... 1”也会被当成摘要。
    """
    idx = par.find(lab)
    if idx == -1:
        return -1
    if idx > 2:  # 允许前面有一点空白或序号
        return -1
    return idx


def read_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


def read_pdf(path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    out = []
    # 摘要通常在前几页，但封面+目录可能占掉 1-2 页，故读前 6 页
    for page in reader.pages[:6]:
        try:
            out.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            continue
    return "\n".join(out)


def paragraphs(text: str):
    """把文本切成候选段落。

    对 PDF 尤其重要：提取出来的正文常常一句话被切成很多短行，
    若只按单行判断，“最长的一行”可能只有十几个字，导致找不到摘要。
    这里把连续的非空短行合并成一个段落，同时保留原本就是整段的行。
    """
    out = []
    buf = []
    for ln in (text or "").replace("\r", "\n").split("\n"):
        ln = norm(ln)
        if not ln:
            if buf:
                out.append("".join(buf))
                buf = []
            continue
        buf.append(ln)
        # 行尾是句末标点或该行已够长，视为段落结束
        if ln.endswith(("。", "！", "？", "；")) or len(ln) >= 60:
            out.append("".join(buf))
            buf = []
    if buf:
        out.append("".join(buf))
    return out


def cjk_len(s: str) -> int:
    """统计中文字符数，用来判断一段是不是真正的正文（目录行几乎没有中文内容）。"""
    return len(re.findall(r"[\u4e00-\u9fff]", s or ""))


def read_doc(path: str) -> str:
    """用自带的 LibreOffice 把 .doc 转成 txt（仅少量文件需要）。"""
    import tempfile
    tmp = os.path.join(ROOT, ".piptmp")
    os.makedirs(tmp, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp) as td:
        cmd = [LIBREOFFICE_NODE, LIBREOFFICE_CLI, "convert",
               "--input", path, "--output", os.path.join(td, "out.txt")]
        try:
            subprocess.run(cmd, capture_output=True, timeout=180, check=False)
        except Exception:  # noqa: BLE001
            return ""
        cand = []
        for dirpath, _, names in os.walk(td):
            for n in names:
                if n.lower().endswith(".txt"):
                    cand.append(os.path.join(dirpath, n))
        if not cand:
            return ""
        return io.open(cand[0], encoding="utf-8", errors="ignore").read()


def strip_cover(text: str) -> str:
    """剥掉段落开头粘连的封面信息。

    PDF/docx 提取时，论文标题、作者、"二〇二五年三月"这类封面文字
    常与"摘要"挤在同一段里，例如：
        “当代青年的家庭生育观念研究摘要：本研究从……”
        “二〇二五 年 三 月摘要：志愿服务是……”
        “小组成员：朱一晨 游东凡 周煜晗摘要“银发经济是……”
    这里把“摘要”标记之前的部分截掉，只保留正文。
    """
    for lab in ABSTRACT_LABELS:
        idx = text.find(lab)
        # 摘要标记通常就在段落开头附近；放宽到 140 字，
        # 以便覆盖“成 员：叶妙童 2401111420 ……”这类较长的封面行
        if 0 < idx <= 140:
            return text[idx + len(lab):].lstrip()
    m = re.match(r"^摘\s*要\s*[:：]?\s*", text)
    if m:
        return text[m.end():]
    return text


def strip_leading_title(text: str, title: str) -> str:
    """去掉正文开头粘连的论文标题。

    例：“面向高校留学生阐释习近平新时代中国特色社会主义思想的路径研究摘要习近平……”
    前面那截就是课题名称，删掉后读起来才像摘要。
    """
    if not title:
        return text
    t = re.sub(r"[\s“”\"'《》]", "", title)
    head = re.sub(r"[\s“”\"'《》]", "", text[: len(t) + 12])
    if head.startswith(t):
        cut = 0
        seen = 0
        for i, ch in enumerate(text):
            if not re.match(r"[\s“”\"'《》]", ch):
                seen += 1
                if seen >= len(t):
                    cut = i + 1
                    break
        return text[cut:].lstrip(" ：:，,。")
    return text


def extract_abstract(text: str) -> str:
    """从整篇文本里定位并返回摘要段落。

    优先级：
      1. 段落开头出现“摘要：”等标记 -> 取其后内容，遇到“关键词/目录/第一章”等截断
      2. 退而取正文中中文字符最多的一段（通常是引言），但必须排除目录页
    返回空串表示没找到可靠摘要，调用方应退回自动生成，不要展示目录垃圾。
    """
    # 先按段落合并，避免 PDF 把一句话拆成很多短行导致判定失败
    paras = [p for p in paragraphs(text) if p]

    # 策略一：段落开头的摘要标记
    for i, ln in enumerate(paras):
        for lab in ABSTRACT_LABELS:
            if label_position(ln, lab) == -1:
                continue
            buf = []
            first = ln.split(lab, 1)[1].strip()
            if first and not is_junk(first):
                buf.append(first)
            for nxt in paras[i + 1:]:
                if not nxt or is_junk(nxt):
                    continue
                if any(e in nxt[:12] for e in ABSTRACT_END):
                    break
                buf.append(nxt)
                if cjk_len(" ".join(buf)) > 400:
                    break
            got = norm(" ".join(buf))
            got = strip_cover(got)
            # 摘要至少要 60 个中文字，且不能像目录
            if cjk_len(got) >= 60 and got.count(".") < 6:
                return got

    # 策略二：取**靠前**的长段落，而不是全文最长的一段。
    # 全文最长常常是方法、访谈记录或附录表格（实测抓到过“被访者：陈XX”“表2 开放式编码”）。
    # 真正的摘要/引言一定出现在正文开头部分，因此按顺序找第一段合格的长段落。
    for p in paras:
        if cjk_len(p) < 80 or is_junk(p):
            continue
        if any(e in p[:12] for e in ABSTRACT_END):
            continue
        if p.count(".") >= 6:
            continue
        # 排除明显的非摘要内容
        if len(re.findall(r"[0-9]", p)) > cjk_len(p) * 0.4:  # 数字比例过高
            continue
        return strip_cover(p)
    # 策略三：退一步，放弃数字比例限制，仍取靠前的长段落
    for p in paras:
        if cjk_len(p) >= 80 and not is_junk(p) and p.count(".") < 6:
            return strip_cover(p)
    return ""


def tidy(text: str, limit: int = 200) -> str:
    """压掉多余空白，并按完整句子截断到 limit 字左右。"""
    text = norm(re.sub(r"\s+", " ", text))
    text = re.sub(r"^[：:，,。、\s]+", "", text)
    if len(text) <= limit:
        return text
    window = text[: limit + 60]
    idx = max(window.rfind(m) for m in "。；！？")
    if idx >= limit * 0.5:
        return text[: idx + 1]
    return window[:limit] + "……"


def pick_files(no: int):
    """返回该序号的候选文件（作品提交优先，其次附件一）。"""
    if not os.path.isdir(SRC_DIR):
        return []
    sub, att = [], []
    for name in sorted(os.listdir(SRC_DIR)):
        if name.startswith("._") or not re.match(r"^%d特贡" % no, name):
            continue
        full = os.path.join(SRC_DIR, name)
        if "作品提交" in name:
            sub.append(full)
        elif "附件一" in name:
            att.append(full)
    return sub + att


def read_any(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".docx":
            return read_docx(path)
        if ext == ".pdf":
            return read_pdf(path)
        if ext == ".doc":
            return read_doc(path)
    except Exception as e:  # noqa: BLE001
        print("     读取失败 %s: %s" % (os.path.basename(path)[:36], type(e).__name__))
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="只报告，不写文件")
    args = ap.parse_args()

    print("=" * 72)
    print("从源文件提取课题摘要")
    print("=" * 72)
    print("源目录: %s" % SRC_DIR)
    if not os.path.isdir(SRC_DIR):
        print("找不到源目录")
        return 1

    # 序号取自 xlsx 清单
    xlsx = os.path.join(os.path.dirname(SRC_DIR), "理论研究室.xlsx")
    import openpyxl
    ws = openpyxl.load_workbook(xlsx, data_only=True).worksheets[0]
    items = []
    for row in ws.iter_rows(values_only=True):
        cells = ["" if c is None else str(c).strip() for c in row]
        if len(cells) >= 3 and cells[0].isdigit():
            items.append({"no": int(cells[0]), "title": cells[1], "owner": cells[2]})

    result = {}
    stats = {"docx": 0, "pdf": 0, "doc": 0, "命中标记": 0, "兜底段落": 0, "失败": 0}

    for it in items:
        no = it["no"]
        files = pick_files(no)
        text, src = "", ""
        for f in files:
            t = read_any(f)
            if t:
                text, src = t, os.path.basename(f)
                break
        if not text:
            stats["失败"] += 1
            print("  %2d  %-40s  无可用文本" % (no, it["title"][:38]))
            continue

        ext = os.path.splitext(src)[1].lower().lstrip(".")
        stats[ext if ext in stats else "docx"] += 1

        raw = extract_abstract(text)
        has_label = any(lab in text for lab in ABSTRACT_LABELS)
        stats["命中标记" if has_label else "兜底段落"] += 1

        summary = tidy(strip_leading_title(raw, it["title"]))
        result[str(no)] = {"summary": summary, "source": src, "hasLabel": has_label}
        flag = "摘要" if has_label else "兜底"
        print("  %2d  %-34s [%s/%s] %d 字" % (
            no, it["title"][:32], ext, flag, len(summary)))
        if summary:
            print("        %s" % summary[:88])

    print()
    print("-" * 72)
    print("统计: 有效 %d / %d" % (len(result), len(items)))
    print("  来源格式: docx %d, pdf %d, doc %d" % (stats["docx"], stats["pdf"], stats["doc"]))
    print("  命中摘要标记 %d，按最长段落兜底 %d，失败 %d" % (
        stats["命中标记"], stats["兜底段落"], stats["失败"]))
    empty = [k for k, v in result.items() if len(v["summary"]) < 30]
    if empty:
        print("  摘要过短（<30字）的序号: %s" % ", ".join(sorted(empty, key=int)))

    if args.report:
        return 0
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    print()
    print("已写入 %s" % OUT_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
