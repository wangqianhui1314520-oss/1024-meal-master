#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合成作品封面 cover.png（1920x1080）：AI 食物底图 + 标题层"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080
BASE = "assets/cover_base.png"
OUT = "assets/cover.png"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
FONT_REG = "C:/Windows/Fonts/msyh.ttc"

RED = (200, 16, 46)
DARK = (43, 33, 24)
BROWN = (122, 100, 66)


def f(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def main():
    base = Image.open(BASE).convert("RGB")

    # 铺满 1920x1080（居中裁切）
    bw, bh = base.size
    scale = max(W / bw, H / bh)
    base = base.resize((int(bw * scale), int(bh * scale)), Image.LANCZOS)
    bx = (base.width - W) // 2
    by = (base.height - H) // 2
    img = base.crop((bx, by, bx + W, by + H))

    # 左侧暖色渐变纱罩，保证文字可读
    scrim = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(scrim)
    for x in range(W):
        a = max(0, int(215 * (1 - x / 1050)))
        sd.line([(x, 0), (x, H)], fill=a)
    warm = Image.new("RGB", (W, H), (255, 244, 222))
    img = Image.composite(warm, img, scrim)

    d = ImageDraw.Draw(img, "RGBA")

    # 顶部徽章
    d.rounded_rectangle([110, 96, 870, 176], radius=40, fill=RED)
    d.text((150, 136), "WaytoAGI 1024 超能 Coding 周末 · 用餐赛道",
           font=f(38), fill=(255, 255, 255), anchor="lm")

    # 主标题（轻投影）
    d.text((116, 356), "干饭指挥官", font=f(150), fill=(0, 0, 0, 40), anchor="lm")
    d.text((110, 350), "干饭指挥官", font=f(150), fill=DARK, anchor="lm")

    # 副标题
    d.text((116, 472), "人数 + 预算 + 饮食偏好  →  一桌不超预算、项项有依据的方案",
           font=f(38, bold=False), fill=BROWN, anchor="lm")

    # 数据 chips
    chips = [("官方题 ¥149.4 / 150", RED), ("预算利用率 99.6%", (217, 105, 30)),
             ("零依赖 · 确定性输出", (43, 33, 24))]
    cx = 116
    cy = 560
    for text, color in chips:
        wtxt = d.textlength(text, font=f(32))
        d.rounded_rectangle([cx, cy, cx + wtxt + 56, cy + 72], radius=36,
                            fill=(255, 255, 255, 215), outline=color, width=3)
        d.text((cx + 28, cy + 36), text, font=f(32), fill=color, anchor="lm")
        cx += wtxt + 56 + 20

    # 底部信息条
    d.line([116, 900, 700, 900], fill=(43, 33, 24, 60), width=2)
    d.text((116, 950), "meal-master · WorkBuddy Skill · 评委现场点一单即出结果",
           font=f(32, bold=False), fill=DARK, anchor="lm")
    d.text((116, 1006), "王乾辉 · 游承峰工作室",
           font=f(26, bold=False), fill=BROWN, anchor="lm")

    img.save(OUT, "PNG")
    print("saved", OUT, img.size)


if __name__ == "__main__":
    main()
