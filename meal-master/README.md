# 干饭指挥官 · Meal Master

> **一句话说明：输入人数、预算和饮食偏好，秒出一桌不超预算的搭配方案——每一项为什么这么选，都写得明明白白。**

WaytoAGI「1024 超能 Coding 周末」**用餐赛道**参赛作品。
赛道题：*把饭点安排明白——6 个人、预算 150 块、其中 2 人不吃辣，让 AI 搭配一桌。*

## 官方题实测（评委同款输入）

```
$ python scripts/plan_meal.py --demo
```

| 人群 | 餐品 | 数量 | 小计 |
|---|---|---|---|
| 无辣不欢 · 4 人 | 麦辣鸡腿堡三件套（券后） | ×4 | ¥91.6 |
| 不吃辣 · 2 人 | 1+1 随心配（麦香鸡堡+中可口可乐） | ×2 | ¥25.8 |
| 不吃辣 · 2 人 | 中薯条 | ×2 | ¥26 |
| 全桌共享 | 圆筒冰淇淋 | ×1 | ¥6 |

**合计 ¥149.4 / ¥150 · 结余 ¥0.6 · 预算利用率 99.6%**

关键决策记录（引擎自动生成）：

- 麦辣三件套券后 ¥22.9（原价 ¥39.5），是全菜单最低的「堡+薯+饮料」组合，4 位无辣不欢直接用；
- 不吃辣组最便宜的完整套餐需 ¥33.5/人，会击穿全桌预算 → 切换 ¥12.9 红区 1+1 组合保底（有堡有饮料），把预算让给小食；
- 该组合不含小食 → 补中薯条，做到全桌人人有薯；
- 结余 ¥6.6 → 加 1 个圆筒收尾。

## 快速开始

零第三方依赖，Python 3.8+ 直接跑：

```bash
# 官方题
python scripts/plan_meal.py --demo

# 自定义：8 人 · 300 元 · 3 人不吃辣 · 1 人素食
python scripts/plan_meal.py --people 8 --budget 300 --no-spicy 3 --vegetarian 1

# 生成可投屏的结果页（HTML）
python scripts/plan_meal.py --people 6 --budget 150 --no-spicy 2 --format html --out result.html

# 结构化数据（JSON）
python scripts/plan_meal.py --demo --format json
```

输出格式：`text`（默认）/ `md` / `json` / `html`。

## 它是怎么搭配的

1. **分组**：按饮食偏好拆成「无辣不欢 / 不吃辣 / 素食」，硬约束过滤（不吃辣组绝不出现辣堡，素食组绝不出现肉）；
2. **主食**：每组选「饱腹度最高中价格最低」的套餐；
3. **预算修复**：全桌超支时，按「让位最多」原则把整组主食降级到红区 1+1 组合，循环直到可行；
4. **补齐**：缺饮品补饮品、缺小食补招牌小食（中薯条优先）；
5. **收尾**：结余先买分享装（4 人以上）撑氛围，再 cheapest-first 买甜品；
6. **记账**：全程不击穿预算；每一次降级/切换都写进「引擎决策记录」。

设计原则：**确定性**（同输入同输出）、**可解释**（每项带依据）、**零依赖**（标准库）。

## 工程结构

```
meal-master/
├── SKILL.md                        # WorkBuddy 技能定义（触发词+工作流+契约）
├── scripts/
│   └── plan_meal.py                # 搭配引擎（CLI，零依赖）
├── references/
│   └── menu_snapshot.json          # 麦当劳菜单快照（2026-10-25，含券后价/辣素标签/饱腹度）
└── tests/
    ├── test_plan_meal.py           # 回归测试 22 条
    └── mutation_check.py           # 变异校验（3 个关键变异全被杀）
```

## 质量证据

| 项 | 结果 |
|---|---|
| 回归测试 | 22/22 通过（官方题 / 预算修复 / 分组约束 / 边界输入 / 确定性 / 四格式渲染） |
| 变异校验 | baseline 全绿 → 3/3 变异被杀（禁用预算修复 7 失败 / 去掉辣过滤 3 失败 / 小食补齐失效 2 失败）→ 还原复绿 |
| 官方题 | ¥149.4 / ¥150，利用率 99.6%，全项带依据 |

复现：`python tests/test_plan_meal.py` → `python tests/mutation_check.py`

## 麦当劳 MCP 升级路径（可选）

基座为本地菜单快照，可离线运行。接入官方 MCP 后可升级为「实时菜单 + 自动领券 + 真实下单」：

1. 前往 <https://open.mcd.cn/mcp> 手机号登录，控制台激活 MCP Token；
2. MCP Client 配置（Streamable HTTP）：
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
3. 将引擎第 2 步替换为 MCP 工具链：`query-meals` 拉菜单 → `available-coupons` 领券 →
   `calculate-price` 核价 → `create-order` 下单；本地快照降级为兜底。

> 本次参赛版本以本地快照为数据源（赛场无 Token 环境保证可跑）；
> 快照价格为 2026-10-25 可见的活动价，正式下单以小程序/MCP 实时价为准。

## 参赛信息

- 赛事：WaytoAGI 全国 AI 切磋大会「1024 超能 Coding 周末」· 用餐赛道
- 赛道要求：做一个能实际运行的用餐 Skill，讲清人数、预算和饮食偏好，评委现场点一单看结果
- 制作工具：WorkBuddy（本仓库全部代码、测试与文档均在 WorkBuddy 会话中产出，附开发对话记录）
- 作者：王乾辉（游承峰工作室）
