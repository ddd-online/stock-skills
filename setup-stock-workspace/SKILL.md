---
name: setup-stock-workspace
description: 一次性初始化股票交易工作区：创建目录结构（ACCOUNT.md、NOTES.md、POSITION.md、MUST.md、WATCHLIST.md、TRADE-STATS.md、stocks/<纯数字代码>/ 下的 TRADE-RULES.md、TRADE-SUMMARY.md 与 history/YYYY-MM-DD/；STOCK-REVIEW.md 由 stock-review 首次检查时创建），收集交易费用设置（佣金费率、最低佣金、印花税、过户费）与资金规则（现金储备≥30%、单笔预算≤2%、当前档位）写入 ACCOUNT.md，收集复盘/通知邮件收件人写入 AGENTS.md，填入种子模板，并把目录与文件规则写入 AGENTS.md，让之后的 agent 打开项目就知道如何归档交易。MUST.md 默认只有一个标题，由用户自行填写个人交易风格与必须遵守的规则，所有 SKILL 必须遵守；WATCHLIST.md 是观察池（标的/触发条件/预案/状态）；TRADE-STATS.md 是交易统计表（每笔清仓填一行，每 5-10 笔结算四指标）。当用户请求“初始化股票交易项目/新建交易工作区/搭建炒股 workspace”时使用；一个项目只运行一次。
---

# Setup Stock Workspace

初始化股票交易工作区的目录、文件，并把规则写入 AGENTS.md。这是提示驱动的一次性流程：探索 → 确认 → 初始化 → 写入 AGENTS.md → 完成。

## 触发与前置条件

- 触发：用户请求初始化股票交易工作区。
- 前置：一个项目只初始化一次；已初始化时仅用于重置，必须经用户确认，不擅自覆盖已有文件。
- 产出：目录与种子文件 + AGENTS.md 中的 `## 股票交易工作区` 区块；其他 SKILL 均依赖本 SKILL 初始化的工作区文件。

## 1. 探索

检查目标项目现状，不假设：

- 目标目录是否存在？是空目录还是已有文件？
- AGENTS.md 是否存在？是否已有 `## 股票交易工作区` 区块？
- 是否已有 ACCOUNT.md / POSITION.md / stocks/ 等初始化痕迹？
- 若已初始化：告知用户这是一次性设置，询问是否需要重置；不擅自覆盖已有文件。

## 2. 确认

向用户展示模板映射（见 [references/template-map.md](./references/template-map.md)），逐项确认：

- 目录/文件用途（11 项）是否符合预期
- 股票代码文件夹命名：纯数字代码（如 600410）
- AGENTS.md：存在时原地更新 `## 股票交易工作区` 区块；不存在则新建
- 交易费用设置（用于每次交易的费用计算，写入 ACCOUNT.md）：
  - 佣金费率：默认万2.5，向用户确认券商实际费率（如万1.5）
  - 是否有最低佣金：默认有、最低5元/笔；无则填“无”
  - 印花税：默认卖出 0.05%（规则固定，可调整）
  - 过户费：默认 0.01‰（规则固定，可调整）
  - 拿不到用户答案时用默认值，并在 ACCOUNT.md 标注“默认值，待确认”
- 复盘/通知邮件收件人：询问用户邮箱地址（用于 stock-report 每日复盘邮件；写入 AGENTS.md「邮件」章节）；用户不提供则写“未提供”，复盘时自动改为生成 report/ 报告文件

## 3. 初始化

按 template-map.md 创建目录和文件（用 assets/ 下的种子模板，保留字段结构）：

```
<项目根>/
├── ACCOUNT.md          ← assets/ACCOUNT.md
├── NOTES.md            ← assets/NOTES.md
├── POSITION.md         ← assets/POSITION.md
├── MUST.md             ← assets/MUST.md（默认只有一个标题，用户自行编辑）
├── WATCHLIST.md        ← assets/WATCHLIST.md（观察池：标的/触发条件/预案/状态）
├── TRADE-STATS.md      ← assets/TRADE-STATS.md（交易统计表：每笔清仓填一行，每5-10笔结算四指标）
└── stocks/                     ← 初始为空，不建占位文件夹
```

规则：

