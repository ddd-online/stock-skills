---
name: setup-stock-workspace
description: 一次性初始化股票交易工作区：创建目录结构（ACCOUNT.md、NOTES.md、POSITION.md、stocks/股票代码/ 下的 STOCK-REVIEW.md、TRADE-RULES.md、TRADE-SUMMARY.md 与 history/YYYY-MM-DD/），填入种子模板，并把目录与文件规则写入 AGENTS.md，让之后的 agent 打开项目就知道如何归档交易。当用户请求“初始化股票交易项目/新建交易工作区/搭建炒股 workspace”时使用；一个项目只运行一次。
---

# Setup Stock Workspace

初始化股票交易工作区的目录、文件，并把规则写入 AGENTS.md。这是提示驱动的一次性流程：探索 → 确认 → 初始化 → 写入 AGENTS.md → 完成。

## 1. 探索

检查目标项目现状，不假设：

- 目标目录是否存在？是空目录还是已有文件？
- AGENTS.md 是否存在？是否已有 `## 股票交易工作区` 区块？
- 是否已有 ACCOUNT.md / POSITION.md / stocks/ 等初始化痕迹？
- 若已初始化：告知用户这是一次性设置，询问是否需要重置；不擅自覆盖已有文件。

## 2. 确认

向用户展示模板映射（见 [references/template-map.md](./references/template-map.md)），逐项确认：

- 目录/文件用途（8 项）是否符合预期
- 股票代码文件夹命名：纯数字代码（如 600410）
- AGENTS.md：存在时原地更新 `## 股票交易工作区` 区块；不存在则新建

## 3. 初始化

按 template-map.md 创建目录和文件（用 assets/ 下的种子模板，保留字段结构）：

```
<项目根>/
├── ACCOUNT.md          ← assets/ACCOUNT.md
├── NOTES.md            ← assets/NOTES.md
├── POSITION.md         ← assets/POSITION.md
└── stocks/                     ← 初始为空，不建占位文件夹
```

规则：

- 首次实盘交易某只股票时，创建 stocks/<纯数字代码>/（如 600410），放入 assets/stocks/ 的三个种子模板 + history/ 目录
- 清仓时：创建 history/YYYY-MM-DD/，把 STOCK-REVIEW.md / TRADE-RULES.md / TRADE-SUMMARY.md **移动**到该目录（归档=移动，工作区不留副本）；下次交易该股时重新生成三个文件
- 已存在的文件不覆盖；空文件用种子模板填充；全部 UTF-8 编码

## 4. 写入 AGENTS.md

在 AGENTS.md 中写入 `## 股票交易工作区` 区块（存在则原地更新，不重复追加；保留用户其他内容）：

```markdown
## 股票交易工作区

### 目录与文件规则

- ACCOUNT.md：账户总览（本金、现金、总盈亏、资金变化记录），每次资金变动后更新
- NOTES.md：复盘后沉淀的知识、教训、准则，逐条记录
- POSITION.md：当前持仓状态（仓位、成本、止损止盈），买入/卖出后立即更新
- stocks/<代码>/：每只股票一个文件夹（纯数字代码）
  - STOCK-REVIEW.md：个股复盘（stock-review 的结果写入）
  - TRADE-RULES.md：个股交易规则（trade-rules-generate 生成，交易期间严格遵守）
  - TRADE-SUMMARY.md：个股交易总结（清仓时写入一次）
  - history/YYYY-MM-DD/：清仓后将上述三个文件**移动**到该日期目录归档（工作区不留副本，下次交易重新生成）

stocks/ 初始为空，不建占位文件夹；首次交易某股时创建其代码文件夹。

### 交易生命周期

分析（stock-analysis）→ 建仓（position-management，更新 POSITION.md）→ 每日复盘（stock-review）→ 清仓 → 写 TRADE-SUMMARY.md → 归档 history/日期/ → 复盘结论沉淀到 NOTES.md

### 数据源

- 行情：腾讯公开接口（各 skill 的 scripts/fetch_quote.py）
- 财报：东方财富 datacenter（scripts/fetch_fundamentals.py）

### 纪律

- 教学演示不构成投资建议；不替用户做买卖决定
- 止损无条件执行；跳空破位/暴跌日不等收盘；接受滑点
- 每笔真实交易必须归档：POSITION.md → TRADE-SUMMARY.md → history
```

## 5. 完成

告诉用户初始化完成，之后的 agent 打开项目会读取 AGENTS.md 并知道如何归档交易。说明：再次运行本 skill 仅用于重置，会先确认、不擅自覆盖。

## 参考资料

- references/template-map.md — 目录/文件用途与归档规则表

## 资产（种子模板）

- assets/ACCOUNT.md、assets/NOTES.md、assets/POSITION.md — 根级种子模板
- assets/stocks/STOCK-REVIEW.md、assets/stocks/TRADE-RULES.md、assets/stocks/TRADE-SUMMARY.md — 个股种子模板
