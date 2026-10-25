#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
干饭指挥官 · 用餐搭配引擎（meal-master）
=====================================
输入人数、预算、饮食偏好，输出一桌可执行的搭配方案：
  1. 按需求分组（无辣不欢 / 不吃辣 / 素食），硬约束过滤
  2. 每组优先选「满腹组合」（饱腹度最高中价格最低）
  3. 全桌超支时，按「让位最多」原则把整组主食降级到红区组合，直到可行
  4. 饮品/小食补齐（每人至少有喝、有薯）
  5. 结余买分享装/甜品收尾，全程不超预算
  6. 每一项选择都附带可解释的依据

零第三方依赖，Python 3.8+ 标准库可直接运行。

用法：
  python plan_meal.py --people 6 --budget 150 --no-spicy 2
  python plan_meal.py --demo                      # 官方题：6人150元2人不吃辣
  python plan_meal.py --people 8 --budget 300 --format html --out demo.html
"""

import argparse
import json
import sys
from pathlib import Path

MENU_PATH = Path(__file__).resolve().parent.parent / "references" / "menu_snapshot.json"


# ---------------------------------------------------------------- 基础工具

def money(v):
    """149.4 -> '¥149.4'；41.0 -> '¥41'"""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return f"¥{s}"


def load_menu(path=MENU_PATH):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]
    # includes 中的名称 -> 品类 映射（如 "中薯条" -> snack）
    name_cat = {}
    for it in items:
        for inc in it.get("includes", []):
            name_cat[inc] = it["category"]
        name_cat[it["name"]] = it["category"]
    return items, name_cat


def covered_categories(item, name_cat):
    """一个组合/单品覆盖了哪些品类（combo/snack/drink...）"""
    cats = {item["category"]}
    for inc in item.get("includes", []):
        cats.add(name_cat.get(inc, "other"))
    return cats


def allowed(item, allow_spicy, vegetarian):
    if vegetarian and not item.get("vegetarian"):
        return False
    if not allow_spicy and item.get("spicy"):
        return False
    return True


# ---------------------------------------------------------------- 分组

def build_groups(people, no_spicy, vegetarian):
    spicy_ok = people - no_spicy - vegetarian
    if spicy_ok < 0:
        raise ValueError(
            f"不吃辣({no_spicy})+素食({vegetarian}) 不能超过总人数({people})"
        )
    groups = []
    if spicy_ok > 0:
        groups.append({"key": "spicy_ok", "name": "无辣不欢", "count": spicy_ok,
                       "allow_spicy": True, "vegetarian": False})
    if no_spicy > 0:
        groups.append({"key": "no_spicy", "name": "不吃辣", "count": no_spicy,
                       "allow_spicy": False, "vegetarian": False})
    if vegetarian > 0:
        groups.append({"key": "vegetarian", "name": "素食", "count": vegetarian,
                       "allow_spicy": False, "vegetarian": True})
    return groups


# ---------------------------------------------------------------- 搭配引擎

class Planner:
    def __init__(self, people, budget, no_spicy=0, vegetarian=0, menu=None):
        if people < 1:
            raise ValueError("人数至少 1 人")
        if budget <= 0:
            raise ValueError("预算必须大于 0")
        self.people = people
        self.budget = round(float(budget), 2)
        self.groups = build_groups(people, no_spicy, vegetarian)
        if menu is None:
            menu = load_menu()
        self.items, self.name_cat = menu
        self.lines = []        # {item, qty, group_key(None=全桌), reason, phase, from_item}
        self.feasible = True
        self.warnings = []
        self.notes = []

    # ---------------- 记账

    def _add(self, item, qty, group_key, phase, from_item=None, left_before=None):
        self.lines.append({"item": item, "qty": qty, "group_key": group_key,
                           "reason": "", "phase": phase, "from_item": from_item,
                           "left_before": left_before})

    def _total(self):
        return round(sum(l["item"]["price"] * l["qty"] for l in self.lines), 2)

    # ---------------- 候选池

    def group_pool(self, g):
        return [i for i in self.items
                if i["category"] == "combo" and allowed(i, g["allow_spicy"], g["vegetarian"])]

    def preferred_staple(self, g):
        """满腹优先：饱腹度最高中取最便宜"""
        pool = self.group_pool(g)
        if not pool:
            return None
        pool.sort(key=lambda i: (-i["satiety"], i["price"], i["name"]))
        return pool[0]

    def economy_staple(self, g):
        """红区保底：饱腹度>=2 中最便宜"""
        pool = [i for i in self.group_pool(g) if i["satiety"] >= 2]
        if not pool:
            return None
        pool.sort(key=lambda i: (i["price"], i["name"]))
        return pool[0]

    # ---------------- 阶段 1：主食

    def phase_staples(self):
        for g in self.groups:
            pref = self.preferred_staple(g)
            if pref is None:
                self.warnings.append(f"「{g['name']}」组没有合格主食，需人工介入")
                self.feasible = False
                continue
            g["staple"] = pref
            self._add(pref, g["count"], g["key"], "staple")

    # ---------------- 阶段 2：预算修复（整组降级）

    def repair_budget(self):
        while self._total() > self.budget:
            best = None  # (saving, count, group, target)
            for g in self.groups:
                cur = g.get("staple")
                if cur is None:
                    continue
                cheaper = [i for i in self.group_pool(g)
                           if i["price"] < cur["price"] and i["satiety"] >= 2]
                if not cheaper:
                    continue
                target = min(cheaper, key=lambda i: (i["price"], i["name"]))
                saving = round((cur["price"] - target["price"]) * g["count"], 2)
                cand = (saving, g["count"], g, target)
                if best is None or cand[0] > best[0]:
                    best = cand
            if best is None:
                self.feasible = False
                self.warnings.append(
                    f"即使全组使用最低合格主食，合计 {money(self._total())} 仍超预算 "
                    f"{money(self.budget)}，无法可行搭配"
                )
                return
            saving, _, g, target = best
            old = g["staple"]
            for l in self.lines:
                if l["phase"] == "staple" and l["group_key"] == g["key"]:
                    l["from_item"] = old
                    l["item"] = target
            g["staple"] = target
            self.notes.append(
                f"「{g['name']}」组主食由 {old['name']} 降级为 {target['name']}，"
                f"为保全桌预算让位 {money(saving)}"
            )

    # ---------------- 阶段 3：饮品/小食补齐

    def phase_topup(self):
        for g in self.groups:
            staple = g.get("staple")
            if staple is None:
                continue
            cats = covered_categories(staple, self.name_cat)
            # 3a. 饮品保障
            if "drink" not in cats:
                drinks = sorted(
                    [i for i in self.items if i["category"] == "drink"
                     and allowed(i, g["allow_spicy"], g["vegetarian"])],
                    key=lambda i: (i["price"], i["name"]))
                if drinks and self.spent_if(drinks[0], g["count"]) <= self.budget:
                    self._add(drinks[0], g["count"], g["key"], "topup")
            # 3b. 小食保障（优先正餐小食薯条类，其次派/苹果片等）
            if "snack" not in cats:
                snacks = sorted(
                    [i for i in self.items if i["category"] in ("snack", "dessert")
                     and i["satiety"] >= 1
                     and allowed(i, g["allow_spicy"], g["vegetarian"])],
                    key=lambda i: (0 if i.get("staple") else 1, i["price"], i["name"]))
                if snacks and self.spent_if(snacks[0], g["count"]) <= self.budget:
                    self._add(snacks[0], g["count"], g["key"], "topup")

    def spent_if(self, item, qty):
        return round(self._total() + item["price"] * qty, 2)

    # ---------------- 阶段 4：分享装/甜品收尾

    def phase_finale(self):
        veg_any = any(g["vegetarian"] for g in self.groups)
        candidates = [i for i in self.items
                      if i["category"] in ("dessert", "share")
                      and (not veg_any or i.get("vegetarian"))]
        if not candidates:
            return
        cap = max(2, self.people // 2)
        bought = {}
        # 4 人以上先安排一个分享装撑场面
        if self.people >= 4:
            shares = sorted([i for i in candidates if i["category"] == "share"],
                            key=lambda i: (i["price"], i["name"]))
            if shares and self.spent_if(shares[0], 1) <= self.budget:
                left = round(self.budget - self._total(), 2)
                self._add(shares[0], 1, None, "finale", left_before=left)
                bought[shares[0]["id"]] = 1
        # 结余 cheapest-first，同款最多 3 份，总数不超 cap
        while sum(bought.values()) < cap:
            affordable = [i for i in candidates
                          if bought.get(i["id"], 0) < 3
                          and self.spent_if(i, 1) <= self.budget]
            if not affordable:
                break
            pick = min(affordable, key=lambda i: (i["price"], i["name"]))
            left = round(self.budget - self._total(), 2)
            self._add(pick, 1, None, "finale", left_before=left)
            bought[pick["id"]] = bought.get(pick["id"], 0) + 1

    # ---------------- 依据文案

    def finalize_reasons(self):
        for l in self.lines:
            it = l["item"]
            if l["phase"] == "staple":
                if it.get("original_price"):
                    l["reason"] = (
                        f"券后活动价 {money(it['price'])}（原价 {money(it['original_price'])}），"
                        f"全菜单最低的「{' + '.join(it['includes'])}」组合，饱腹度 {it['satiety']} 级"
                    )
                elif l["from_item"] is not None:
                    l["reason"] = (
                        f"预算压缩切换：原选 {l['from_item']['name']} "
                        f"{money(l['from_item']['price'])}/人 会击穿全桌预算，"
                        f"改选满足约束的最低合格组合（有堡有饮料），把预算让给小食"
                    )
                else:
                    l["reason"] = (
                        f"满足该组饮食约束的满腹组合中价格最低，{money(it['price'])}/人，"
                        f"饱腹度 {it['satiety']} 级"
                    )
            elif l["phase"] == "topup":
                if it["category"] == "drink":
                    l["reason"] = f"该组组合不含饮品，补 {it['name']} 保证每人有喝"
                else:
                    l["reason"] = f"该组组合不含小食，补 {it['name']} 让每人都有小食"
            else:  # finale
                if it["category"] == "share":
                    l["reason"] = f"全桌 {self.people} 人聚餐，加 {it['name']} 撑起分享氛围"
                else:
                    l["reason"] = f"结余 {money(l['left_before'])}，加 {it['name']} 收尾"

    # ---------------- 输出结构

    def run(self):
        self.phase_staples()
        self.repair_budget()
        if self.feasible:
            self.phase_topup()
            self.phase_finale()
        self.finalize_reasons()
        return self.result()

    def result(self):
        total = self._total()
        table = []
        for g in self.groups:
            g_lines = [l for l in self.lines if l["group_key"] == g["key"]]
            if g_lines:
                table.append({"group": g, "lines": g_lines})
        shared = [l for l in self.lines if l["group_key"] is None]
        return {
            "input": {
                "people": self.people, "budget": self.budget,
                "no_spicy": next((g["count"] for g in self.groups if g["key"] == "no_spicy"), 0),
                "vegetarian": next((g["count"] for g in self.groups if g["key"] == "vegetarian"), 0),
            },
            "per_head": round(self.budget / self.people, 2),
            "table": table,
            "shared": shared,
            "total": total,
            "left": round(self.budget - total, 2),
            "utilization": round(total / self.budget * 100, 1),
            "feasible": self.feasible,
            "warnings": self.warnings,
            "notes": self.notes,
        }


# ---------------------------------------------------------------- 渲染

def render_text(r):
    L = []
    L.append("=" * 56)
    L.append(" 干饭指挥官 · 今日桌单")
    L.append("=" * 56)
    inp = r["input"]
    L.append(f" 需求：{inp['people']} 人 · 预算 {money(inp['budget'])}"
             f" · 不吃辣 {inp['no_spicy']} 人 · 素食 {inp['vegetarian']} 人")
    L.append(f" 人均预算：{money(r['per_head'])}")
    L.append("-" * 56)
    for block in r["table"]:
        g = block["group"]
        L.append(f"【{g['name']} · {g['count']} 人】")
        for l in block["lines"]:
            it = l["item"]
            L.append(f"  {it['name']} x{l['qty']}  {money(it['price'] * l['qty'])}")
            L.append(f"    └ {l['reason']}")
        L.append("")
    if r["shared"]:
        L.append("【全桌共享】")
        for l in r["shared"]:
            it = l["item"]
            L.append(f"  {it['name']} x{l['qty']}  {money(it['price'] * l['qty'])}")
            L.append(f"    └ {l['reason']}")
        L.append("")
    L.append("-" * 56)
    L.append(f" 合计：{money(r['total'])} / {money(inp['budget'])}"
             f"（结余 {money(r['left'])} · 预算利用率 {r['utilization']}%）")
    for n in r["notes"]:
        L.append(f" · {n}")
    for w in r["warnings"]:
        L.append(f" ⚠ {w}")
    if not r["feasible"]:
        L.append(" ⚠ 当前预算无法满足全部约束，以上为最接近方案")
    L.append("=" * 56)
    return "\n".join(L)


def render_md(r):
    inp = r["input"]
    out = ["# 干饭指挥官 · 今日桌单\n",
           f"- 需求：**{inp['people']} 人** · 预算 **{money(inp['budget'])}**"
           f" · 不吃辣 {inp['no_spicy']} 人 · 素食 {inp['vegetarian']} 人",
           f"- 人均预算：{money(r['per_head'])}\n"]
    for block in r["table"]:
        g = block["group"]
        out.append(f"## {g['name']} · {g['count']} 人\n")
        out.append("| 餐品 | 数量 | 小计 | 选择依据 |")
        out.append("|---|---|---|---|")
        for l in block["lines"]:
            it = l["item"]
            out.append(f"| {it['name']} | {l['qty']} | {money(it['price'] * l['qty'])} | {l['reason']} |")
        out.append("")
    if r["shared"]:
        out.append("## 全桌共享\n")
        out.append("| 餐品 | 数量 | 小计 | 选择依据 |")
        out.append("|---|---|---|---|")
        for l in r["shared"]:
            it = l["item"]
            out.append(f"| {it['name']} | {l['qty']} | {money(it['price'] * l['qty'])} | {l['reason']} |")
        out.append("")
    out.append("## 汇总\n")
    out.append(f"- **合计：{money(r['total'])} / {money(inp['budget'])}**")
    out.append(f"- 结余 {money(r['left'])} · 预算利用率 {r['utilization']}%")
    for n in r["notes"]:
        out.append(f"- {n}")
    for w in r["warnings"]:
        out.append(f"- ⚠ {w}")
    return "\n".join(out)


def render_json(r):
    def ser(l):
        return {"id": l["item"]["id"], "name": l["item"]["name"],
                "qty": l["qty"], "subtotal": round(l["item"]["price"] * l["qty"], 2),
                "reason": l["reason"], "phase": l["phase"]}
    return json.dumps({
        "input": r["input"], "per_head": r["per_head"],
        "table": [{"group": b["group"]["name"], "count": b["group"]["count"],
                   "lines": [ser(l) for l in b["lines"]]} for b in r["table"]],
        "shared": [ser(l) for l in r["shared"]],
        "total": r["total"], "left": r["left"], "utilization": r["utilization"],
        "feasible": r["feasible"], "warnings": r["warnings"], "notes": r["notes"],
    }, ensure_ascii=False, indent=2)


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(r):
    inp = r["input"]
    rows = []
    for block in r["table"]:
        g = block["group"]
        rows.append(f'<tr class="grp"><td colspan="4">{_esc(g["name"])} · {g["count"]} 人</td></tr>')
        for l in block["lines"]:
            it = l["item"]
            rows.append("<tr>"
                        f"<td>{_esc(it['name'])}</td>"
                        f"<td class='c'>x{l['qty']}</td>"
                        f"<td class='c'>{money(it['price'] * l['qty'])}</td>"
                        f"<td class='reason'>{_esc(l['reason'])}</td></tr>")
    if r["shared"]:
        rows.append('<tr class="grp"><td colspan="4">全桌共享</td></tr>')
        for l in r["shared"]:
            it = l["item"]
            rows.append("<tr>"
                        f"<td>{_esc(it['name'])}</td>"
                        f"<td class='c'>x{l['qty']}</td>"
                        f"<td class='c'>{money(it['price'] * l['qty'])}</td>"
                        f"<td class='reason'>{_esc(l['reason'])}</td></tr>")
    notes = "".join(f"<li>{_esc(n)}</li>" for n in r["notes"])
    warns = "".join(f"<li>{_esc(w)}</li>" for w in r["warnings"])
    badge = "方案可行 · 不超预算" if r["feasible"] else "超预算警告"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>干饭指挥官 · {inp['people']}人{money(inp['budget'])}桌单</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #fff8ec; color: #2b2118; padding: 32px 20px; }}
  .wrap {{ max-width: 880px; margin: 0 auto; }}
  .hero {{ background: linear-gradient(135deg, #ffcf3f, #ff9d2e);
           border-radius: 20px; padding: 28px 32px; color: #3a2503;
           box-shadow: 0 8px 24px rgba(255,157,46,.25); }}
  .hero h1 {{ font-size: 30px; letter-spacing: 1px; }}
  .hero .req {{ margin-top: 10px; font-size: 15px; opacity: .85; }}
  .total {{ margin-top: 16px; display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }}
  .total .big {{ font-size: 44px; font-weight: 800; }}
  .total .sub {{ font-size: 14px; }}
  .badge {{ display: inline-block; margin-top: 12px; background: rgba(255,255,255,.65);
            border-radius: 999px; padding: 4px 14px; font-size: 13px; font-weight: 600; }}
  .bar {{ height: 10px; background: rgba(255,255,255,.55); border-radius: 999px;
          margin-top: 14px; overflow: hidden; }}
  .bar > div {{ height: 100%; width: {min(r['utilization'], 100)}%;
                background: #d2691e; border-radius: 999px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 22px;
           background: #fff; border-radius: 14px; overflow: hidden;
           box-shadow: 0 4px 16px rgba(120,80,20,.08); }}
  th, td {{ padding: 10px 14px; font-size: 14px; text-align: left;
            border-bottom: 1px solid #f3e6cf; vertical-align: top; }}
  th {{ background: #ffefd0; font-size: 13px; color: #7a5a1e; }}
  tr.grp td {{ background: #fff3d6; font-weight: 700; color: #8a5a00; }}
  td.c {{ text-align: center; white-space: nowrap; }}
  td.reason {{ color: #6d5b3f; font-size: 13px; }}
  .foot {{ margin-top: 18px; font-size: 13px; color: #8a7a5c; }}
  .foot ul {{ margin: 6px 0 0 18px; }}
  .src {{ margin-top: 14px; font-size: 12px; color: #a3926e; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <h1>🍔 干饭指挥官 · 今日桌单</h1>
    <div class="req">{inp['people']} 人 · 预算 {money(inp['budget'])} · 不吃辣 {inp['no_spicy']} 人 · 素食 {inp['vegetarian']} 人 · 人均 {money(r['per_head'])}</div>
    <div class="total"><span class="big">{money(r['total'])}</span>
      <span class="sub">/ {money(inp['budget'])}（结余 {money(r['left'])} · 利用率 {r['utilization']}%）</span></div>
    <div class="badge">{badge}</div>
    <div class="bar"><div></div></div>
  </div>
  <table>
    <thead><tr><th>餐品</th><th style="text-align:center">数量</th>
      <th style="text-align:center">小计</th><th>选择依据</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <div class="foot">
    <b>引擎决策记录：</b>
    <ul>{notes}</ul>
    <ul>{warns}</ul>
  </div>
  <div class="src">菜单来源：麦当劳中国公开菜单与活动价本地快照（2026-10-25），价格为快照值，正式下单以小程序/MCP 实时价为准。</div>
</div>
</body>
</html>"""


