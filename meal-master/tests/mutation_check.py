# -*- coding: utf-8 -*-
"""mutation check: 证明测试套件能杀死关键变异"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "scripts" / "plan_meal.py"
PY = sys.executable

backup = TARGET.read_bytes()


def run_tests():
    p = subprocess.run([PY, str(ROOT / "tests" / "test_plan_meal.py")],
                       capture_output=True, text=True, timeout=180)
    return p.returncode, p.stdout + p.stderr


results = []
try:
    rc, out = run_tests()
    results.append(("baseline", rc, out.count("FAIL:") + out.count("ERROR:")))

    src = backup.decode("utf-8")

    # 变异 1：禁用预算修复回路 -> 官方题必然超支
    m1 = src.replace("while self._total() > self.budget:",
                     "while False and self._total() > self.budget:")
    assert m1 != src, "mutation 1 did not apply"
    TARGET.write_text(m1, encoding="utf-8")
    rc, out = run_tests()
    results.append(("m1_no_repair", rc, out.count("FAIL:") + out.count("ERROR:")))
    TARGET.write_bytes(backup)

    # 变异 2：去掉辣味过滤 -> 不吃辣组会混入辣堡
    m2 = src.replace('    if not allow_spicy and item.get("spicy"):\n        return False\n', "")
    assert m2 != src, "mutation 2 did not apply"
    TARGET.write_text(m2, encoding="utf-8")
    rc, out = run_tests()
    results.append(("m2_no_spicy_filter", rc, out.count("FAIL:") + out.count("ERROR:")))
    TARGET.write_bytes(backup)

    # 变异 3：小食补齐失效 -> 每人有薯断言的守卫
    m3 = src.replace('if "snack" not in cats:', 'if False and "snack" not in cats:')
    assert m3 != src, "mutation 3 did not apply"
    TARGET.write_text(m3, encoding="utf-8")
    rc, out = run_tests()
    results.append(("m3_no_snack_topup", rc, out.count("FAIL:") + out.count("ERROR:")))
    TARGET.write_bytes(backup)

    rc, out = run_tests()
    results.append(("restored", rc, out.count("FAIL:") + out.count("ERROR:")))
finally:
    TARGET.write_bytes(backup)

print("== mutation results ==")
for name, rc, fails in results:
    print(f"{name:24s} rc={rc} failed={fails}")

base_rc = results[0][1]
mutants_killed = all(r[1] != 0 and r[2] > 0 for r in results[1:4])
restored_ok = results[-1][1] == 0
print()
print(f"baseline_green      : {base_rc == 0}")
print(f"all_mutants_killed  : {mutants_killed}")
print(f"restored_green      : {restored_ok}")
ok = base_rc == 0 and mutants_killed and restored_ok
print("VERDICT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
