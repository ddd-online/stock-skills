#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股/ETF 强势股榜单数据报告（东方财富公开接口，无需密钥）。

用法:
    python fetch_strong_stocks.py [--top N] [--board all|hs|main|cyb|kcb|bj|etf]
                                  [--min-turnover PCT] [--max-turnover PCT]
                                  [--min-gain PCT] [--max-gain PCT]
                                  [--include-st] [--json]

输出: 强势股榜单报告——按涨跌幅从高到低返回 Top N 候选；指定涨幅区间
（--min-gain/--max-gain，如 3–5%）时自动翻页拉全区间再过滤（接口单页上限 100）
（代码/名称/现价/涨跌幅/量比/换手/成交额/振幅/PE/主力净流入/行业，标注“涨停≈”），
默认剔除 ST；不产生缓存文件。
"""

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HOSTS = [
    "https://push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
]

# fs 板块过滤：m:0=深市 m:1=沪市（t:6 主板、t:80 创业板、t:2 沪主板、t:23 科创板、
# t:81+s:2048 北交所）；b:MK 系列为 ETF 板块
BOARDS = {
    "all": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
    "hs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
    "main": "m:1+t:2,m:0+t:6",
    "cyb": "m:0+t:80",
    "kcb": "m:1+t:23",
    "bj": "m:0+t:81+s:2048",
    "etf": "b:MK0021,b:MK0022,b:MK0023,b:MK0024",
}

FIELDS = (
    "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,"
    "f20,f21,f23,f62,f100,f124"
)

BOARD_NAMES = {
    "all": "沪深京 A 股",
    "hs": "沪深 A 股",
    "main": "沪深主板",
    "cyb": "创业板",
    "kcb": "科创板",
    "bj": "北交所",
    "etf": "ETF",
}


def http_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://data.eastmoney.com/",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def decode_json(raw):
    """接口编码不稳定（UTF-8/GB18030 混用）：先按 UTF-8 解析，乱码则回退 GB18030。"""
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


def fmt_wan(value):
    if value is None:
        return "-"
    return "{:,.0f}".format(value / 10000.0)


def fmt_yi(value):
    if value is None:
        return "-"
    return "{:,.2f}亿".format(value / 100000000.0)


def fmt_dt(ts):
    if not ts:
        return "-"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return "-"


def to_sec_code(market, digits):
    # market: 1=沪市、0=深市/北交所；北交所代码 4/8 开头或 92 开头
    if market == "1":
        return "sh" + digits
    if digits[:2] == "92" or digits[0] in ("4", "8"):
        return "bj" + digits
    return "sz" + digits


def limit_threshold(digits):
    if digits[:2] in ("30", "68"):
        return 20.0
    if digits[:2] == "92" or digits[0] in ("4", "8"):
        return 30.0
    return 10.0


def is_limit_up(price, high, change_pct, digits):
    threshold = limit_threshold(digits)
    if price is None or high is None or high <= 0 or change_pct is None:
        return False
    return price >= high - 1e-9 and change_pct >= threshold - 0.4


def fetch_page(board, page_no, page_size):
    last_error = None
    for host in HOSTS:
        try:
            url = (
                "{host}/api/qt/clist/get?pn={pn}&pz={pz}&po=1&np=1&fltt=2&invt=2"
                "&fid=f3&fs={fs}&fields={fields}"
            ).format(host=host, pn=page_no, pz=page_size,
                     fs=BOARDS[board], fields=FIELDS)
            data = decode_json(http_get(url))
            node = data.get("data") or {}
            diff = node.get("diff") or []
            if data.get("rc") != 0 or not diff:
                last_error = "第 {} 页接口无数据 rc={}".format(page_no, data.get("rc"))
                continue
            return diff
        except Exception as exc:  # noqa: BLE001 网络或解析失败时切换备用源
            last_error = str(exc)
            continue
    raise RuntimeError("东方财富接口第 {} 页拉取失败：{}".format(page_no, last_error))


def fetch_raw(board, top, min_gain, max_gain):
    """无涨幅过滤时只取涨幅榜前 top；有涨幅区间时自动翻页直到覆盖区间下限。"""
    if min_gain <= 0 and max_gain <= 0:
        return fetch_page(board, 1, top)
    page_size = 100
    max_pages = 60  # 覆盖全市场约 5500+ 只
    collected = []
    for page_no in range(1, max_pages + 1):
        page = fetch_page(board, page_no, page_size)
        if not page:
            break
        collected.extend(page)
        last_pct = to_float(page[-1].get("f3"))
        if min_gain > 0 and (last_pct is None or last_pct < min_gain):
            break
    return collected


def normalize_rows(diff, min_turnover, max_turnover, min_gain, max_gain, include_st):
    rows = []
    for raw in diff:
        digits = str(raw.get("f12") or "")
        name = str(raw.get("f14") or "")
        if len(digits) != 6 or not digits.isdigit():
            continue
        if not include_st and "ST" in name.upper():
            continue
        turnover = to_float(raw.get("f8"))
        if min_turnover > 0 and (turnover is None or turnover < min_turnover):
            continue
        if max_turnover > 0 and (turnover is None or turnover > max_turnover):
            continue
        price = to_float(raw.get("f2"))
        high = to_float(raw.get("f15"))
        change_pct = to_float(raw.get("f3"))
        if min_gain > 0 and (change_pct is None or change_pct < min_gain):
            continue
        if max_gain > 0 and (change_pct is None or change_pct > max_gain):
            continue
        sec_code = to_sec_code(str(raw.get("f13") or ""), digits)
        rows.append({
            "code": sec_code,
            "name": name,
            "price": price,
            "change_pct": change_pct,
            "volume_ratio": to_float(raw.get("f10")),
            "turnover_pct": turnover,
            "amount_wan": fmt_wan(to_float(raw.get("f6"))),
            "amplitude_pct": to_float(raw.get("f7")),
            "pe": to_float(raw.get("f9")),
            "total_cap": fmt_yi(to_float(raw.get("f20"))),
            "main_inflow_wan": fmt_wan(to_float(raw.get("f62"))),
            "industry": str(raw.get("f100") or "-"),
            "ts": to_float(raw.get("f124")),
            "limit_up": is_limit_up(price, high, change_pct, digits),
        })
    return rows


def turnover_desc(min_turnover, max_turnover):
    if min_turnover > 0 and max_turnover > 0:
        return "{}% < 换手 < {}%".format(fmt_num(min_turnover), fmt_num(max_turnover))
    if min_turnover > 0:
        return "换手 ≥ {}%".format(fmt_num(min_turnover))
    if max_turnover > 0:
        return "换手 < {}%".format(fmt_num(max_turnover))
    return "不过滤换手率"


def gain_desc(min_gain, max_gain):
    if min_gain > 0 and max_gain > 0:
        return "{}% ≤ 涨跌幅 ≤ {}%".format(fmt_num(min_gain), fmt_num(max_gain))
    if min_gain > 0:
        return "涨跌幅 ≥ {}%".format(fmt_num(min_gain))
    if max_gain > 0:
        return "涨跌幅 ≤ {}%".format(fmt_num(max_gain))
    return "不过滤涨幅"


def render_text(rows, board, top, min_turnover, max_turnover,
                min_gain, max_gain, include_st, quote_time):
    lines = []
    lines.append("# 强势股榜（Top {top} · {board} · 数据时间 {time}）".format(
        top=top, board=BOARD_NAMES[board], time=quote_time))
    lines.append("")
    lines.append("排序：按涨跌幅从高到低；默认剔除 ST（名称含 ST）；"
                 "换手率过滤：{tdesc}；涨幅过滤：{gdesc}。"
                 "数据未经验证，仅作尾盘审视初筛。".format(
                     tdesc=turnover_desc(min_turnover, max_turnover),
                     gdesc=gain_desc(min_gain, max_gain)))
    if len(rows) < top:
        lines.append("注：过滤后实际返回 {n} 只（请求 {top} 只）；"
                     "需要更多候选请调大 --top。".format(n=len(rows), top=top))
    lines.append("")
    header = "| # | 代码 | 名称 | 现价 | 涨跌幅% | 量比 | 换手% | 成交额(万) | 振幅% | PE | 主力净流入(万) | 行业 | 备注 |"
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for i, r in enumerate(rows, 1):
        note = "涨停≈" if r["limit_up"] else "-"
        lines.append("| {i} | {code} | {name} | {price} | {chg} | {vr} | {to} | {amt} | "
                     "{amp} | {pe} | {flow} | {ind} | {note} |".format(
                         i=i, code=r["code"], name=r["name"],
                         price=fmt_num(r["price"]), chg=fmt_num(r["change_pct"]),
                         vr=fmt_num(r["volume_ratio"], 2), to=fmt_num(r["turnover_pct"]),
                         amt=r["amount_wan"], amp=fmt_num(r["amplitude_pct"]),
                         pe=fmt_num(r["pe"]), flow=r["main_inflow_wan"],
                         ind=r["industry"], note=note))
    lines.append("")
    lines.append("数据来源：东方财富行情中心公开接口；行情时间为当日实时/延迟数据，"
                 "精确到分钟级，使用时以交易所数据为准。")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="A股/ETF 强势股榜单数据报告（东方财富公开接口）")
    parser.add_argument("--top", type=int, default=20, help="榜单数量（默认 20）")
    parser.add_argument("--board", choices=sorted(BOARDS), default="hs",
                        help="板块（默认 hs：沪深 A 股）")
    parser.add_argument("--min-turnover", type=float, default=0,
                        help="最低换手率过滤，如 5 表示 >5%（默认不过滤）")
    parser.add_argument("--max-turnover", type=float, default=0,
                        help="最高换手率过滤，如 30 表示 <30%（默认不过滤）")
    parser.add_argument("--min-gain", type=float, default=0,
                        help="最低涨幅过滤，如 3 表示 ≥3%（默认不过滤）")
    parser.add_argument("--max-gain", type=float, default=0,
                        help="最高涨幅过滤，如 5 表示 ≤5%（默认不过滤）")
    parser.add_argument("--include-st", action="store_true", help="不剔除名称含 ST 的股票")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    diff = fetch_raw(args.board, args.top, args.min_gain, args.max_gain)
    rows = normalize_rows(diff, args.min_turnover, args.max_turnover,
                          args.min_gain, args.max_gain, args.include_st)[:args.top]
    ts = next((r["ts"] for r in rows if r["ts"]), time.time())
    quote_time = fmt_dt(ts)

    if args.json:
        payload = {
            "board": args.board,
            "board_name": BOARD_NAMES[args.board],
            "top": args.top,
            "min_turnover": args.min_turnover,
            "max_turnover": args.max_turnover,
            "min_gain": args.min_gain,
            "max_gain": args.max_gain,
            "include_st": args.include_st,
            "quote_time": quote_time,
            "rows": rows,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("榜单为空：请调整过滤条件（--min-turnover / --max-turnover / "
              "--min-gain / --max-gain / --board / --include-st）后重试。")
        return
    print(render_text(rows, args.board, args.top, args.min_turnover,
                      args.max_turnover, args.min_gain, args.max_gain,
                      args.include_st, quote_time))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 统一报错，不静默
        sys.exit("错误：{}".format(exc))
