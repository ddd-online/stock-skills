---
name: market-data
description: 拉取A股真实市场数据并输出数据报告（行情/日K/MA、财报核心指标、新闻公告、资金流向、强势股榜、板块行情榜/成分股榜/板块财务榜、涨停板数据，腾讯与东方财富公开接口，无需密钥）。其他 SKILL（stock-analysis、stock-review、position-management、stock-report、buying-at-close、leader-catch、limit-up 等）需要行情/财报/新闻/资金/强势股/板块龙头候选/涨停板数据时调用本 SKILL，不自行重复实现。当用户请求“查行情、看报价、拉数据、查财报、看新闻公告、看资金流向、看涨幅榜、选强势股、看板块/题材榜、扫龙头、看涨停/跌停/连板/炸板、复盘涨停”或分析、复盘前需要真实数据时使用。
---

# 市场数据报告（market-data）

数据层 SKILL：统一拉取 A 股真实数据并输出数据报告，其他 SKILL 需要数据时应用本 SKILL。

## 数据能力

| 报告 | 脚本 | 数据源 | 报告内容 |
|---|---|---|---|
| 行情报告 | scripts/fetch_quote.py | 腾讯行情公开接口 | 实时报价、涨跌、成交量/换手/振幅、PE/PB/市值、涨停/跌停、MA5/10/20/60、最近N根日K |
| 财报报告 | scripts/fetch_fundamentals.py | 东方财富数据中心 | 最近N个报告期营收/净利及同比、毛利率、净利率、负债率、ROE、经营现金流 |
| 新闻公告报告 | scripts/fetch_news.py | 东方财富新闻搜索 + 公告 | 最近N条新闻与公告（时间/标题/来源/链接） |
| 资金流向报告 | scripts/fetch_capital_flow.py | 东方财富资金流 | 最新交易日主力/大中小单净流入 + 近5日主力净流入 |
| 强势股榜报告 | scripts/fetch_strong_stocks.py | 东方财富行情中心 | 按涨跌幅排序的 Top N 强势股榜（代码/名称/现价/涨跌幅/量比/换手/成交额/振幅/PE/主力净流入/行业，标注“涨停≈”），支持板块与换手率/涨幅区间过滤（--min-turnover/--max-turnover/--min-gain/--max-gain，如 3%–5%），默认剔除 ST |
| 板块行情榜报告 | scripts/fetch_sector_boards.py | 东方财富板块行情（push2 clist） | 行业/概念板块榜——按当日涨跌幅/主力净流入/成交额/近5日/近10日涨跌幅排序（--sort），含板块指数、今日/5日/10日涨幅（东财口径）、领涨股（名称/代码/涨幅）、上涨/下跌家数、成交额、换手、主力净流入；支持 --type industry/concept/all、--min-up 上涨家数与 --search 板块名关键词过滤 |
| 板块成分股榜报告 | scripts/fetch_sector_leaders.py | 东方财富板块行情 + 行情中心 | 指定板块（--board BKxxxx）成分股按当日涨跌幅/资金/成交额/近5日/近10日涨幅排序，表头附板块今日/5日/10日涨幅与领涨股；每行含现价、当日/5日/10日涨幅、换手、量比、成交额、振幅、PE、流通/总市值、主力净流入、行业并标注“涨停≈”；支持换手/涨幅/流通市值区间过滤，默认剔除 ST |
| 板块财务排名报告 | scripts/fetch_sector_fundamentals.py | 东方财富板块行情 + 数据中心 F10 | 指定板块（--board BKxxxx）总市值前 N 名成分股的最新报告期财务数据（营收及同比、净利及同比、毛利率、ROE、负债率、经营现金流），按营收与按净利分别排序，供“行业龙头（基本面第一梯队）”筛选 |
| 涨停板数据报告 | scripts/fetch_limit_up.py | 东方财富涨停板专题（push2ex）+ 腾讯行情 | 涨停/跌停/炸板池与家数（含昨日对比、封板率）、连板高度与最高板（实时行情核对一字板）、昨日涨停今日表现（晋级家数/晋级率/涨跌分布/平均涨幅）、涨停股行业分布；--date 指定日期，缺省自动取最近有数据交易日；涨停池口径不含 ST 与科创板 |

## 使用方式

其他 SKILL 需要数据时，在工作区根目录运行本 SKILL 的脚本（路径以实际安装位置为准，如仓库内为 `market-data/scripts/...`）：

```bash
python market-data/scripts/fetch_quote.py <代码> --days 60
python market-data/scripts/fetch_fundamentals.py <代码> --periods 4
python market-data/scripts/fetch_news.py <代码> --news 5 --ann 5
python market-data/scripts/fetch_capital_flow.py <代码>
python market-data/scripts/fetch_strong_stocks.py --top 20 --min-turnover 5 --max-turnover 30
python market-data/scripts/fetch_strong_stocks.py --min-gain 3 --max-gain 5 --top 50
python market-data/scripts/fetch_sector_boards.py --type concept --sort change --top 15 --min-up 5
python market-data/scripts/fetch_sector_boards.py --type industry --sort gain5 --top 15
python market-data/scripts/fetch_sector_boards.py --type concept --search 液冷 --top 5
python market-data/scripts/fetch_sector_leaders.py --board BK1151 --top 30 --min-turnover 5 --max-turnover 10 --min-float-cap 50 --max-float-cap 200
python market-data/scripts/fetch_sector_fundamentals.py --board BK1151 --top 12
python market-data/scripts/fetch_limit_up.py
python market-data/scripts/fetch_limit_up.py --date 20260908
```

代码格式：`sh600410` / `sz002491` / `bj920002`（sh=沪、sz=深、bj=北交所）。脚本默认输出中文报告，`--json` 输出 JSON；不产生任何缓存文件。

强势股榜、fetch_sector_leaders / fetch_sector_fundamentals 与 fetch_limit_up 返回的个股代码已是 sh/sz/bj 前缀格式，可直接传给 fetch_quote / fetch_capital_flow / fetch_news 做个股细审。板块代码为 BK 前缀（如 BK1151），由 fetch_sector_boards 输出，经 `--board` 传给 fetch_sector_leaders / fetch_sector_fundamentals；分析“活跃板块/题材”时先跑 fetch_sector_boards 确定 BK 代码，再下钻成分股与财务榜。

## 硬性规则

- 真实数据：接口拉不到就明确报错，禁止编造价格、PE/PB、营收、利润、新闻、公告或资金流向。
- 数据日期：报告中引用数据必须标注数据时间（行情报告含数据时间，其余报告注明数据来源与报告期/交易日）。
- 单位与口径：以脚本输出为准——行情量为手、资金流为正负元（展示为万元）、财报为报告期累计值，同比须与去年同期比。
- 不构成投资建议：报告末尾注明数据来源。
