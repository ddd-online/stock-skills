# 模板目录与文件用途

| # | 路径 | 用途 |
|---|---|---|
| 1 | ACCOUNT.md | 账户总览（本金/现金/总盈亏/累计支取/实际可用资产/资金变化记录）+ 交易费用设置 + 资金规则（现金储备≥实际可用资产30%、单笔预算≤实际可用资产2%、当前档位） |
| 2 | NOTES.md | 复盘沉淀的知识、教训、准则 |
| 3 | POSITION.md | 当前持仓总览表（股票/手数/成本/现价/止损止盈/时间止损/浮动盈亏）+ 持仓明细（每只持仓一节：买入日期/买入成本/现价浮动盈亏/止损/止盈/时间止损/买入理由/备注） |
| 4 | MUST.md | 个人交易风格与必守规则，所有 SKILL 必须遵守 |
| 5 | WATCHLIST.md | 观察池（标的/触发条件/预案/状态），由 stock-analysis 判定进出，watchlist-review 定期审视 |
| 6 | TRADE-STATS.md | 账户级交易统计：每笔清仓填一行（日期/股票/方向/价格/盈亏/是否符合系统/违规说明），每 5-10 笔结算胜率/平均盈亏/期望值/最大回撤 |
| 7 | stocks/<股票名称-股票代码>/ | 每只股票一个文件夹，文件夹名=股票名称-股票代码（如 华胜天成-600410），名称以 POSITION.md / $market-data 返回为准，首次交易该股时创建 |
| 8 | stocks/<股票名称-股票代码>/STOCK-REVIEW.md | 个股交易计划 + 每日检查记录：position-management 建仓时创建并写入交易计划；stock-review 持仓期间追加每日检查行（stock-analysis 六格清单分析交接后不落盘；平仓复盘只写 TRADE-SUMMARY.md） |
| 9 | stocks/<股票名称-股票代码>/TRADE-SUMMARY.md | 个股交易记录与总结：逐笔追加交易记录，清仓补写盈亏与总结；由 position-management 维护，清仓后归档 |
| 10 | stocks/<股票名称-股票代码>/history/YYYY-MM-DD/ | 清仓归档目录：把 STOCK-REVIEW.md、TRADE-SUMMARY.md 移动到此 |

## 命名与生命周期

- 股票文件夹：股票名称-股票代码（如 华胜天成-600410），首次实盘交易该股时创建，不建"股票名称-股票代码"占位文件夹
- history 目录：清仓当日创建（YYYY-MM-DD 格式）
- 归档动作：清仓 → 平仓复盘只写 TRADE-SUMMARY.md（补写本次盈亏与总结）→ STOCK-REVIEW.md / TRADE-SUMMARY.md **移动**到 history/日期/（归档=移动，工作区不留副本；下次建仓该股时由 position-management 重新创建）
- 写入规则：已存在的文件不覆盖；空文件用种子模板填充
