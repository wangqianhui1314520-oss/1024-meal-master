#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""干饭指挥官 · 回归测试套件（stdlib unittest，零依赖）

运行：python tests/test_plan_meal.py
覆盖：官方题、预算修复、分组约束、边界输入、确定性、不可行场景
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import plan_meal as pm  # noqa: E402


def plan(people, budget, no_spicy=0, vegetarian=0):
    return pm.Planner(people, budget, no_spicy, vegetarian).run()


class TestOfficialProblem(unittest.TestCase):
    """官方题：6 人 · 150 元 · 2 人不吃辣"""

    @classmethod
    def setUpClass(cls):
        cls.r = plan(6, 150, 2, 0)

    def test_total_within_budget(self):
        self.assertLessEqual(self.r["total"], 150)
        self.assertTrue(self.r["feasible"])

    def test_high_utilization(self):
        self.assertGreaterEqual(self.r["utilization"], 95)

    def test_spicy_group_gets_spicy_staple(self):
        block = next(b for b in self.r["table"] if b["group"]["key"] == "spicy_ok")
        staple = block["lines"][0]
        self.assertTrue(staple["item"]["spicy"])
        self.assertEqual(staple["qty"], 4)

    def test_no_spicy_group_has_no_spicy_item(self):
        block = next(b for b in self.r["table"] if b["group"]["key"] == "no_spicy")
        for l in block["lines"]:
            self.assertFalse(l["item"]["spicy"], l["item"]["name"])

    def test_everyone_has_staple(self):
        total_people = sum(b["group"]["count"] for b in self.r["table"])
        self.assertEqual(total_people, 6)

    def test_every_line_has_reason(self):
        for l in [x for b in self.r["table"] for x in b["lines"]] + self.r["shared"]:
            self.assertTrue(l["reason"].strip(), l["item"]["name"])

    def test_downgrade_note_recorded(self):
        self.assertTrue(any("降级" in n for n in self.r["notes"]))


class TestBudgetRepair(unittest.TestCase):
    """预算修复回路"""

    def test_tight_budget_two_people(self):
        r = plan(2, 30)
        self.assertTrue(r["feasible"])
        self.assertLessEqual(r["total"], 30)

    def test_generous_budget_adds_share(self):
        r = plan(4, 200)
        self.assertTrue(r["feasible"])
        self.assertLessEqual(r["total"], 200)
        self.assertTrue(any(l["item"]["category"] == "share" for l in r["shared"]))

    def test_infeasible_budget_flags_warning(self):
        r = plan(1, 10)
        self.assertFalse(r["feasible"])
        self.assertTrue(r["warnings"])


class TestGroupConstraints(unittest.TestCase):
    """分组硬约束"""

    def test_all_vegetarian(self):
        r = plan(4, 200, 0, 4)
        self.assertTrue(r["feasible"])
        for b in r["table"]:
            for l in b["lines"]:
                self.assertTrue(l["item"]["vegetarian"], l["item"]["name"])

    def test_vegetarian_with_tight_budget_still_feasible(self):
        r = plan(6, 150, 0, 2)
        self.assertTrue(r["feasible"])
        self.assertLessEqual(r["total"], 150)
        veg_block = next(b for b in r["table"] if b["group"]["key"] == "vegetarian")
        for l in veg_block["lines"]:
            self.assertTrue(l["item"]["vegetarian"], l["item"]["name"])

    def test_all_no_spicy(self):
        r = plan(8, 300, 8, 0)
        self.assertTrue(r["feasible"])
        for b in r["table"]:
            for l in b["lines"]:
                self.assertFalse(l["item"]["spicy"], l["item"]["name"])

    def test_mixed_large_group(self):
        r = plan(12, 400, 3, 1)
        self.assertTrue(r["feasible"])
        self.assertLessEqual(r["total"], 400)

    def test_single_person(self):
        r = plan(1, 60)
        self.assertTrue(r["feasible"])
        self.assertLessEqual(r["total"], 60)


class TestInputValidation(unittest.TestCase):
    """输入校验"""

    def test_overlapping_preferences_rejected(self):
        with self.assertRaises(ValueError):
            plan(6, 150, 4, 3)

    def test_zero_people_rejected(self):
        with self.assertRaises(ValueError):
            plan(0, 150)

    def test_zero_budget_rejected(self):
        with self.assertRaises(ValueError):
            plan(6, 0)


class TestDeterminism(unittest.TestCase):
    """确定性：同输入必须同输出"""

    def test_same_input_same_output(self):
        a = json.dumps(plan(6, 150, 2, 0), ensure_ascii=False, sort_keys=True, default=str)
        b = json.dumps(plan(6, 150, 2, 0), ensure_ascii=False, sort_keys=True, default=str)
        self.assertEqual(a, b)


class TestRenderers(unittest.TestCase):
    """四种输出格式都能渲染"""

    @classmethod
    def setUpClass(cls):
        cls.r = plan(6, 150, 2, 0)

    def test_all_formats_render(self):
        for fmt, fn in pm.RENDERERS.items():
            out = fn(self.r)
            self.assertTrue(out.strip(), fmt)

    def test_json_roundtrip(self):
        data = json.loads(pm.render_json(self.r))
        self.assertEqual(data["input"]["people"], 6)
        self.assertLessEqual(data["total"], 150)

    def test_html_contains_total(self):
        self.assertIn("149.4", pm.render_html(self.r))


if __name__ == "__main__":
    unittest.main(verbosity=2)
