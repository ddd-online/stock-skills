#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股 涨停板数据报告（涨停/跌停/炸板池 + 昨日涨停今日表现，东方财富公开接口）。

用法:
    python fetch_limit_up.py [--date YYYYMMDD] [--json]

输出: 涨停板全景报告——
1) 当日涨停/跌停/炸板家数（含与昨日对比、封板率）；
2) 连板最高板数、最高板标的与一字板判定（腾讯实时行情核对开高低收相等）；
3) 昨日涨停股今日表现：继续涨停（晋级）家数与晋级率、上涨/下跌/平均涨幅；
4) 涨停股行业分布（供“当日主线板块”合并板块行情榜使用）。

口径: 东财 push2ex 涨停板专题（涨停池不含 ST 与科创板）；--date 缺省时自动取最近
有数据的交易日；不产生缓存文件。
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

POOL_HOSTS = [
    "https://push2ex.eastmoney.com",
    "http://push2ex.eastmoney.com",
]

QT_URL = "http://qt.gtimg.cn/q={codes}"
UT = "7eea3edcaed734bea9cbfc24409ed989"

POOL_EP = {
    "zt": "getTopicZTPool",
    "dt": "getTopicDTPool",
    "zb": "getTopicZBPool",
}

POOL_SORT = {
    "zt": "fbt:asc",
    "dt": "fund:asc",
    "zb": "fbt:asc",
}


def http_get(url, referer):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": referer,
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


def decode_json(raw):
    text = raw.decode("utf-8", errors="replace")
    if "\ufffd" in text:
        text = raw.decode("gb18030", errors="replace")
    return json.loads(text)


def to_float(value):
    try:
        if isinstance(value, str):
            value = value.replace(",", "")
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_num(value, digits=2):
    if value is None:
        return "-"
    return "{:.{}f}".format(value, digits)


def fmt_time(raw_value):
    """接口时间 92500 -> 09:25:00。"""
    try:
        num = int(raw_value)
        s = "{:06d}".format(num)
        return "{}:{}:{}".format(s[0:2], s[2:4], s[4:6])
    except (TypeError, ValueError):
        return "-"


def fmt_zt_stat(zttj):
    try:
        days = int(zttj.get("days") or 0)
        ct = int(zttj.get("ct") or 0)
    except (TypeError, ValueError, AttributeError):
        return "-"
    if days <= 0 or ct <= 0:
        return "-"
    return "{}天{}板".format(days, ct)


def to_sec_code(market, digits):
    if market == "1":
        return "sh" + digits
    if digits[:2] == "92" or digits[0] in ("4", "8"):
        return "bj" + digits
    return "sz" + digits


def fetch_pool(kind, date_str):
    """返回 {pool, tc, qdate}；kind: zt/dt/zb。"""
    last_error = None
    url_tpl = (
        "{host}/{ep}?ut={ut}&dpt=wz.ztzt&Pageindex=0&pagesize=10000"
        "&sort={sort}&date={date}"
    )
    for host in POOL_HOSTS:
        try:
            url = url_tpl.format(
                host=host, ep=POOL_EP[kind], ut=UT,
                sort=POOL_SORT[kind], date=date_str)
            data = decode_json(http_get(url, "https://data.eastmoney.com/"))
            node = data.get("data") or {}
            if data.get("rc") != 0 or node is None:
                last_error = "接口无数据 rc={}".format(data.get("rc"))
                continue
            return {
                "pool": node.get("pool") or [],
                "tc": node.get("tc"),
                "qdate": node.get("qdate"),
            }
        except Exception as exc:  # noqa: BLE001 网络或解析失败时切换备用源
            last_error = str(exc)
            continue
    raise RuntimeError("东方财富涨停板接口（{}）拉取失败：{}".format(kind, last_error))


def pool_has_rows(payload):
    return bool(payload.get("pool")) or (payload.get("tc") or 0) > 0


def walk_date(start_date, max_back=15):
    """从 start_date 向前找第一个有涨停数据的交易日；跳过周末。"""
    for i in range(max_back):
        day = start_date - timedelta(days=i)
        if day.weekday() >= 5:
            continue
        try:
            payload = fetch_pool("zt", day.strftime("%Y%m%d"))
        except Exception:
            continue
        if pool_has_rows(payload):
            return day, payload
    return start_date, {"pool": [], "tc": 0, "qdate": None}


