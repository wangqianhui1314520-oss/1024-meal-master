#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成参赛海报 PNG（1920x1080）——干饭指挥官 · 1024 用餐赛道"""
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
FONT_REG = "C:/Windows/Fonts/msyh.ttc"

RED = (200, 16, 46)
DARK = (43, 33, 24)
BROWN = (138, 122, 92)
WHITE = (255, 255, 255)
ORANGE = (217, 105, 30)


def f(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def vgrad(size, top, bottom):
    w, h = size
    img = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        img.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img.resize((w, h))


def main():
    img = vgrad((W, H), (255, 224, 138), (255, 176, 58))
    d = ImageDraw.Draw(img, "RGBA")

    # 背景装饰圆
    for cx, cy, r, a in [(1700, 180, 260, 28), (180, 900, 220, 24), (1620, 880, 150, 20)]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, a))

    # 顶部徽章
    d.rounded_rectangle([140, 90, 900, 170], radius=40, fill=RED)
    d.text((190, 130), "WaytoAGI 1024 超能 Coding 周末 · 用餐赛道",
           font=f(38), fill=WHITE, anchor="lm")

    # 主卡片
    d.rounded_rectangle([120, 210, 1800, 850], radius=36, fill=(0, 0, 0, 28))
    d.rounded_rectangle([140, 230, 1780, 830], radius=36, fill=WHITE)

    # 标题区
    d.text((210, 320), "干饭指挥官", font=f(96), fill=DARK, anchor="lm")
    d.text((215, 405), "人数 + 预算 + 饮食偏好  →  一桌不超预算、项项有依据的方案",
           font=f(36, bold=False), fill=BROWN, anchor="lm")

    # 条件 chips
    chips = ["官方题：6 人", "预算 ¥150", "2 人不吃辣"]
    cx = 210
    for c in chips:
        wch = d.textlength(c, font=f(34)) + 64
        d.rounded_rectangle([cx, 450, cx + wch, 522], radius=36,
                            outline=ORANGE, width=3)
        d.text((cx + 32, 486), c, font=f(34), fill=ORANGE, anchor="lm")
        cx += wch + 24

    # 桌单（左列）
    rows = [
        ("麦辣鸡腿堡三件套（券后）", "×4", "¥91.6"),
        ("1+1 随心配（麦香鸡堡+可乐）", "×2", "¥25.8"),
        ("中薯条", "×2", "¥26"),
        ("圆筒冰淇淋", "×1", "¥6"),
    ]
    y = 590
    d.line([210, 560, 1090, 560], fill=(243, 230, 207), width=3)
    for name, qty, price in rows:
        d.text((210, y), name, font=f(38), fill=DARK, anchor="lm")
        d.text((950, y), qty, font=f(38), fill=BROWN, anchor="rm")
        d.text((1090, y), price, font=f(38, bold=True), fill=DARK, anchor="rm")
        y += 62

    # 右栏：大数字 + 利用率
    d.rounded_rectangle([1150, 550, 1710, 780], radius=28, fill=(255, 248, 236))
    d.text((1430, 615), "¥149.4", font=f(92), fill=RED, anchor="mm")
    d.text((1430, 680), "/ ¥150 · 预算利用率 99.6%", font=f(30, bold=False),
           fill=BROWN, anchor="mm")
    d.rounded_rectangle([1210, 715, 1650, 745], radius=15, fill=(243, 230, 207))
    d.rounded_rectangle([1210, 715, 1210 + 440 * 0.996, 745], radius=15, fill=RED)

    # 依据
    d.text((210, 800), "依据：券后 22.9 元是全菜单最低三件套；不吃辣组切红区 1+1 保底，把预算让给小食。",
           font=f(28, bold=False), fill=BROWN, anchor="lm")

    # 底部信息
    d.text((140, 950), "meal-master · WorkBuddy 制作 · 每项选择都有依据",
           font=f(34), fill=(255, 255, 255, 230), anchor="lm")
    d.text((140, 1010), "干饭指挥官：把「今天吃什么」变成一桌安排得明明白白的方案",
           font=f(28, bold=False), fill=(255, 255, 255, 190), anchor="lm")

    out = "assets/poster.png"
    img.save(out, "PNG")
    print("saved", out, img.size)


if __name__ == "__main__":
    main()
