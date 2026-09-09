#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股 板块成分股榜数据报告（东方财富公开接口，无需密钥）。

用法:
    python fetch_sector_leaders.py --board BK0882 [--top N] [--sort change|flow|amount|gain5|gain10]
                                     [--min-turnover PCT] [--max-turnover PCT]
                                     [--min-gain PCT] [--max-gain PCT]
                                     [--min-float-cap YI] [--max-float-cap YI]
                                     [--include-st] [--json]

输出: 指定板块（BK 代码）的成分股行情榜——按所选排序返回 Top N 成分股，含现价、当日涨跌幅、
近5日/近10日累计涨跌幅、换手、量比、成交额、振幅、PE、流通/总市值、主力净流入、行业，
并标注“涨停≈”；带换手/涨幅/市值过滤时自动多翻页补齐候选；表头附板块当日/近5日/近10日涨幅、
领涨股与涨跌家数；不产生缓存文件。
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

SORTS = {
    "change": "f3",
    "flow": "f62",
    "amount": "f6",
    "gain5": "f109",
    "gain10": "f160",
}

SORT_NAMES = {
    "change": "当日涨跌幅",
    "flow": "主力净流入",
    "amount": "成交额",
    "gain5": "近5日涨跌幅",
    "gain10": "近10日涨跌幅",
}

BOARD_FIELDS = (
    "f2,f3,f6,f8,f12,f13,f14,f62,f104,f105,f109,f128,f136,f140,f141,f160"
)

STOCK_FIELDS = (
    "f2,f3,f6,f7,f8,f9,f10,f12,f13,f14,f15,f20,f21,f62,f100,f109,f124,f160"
)


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


def fetch_json(url_tpl, **params):
    last_error = None
    for host in HOSTS:
        try:
            url = url_tpl.format(host=host, **params)
            data = decode_json(http_get(url))
            if data.get("rc") != 0:
                last_error = "接口无数据 rc={}".format(data.get("rc"))
                continue
            return data
        except Exception as exc:  # noqa: BLE001 网络或解析失败时切换备用源
            last_error = str(exc)
            continue
    raise RuntimeError("东方财富接口拉取失败：{}".format(last_error))


def fetch_board_quote(bk_code):
    """拉取板块自身行情：当日/5日/10日涨幅、领涨股、涨跌家数、主力净流入。"""
    url_tpl = (
        "{host}/api/qt/ulist.np/get?fltt=2&invt=2&secids=90.{bk}"
        "&fields={fields}"
    )
    data = fetch_json(url_tpl, bk=bk_code, fields=BOARD_FIELDS)
    node = data.get("data") or {}
    diff = node.get("diff") or []
    if not diff:
        raise RuntimeError("未找到板块 {}：请确认 BK 代码来自 fetch_sector_boards 输出。".format(bk_code))
    raw = diff[0]
    return {
        "code": str(raw.get("f12") or bk_code),
        "name": str(raw.get("f14") or bk_code),
        "index": to_float(raw.get("f2")),
        "change_pct": to_float(raw.get("f3")),
        "change5_pct": to_float(raw.get("f109")),
        "change10_pct": to_float(raw.get("f160")),
        "leader_name": str(raw.get("f128") or "-"),
        "leader_change_pct": to_float(raw.get("f136")),
        "up_count": to_float(raw.get("f104")),
        "down_count": to_float(raw.get("f105")),
        "amount_yi": round((to_float(raw.get("f6")) or 0) / 1e8, 2),
        "turnover_pct": to_float(raw.get("f8")),
        "main_inflow_yi": round((to_float(raw.get("f62")) or 0) / 1e8, 2),
    }


def fetch_stocks(bk_code, sort, need):
    """按页拉板块成分股（fs=b:BKxxxx），直到覆盖 need 只。"""
    page_size = 100
    collected = []
    last_error = None
    for page_no in range(1, 30):
        url_tpl = (
            "{host}/api/qt/clist/get?pn={pn}&pz={pz}&po=1&np=1&fltt=2&invt=2"
            "&fid={fid}&fs=b:{bk}&fields={fields}"
        )
        page = None
        page_error = None
        for host in HOSTS:
            try:
                url = url_tpl.format(
                    host=host, pn=page_no, pz=page_size, fid=SORTS[sort],
                    bk=bk_code, fields=STOCK_FIELDS)
                data = decode_json(http_get(url))
                if data.get("rc") != 0:
                    page_error = "接口无数据 rc={}".format(data.get("rc"))
                    continue
                page = ((data.get("data") or {}).get("diff") or [])
                break
            except Exception as exc:  # noqa: BLE001 网络或解析失败时切换备用源
                page_error = str(exc)
                continue
        if page is None:
            last_error = "第 {} 页拉取失败：{}".format(page_no, page_error)
            break
        if not page:
            break
        collected.extend(page)
        if len(page) < page_size or len(collected) >= need:
            break
    if not collected and last_error:
        raise RuntimeError(last_error)
    return collected