def parse_date(text):
    try:
        return datetime.strptime(text.strip(), "%Y%m%d")
    except (ValueError, AttributeError):
        sys.exit("错误：--date 格式应为 YYYYMMDD（如 20260908）。")


def fetch_quotes(sec_codes):
    """腾讯批量实时行情；返回 {6位代码: dict}。"""
    result = {}
    codes = [c for c in sec_codes if c]
    for i in range(0, len(codes), 40):
        chunk = codes[i:i + 40]
        url = QT_URL.format(codes=",".join(chunk))
        raw = http_get(url, "http://finance.qq.com").decode("gbk", errors="ignore")
        for line in raw.splitlines():
            if not line.startswith("v_"):
                continue
            body = line.split('"', 2)[1]
            f = body.split("~")
            if len(f) < 49:
                continue
            result[str(f[2])] = {
                "name": f[1],
                "price": to_float(f[3]),
                "open": to_float(f[5]),
                "high": to_float(f[33]),
                "low": to_float(f[34]),
                "pct": to_float(f[32]),
                "quote_date": str(f[30])[:8],
            }
    return result


def latest_quote_date():
    """取上证指数实时行情的日期，作为市场最新数据日期的基准。"""
    q = fetch_quotes(["sh000001"]).get("000001")
    return q.get("quote_date") if q else None


def normalize_pool_row(raw):
    digits = str(raw.get("c") or "")
    if len(digits) != 6 or not digits.isdigit():
        return None
    return {
        "code": to_sec_code(str(raw.get("m") or ""), digits),
        "name": str(raw.get("n") or "-"),
        "price": round((to_float(raw.get("p")) or 0) / 1000.0, 2),
        "pct": to_float(raw.get("zdp")),
        "amount_yi": round((to_float(raw.get("amount")) or 0) / 1e8, 2),
        "float_cap_yi": round((to_float(raw.get("ltsz")) or 0) / 1e8, 2),
        "total_cap_yi": round((to_float(raw.get("tshare")) or 0) / 1e8, 2),
        "turnover_pct": to_float(raw.get("hs")),
        "board_count": int(raw.get("lbc")) if raw.get("lbc") else None,
        "first_seal": fmt_time(raw.get("fbt")),
        "last_seal": fmt_time(raw.get("lbt")),
        "break_count": int(raw.get("zbc")) if raw.get("zbc") else None,
        "seal_fund_yi": round((to_float(raw.get("fund")) or 0) / 1e8, 2),
        "industry": str(raw.get("hybk") or "-"),
        "zt_stat": fmt_zt_stat(raw.get("zttj")),
    }


def resolve_dates(date_arg):
    """返回 (base_date, prev_date, base_payload, prev_payload)。"""
    if date_arg:
        base_date = parse_date(date_arg)
    else:
        base_date = datetime.now()
    found, base_payload = walk_date(base_date)
    qdate = latest_quote_date()
    if qdate and found.strftime("%Y%m%d") > qdate:
        # 涨停池接口可能回退到最新有数据日；行情日期更可信，回退到行情日期
        base_date = datetime.strptime(qdate, "%Y%m%d")
        base_payload = fetch_pool("zt", qdate)
    else:
        base_date = found
    if not pool_has_rows(base_payload):
        base_payload = {"pool": [], "tc": 0, "qdate": None}
    prev_day, prev_payload = walk_date(base_date - timedelta(days=1))
    return base_date, prev_day, base_payload, prev_payload


def industry_distribution(zt_rows):
    dist = {}
    for r in zt_rows:
        ind = r["industry"]
        dist[ind] = dist.get(ind, 0) + 1
    total = len(zt_rows) or 1
    out = []
    for ind, cnt in sorted(dist.items(), key=lambda x: x[1], reverse=True):
        out.append({
            "industry": ind,
            "count": cnt,
            "pct": round(cnt * 100.0 / total, 1),
        })
    return out


