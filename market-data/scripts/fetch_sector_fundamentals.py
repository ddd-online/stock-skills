#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股 板块成分股财务排名数据报告（东方财富公开接口，无需密钥）。

用法:
    python fetch_sector_fundamentals.py --board BK0882 [--top N] [--include-st] [--json]

输出: 指定板块（BK 代码）总市值前 N 名成分股的最新报告期财务数据——
营收（及同比）、净利（及同比）、毛利率、ROE、负债率，按营收与按净利分别排序，
供“行业龙头（基本面第一梯队）”筛选使用；不产生缓存文件。

口径: 候选=板块内按总市值降序取前 N；财报=最近一期累计值（与去年同期比）；
主营构成/收入占比不在本脚本范围，需另用 F10/公告核验。
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HOSTS = [
    "https://push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
]

FIN_API = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
    "?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL&filter={filter}"
    "&pageNumber=1&pageSize=1&sortTypes=-1&sortColumns=REPORT_DATE"
    "&source=HSF10&client=PC"
)

BOARD_FIELDS = "f12,f13,f14,f3,f104,f105,f128,f136"
STOCK_FIELDS = "f2,f3,f12,f13,f14,f20,f21"


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


def fmt_dt(ts):
    if not ts:
        return "-"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return "-"


def to_sec_code(market, digits):
    if market == "1":
        return "sh" + digits
    if digits[:2] == "92" or digits[0] in ("4", "8"):
        return "bj" + digits
    return "sz" + digits


def fetch_json(url_tpl, **params):
    last_error = None
    for host in HOSTS:
        try:
            url = url_tpl.format(host=host, **params)
            data = decode_json(http_get(url, "https://data.eastmoney.com/"))
            if data.get("rc") != 0:
                last_error = "接口无数据 rc={}".format(data.get("rc"))
                continue
            return data
        except Exception as exc:  # noqa: BLE001 网络或解析失败时切换备用源
            last_error = str(exc)
            continue
    raise RuntimeError("东方财富行情接口拉取失败：{}".format(last_error))


def fetch_board_quote(bk_code):
    url_tpl = "{host}/api/qt/ulist.np/get?fltt=2&invt=2&secids=90.{bk}&fields={fields}"
    data = fetch_json(url_tpl, bk=bk_code, fields=BOARD_FIELDS)
    node = data.get("data") or {}
    diff = node.get("diff") or []
    if not diff:
        raise RuntimeError("未找到板块 {}：请确认 BK 代码来自 fetch_sector_boards 输出。".format(bk_code))
    raw = diff[0]
    return {
        "code": str(raw.get("f12") or bk_code),
        "name": str(raw.get("f14") or bk_code),
        "change_pct": to_float(raw.get("f3")),
        "up_count": to_float(raw.get("f104")),
        "down_count": to_float(raw.get("f105")),
        "leader_name": str(raw.get("f128") or "-"),
        "leader_change_pct": to_float(raw.get("f136")),
    }


def fetch_top_by_cap(bk_code, top):
    """按总市值（f20）降序取板块前 top 名成分股。"""
    url_tpl = (
        "{host}/api/qt/clist/get?pn=1&pz={pz}&po=1&np=1&fltt=2&invt=2"
        "&fid=f20&fs=b:{bk}&fields={fields}"
    )
    data = fetch_json(url_tpl, pz=top, bk=bk_code, fields=STOCK_FIELDS)
    return ((data.get("data") or {}).get("diff") or [])


def fetch_latest_finance(sec_code):
    """按个股拉最新一期财报核心指标（与 fetch_fundamentals 同一数据中心接口）。"""
    upper = sec_code.upper().strip()
    if upper.startswith("SH"):
        secucode = upper[2:] + ".SH"
    elif upper.startswith("SZ"):
        secucode = upper[2:] + ".SZ"
    elif upper.startswith("BJ"):
        secucode = upper[2:] + ".BJ"
    else:
        return None
    url = FIN_API.format(
        filter=urllib.parse.quote('(SECUCODE="{}")'.format(secucode), safe=""))
    raw = http_get(url, "https://emweb.securities.eastmoney.com/")
    data = decode_json(raw)
    rows = ((data.get("result") or {}).get("data") or [])
    if not rows:
        return None
    r = rows[0]
    return {
        "report": str(r.get("REPORT_DATE_NAME") or "-"),
        "revenue_yi": round((to_float(r.get("TOTALOPERATEREVE")) or 0) / 1e8, 2),
        "revenue_yoy_pct": to_float(r.get("TOTALOPERATEREVETZ")),
        "net_profit_yi": round((to_float(r.get("PARENTNETPROFIT")) or 0) / 1e8, 2),
        "net_profit_yoy_pct": to_float(r.get("PARENTNETPROFITTZ")),
        "gross_margin_pct": to_float(r.get("XSMLL")),
        "net_margin_pct": to_float(r.get("XSJLL")),
        "debt_ratio_pct": to_float(r.get("ZCFZL")),
        "roe_pct": to_float(r.get("ROEJQ")),
        "net_cash_operate_yi": round((to_float(r.get("NETCASH_OPERATE_PK")) or 0) / 1e8, 2),
    }