def normalize_rows(diff, min_turnover, max_turnover, min_gain, max_gain,
                   min_float_cap, max_float_cap, include_st):
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
        change_pct = to_float(raw.get("f3"))
        if min_gain > 0 and (change_pct is None or change_pct < min_gain):
            continue
        if max_gain > 0 and (change_pct is None or change_pct > max_gain):
            continue
        float_cap_yi = to_float(raw.get("f21"))
        if float_cap_yi is not None:
            float_cap_yi = float_cap_yi / 1e8
        if min_float_cap > 0 and (float_cap_yi is None or float_cap_yi < min_float_cap):
            continue
        if max_float_cap > 0 and (float_cap_yi is None or float_cap_yi > max_float_cap):
            continue
        price = to_float(raw.get("f2"))
        high = to_float(raw.get("f15"))
        sec_code = to_sec_code(str(raw.get("f13") or ""), digits)
        rows.append({
            "code": sec_code,
            "name": name,
            "price": price,
            "change_pct": change_pct,
            "change5_pct": to_float(raw.get("f109")),
            "change10_pct": to_float(raw.get("f160")),
            "volume_ratio": to_float(raw.get("f10")),
            "turnover_pct": turnover,
            "amount_wan": fmt_wan(to_float(raw.get("f6"))),
            "amplitude_pct": to_float(raw.get("f7")),
            "pe": to_float(raw.get("f9")),
            "total_cap_yi": round((to_float(raw.get("f20")) or 0) / 1e8, 2),
            "float_cap_yi": round(float_cap_yi, 2) if float_cap_yi is not None else None,
            "main_inflow_wan": fmt_wan(to_float(raw.get("f62"))),
            "industry": str(raw.get("f100") or "-"),
            "ts": to_float(raw.get("f124")),
            "limit_up": is_limit_up(price, high, change_pct, digits),
        })
    return rows


def filter_desc(min_turnover, max_turnover, min_gain, max_gain,
                min_float_cap, max_float_cap, include_st):
    parts = []
    if include_st:
        parts.append("含 ST")
    else:
        parts.append("剔除 ST")
    if min_turnover > 0 or max_turnover > 0:
        parts.append(_range_desc("换手", min_turnover, max_turnover, "%"))
    if min_gain > 0 or max_gain > 0:
        parts.append(_range_desc("当日涨幅", min_gain, max_gain, "%"))
    if min_float_cap > 0 or max_float_cap > 0:
        parts.append(_range_desc("流通市值", min_float_cap, max_float_cap, "亿"))
    return "；".join(parts)


def _range_desc(label, lo, hi, unit):
    if lo > 0 and hi > 0:
        return "{label} {lo}{unit}–{hi}{unit}".format(
            label=label, lo=fmt_num(lo), hi=fmt_num(hi), unit=unit)
    if lo > 0:
        return "{label} ≥{lo}{unit}".format(label=label, lo=fmt_num(lo), unit=unit)
    return "{label} ≤{hi}{unit}".format(label=label, hi=fmt_num(hi), unit=unit)