def one_word_check(rows, quotes):
    """用实时行情核对：今开=最高=最低=现价 且涨幅为正 → 一字板。"""
    marked = {}
    for r in rows:
        q = quotes.get(r["code"][2:])
        if q is None:
            marked[r["code"]] = None
            continue
        vals = [q["open"], q["high"], q["low"], q["price"]]
        if all(v is not None for v in vals) and max(vals) - min(vals) < 0.005 \
                and (q["pct"] or 0) > 0:
            marked[r["code"]] = True
        else:
            marked[r["code"]] = False
    return marked


def render_text(base, prev, zt_rows, zb_rows, dt_rows, prev_zt_rows,
                prev_zb_rows, prev_dt_rows, quotes, quote_date, one_word):
    zt_n = len(zt_rows)
    zb_n = len(zb_rows)
    dt_n = len(dt_rows)
    prev_zt_n = len(prev_zt_rows)
    prev_zb_n = len(prev_zb_rows)
    prev_dt_n = len(prev_dt_rows)
    close_rate = None
    prev_close_rate = None
    if zt_n + zb_n > 0:
        close_rate = zt_n * 100.0 / (zt_n + zb_n)
    if prev_zt_n + prev_zb_n > 0:
        prev_close_rate = prev_zt_n * 100.0 / (prev_zt_n + prev_zb_n)
    prev_max_board = max((r["board_count"] or 1 for r in prev_zt_rows), default=None)

    lines = []
    lines.append("# 涨停板数据报告（数据日期 {} · 行情日期 {} · 生成时间 {}）".format(
        base.strftime("%Y-%m-%d"), quote_date or "-",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    lines.append("")
    lines.append("口径：东财 push2ex 涨停板专题，涨停池不含 ST 与科创板；"
                 "盘中运行数值随行情变化。")
    lines.append("")

    lines.append("## 一、今日涨停/跌停/炸板概览")
    lines.append("")
    lines.append("| 指标 | 今日({}) | 昨日({}) |".format(
        base.strftime("%m-%d"), prev.strftime("%m-%d") if prev_zt_n else "-"))
    lines.append("|---|---|---|")
    lines.append("| 涨停家数 | {} | {} |".format(zt_n, prev_zt_n or "-"))
    lines.append("| 跌停家数 | {} | {} |".format(dt_n, prev_dt_n or "-"))
    lines.append("| 炸板家数 | {} | {} |".format(zb_n, prev_zb_n or "-"))
    lines.append("| 封板率 | {}% | {}% |".format(
        fmt_num(close_rate, 1), fmt_num(prev_close_rate, 1)))
    lines.append("")
    if prev_zt_n:
        diff = zt_n - prev_zt_n
        lines.append("涨停家数较昨日 {}（{}）".format(
            "+{}".format(diff) if diff >= 0 else str(diff),
            "增加" if diff >= 0 else "减少"))
        lines.append("")

    board_rows = [r for r in zt_rows if (r["board_count"] or 1) >= 2]
    board_rows.sort(key=lambda r: r["board_count"] or 0, reverse=True)
    lines.append("## 二、连板高度与最高板")
    lines.append("")
    if board_rows:
        max_board = max(r["board_count"] for r in board_rows)
        top = [r for r in board_rows if r["board_count"] == max_board][:5]
        if prev_max_board:
            lines.append("最高 {} 板（昨日最高 {} 板）：{}。".format(
                max_board, prev_max_board,
                "、".join("{}（{}）".format(r["name"], r["code"]) for r in top)))
        else:
            lines.append("最高 {} 板：{}。".format(
                max_board,
                "、".join("{}（{}）".format(r["name"], r["code"]) for r in top)))
    else:
        lines.append("今日无 2 板及以上个股（最高为 1 板/首板）。")
    lines.append("")
    if board_rows:
        header = ("| 板数 | 代码 | 名称 | 涨停统计 | 首封/末封 | 换手% | "
                  "封板资金(亿) | 行业 | 一字 |")
        sep = "|---|---|---|---|---|---|---|---|---|"
        lines.append(header)
        lines.append(sep)
        for r in board_rows[:15]:
            mark = one_word.get(r["code"])
            mark_text = "是" if mark is True else ("否" if mark is False else "-")
            lines.append("| {b} | {code} | {name} | {stat} | {fs}/{ls} | {hs} | "
                         "{fund} | {ind} | {mark} |".format(
                             b=r["board_count"], code=r["code"], name=r["name"],
                             stat=r["zt_stat"], fs=r["first_seal"], ls=r["last_seal"],
                             hs=fmt_num(r["turnover_pct"]),
                             fund=fmt_num(r["seal_fund_yi"]),
                             ind=r["industry"], mark=mark_text))
        lines.append("")

    lines.append("## 三、昨日涨停今日表现（晋级与炸板）")
    lines.append("")
    if not prev_zt_n:
        lines.append("昨日无涨停数据（或接口仅覆盖近 30 个交易日），无法计算晋级率。")
    else:
        prev_codes = set(r["code"] for r in prev_zt_rows)
        today_codes = set(r["code"] for r in zt_rows)
        promote = sorted(prev_codes & today_codes)
        rate = len(promote) * 100.0 / prev_zt_n
        lines.append("- 昨日涨停 {} 只；今日继续涨停 {} 只（晋级率 {}%）".format(
            prev_zt_n, len(promote), fmt_num(rate, 1)))
        valid = []
        for r in prev_zt_rows:
            q = quotes.get(r["code"][2:])
            if q and q["pct"] is not None:
                valid.append(q)
        if quote_date == base.strftime("%Y%m%d") and valid:
            up = sum(1 for q in valid if q["pct"] > 0)
            down = sum(1 for q in valid if q["pct"] < 0)
            flat = sum(1 for q in valid if q["pct"] == 0)
            avg = sum(q["pct"] for q in valid) / len(valid)
            lines.append("- 有行情 {} 只：上涨 {} / 下跌 {} / 平 {}；平均涨幅 {}%".format(
                len(valid), up, down, flat, fmt_num(avg, 2)))
        elif valid:
            lines.append("- 行情日期（{}）与基准日期不一致，涨跌分布不作基准对比；"
                         "仅以上述池交集计晋级。".format(quote_date or "-"))
        else:
            lines.append("- 未取到批量行情，仅以上述池交集计晋级。")
        lines.append("")
    if zb_n:
        lines.append("- 今日炸板 {} 只，封板率 {}%；昨日炸板 {} 只。".format(
            zb_n, fmt_num(close_rate, 1), prev_zb_n or "-"))
        lines.append("- 炸板潮判定见分析报告（默认：炸板率 ≥35% 或炸板家数 ≥15 "
                     "且有明显增多 → 有炸板潮迹象）。")
    else:
        lines.append("- 今日炸板 0 只，无炸板潮迹象。")
    lines.append("")

    dist = industry_distribution(zt_rows)
    lines.append("## 四、涨停股行业分布（Top 10，供合并板块行）")
    lines.append("")
    if not dist:
        lines.append("无涨停股。")
    else:
        lines.append("| # | 行业 | 涨停家数 | 占比% |")
        lines.append("|---|---|---|---|")
        for i, d in enumerate(dist[:10], 1):
            lines.append("| {} | {} | {} | {} |".format(
                i, d["industry"], d["count"], fmt_num(d["pct"], 1)))
        lines.append("")

    if zb_rows:
        lines.append("### 炸板池（Top 10）")
        lines.append("")
        lines.append("| 代码 | 名称 | 最新价 | 现涨跌幅% | 炸板次数 | 涨停统计 | 行业 |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in zb_rows[:10]:
            lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                r["code"], r["name"], fmt_num(r["price"]), fmt_num(r["pct"]),
                r["break_count"] if r["break_count"] is not None else "-",
                r["zt_stat"], r["industry"]))
        lines.append("")
    if dt_rows:
        lines.append("### 跌停池（Top 10）")
        lines.append("")
        lines.append("| 代码 | 名称 | 最新价 | 涨跌幅% | 行业 |")
        lines.append("|---|---|---|---|---|")
        for r in dt_rows[:10]:
            lines.append("| {} | {} | {} | {} | {} |".format(
                r["code"], r["name"], fmt_num(r["price"]), fmt_num(r["pct"]),
                r["industry"]))
        lines.append("")
    lines.append("数据来源：东方财富涨停板行情（push2ex）+ 腾讯行情公开接口；"
                 "涨停池口径不含 ST 与科创板，使用时以交易所数据为准。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="A股 涨停板数据报告（东方财富公开接口）")
    ap.add_argument("--date", type=str, default="",
                    help="数据日期 YYYYMMDD（默认自动取最近有数据的交易日）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    base, prev, base_payload, prev_payload = resolve_dates(args.date)
    base_str = base.strftime("%Y%m%d")
    prev_str = prev.strftime("%Y%m%d")

    zt = fetch_pool("zt", base_str)
    dt = fetch_pool("dt", base_str)
    zb = fetch_pool("zb", base_str)
    prev_zt = fetch_pool("zt", prev_str)
    prev_zb = fetch_pool("zb", prev_str)
    prev_dt = fetch_pool("dt", prev_str)

    zt_rows = [r for r in (normalize_pool_row(x) for x in zt["pool"]) if r]
    zb_rows = [r for r in (normalize_pool_row(x) for x in zb["pool"]) if r]
    dt_rows = [r for r in (normalize_pool_row(x) for x in dt["pool"]) if r]
    prev_zt_rows = [r for r in (normalize_pool_row(x) for x in prev_zt["pool"]) if r]
    prev_zb_rows = [r for r in (normalize_pool_row(x) for x in prev_zb["pool"]) if r]
    prev_dt_rows = [r for r in (normalize_pool_row(x) for x in prev_dt["pool"]) if r]

    board_rows = [r for r in zt_rows if (r["board_count"] or 1) >= 2]
    one_word_codes = sorted(set(r["code"] for r in board_rows[:15]))
    quotes = fetch_quotes(one_word_codes)
    quote_date = next((q["quote_date"] for q in quotes.values() if q["quote_date"]),
                      base_str)

    if prev_zt_rows:
        perf_codes = sorted(set(r["code"] for r in prev_zt_rows))
        for code, q in fetch_quotes(perf_codes).items():
            quotes.setdefault(code, q)
            if q["quote_date"]:
                quote_date = q["quote_date"]

    one_word = one_word_check(board_rows, quotes)

    if args.json:
        prev_codes = set(r["code"] for r in prev_zt_rows)
        today_codes = set(r["code"] for r in zt_rows)
        perf = []
        for r in prev_zt_rows:
            q = quotes.get(r["code"][2:])
            perf.append({
                "code": r["code"],
                "name": r["name"],
                "today_pct": q["pct"] if q else None,
                "continue_limit": r["code"] in today_codes,
            })
        payload = {
            "base_date": base_str,
            "prev_date": prev_str,
            "quote_date": quote_date,
            "overview": {
                "zt_count": len(zt_rows),
                "dt_count": len(dt_rows),
                "zb_count": len(zb_rows),
                "prev_zt_count": len(prev_zt_rows),
                "prev_dt_count": len(prev_dt_rows),
                "prev_zb_count": len(prev_zb_rows),
                "seal_rate_pct": round(len(zt_rows) * 100.0 / (len(zt_rows) + len(zb_rows)), 1)
                if len(zt_rows) + len(zb_rows) else None,
                "prev_seal_rate_pct": round(prev_zt_n * 100.0 / (prev_zt_n + prev_zb_n), 1)
                if prev_zt_n + prev_zb_n else None,
            },
            "board_levels": board_rows[:15],
            "prev_max_board": prev_max_board,
            "one_word": {code: bool(v) for code, v in one_word.items() if v is not None},
            "yesterday_performance": {
                "prev_zt_count": len(prev_zt_rows),
                "promote_count": len(prev_codes & today_codes),
                "rows": perf,
            },
            "industry_dist": industry_distribution(zt_rows),
            "zb_rows": zb_rows[:10],
            "dt_rows": dt_rows[:10],
            "note": "数据来源：东方财富 push2ex + 腾讯行情；涨停池不含 ST 与科创板",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    text = render_text(base, prev, zt_rows, zb_rows, dt_rows, prev_zt_rows,
                       prev_zb_rows, prev_dt_rows, quotes, quote_date, one_word)
    print(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 统一报错，不静默
        sys.exit("错误：{}".format(exc))
