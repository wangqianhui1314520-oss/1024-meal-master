---
name: meal-master
display_name: 干饭指挥官
display_name_en: Meal Master
description: 当用户需要安排一顿饭时使用——「今天吃什么」「聚餐怎么点」「N个人X块钱怎么搭配」「有人不吃辣/有素食」。输入人数、预算、饮食偏好，立即产出一桌可执行的就餐搭配方案（含每人明细、总价、预算利用率、逐项选择依据），全程不超预算。用餐场景的点餐决策、麦当劳搭配、工作餐安排均触发本技能。
description_zh: 人数+预算+饮食偏好，秒出一桌不超预算的搭配方案，每项选择都有依据
description_en: Turn headcount, budget and dietary preferences into an explainable meal plan that never exceeds budget
examples_zh:
  - "6 个人，150 块，2 人不吃辣，帮我配一桌"
  - "今天吃什么？8 个人 300 块，有 1 个素食"
  - "安排一下明天部门 12 人的午餐，预算 400"
examples_en:
  - "Plan a meal for 6 people, 150 CNY, 2 no-spicy"
  - "What should we eat? 8 people, 300 CNY, 1 vegetarian"
  - "Lunch for 12, budget 400"
version: 1.0.0
author: 游承峰工作室（王乾辉）
---

# 干饭指挥官 · 用餐搭配技能

## 能力定义

把「今天吃什么」这个模糊问题，变成一张**可执行、不超预算、每项有依据**的桌单。

## 输入契约

| 字段 | 必填 | 说明 | 缺省 |
|---|---|---|---|
| 人数 people | 是 | 正整数 | 无 |
| 预算 budget | 是 | 总预算（元），正数 | 无 |
| 不吃辣人数 no_spicy | 否 | 0 ~ people | 0 |
| 素食人数 vegetarian | 否 | 0 ~ people，与不吃辣人数互不重叠 | 0 |

约束：`no_spicy + vegetarian ≤ people`，否则向用户说明并请求修正，**不得**自行臆造数字。

## 执行工作流

1. **解析需求**：从用户原话提取四个参数；有缺漏先问，不要猜。
2. **运行引擎**（零依赖，Python 3.8+）：
   ```bash
   python scripts/plan_meal.py --people <N> --budget <B> [--no-spicy K] [--vegetarian K] [--format text|md|json|html]
   ```
   官方演示题（赛场同款）：`python scripts/plan_meal.py --demo`
3. **呈现桌单**：按人群分组列出餐品×数量×小计，附每项「选择依据」，末尾给出
   合计 / 预算 / 结余 / 预算利用率，以及引擎的降级决策记录。
4. **解释关键决策**：若发生了预算降级（如不吃辣组从套餐切到 1+1 红区组合），
   必须向用户说明原因——这是本技能的核心价值：**钱花得明白**。
5. **兜底与边界**：
   - 预算过低无法可行搭配时，输出最接近方案并明确警告，建议最低可行预算；
   - 菜单为本地快照（references/menu_snapshot.json，2026-10-25），
     向用户声明正式价格以下单时小程序/MCP 实时价为准。

## 输出契约

- 终端：人类可读桌单（默认 text 格式）；
- 文件：`--format html` 产出可投屏的结果页，`--format json` 产出结构化数据；
- 硬性要求：**总价 ≤ 预算**（除显式警告的不可行场景）；每一项都有非空依据；
  同输入必须同输出（确定性）。

## 搭配策略（引擎内部逻辑，仅供解释时引用）

1. 按饮食偏好分组：无辣不欢 / 不吃辣 / 素食，硬约束过滤辣味与非素项；
2. 每组选「饱腹度最高中价格最低」的套餐作为主食；
3. 全桌超支时，按「让位最多」原则把整组主食降级到红区 1+1 组合，循环至可行；
4. 补齐：缺饮品的补饮品，缺小食的补招牌小食（中薯条优先）；
5. 收尾：结余先买分享装（4 人以上），再 cheapest-first 买甜品；
6. 全程记账，任一步不得击穿预算。

## 麦当劳 MCP 升级路径（可选）

本技能基座为本地菜单快照，可离线运行。如需实时菜单/价格/优惠券与真实下单，
可申请麦当劳中国 MCP Token（https://open.mcd.cn/mcp ，手机号登录→控制台→激活），
在 MCP Client 中配置：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_MCP_TOKEN" }
    }
  }
}
```

随后将本技能工作流第 2 步的本地引擎调用，替换为 MCP 工具链
（query-meals 拉菜单 → available-coupons 领券 → calculate-price 核价 →
create-order 下单），references/menu_snapshot.json 仅作兜底。

## 质量护栏

- 回归测试：`python tests/test_plan_meal.py`（22 条，覆盖官方题/预算修复/分组约束/边界/确定性/渲染）；
- 变异校验：`python tests/mutation_check.py`（3 个关键变异全被杀，基线复绿）；
- 修改引擎或菜单数据后，必须重跑以上两项，全绿方可交付。
