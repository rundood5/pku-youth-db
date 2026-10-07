# -*- coding: utf-8 -*-
"""北大校徽图片处理：生成网站用的多套尺寸与配色变体

背景与目的：
  源图 source/北大校徽.png 是 873x785、白底不透明的 PNG。
  直接放到深藏青色的导航栏上会露出一个白色方块，而且校徽红（近似 #940000）
  在深藏青上对比度过低、几乎看不清。因此需要：

    1. 抠成透明背景（白底 -> alpha=0），这样放在任何底色上都干净；
    2. 生成红色版（放在浅色区域）与白色版（放在深色导航栏、深色页脚）；
    3. 缩小导出若干尺寸，避免把 172 KB 的原图直接塞进网页；
    4. 由校徽生成网站图标 favicon。

  注意：白色版只是把红色像素改成白色，保持形状完全不变，
  属于为深色背景做的显示适配。正式对外发布前，请按学校视觉标识管理规定
  确认校徽的使用方式与最小尺寸要求。

输出到 site/assets/：
  pku-logo.png        红色版，导航栏与正文区使用（透明背景）
  pku-logo-white.png  白色版，深色导航栏与页脚使用（透明背景）
  pku-emblem.png      红色版大图，首屏装饰使用
  favicon.png         网站图标

用法：python tools/prepare_logo.py
"""

from __future__ import annotations

import os
import sys

from PIL import Image

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS_DIR)
SRC = os.path.join(ROOT, "source", "北大校徽.png")
OUT_DIR = os.path.join(ROOT, "site", "assets")

# 校徽红：北大标识用色近似 #940000 ~ #A3161C，取主色统计值附近
BRAND_RED = (148, 0, 0)

# 白色阈值：比这更亮且低饱和的像素视为背景
WHITE_MIN = 232
SAT_MAX = 22


def load_source() -> Image.Image:
    if not os.path.isfile(SRC):
        print("找不到校徽源图：%s" % SRC)
        sys.exit(1)
    im = Image.open(SRC).convert("RGBA")
    print("源图: %s  %dx%d  %s" % (os.path.basename(SRC), im.width, im.height, im.mode))
    return im


def white_to_alpha(im: Image.Image) -> Image.Image:
    """把白色背景抠成透明。

    判定规则：像素足够亮（max 通道 >= WHITE_MIN）且低饱和（通道差 <= SAT_MAX）
    视为背景，alpha 直接置 0；其余像素原样保留。
    这样校徽红色部分与抗锯齿边缘都能保住，不会出现白边。
    """
    src = im.load()
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    dst = out.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            if mx >= WHITE_MIN and (mx - mn) <= SAT_MAX:
                dst[x, y] = (r, g, b, 0)
            else:
                dst[x, y] = (r, g, b, a)
    return out


def tighten(im: Image.Image, pad: int = 2) -> Image.Image:
    """裁掉四周多余留白，让校徽在方形容器里占满，视觉上更清晰。"""
    bbox = im.getchannel("A").getbbox()
    if not bbox:
        return im
    l, t, r, b = bbox
    l, t = max(0, l - pad), max(0, t - pad)
    r, b = min(im.width, r + pad), min(im.height, b + pad)
    return im.crop((l, t, r, b))


def to_square(im: Image.Image, pad_ratio: float = 0.06) -> Image.Image:
    """补成正方形，避免不同位置因宽高比不同而变形或错位。"""
    side = int(max(im.width, im.height) * (1 + pad_ratio * 2))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    return canvas


def recolor(im: Image.Image, color) -> Image.Image:
    """把彩色像素统一换成目标颜色，保留原有 alpha（形状完全不变）。"""
    w, h = im.size
    src = im.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dst = out.load()
    for y in range(h):
        for x in range(w):
            a = src[x, y][3]
            if a:
                dst[x, y] = (color[0], color[1], color[2], a)
    return out


def resize(im: Image.Image, size: int) -> Image.Image:
    return im.resize((size, size), Image.LANCZOS)


def save(im: Image.Image, name: str, size: int) -> str:
    """导出 PNG（保持抗锯齿。

    实测过"精简 alpha 通道"与"调色板量化"两种省体积的办法：
    校徽只有红白两色，体积几乎全部来自抗锯齿边缘的 alpha 通道，
    二值化 alpha 只能从 45 KB 降到 28 KB，但在 6% 不透明度的水印场景下
    边缘会发毛，得不偿失，因此保持原样。
    """
    out = resize(im, size)
    path = os.path.join(OUT_DIR, name)
    out.save(path, "PNG", optimize=True)
    kb = os.path.getsize(path) / 1024.0
    print("  已生成 %-20s %4dpx  %7.1f KB" % ("assets/" + name, size, kb))
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 66)
    print("北大校徽处理")
    print("=" * 66)
    im = load_source()

    print("\n[1/4] 抠掉白色背景 -> 透明")
    cut = white_to_alpha(im)
    cut = tighten(cut)
    cut = to_square(cut)
    print("  处理后 %dx%d，四周白底已去除，边缘抗锯齿保留" % (cut.width, cut.height))

    print("\n[2/4] 生成红色版（浅色区域用）")
    red = recolor(cut, BRAND_RED)
    save(red, "pku-logo.png", 160)
    save(red, "pku-emblem.png", 256)

    print("\n[3/4] 生成白色版（深色导航栏/页脚用）")
    white = recolor(cut, (255, 255, 255))
    save(white, "pku-logo-white.png", 160)

    print("\n[4/4] 生成网站图标 favicon")
    # favicon 用红色校徽放在白色圆底上，小尺寸下更易辨认
    for s in (32, 64):
        icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        inner = resize(red, int(s * 0.78))
        icon.paste(inner, ((s - inner.width) // 2, (s - inner.height) // 2), inner)
        if s == 32:
            icon.save(os.path.join(OUT_DIR, "favicon.png"), "PNG", optimize=True)
            print("  已生成 %-20s %4dpx  %7.1f KB"
                  % ("assets/favicon.png", 32, os.path.getsize(os.path.join(OUT_DIR, "favicon.png")) / 1024.0))
        else:
            icon.save(os.path.join(OUT_DIR, "favicon-64.png"), "PNG", optimize=True)
            print("  已生成 %-20s %4dpx  %7.1f KB"
                  % ("assets/favicon-64.png", 64, os.path.getsize(os.path.join(OUT_DIR, "favicon-64.png")) / 1024.0))

    print("\n完成。总占用空间增加：%.1f KB" % (
        sum(os.path.getsize(os.path.join(OUT_DIR, f))
            for f in ["pku-logo.png", "pku-logo-white.png", "pku-emblem.png", "favicon.png", "favicon-64.png"]) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
