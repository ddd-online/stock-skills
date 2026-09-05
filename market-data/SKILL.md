---
name: market-data
description: 拉取A股真实市场数据并输出数据报告（行情/日K/MA、财报核心指标、新闻公告、资金流向、强势股榜，腾讯与东方财富公开接口，无需密钥）。其他 SKILL（stock-analysis、stock-review、position-management、stock-report、buying-at-close 等）需要行情/财报/新闻/资金/强势股榜单数据时调用本 SKILL，不自行重复实现。当用户请求“查行情、看报价、拉数据、查财报、看新闻公告、看资金流向、看涨幅榜、选强势股”或分析、复盘前需要真实数据时使用。
---

# 市场数据报告（market-data）

数据层 SKILL：统一拉取 A 股真实数据并输出数据报告，其他 SKILL 需要数据时应用本 SKILL。

## 数据能力

| 报告 | 脚本 | 数据源 | 报告内容 |
|---|---|---|---|
| 行情报告 | scripts/fetch_quote.py | 腾讯行情公开接口 | 实时报价、涨跌、成交量/换手/振幅、PE/PB/市值、涨停/跌停、MA5/10/20/60、最近N根日K |
| 财报报告 | scripts/fetch_fundamentals.py | 东方财富数据中心 | 最近N个报告期营收/净利及同比、毛利率、净利率、负债率、ROE |
| 新闻公告报告 | scripts/fetch_news.py | 东方财富新闻搜索 + 公告 | 最近N条新闻与公告（时间/标题/来源/链接） |
| 资金流向报告 | scripts/fetch_capital_flow.py | 东方财富资金流 | 最新交易日主力/大中小单净流入 + 近5日主力净流入 |
| 强势股榜报告 | scripts/fetch_strong_stocks.py | 东方财富行情中心 | 按涨跌幅排序的 Top N 强势股榜（代码/名称/现价/涨跌幅/量比/换手/成交额/振幅/PE/主力净流入/行业，标注“涨停≈”），支持板块与换手率/涨幅区间过滤（--min-turnover/--max-turnover/--min-gain/--max-gain，如 3%–5%），默认剔除 ST |

## 使用方式

其他 SKILL 需要数据时，在工作区根目录运行本 SKILL 的脚本（路径以实际安装位置为准，如仓库内为 `market-data/scripts/...`）：

```bash
python market-data/scripts/fetch_quote.py <代码> --days 60
python market-data/scripts/fetch_fundamentals.py <代码> --periods 4
python market-data/scripts/fetch_news.py <代码> --news 5 --ann 5
python market-data/scripts/fetch_capital_flow.py <代码>
python market-data/scripts/fetch_strong_stocks.py --top 20 --min-turnover 5 --max-turnover 30
python market-data/scripts/fetch_strong_stocks.py --min-gain 3 --max-gain 5 --top 50
```

代码格式：`sh600410` / `sz002491` / `bj920002`（sh=沪、sz=深、bj=北交所）。脚本默认输出中文报告，`--json` 输出 JSON；不产生任何缓存文件。

强势股榜返回的代码已是 sh/sz/bj 前缀格式，可直接传给 fetch_quote / fetch_capital_flow / fetch_news 做个股细审。

## 硬性规则

- 真实数据：接口拉不到就明确报错，禁止编造价格、PE/PB、营收、利润、新闻、公告或资金流向。
- 数据日期：报告中引用数据必须标注数据时间（行情报告含数据时间，其余报告注明数据来源与报告期/交易日）。
- 单位与口径：以脚本输出为准——行情量为手、资金流为正负元（展示为万元）、财报为报告期累计值，同比须与去年同期比。
- 不构成投资建议：报告末尾注明数据来源。