- 首次实盘交易某只股票时，创建 stocks/<纯数字代码>/（如 600410），放入 assets/stocks/ 的两个种子模板（TRADE-RULES.md、TRADE-SUMMARY.md）+ history/ 目录；STOCK-REVIEW.md 由 stock-review 首次检查时按自己的模板创建
- 清仓时：创建 history/YYYY-MM-DD/，把 STOCK-REVIEW.md / TRADE-RULES.md / TRADE-SUMMARY.md **移动**到该目录（归档=移动，工作区不留副本）；下次交易该股时重新生成（STOCK-REVIEW.md 由 stock-review 创建，TRADE-RULES.md / TRADE-SUMMARY.md 由本 SKILL 种子模板生成）
- 已存在的文件不覆盖；空文件用种子模板填充；全部 UTF-8 编码
- 按确认结果填写 ACCOUNT.md 的交易费用设置；缺失或未确认的项用默认值并标注“默认值，待确认”
- report/ 为复盘报告输出目录（初始为空）：AGENTS.md 未配置邮箱时，stock-report 将复盘邮件正文以 md 文件保存到此处

## 4. 写入 AGENTS.md

在 AGENTS.md 中写入 `## 股票交易工作区` 区块（存在则原地更新，不重复追加；保留用户其他内容），其中「邮件」章节按确认结果填入收件人邮箱；用户未提供则写“未提供”：

```markdown
## 股票交易工作区

### 目录与文件规则

- ACCOUNT.md：账户总览（本金、现金、总盈亏、资金变化记录）+ 交易费用设置（佣金费率/最低佣金/印花税/过户费）+ 资金规则（现金储备≥30%、单笔预算≤2%、当前档位），每次资金变动后更新
- NOTES.md：复盘后沉淀的知识、教训、准则，逐条记录
- POSITION.md：当前持仓状态（仓位、成本、止损止盈），买入/卖出后立即更新
- MUST.md：个人交易风格与必须遵守的规则（默认只有一个标题，用户自行编辑），所有 SKILL 必须遵守
- WATCHLIST.md：观察池（标的/类型/体检结论/触发条件/止损止盈预案/状态），由 stock-analysis 判定进出池，watchlist-review 定期审视更新
- TRADE-STATS.md：交易统计表（每笔清仓填一行；每 5-10 笔结算胜率/平均盈亏/期望值/最大回撤，用统计判断系统是否有效），由 position-management 更新
- report/：复盘报告输出目录（AGENTS.md 未配置邮箱时，复盘邮件正文以 md 文件保存到此处），由 stock-report 写入
- stocks/<纯数字代码>/：每只股票一个文件夹（纯数字代码）
  - STOCK-REVIEW.md：个股每日检查（stock-review 首次检查时按自己的模板创建并写入）
  - TRADE-RULES.md：个股交易规则（trade-rules-generate 生成，交易期间严格遵守）
  - TRADE-SUMMARY.md：个股交易总结（清仓时写入一次）
  - history/YYYY-MM-DD/：清仓后将上述三个文件**移动**到该日期目录归档（工作区不留副本，下次交易重新生成）

stocks/ 初始为空，不建占位文件夹；首次交易某股时创建其代码文件夹。

### 交易生命周期

分析（stock-analysis）→ 生成规则（trade-rules-generate）→ 建仓（position-management，更新 POSITION.md）→ 每日检查（stock-review，触发时给出平仓结论）→ 用户清仓 → 平仓总结（position-management 按卖出价结算，写 TRADE-SUMMARY.md → 更新 TRADE-STATS.md 四指标 → 归档 history/日期/）→ 复盘结论沉淀到 NOTES.md

### 数据源

- 行情、财报、新闻公告、资金流向等真实数据统一由 $market-data 拉取

### 邮件

- 复盘/通知邮件收件人：{{邮箱；未提供则写“未提供”}}（通过 agently-mail 发送）

### 纪律

- 不构成投资建议；不替用户做买卖决定
- 止损无条件执行；跳空破位/暴跌日不等收盘；接受滑点
- 费用计算以 ACCOUNT.md 交易费用设置为准（佣金费率、最低佣金、印花税、过户费）
- 所有 SKILL 必须遵守 MUST.md 中的个人交易风格与规则
- 没有触发条件不建仓；观察池标的必须三要素齐全（标的、触发条件、预案）
- 每笔真实交易必须归档：POSITION.md → TRADE-SUMMARY.md → history
- 每 5-10 笔结算一次四指标（胜率、平均盈亏、期望值、最大回撤），一次只改一条规则
```

## 5. 完成

告诉用户初始化完成，之后的 agent 打开项目会读取 AGENTS.md 并知道如何归档交易。说明：再次运行本 skill 仅用于重置，会先确认、不擅自覆盖。

## 参考资料

- references/template-map.md — 目录/文件用途与归档规则表

## 资产（种子模板）

- assets/ACCOUNT.md、assets/NOTES.md、assets/POSITION.md、assets/MUST.md、assets/WATCHLIST.md、assets/TRADE-STATS.md — 根级种子模板
- assets/stocks/TRADE-RULES.md、assets/stocks/TRADE-SUMMARY.md — 个股种子模板（STOCK-REVIEW.md 模板由 stock-review 持有）