def render_text(board, rows, quote_time):
    lines = []
    up = "-" if board["up_count"] is None else int(board["up_count"])
    down = "-" if board["down_count"] is None else int(board["down_count"])
    lines.append("# 板块成分股财务排名（{name} {code} · 报告生成时间 {time}）".format(
        name=board["name"], code=board["code"], time=quote_time))
    lines.append("")
    lines.append("板块：今日 {chg}% · 领涨股 {lead}（{lchg}%） · 上涨 {up} / 下跌 {down}".format(
        chg=fmt_num(board["change_pct"]), lead=board["leader_name"],
        lchg=fmt_num(board["leader_change_pct"]), up=up, down=down))
    lines.append("")
    lines.append("候选口径：板块内按总市值降序取前 {n} 名；财报为最新报告期累计值，"
                 "同比须与去年同期比。未取到财报的个股已标注。".format(n=len(rows)))
    lines.append("")

    def table(rows_, title, key):
        lines.append("## {title}（按{key_name}降序）".format(
            title=title, key_name="营收" if key == "revenue_yi" else "净利"))
        lines.append("")
        lines.append("| # | 代码 | 名称 | 报告期 | 流通市值(亿) | 营收(亿) | 营收同比% | "
                     "净利(亿) | 净利同比% | 毛利率% | ROE% | 负债率% | 经营现金流(亿) |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for i, r in enumerate(rows_, 1):
            lines.append("| {i} | {code} | {name} | {rp} | {fc} | {rev} | {ry} | "
                         "{np} | {ny} | {gm} | {roe} | {debt} | {cash} |".format(
                             i=i, code=r["code"], name=r["name"],
                             rp=str(r.get("report") or "-")[:14],
                             fc=fmt_num(r["float_cap_yi"]),
                             rev=fmt_num(r["revenue_yi"]),
                             ry=fmt_num(r["revenue_yoy_pct"]),
                             np=fmt_num(r["net_profit_yi"]),
                             ny=fmt_num(r["net_profit_yoy_pct"]),
                             gm=fmt_num(r["gross_margin_pct"]),
                             roe=fmt_num(r["roe_pct"]),
                             debt=fmt_num(r["debt_ratio_pct"]),
                             cash=fmt_num(r["net_cash_operate_yi"])))
        lines.append("")

    rev_rank = sorted(rows, key=lambda x: x["revenue_yi"] or -1, reverse=True)
    table(rev_rank, "营收榜", "revenue_yi")
    profit_rank = sorted(rows, key=lambda x: x["net_profit_yi"] or -1, reverse=True)
    table(profit_rank, "净利榜", "net_profit_yi")

    missing = [r["code"] + " " + r["name"] for r in rows
               if r.get("report") == "-" or r["revenue_yi"] is None]
    if missing:
        lines.append("未取到最新财报：{}（数据缺失时不可作为行业龙头依据）".format("、".join(missing)))
        lines.append("")
    lines.append("数据来源：东方财富数据中心（F10 主要财务指标）+ 板块成分行情；"
                 "主营收入占比需另用 F10/公告核验，本报告不提供。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="A股 板块成分股财务排名报告（东方财富公开接口）")
    ap.add_argument("--board", required=True,
                    help="板块 BK 代码（如 BK0882，来自 fetch_sector_boards 输出）")
    ap.add_argument("--top", type=int, default=12,
                    help="按总市值取前 N 名拉财报（默认 12，最多 30；每只一次财报请求）")
    ap.add_argument("--include-st", action="store_true", help="不剔除名称含 ST 的股票")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    bk_code = args.board.strip().upper()
    if not bk_code.startswith("BK") or not bk_code[2:].isdigit():
        sys.exit("错误：--board 应为 BK 代码（如 BK0882）。")
    if args.top <= 0 or args.top > 30:
        sys.exit("错误：--top 应为 1–30 的整数。")

    board = fetch_board_quote(bk_code)
    diff = fetch_top_by_cap(bk_code, args.top)
    rows = []
    for raw in diff:
        digits = str(raw.get("f12") or "")
        name = str(raw.get("f14") or "")
        if len(digits) != 6 or not digits.isdigit():
            continue
        if not args.include_st and "ST" in name.upper():
            continue
        sec_code = to_sec_code(str(raw.get("f13") or ""), digits)
        fin = fetch_latest_finance(sec_code)
        if fin is None:
            fin = {"report": "-", "revenue_yi": None, "revenue_yoy_pct": None,
                   "net_profit_yi": None, "net_profit_yoy_pct": None,
                   "gross_margin_pct": None, "net_margin_pct": None,
                   "debt_ratio_pct": None, "roe_pct": None}
        row = {
            "code": sec_code,
            "name": name,
            "price": to_float(raw.get("f2")),
            "change_pct": to_float(raw.get("f3")),
            "float_cap_yi": round((to_float(raw.get("f21")) or 0) / 1e8, 2),
            "total_cap_yi": round((to_float(raw.get("f20")) or 0) / 1e8, 2),
        }
        row.update(fin)
        rows.append(row)
        if len(rows) >= args.top:
            break

    quote_time = fmt_dt(time.time())
    if args.json:
        payload = {
            "board": board,
            "top": args.top,
            "quote_time": quote_time,
            "rows": rows,
            "note": "数据来源：东方财富数据中心 + 板块成分行情；最新报告期累计口径",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("未获取到任何成分股数据：请确认 --board 正确，或放宽 --top/--include-st。")
        return
    print(render_text(board, rows, quote_time))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 统一报错，不静默
        sys.exit("错误：{}".format(exc))
