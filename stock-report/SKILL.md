---
name: stock-report
description: A股交易日每日复盘（午间 11:45 精简版 / 收盘 15:15 完整版）：持仓检查（$stock-review）、观察池审视（$watchlist-review，逐只调用 $stock-analysis）、按复盘模板生成复盘内容并写入 report/（午间 report/股票午间复盘-YYYY-MM-DD.md；收盘 report/股票每日复盘-YYYY-MM-DD-收盘.md）；收件人从 AGENTS.md「邮件」章节读取，有邮箱时再经 $agently-mail 发送对应主题邮件。当用户请求“每日复盘 / 午间复盘 / 收盘复盘 / 生成复盘报告 / 发送复盘邮件”或定时任务触发时使用；非交易日直接结束，不读写文件、不调用行情与邮件接口。
---

# 股票每日复盘（stock-report）

## 触发与前置

- 触发：A股交易日 11:45（午间复盘）与 15:15（收盘复盘）定时触发，或用户直接请求。
- 前置：当日为 A 股交易日（非周末、非法定节假日）且当前时间 ≥ 触发时间；非交易日直接结束——不读写文件、不调用行情与邮件接口。
- 依赖：ACCOUNT.md、POSITION.md、WATCHLIST.md、stocks/<股票名称-股票代码>/、AGENTS.md（邮件章节取收件人）；协作 skill：$stock-review（持仓检查）、$watchlist-review（观察池审视，内部逐只调用 $stock-analysis）、$agently-mail（有邮箱时发送）、$market-data（行情/新闻/资金数据）。

## 两种模式

| 步骤 | 午间复盘（11:45） | 收盘复盘（15:15） |
|---|---|---|
| 1. 持仓检查 | $stock-review 精简输出；不写 STOCK-REVIEW.md | $stock-review 完整输出；写入 stocks/<股票名称-股票代码>/STOCK-REVIEW.md，回写 POSITION.md 现价与浮动盈亏 |
| 2. 观察池审视 | $watchlist-review：逐只调用 $stock-analysis 审视并回写 WATCHLIST.md | 同左 |
| 3. 生成复盘内容 | 按 references/report-template.md「午间版」 | 按 references/report-template.md「收盘版」 |
| 4. 输出与发送 | 写入 report/股票午间复盘-YYYY-MM-DD.md；AGENTS.md 有邮箱 → $agently-mail 发送（主题：股票午间复盘 YYYY-MM-DD） | 写入 report/股票每日复盘-YYYY-MM-DD-收盘.md；有邮箱 → 发送（主题：股票每日复盘（YYYY-MM-DD 收盘）） |

## 流程

1. 持仓检查：读 POSITION.md 全部持仓，逐只执行 $stock-review——价格位置（盘中/收盘）、量能（半日/全日）、止损/止盈/时间止损是否触发；触发平仓规则的持仓在报告中明确标注「建议平仓」（仅提示，不下单）。
2. 观察池审视：两种模式都执行 $watchlist-review——逐只调用 $stock-analysis 审视池内标的，按结论更新 WATCHLIST.md 状态（等待/信号触发/移除）；触发信号的标的提示用 $position-management 复核仓位；观察池为空时输出“观察池为空”并跳过。
3. 生成复盘内容：读取 references/report-template.md 对应版本，填充 {{...}} 字段；当天没有的内容删行；数字标注数据时间；证据先行，拿不到数据明确标注、不编造。
4. 输出与发送：report/ 不存在则创建；先把正文写入 report/（午间 report/股票午间复盘-YYYY-MM-DD.md；收盘 report/股票每日复盘-YYYY-MM-DD-收盘.md）；再从 AGENTS.md「邮件」章节解析「复盘/通知邮件收件人：<邮箱>」——有邮箱 → 调用 $agently-mail 按对应主题发送该正文并记录日志（区分午间/收盘）；无邮箱 → 不调用邮件接口，报告文件即交付物。回复中告知文件位置与发送结果。

## 异常处理

- 非交易日：直接结束，不生成任何文件、不调用行情与邮件接口。
- 午间报告生成或邮件发送失败：保留报告文件并记录错误日志；不影响收盘复盘。
- 收盘报告生成或邮件发送失败：保留全部报告文件（含午间残留）并记录错误日志。
- 收件人缺失：只写 report/ 报告文件，不调用邮件接口；视为正常交付，不记失败。
- 任一环节分析异常：记录错误日志并继续；某只持仓/观察标的失败时标注失败原因，不阻塞其余标的。
- report/ 写入失败：明确报错，不把报告输出到其它位置替代。

## 硬性规则

- 不替用户下单：「建议平仓」只提示，实际卖出由用户在可交易时间执行。
- 数据必须真实：行情/新闻/资金用 $market-data 拉取，失败则标注，不编造现价。
- 持仓期间不调整既定止损/止盈；触发规则按 POSITION.md 记录执行。
- 报告必落盘：复盘结果一律先写入 report/ 报告文件（午间/收盘文件名规则固定）。
- 收件人不写死：一律从 AGENTS.md 读取；AGENTS.md 无邮箱时不调用邮件接口，报告文件即正常交付。
- 不执行清理步骤：本次任务不删除 report/ 交付文件，也不维护临时草稿/缓存清理流程。

## 参考资料

- references/report-template.md — 午间版与收盘版合并的复盘报告模板（生成复盘内容时读对应版本，同一正文既落盘 report/ 也可作邮件正文）。