def render_text(board, rows, sort, top, quote_time, filter_text):
    lines = []
    up = "-" if board["up_count"] is None else int(board["up_count"])
    down = "-" if board["down_count"] is None else int(board["down_count"])
    lines.append("# 板块成分股榜（{name} {code} · 排序：{sort} · Top {top} · 数据时间 {time}）".format(
        name=board["name"], code=board["code"], sort=SORT_NAMES[sort],
        top=top, time=quote_time))
    lines.append("")
    lines.append("板块：今日 {chg}% · 近5日 {c5}% · 近10日 {c10}% · 领涨股 {lead}（{lchg}%）"
                 " · 上涨 {up} / 下跌 {down} · 成交额 {amt}亿 · 主力净流入 {flow}亿".format(
                     chg=fmt_num(board["change_pct"]),
                     c5=fmt_num(board["change5_pct"]),
                     c10=fmt_num(board["change10_pct"]),
                     lead=board["leader_name"],
                     lchg=fmt_num(board["leader_change_pct"]),
                     up=up, down=down, amt=fmt_num(board["amount_yi"], 2),
                     flow=fmt_num(board["main_inflow_yi"], 2)))
    lines.append("")
    lines.append("过滤：{}。近5日/近10日涨跌幅为东财口径（含当日累计）。".format(filter_text))
    if len(rows) < top:
        lines.append("注：过滤后实际返回 {n} 只（请求 {top} 只）；需要更多候选请调大 --top 或放宽过滤。".format(
            n=len(rows), top=top))
    lines.append("")
    header = ("| # | 代码 | 名称 | 现价 | 今日% | 5日% | 10日% | 换手% | 量比 | "
              "成交额(万) | 振幅% | PE | 流通市值(亿) | 总市值(亿) | 主力净流入(万) | 行业 | 备注 |")
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for i, r in enumerate(rows, 1):
        note = "涨停≈" if r["limit_up"] else "-"
        lines.append("| {i} | {code} | {name} | {price} | {chg} | {c5} | {c10} | {to} | {vr} | "
                     "{amt} | {amp} | {pe} | {fc} | {tc} | {flow} | {ind} | {note} |".format(
                         i=i, code=r["code"], name=r["name"],
                         price=fmt_num(r["price"]), chg=fmt_num(r["change_pct"]),
                         c5=fmt_num(r["change5_pct"]), c10=fmt_num(r["change10_pct"]),
                         to=fmt_num(r["turnover_pct"]), vr=fmt_num(r["volume_ratio"], 2),
                         amt=r["amount_wan"], amp=fmt_num(r["amplitude_pct"]),
                         pe=fmt_num(r["pe"]), fc=fmt_num(r["float_cap_yi"]),
                         tc=fmt_num(r["total_cap_yi"]), flow=r["main_inflow_wan"],
                         ind=r["industry"], note=note))
    lines.append("")
    lines.append("数据来源：东方财富板块/行情公开接口；行情时间为当日实时/延迟数据，"
                 "精确到分钟级，使用时以交易所数据为准。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="A股 板块成分股榜数据报告（东方财富公开接口）")
    ap.add_argument("--board", required=True,
                    help="板块 BK 代码（如 BK0882，来自 fetch_sector_boards 输出）")
    ap.add_argument("--top", type=int, default=30, help="榜单数量（默认 30）")
    ap.add_argument("--sort", choices=sorted(SORTS), default="change",
                    help="排序字段（默认 change 当日涨跌幅）")
    ap.add_argument("--min-turnover", type=float, default=0,
                    help="最低换手率过滤，如 5 表示 >5%%（默认不过滤）")
    ap.add_argument("--max-turnover", type=float, default=0,
                    help="最高换手率过滤，如 10 表示 <10%%（默认不过滤）")
    ap.add_argument("--min-gain", type=float, default=0,
                    help="最低当日涨幅过滤，如 3 表示 ≥3%%（默认不过滤）")
    ap.add_argument("--max-gain", type=float, default=0,
                    help="最高当日涨幅过滤，如 10 表示 ≤10%%（默认不过滤）")
    ap.add_argument("--min-float-cap", type=float, default=0,
                    help="最低流通市值（亿）过滤，如 50（默认不过滤）")
    ap.add_argument("--max-float-cap", type=float, default=0,
                    help="最高流通市值（亿）过滤，如 200（默认不过滤）")
    ap.add_argument("--include-st", action="store_true", help="不剔除名称含 ST 的股票")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    bk_code = args.board.strip().upper()
    if not bk_code.startswith("BK") or not bk_code[2:].isdigit():
        sys.exit("错误：--board 应为 BK 代码（如 BK0882）。")
    if args.top <= 0:
        sys.exit("错误：--top 必须为正整数。")

    board = fetch_board_quote(bk_code)
    has_filter = bool(args.min_turnover or args.max_turnover or args.min_gain
                      or args.max_gain or args.min_float_cap or args.max_float_cap)
    raw_need = args.top if not has_filter else max(args.top * 5, 300)
    diff = fetch_stocks(bk_code, args.sort, raw_need)
    rows = normalize_rows(
        diff, args.min_turnover, args.max_turnover, args.min_gain, args.max_gain,
        args.min_float_cap, args.max_float_cap, args.include_st)[:args.top]
    ts = next((r["ts"] for r in rows if r["ts"]), time.time())
    quote_time = fmt_dt(ts)

    if args.json:
        payload = {
            "board": board,
            "sort": args.sort,
            "sort_name": SORT_NAMES[args.sort],
            "top": args.top,
            "quote_time": quote_time,
            "rows": rows,
            "note": "数据来源：东方财富板块/行情公开接口；近5日/近10日涨跌幅为东财口径",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("板块成分股榜为空：请调整过滤条件（--top / --sort / --min-turnover / "
              "--max-turnover / --min-gain / --max-gain / --min-float-cap / "
              "--max-float-cap / --include-st）后重试。")
        return
    print(render_text(board, rows, args.sort, args.top, quote_time,
                      filter_desc(args.min_turnover, args.max_turnover,
                                  args.min_gain, args.max_gain,
                                  args.min_float_cap, args.max_float_cap,
                                  args.include_st)))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 统一报错，不静默
        sys.exit("错误：{}".format(exc))
