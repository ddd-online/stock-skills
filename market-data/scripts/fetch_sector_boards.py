#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股 板块行情榜数据报告（行业/概念板块，东方财富公开接口，无需密钥）。

用法:
    python fetch_sector_boards.py [--type industry|concept|all] [--sort change|flow|amount|gain5|gain10]
                                  [--top N] [--min-up N] [--json]

输出: 板块行情榜——按所选排序返回 Top N 行业/概念板块，含板块指数、当日涨跌幅、
近5日/近10日累计涨跌幅（东财口径）、领涨股（名称/代码/涨幅）、上涨/下跌家数、
成交额、换手率与主力净流入；不产生缓存文件。
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

# fs 板块全集：m:90=板块市场 t:2=行业板块 t:3=概念板块 f:!50=剔除已退市
BOARD_FS = {
    "industry": "m:90+t:2+f:!50",
    "concept": "m:90+t:3+f:!50",
    "all": "m:90+t:2+f:!50,m:90+t:3+f:!50",
}

BOARD_TYPE_NAMES = {
    "industry": "行业板块",
    "concept": "概念板块",
    "all": "行业+概念板块",
}

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

SORT_VALUES = {
    "change": "change_pct",
    "flow": "main_inflow_yi",
    "amount": "amount_yi",
    "gain5": "change5_pct",
    "gain10": "change10_pct",
}

