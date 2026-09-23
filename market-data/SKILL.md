---
name: market-data
description: 拉取 A 股真实公开行情数据并输出数据报告（行情·日K/MA、财报、新闻公告、资金流向、强势股榜、板块榜与成分股榜、涨停板、集合竞价），供其他 skill 调用。当请求查行情、查财报、看新闻、看资金、看板块榜、看涨停或竞价数据时使用；只取数与报数，不做判定。
---

# 市场数据报告（market-data）

数据层 SKILL：统一拉取 A 股真实数据并输出数据报告，其他 SKILL 需要数据时应用本 SKILL。

## 数据能力

| 报告 | 脚本 | 数据源 | 报告内容 |
|---|---|---|---|
| 行情报告 | scripts/fetch_quote.py | 腾讯行情公开接口 | 实时报价、涨跌、成交量/换手/振幅、PE/PB/市值、涨停/跌停、MA5/10/20/60、最近N根日K（文本展示最近15根，JSON 返回完整 N 根供计算） |
| 财报报告 | scripts/fetch_fundamentals.py | 东方财富数据中心 | 最近N个报告期营收/净利及同比、毛利率、净利率、负债率、ROE、经营现金流 |
| 新闻公告报告 | scripts/fetch_news.py | 东方财富新闻搜索 + 公告 | 最近N条新闻与公告（时间/标题/来源/链接） |
| 资金流向报告 | scripts/fetch_capital_flow.py | 东方财富资金流 + 新浪资金流（备用源） | 最新交易日主力/大中小单净流入 + 近5日主力净流入；**东财资金流接口不可用时自动切新浪个股资金流**（主力净额＝大单+超大单口径，超大单/大单/中单/小单拆分标「未获取」），--source auto/eastmoney/sina |
| 强势股榜报告 | scripts/fetch_strong_stocks.py | 东方财富行情中心 + 新浪/腾讯（备用源） | 按涨跌幅排序的 Top N 强势股榜（代码/名称/现价/涨跌幅/量比/换手/成交额/振幅/PE/主力净流入/行业，标注“涨停≈”），支持板块与换手率/涨幅区间过滤（--min-turnover/--max-turnover/--min-gain/--max-gain，如 3%–5%），默认剔除 ST；**东财接口不可用时自动切新浪涨跌幅榜**（量比取腾讯快照、主力净流入取新浪资金流、行业取东财 F10 一级行业），--source auto/eastmoney/sina |
| 板块行情榜报告 | scripts/fetch_sector_boards.py | 东方财富板块行情（push2 clist）+ 腾讯板块行情（备用源） | 行业/概念板块榜——按当日涨跌幅/主力净流入/成交额/近5日/近10日涨跌幅排序（--sort），含板块指数、今日/5日/10日涨幅、领涨股（名称/代码/涨幅）、上涨/下跌家数、成交额、换手、主力净流入；支持 --type industry/concept/all、--min-up 上涨家数与 --search 板块名关键词过滤；**东财板块接口不可用时自动切腾讯板块行情（板块榜 + 板块指数日K），主力净流入照常给出**，报告标注实际数据源与口径，--source auto/eastmoney/tencent 可强制数据源，--search 未命中时列出最接近的板块名 |
| 板块成分股榜报告 | scripts/fetch_sector_leaders.py | 东方财富板块行情 + 行情中心 + 东财 F10/腾讯/新浪（备用源） | 指定板块（--board BKxxxx）成分股按当日涨跌幅/资金/成交额/近5日/近10日涨幅排序，表头附板块今日/5日/10日涨幅与领涨股；每行含现价、当日/5日/10日涨幅、换手、量比、成交额、振幅、PE、流通/总市值、主力净流入、行业并标注“涨停≈”；支持换手/涨幅/流通市值区间过滤，默认剔除 ST；**东财接口不可用时自动切备用源**——成分股名单取东财 F10「所属板块」（按 BK 代码匹配）、行情取腾讯快照、近5日/近10日涨幅按腾讯日K回算、资金取新浪资金流、行业取 F10 一级行业，板块行按成分股等权/合计自算并标注口径（F10 名单可能少于行情中心成分股全量），--source auto/eastmoney/f10 |
| 板块财务排名报告 | scripts/fetch_sector_fundamentals.py | 东方财富板块行情 + 数据中心 F10 + 腾讯/东财 F10（备用源） | 指定板块（--board BKxxxx）总市值前 N 名成分股的最新报告期财务数据（营收及同比、净利及同比、毛利率、ROE、负债率、经营现金流），按营收与按净利分别排序，供“行业龙头（基本面第一梯队）”筛选；财报固定取东财数据中心 F10，**成分股名单与板块行在东财板块接口不可用时自动切备用源**（名单取东财 F10「所属板块」、行情取腾讯快照、板块行按成分股等权自算并标注口径），--source auto/eastmoney/f10 |
| 涨停板数据报告 | scripts/fetch_limit_up.py | 东方财富涨停板专题（push2ex）+ 腾讯行情 | 涨停/跌停/炸板池与家数（含昨日对比、封板率）、连板高度与最高板（实时行情核对一字板）、昨日涨停今日表现（晋级家数/晋级率/涨跌分布/平均涨幅）、涨停股行业分布、昨日涨停股今日开盘与尾盘分类（高开/平开/低开 × 尾盘涨停/上涨/平/下跌/跌停，按行业汇总供板块强弱与分化分析）、分板块晋级与炸板统计（各行业昨日/今日涨停家数、板数结构一板~四板及以上与最高板、晋级家数与晋级率、炸板家数与炸板率）；--date 指定日期，缺省自动取最近有数据交易日；--json 额外给出 zt_rows（涨停池全量含首板）、yesterday_performance.rows（昨日涨停股全量，含当日开盘分类与尾盘状态）、zb_all_rows（炸板池全量）、yesterday_open_close（开盘与尾盘分类汇总，含分行业）与 industry_promotion（分板块晋级率/炸板率、板数结构与最高板）；涨停池口径不含 ST 与科创板 |
| 竞价数据报告 | scripts/fetch_auction.py | 腾讯行情（批量报价）+ 东方财富日K | 一批股票的集合竞价：高开幅度（今开 vs 昨收）、竞价成交额、昨日全天成交额、**竞价量占比（竞价成交额 ÷ 昨日全天成交额）**、集体分布（高开/平开/低开家数、平均与中位数高开幅度、量占比分档）、板块分组汇总，并按行情时间标注竞价/盘中/收盘后口径；--file 读「代码 昨日成交额(亿) 行业」清单，--codes 直接给代码（昨日成交额自动补齐，东财不可用时用腾讯日K估算并标 ≈），--top-board 检查昨日最高板是否天地板/跌停 |

