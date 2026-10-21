# 连板天梯数据契约

用途：limit-ladder 生成 HTML 前的字段、分组、断板与模板契约。所有数字来自当日真实行情；缺失写“未获取”，不填 0，不用昨日价格冒充今日价格。

## 1. 输入来源

| 数据 | 来源 | 用途 |
|---|---|---|
| 今日涨停池 | `fetch_limit_up.py --json` 的 `zt_rows` | 今日涨停股、连板数、几天几板、首封时间、行业 |
| 今日炸板池 | 同上的 `zb_all_rows` | 区分“炸板断板”和“未封断板” |
| 数据日期 | 同上的 `base_date` | HTML 标题与文件日期 |
| 上一交易日 | 同上的 `prev_date` | 定位昨日文章 |
| 昨日涨停名单 | `report/涨停板复盘/<prev_date>.md`「涨停全名单（供次日竞价评估）」 | 断板判定与昨日板数 |
| 个股行情 | `fetch_quote.py <代码> --days 5 --json` | 开盘价、收盘/现价、行情时间、涨停价 |

## 2. 今日涨停字段

`zt_rows` 每行至少使用：

| 字段 | 含义 | 用途 |
|---|---|---|
| `code` | `sh/sz/bj` 前缀代码 | 卡片标识、行情查询 |
| `name` | 名称 | 卡片标题 |
| `board_count` | 连板数 | **天梯层级** |
| `zt_stat` | 几天几板，如 `4天3板` | 标注，不决定层级 |
| `first_seal` | 今日首次封板时间 | 今日封板时间 |
| `industry` | 行业 | 卡片标签 |
| `price` | 涨停价 | 核对行情 |

## 3. 昨日文章解析

优先读同目录报告，其次读 `report/涨停板复盘/` 下日期早于 `base_date` 的最近一份。必须读取：

`## 涨停全名单（供次日竞价评估）` 下的 Markdown 表。

表头固定：

```
| 代码 | 名称 | 板数 | 行业 | 成交额(亿) | 首封时间 | 备注 |
```

备注字段可能含 `N天M板` 或“一字”，用正则取 `(\\d+)天(\\d+)板` 作为昨日几天几板标注。报告或表缺失时，才用 `fetch_limit_up.py --date <prev_date> --json` 的 `zt_rows` 重建，并在 HTML 的 `SOURCE_NOTE` 写“由接口重建，未读取昨日文章”。

## 4. 断板判定

设：

- `today_codes` = 今日 `zt_rows` 的代码集合；
- `yesterday_rows` = 昨日文章/重建数据的名单；
- `broken_rows` = `yesterday_rows` 中代码不在 `today_codes` 的行。

每只断板股：

| 字段 | 取值 |
|---|---|
| 天梯层级 | 昨日 `board_count` |
| 今日状态 | 在 `zb_all_rows` → “炸板断板”；否则 → “未封断板” |
| 封板时间 | 昨日 `first_seal`（标“昨日封板”） |
| 开盘价 | 今日 `quote.open` |
| 收盘价 | 收盘后 `quote.price`；盘中写“现价（临时）” |
| 几天几板 | 昨日备注中的 `N天M板`，没有则 `-` |

收盘后（行情时间 >= 15:00 且日期为数据日期）才把断板写成定稿；盘中运行只写“临时断板，未定稿”。

## 5. 行情补齐

需要行情的代码 = `today_codes ∪ broken_codes`。同一代码只调用一次 `fetch_quote.py`，按代码缓存。

使用字段：

- `quote.open`：开盘价；
- `quote.price`：收盘后为收盘价，盘中为现价；
- `quote.datetime`：行情时间；
- `quote.limit_up`：涨停价，核对是否仍封板。

字段缺失：卡片写“未获取”，不阻塞其他股票；HTML 的 `SOURCE_NOTE` 记录缺失只数。

## 6. 天梯分组

建议中间结构：

```json
{
  "meta": {
    "data_date": "2026-10-21",
    "generated_at": "2026-10-21 15:40",
    "status": "收盘定稿",
    "up_count": 0,
    "max_board": 0,
    "continuous_count": 0,
    "broken_count": 0
  },
  "levels": [
    {
      "level": 3,
      "today": [],
      "broken": []
    }
  ]
}
```

规则：

1. 层级取今日与断板的最高 `board_count`，从高到低排到 1 板；
2. 今日股票按 `board_count` 放入 `today`；
3. 断板股票按昨日 `board_count` 放入 `broken`；
4. 一个层级既无今日股票也无断板股票时删除该层；
5. 卡片排序：同层今日股票按首封时间升序，断板按昨日首封时间升序。

## 7. HTML 占位符

复制 `assets/ladder-template.html`，只替换：

| 占位符 | 内容 |
|---|---|
| `{{TITLE}}` | `连板天梯 · YYYY-MM-DD` |
| `{{DATA_DATE}}` | 数据日期 |
| `{{GENERATED_AT}}` | 生成时间 |
| `{{DATA_WINDOW}}` | `收盘定稿` 或 `盘中临时，未定稿` |
| `{{SUMMARY_HTML}}` | 5 个汇总卡片 |
| `{{LADDER_HTML}}` | 层级行与股票卡片 |
| `{{SOURCE_NOTE}}` | 数据源、昨日文章路径、缺失项、重跑覆盖说明 |
| `{{DISCLAIMER}}` | `不构成投资建议` |

## 8. 固定卡片结构

层级行骨架：

```html
<section class="ladder-row">
  <div class="level">
    <span class="level-num">4</span>
    <span class="level-label">板</span>
  </div>
  <div class="cards">
    <!-- 今日股票卡片与断板卡片放在这里 -->
  </div>
</section>
```

今日涨停卡片：

```html
<article class="stock-card">
  <div class="card-top">
    <strong class="stock-name">名称</strong>
    <span class="stock-code">sh600000</span>
  </div>
  <div class="tags">
    <span class="tag tag-board">3连板</span>
    <span class="tag tag-stat">4天3板</span>
    <span class="tag">行业</span>
  </div>
  <dl class="meta">
    <div><dt>首封</dt><dd>09:31:00</dd></div>
    <div><dt>开盘</dt><dd>10.00</dd></div>
  </dl>
</article>
```

断板卡片：

```html
<article class="stock-card is-broken">
  <div class="broken-stamp">断板</div>
  <div class="card-top">
    <strong class="stock-name">名称</strong>
    <span class="stock-code">sh600000</span>
  </div>
  <div class="tags">
    <span class="tag tag-board">昨日 3连板</span>
    <span class="tag tag-stat">4天3板</span>
    <span class="tag tag-broken">炸板断板 / 未封断板</span>
  </div>
  <dl class="meta">
    <div><dt>昨封</dt><dd>09:31:00</dd></div>
    <div><dt>今开</dt><dd>10.00</dd></div>
    <div><dt>收盘</dt><dd>9.80</dd></div>
  </dl>
</article>
```

不得改类名、颜色变量或卡片层级；需要新增信息时放进 `tags` 或 `meta`，保持模板风格。

## 9. 校验清单

- 每个层级都有 `N板` 标签，层级从高到低；
- 今日股票只按 `board_count` 分层，`zt_stat` 仅显示为标签；
- 昨日涨停今日未封的股票全部出现在断板卡片中；
- 断板卡片有昨日板数、昨日封板时间、今日开盘价、今日收盘价；
- 每张今日卡片有首封时间、开盘价、几天几板标注；
- 盘中 HTML 明确标“临时”，不把现价写成收盘价；
- 数据缺失项写“未获取”；
- HTML 底部有数据来源与“不构成投资建议”。