# f109=近5日累计涨跌幅、f160=近10日累计涨跌幅（东财 clist 板块/个股通用口径）
FIELDS = (
    "f2,f3,f6,f8,f12,f13,f14,f62,f104,f105,f109,f124,f128,f136,f140,f141,f160"
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
    # 领涨股市场：1=沪市、0=深市（北交所领涨股极少见，按深市口径处理即可）
    if market == "1":
        return "sh" + digits
    return "sz" + digits


def fetch_page(board_type, sort, page_no, page_size):
    last_error = None
    url_tpl = (
        "{host}/api/qt/clist/get?pn={pn}&pz={pz}&po=1&np=1&fltt=2&invt=2"
        "&fid={fid}&fs={fs}&fields={fields}"
    )
    for host in HOSTS:
        try:
            url = url_tpl.format(
                host=host, pn=page_no, pz=page_size,
                fid=SORTS[sort], fs=BOARD_FS[board_type], fields=FIELDS,
            )
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
    raise RuntimeError("东方财富板块接口第 {} 页拉取失败：{}".format(page_no, last_error))


def normalize_rows(diff, min_up):
    rows = []
    for raw in diff:
        bk_code = str(raw.get("f12") or "")
        if not bk_code.startswith("BK"):
            continue
        up_count = to_float(raw.get("f104"))
        if min_up > 0 and (up_count is None or up_count < min_up):
            continue
        leader_digits = str(raw.get("f140") or "")
        leader_code = None
        if len(leader_digits) == 6 and leader_digits.isdigit():
            leader_code = to_sec_code(str(raw.get("f141") or ""), leader_digits)
        rows.append({
            "code": bk_code,
            "name": str(raw.get("f14") or "-"),
            "index": to_float(raw.get("f2")),
            "change_pct": to_float(raw.get("f3")),
            "change5_pct": to_float(raw.get("f109")),
            "change10_pct": to_float(raw.get("f160")),
            "leader_name": str(raw.get("f128") or "-"),
            "leader_code": leader_code,
            "leader_change_pct": to_float(raw.get("f136")),
            "up_count": up_count,
            "down_count": to_float(raw.get("f105")),
            "amount_yi": round((to_float(raw.get("f6")) or 0) / 1e8, 2),
            "turnover_pct": to_float(raw.get("f8")),
            "main_inflow_yi": round((to_float(raw.get("f62")) or 0) / 1e8, 2),
            "ts": to_float(raw.get("f124")),
        })
    return rows


def render_text(rows, board_type, sort, top, min_up, search, quote_time):
    lines = []
    lines.append("# 板块行情榜（{board} · 排序：{sort} · Top {top} · 数据时间 {time}）".format(
        board=BOARD_TYPE_NAMES[board_type], sort=SORT_NAMES[sort],
        top=top, time=quote_time))
    lines.append("")
    if min_up > 0:
        lines.append("口径：今日/近5日/近10日涨跌幅为东方财富板块行情口径；"
                     "上涨家数低于 {min_up} 的板块已剔除。数据未经验证，仅供板块扫描。".format(
                         min_up=min_up))
    else:
        lines.append("口径：今日/近5日/近10日涨跌幅为东方财富板块行情口径；"
                     "不过滤上涨家数。数据未经验证，仅供板块扫描。")
    if search:
        lines.append("关键词：仅显示名称包含“{kw}”的板块。".format(kw=search))
    if len(rows) < top:
        lines.append("注：过滤后实际返回 {n} 个板块（请求 {top} 个）。".format(n=len(rows), top=top))
    lines.append("")
    header = ("| # | 板块代码 | 名称 | 指数 | 今日% | 5日% | 10日% | 领涨股 | "
              "领涨股% | 涨/跌家数 | 成交额(亿) | 换手% | 主力净流入(亿) |")
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for i, r in enumerate(rows, 1):
        up = "-" if r["up_count"] is None else int(r["up_count"])
        down = "-" if r["down_count"] is None else int(r["down_count"])
        lines.append("| {i} | {code} | {name} | {idx} | {chg} | {c5} | {c10} | "
                     "{lead} | {lchg} | {up}/{down} | {amt} | {to} | {flow} |".format(
                         i=i, code=r["code"], name=r["name"],
                         idx=fmt_num(r["index"], 2), chg=fmt_num(r["change_pct"]),
                         c5=fmt_num(r["change5_pct"]), c10=fmt_num(r["change10_pct"]),
                         lead=r["leader_name"], lchg=fmt_num(r["leader_change_pct"]),
                         up=up, down=down, amt=fmt_num(r["amount_yi"], 2),
                         to=fmt_num(r["turnover_pct"]), flow=fmt_num(r["main_inflow_yi"], 2)))
    lines.append("")
    lines.append("数据来源：东方财富板块行情公开接口（push2 clist，行业/概念板块）；"
                 "行情时间为当日实时/延迟数据，精确到分钟级，使用时以交易所数据为准。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="A股 板块行情榜数据报告（东方财富公开接口）")
    ap.add_argument("--type", choices=sorted(BOARD_FS), default="industry",
                    help="板块类型：industry 行业 / concept 概念 / all 全部（默认 industry）")
    ap.add_argument("--sort", choices=sorted(SORTS), default="change",
                    help="排序字段（默认 change 当日涨跌幅）")
    ap.add_argument("--top", type=int, default=20, help="榜单数量（默认 20）")
    ap.add_argument("--min-up", type=int, default=0,
                    help="最低上涨家数过滤，如 5 表示剔除上涨家数<5 的小板块（默认不过滤）")
    ap.add_argument("--search", type=str, default="",
                    help="按板块名称关键词定位（如 --search 液冷；会翻完整板块列表后过滤）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.top <= 0:
        sys.exit("错误：--top 必须为正整数。")

    page_size = 100
    max_pages = 12  # 行业+概念合计约 600 个板块，12 页足够
    diff = []
    for page_no in range(1, max_pages + 1):
        page = fetch_page(args.type, args.sort, page_no, page_size)
        diff.extend(page)
        if len(page) < page_size:
            break
        if not args.search and len(diff) >= args.top + page_size:
            break
    rows = normalize_rows(diff, args.min_up)
    if args.search:
        keyword = args.search.strip()
        rows = [r for r in rows if keyword.lower() in r["name"].lower()]
        key = SORT_VALUES[args.sort]
        rows.sort(key=lambda r: (r[key] is None, -(r[key] if r[key] is not None else 0)))
    rows = rows[:args.top]
    ts = next((r["ts"] for r in rows if r["ts"]), time.time())
    quote_time = fmt_dt(ts)

    if args.json:
        payload = {
            "board_type": args.type,
            "board_type_name": BOARD_TYPE_NAMES[args.type],
            "sort": args.sort,
            "sort_name": SORT_NAMES[args.sort],
            "top": args.top,
            "min_up": args.min_up,
            "search": args.search.strip(),
            "quote_time": quote_time,
            "rows": rows,
            "note": "数据来源：东方财富板块行情公开接口；近5日/近10日涨跌幅为东财口径",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("板块榜为空：请调整过滤条件（--type / --sort / --top / --min-up / --search）后重试。")
        return
    print(render_text(rows, args.type, args.sort, args.top, args.min_up,
                      args.search.strip(), quote_time))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 统一报错，不静默
        sys.exit("错误：{}".format(exc))