## 使用方式

其他 SKILL 需要数据时，在工作区根目录运行本 SKILL 的脚本（路径以实际安装位置为准，如仓库内为 `market-data/scripts/...`）：

```bash
python market-data/scripts/fetch_quote.py <代码> --days 60
python market-data/scripts/fetch_fundamentals.py <代码> --periods 4
python market-data/scripts/fetch_news.py <代码> --news 5 --ann 5
python market-data/scripts/fetch_capital_flow.py <代码>
python market-data/scripts/fetch_strong_stocks.py --top 20 --min-turnover 5 --max-turnover 30
python market-data/scripts/fetch_strong_stocks.py --min-gain 3 --max-gain 5 --top 50
python market-data/scripts/fetch_strong_stocks.py --top 20 --source sina
python market-data/scripts/fetch_sector_leaders.py --board BK1151 --top 30 --source f10
python market-data/scripts/fetch_capital_flow.py sh600410 --source sina
python market-data/scripts/fetch_sector_boards.py --type concept --sort change --top 15 --min-up 5
python market-data/scripts/fetch_sector_boards.py --type industry --sort gain5 --top 15
python market-data/scripts/fetch_sector_boards.py --type concept --search 液冷 --top 5
python market-data/scripts/fetch_sector_boards.py --type all --search 风电 --sort flow --top 5
python market-data/scripts/fetch_sector_boards.py --type industry --sort flow --source tencent
python market-data/scripts/fetch_sector_leaders.py --board BK1151 --top 30 --min-turnover 5 --max-turnover 10 --min-float-cap 50 --max-float-cap 200
python market-data/scripts/fetch_sector_fundamentals.py --board BK1151 --top 12
python market-data/scripts/fetch_sector_fundamentals.py --board BK1151 --top 12 --source f10
python market-data/scripts/fetch_limit_up.py
python market-data/scripts/fetch_limit_up.py --date 20260908
python market-data/scripts/fetch_auction.py --codes sh600410,sz002970
python market-data/scripts/fetch_auction.py --file report/涨停板评估/2026-09-15-竞价清单.txt --top-board sz002790
```

