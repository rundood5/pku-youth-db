# -*- coding: utf-8 -*-
"""极简 YAML 结构解析器（专用于校验 GitHub Actions 工作流）

环境里没有 PyYAML，而"工作流 YAML 写错"是 GitHub Pages 部署失败最常见的原因，
所以这里实现一个足够覆盖 Actions 语法的块状解析器，做真实的缩进校验，
而不是用规则去猜。

支持：块映射、块序列、嵌套、行内注释、引号字符串、布尔/数字标量。
不支持也不需要：锚点、多行标量、流式集合。

用法：python tools/check_workflow.py
"""

from __future__ import annotations

import io
import sys

PATH = r"D:\demo\.github\workflows\deploy-pages.yml"


class YamlError(Exception):
    def __init__(self, line_no, msg):
        super().__init__("第 %d 行: %s" % (line_no, msg))
        self.line_no = line_no


def strip_comment(s: str) -> str:
    """去掉行尾注释，但保留引号内的 #。"""
    out, quote = [], None
    for ch in s:
        if quote:
            if ch == quote:
                quote = None
            out.append(ch)
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (not out or out[-1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def scalar(tok: str):
    tok = tok.strip()
    if tok == "":
        return None
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
        return tok[1:-1]
    low = tok.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    try:
        return int(tok)
    except ValueError:
        return tok


def preprocess(text: str):
    items = []
    for i, raw in enumerate(text.split("\n"), 1):
        if raw.strip() == "" or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw:
            raise YamlError(i, "含 TAB 字符；YAML 只能用空格缩进")
        body = strip_comment(raw)
        if body.strip() == "":
            continue
        indent = len(body) - len(body.lstrip(" "))
        items.append((i, indent, body.strip(), raw))
    return items


def parse_block(items, pos, indent):
    """返回 (节点, 新位置)。节点是 dict / list / 标量。"""
    if pos >= len(items):
        return None, pos
    line_no, cur_indent, content, _ = items[pos]
    if cur_indent < indent:
        return None, pos
    if cur_indent > indent:
        raise YamlError(line_no, "缩进比上一级深了 %d 格，但上一行不是键或列表项" % (cur_indent - indent))

    if content.startswith("- ") or content == "-":
        node = []
        while pos < len(items):
            ln, ind, txt, _ = items[pos]
            if ind < indent:
                break
            if ind > indent:
                raise YamlError(ln, "列表项缩进不一致（当前 %d，期望 %d）" % (ind, indent))
            if not (txt.startswith("- ") or txt == "-"):
                break
            rest = txt[1:].strip()
            if rest == "":
                pos += 1
                child, pos = parse_block(items, pos, indent + 2)
                node.append(child)
                continue
            if ":" in rest and not rest.startswith(("'", '"')):
                # 行内开始的映射：- name: xxx
                key, _, val = rest.partition(":")
                key = key.strip()
                item = {}
                if val.strip() == "":
                    pos += 1
                    child, pos = parse_block(items, pos, indent + 4)
                    item[key] = child
                else:
                    item[key] = scalar(val)
                    pos += 1
                    # 该列表项后续同级的键（缩进 = indent + 2，因为 "- " 占两格）
                    while pos < len(items):
                        ln2, ind2, txt2, _ = items[pos]
                        if ind2 != indent + 2:
                            break
                        k2, _, v2 = txt2.partition(":")
                        if not _:
                            raise YamlError(ln2, "期望键值对")
                        if v2.strip() == "":
                            pos += 1
                            child2, pos = parse_block(items, pos, ind2 + 2)
                            item[k2.strip()] = child2
                        else:
                            item[k2.strip()] = scalar(v2)
                            pos += 1
                node.append(item)
            else:
                node.append(scalar(rest))
                pos += 1
        return node, pos

    node = {}
    while pos < len(items):
        ln, ind, txt, _ = items[pos]
        if ind < indent:
            break
        if ind > indent:
            raise YamlError(ln, "缩进比同级深了 %d 格" % (ind - indent))
        if txt.startswith("- "):
            break
        if ":" not in txt:
            raise YamlError(ln, "不是键值对，也不是列表项: %r" % txt)
        key, _, val = txt.partition(":")
        key = key.strip()
        if key == "":
            raise YamlError(ln, "键名为空")
        if val.strip() == "":
            pos += 1
            child, pos = parse_block(items, pos, ind + 2)
            node[key] = child if child is not None else None
        else:
            node[key] = scalar(val)
            pos += 1
    return node, pos


def main():
    text = io.open(PATH, encoding="utf-8", newline="").read()
    print("=" * 66)
    print("GitHub Actions 工作流校验")
    print("=" * 66)
    print("文件: .github/workflows/deploy-pages.yml")
    print("换行符: %s" % ("CRLF（建议改 LF）" if "\r" in text else "LF ✓"))

    try:
        items = preprocess(text)
    except YamlError as e:
        print("\n[FAIL] %s" % e)
        return 1

    try:
        doc, pos = parse_block(items, 0, items[0][1] if items else 0)
    except YamlError as e:
        print("\n[FAIL] YAML 缩进/结构错误 -> %s" % e)
        return 1

    if pos != len(items):
        print("\n[FAIL] 有 %d 行未被解析，结构可能断裂" % (len(items) - pos))
        return 1

    print("YAML 结构解析: 成功 ✓")
    print()

    problems = []
    # 顶层
    if "name" not in doc:
        problems.append("缺少 name")
    triggers = doc.get("on") or doc.get(True)
    if not triggers:
        problems.append("缺少 on（触发条件）")
    if "jobs" not in doc:
        problems.append("缺少 jobs")
    perms = doc.get("permissions") or {}
    if perms.get("pages") != "write":
        problems.append("permissions.pages 必须是 write，否则部署阶段会失败")
    if perms.get("id-token") != "write":
        problems.append("permissions.id-token 必须是 write，否则 deploy-pages 无法获取 OIDC 令牌")

    jobs = doc.get("jobs") or {}
    deploy = jobs.get("deploy") or {}
    if deploy.get("runs-on") != "ubuntu-latest":
        problems.append("jobs.deploy.runs-on 应为 ubuntu-latest")
    steps = deploy.get("steps") or []
    uses_list = [s.get("uses", "") for s in steps if isinstance(s, dict)]

    need_uses = [
        ("actions/checkout@", "检出代码"),
        ("actions/configure-pages@", "配置 Pages"),
        ("actions/upload-pages-artifact@", "上传站点产物"),
        ("actions/deploy-pages@", "部署到 Pages"),
    ]
    for prefix, desc in need_uses:
        if not any(u.startswith(prefix) for u in uses_list):
            problems.append("缺少步骤 %s（%s）" % (prefix + "...", desc))

    # upload-pages-artifact 的 path 必须指向 site
    art_path = None
    for s in steps:
        if isinstance(s, dict) and str(s.get("uses", "")).startswith("actions/upload-pages-artifact@"):
            art_path = (s.get("with") or {}).get("path")
    if art_path != "site":
        problems.append("upload-pages-artifact 的 with.path 应为 site，实际为 %r" % art_path)

    # 触发分支要包含 main
    push = (triggers or {}).get("push") or {}
    branches = push.get("branches") or []
    if "main" not in branches:
        problems.append("on.push.branches 应包含 main，实际为 %r" % branches)

    print("结构检查:")
    print("  工作流名称   : %s" % doc.get("name"))
    print("  触发分支     : %s" % branches)
    print("  任务         : %s" % list(jobs.keys()))
    print("  步骤数       : %d" % len(steps))
    for s in steps:
        if isinstance(s, dict):
            print("     - %s" % (s.get("uses") or s.get("name")))
    print("  发布目录     : %s" % art_path)
    print()

    if problems:
        print("[FAIL] 发现 %d 个会导致部署失败的问题:" % len(problems))
        for p in problems:
            print("   ! %s" % p)
        return 1

    print("[PASS] 工作流配置完整：触发、权限、产物路径、部署步骤均正确")
    print("       推送后在仓库 Settings -> Pages 里把 Source 选为 GitHub Actions 即可自动发布")
    return 0


if __name__ == "__main__":
    sys.exit(main())