RENDERERS = {"text": render_text, "md": render_md, "json": render_json, "html": render_html}


# ---------------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(
        prog="plan_meal.py",
        description="干饭指挥官 · 用餐搭配引擎：人数+预算+饮食偏好 -> 一桌搭配+总价+依据",
    )
    p.add_argument("--people", type=int, help="用餐人数")
    p.add_argument("--budget", type=float, help="总预算（元）")
    p.add_argument("--no-spicy", type=int, default=0, help="不吃辣的人数")
    p.add_argument("--vegetarian", type=int, default=0, help="素食人数")
    p.add_argument("--format", choices=list(RENDERERS), default="text")
    p.add_argument("--out", help="输出文件路径（默认打印到终端）")
    p.add_argument("--demo", action="store_true",
                   help="运行官方题：6 人 · 150 元 · 2 人不吃辣")
    args = p.parse_args(argv)

    if args.demo:
        people, budget, no_spicy, vegetarian = 6, 150, 2, 0
    else:
        if not args.people or not args.budget:
            p.error("请提供 --people 与 --budget（或用 --demo 跑官方题）")
        people, budget = args.people, args.budget
        no_spicy, vegetarian = args.no_spicy, args.vegetarian

    try:
        result = Planner(people, budget, no_spicy, vegetarian).run()
    except ValueError as e:
        print(f"输入错误：{e}", file=sys.stderr)
        return 2

    out = RENDERERS[args.format](result)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"已写入 {args.out}", file=sys.stderr)
    else:
        print(out)
    return 0 if result["feasible"] else 1


if __name__ == "__main__":
    sys.exit(main())