代码格式：`sh600410` / `sz002491` / `bj920002`（sh=沪、sz=深、bj=北交所）。脚本默认输出中文报告，`--json` 输出 JSON；不产生任何缓存文件。

备用取数与切源：scripts/fallback_sources.py 汇总腾讯行情/日K、新浪行情榜与个股资金流、东财 F10「所属板块」（按 BK 代码取成分股）与一级行业，供上述脚本在东财行情中心接口（push2 clist / stock 系列）不可用时自动切换；其他 skill 不直接调用该模块，只读各报告脚本的输出。

竞价数据报告（fetch_auction.py）按批接收 sh/sz/bj 前缀代码，输出可直接用于打板竞价评估（9:25–9:30 运行为竞价口径）。强势股榜、fetch_sector_leaders / fetch_sector_fundamentals 与 fetch_limit_up 返回的个股代码已是 sh/sz/bj 前缀格式，可直接传给 fetch_quote / fetch_capital_flow / fetch_news 做个股细审。板块代码为 BK 前缀（如 BK1151），由 fetch_sector_boards 输出，经 `--board` 传给 fetch_sector_leaders / fetch_sector_fundamentals；分析“活跃板块/题材”时先跑 fetch_sector_boards 确定 BK 代码，再下钻成分股与财务榜。

## 硬性规则

- 真实数据：接口拉不到就明确报错，禁止编造价格、PE/PB、营收、利润、新闻、公告或资金流向。
- 数据日期：报告中引用数据必须标注数据时间（行情报告含数据时间，其余报告注明数据来源与报告期/交易日）。
- 单位与口径：以脚本输出为准——行情量为手、资金流为正负元（展示为万元）、财报为报告期累计值，同比须与去年同期比。板块行情榜主源为东财（主力净流入＝f62）、备用源为腾讯（主力净流入＝zljlr，万元换算亿；近10日涨幅按板块指数收盘价回算），**备用源下板块代码是腾讯板块代码不是 BK 代码**，引用时必须标注实际数据源，跨源数值不得混用于同一张对比表（今日一个源、基准日另一个源时不能直接算比例）。
- 先切源再判缺失：板块行情榜、板块成分股榜、板块财务排名、强势股榜、资金流向五类取数都按 auto 自动切备用源，两源都失败才明确报错；单次拉取失败不得直接让上层把某格记为「未知」。
- 备用源口径差异必须标注：新浪资金流是主力净额（大单+超大单）而非东财主力净流入；东财 F10 成分股是「所属板块」口径、可能少于行情中心成分股全量；强势股榜备用源的行业是东财一级行业。跨源数值不得混用于同一张对比表，报告与引用处都要写清数据源。
- 不构成投资建议：报告末尾注明数据来源。
