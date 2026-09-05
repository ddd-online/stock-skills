#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股 财报核心指标报告（东方财富数据中心公开接口，无需密钥）。

用法:
    python fetch_fundamentals.py <代码> [--periods N] [--json]

代码: sh600410 / sz002498
输出: 财报报告——最近N个报告期的营业总收入、净利润、毛利率、净利率、负债率及同比；
不产生缓存文件。

口径说明: 报告期数值为累计值（一季报=第1季度，中报=上半年，年报=全年）；
同比必须和去年同期比，不能拿一季报和年报直接比。
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_URL = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
    "?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL&filter={filter}"
    "&pageNumber=1&pageSize={size}&sortTypes=-1&sortColumns=REPORT_DATE"
    "&source=HSF10&client=PC"
)


def http_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://emweb.securities.eastmoney.com/",
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_num(value, digits=2):
    if value is None:
        return "-"
    return "{:.{}f}".format(value, digits)


def fetch(code, size):
    secucode = code.upper().strip()
    if secucode.startswith("SH"):
        secucode = secucode[2:] + ".SH"
    elif secucode.startswith("SZ"):
        secucode = secucode[2:] + ".SZ"
    else:
        sys.exit("错误：代码格式应为 sh600410 / sz002498。")
    url = API_URL.format(
        filter=urllib.parse.quote('(SECUCODE="{}")'.format(secucode), safe=""),
        size=size,
    )
    raw = http_get(url)
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    return (data.get("result") or {}).get("data") or []


def build_payload(code, size):
    rows = fetch(code, size)
    if not rows:
        sys.exit("错误：未获取到财报数据，请检查代码是否有误。")
    out = []
    for r in rows:
        out.append({
            "report": r.get("REPORT_DATE_NAME"),
            "revenue_yi": round((to_float(r.get("TOTALOPERATEREVE")) or 0) / 1e8, 2),
            "revenue_yoy_pct": to_float(r.get("TOTALOPERATEREVETZ")),
            "net_profit_yi": round((to_float(r.get("PARENTNETPROFIT")) or 0) / 1e8, 2),
            "net_profit_yoy_pct": to_float(r.get("PARENTNETPROFITTZ")),
            "gross_margin_pct": to_float(r.get("XSMLL")),
            "net_margin_pct": to_float(r.get("XSJLL")),
            "debt_ratio_pct": to_float(r.get("ZCFZL")),
            "roe_pct": to_float(r.get("ROEJQ")),
            "eps": to_float(r.get("EPSJB")),
        })
    return out


def print_text(code, rows):
    print("=" * 92)
    print("财报核心指标（来源：东方财富数据中心）")
    print("=" * 92)
    print("{:<14}{:>10}{:>9}{:>11}{:>9}{:>9}{:>9}{:>9}{:>9}".format(
        "报告期", "营收(亿)", "营收同比%", "净利(亿)", "净利同比%",
        "毛利率%", "净利率%", "负债率%", "ROE%"))
    print("-" * 92)
    for r in rows:
        print("{:<14}{:>10}{:>9}{:>11}{:>9}{:>9}{:>9}{:>9}{:>9}".format(
            str(r.get("report") or "-")[:14],
            fmt_num(r.get("revenue_yi")),
            fmt_num(r.get("revenue_yoy_pct")),
            fmt_num(r.get("net_profit_yi")),
            fmt_num(r.get("net_profit_yoy_pct")),
            fmt_num(r.get("gross_margin_pct")),
            fmt_num(r.get("net_margin_pct")),
            fmt_num(r.get("debt_ratio_pct")),
            fmt_num(r.get("roe_pct")),
        ))
    print("=" * 92)
    print("口径：数值为报告期累计；同比须与去年同期比（一季报比一季报，年报比年报）。")


def main():
    ap = argparse.ArgumentParser(description="A股 财报核心指标报告")
    ap.add_argument("code", help="如 sh600410 / sz002498")
    ap.add_argument("--periods", type=int, default=4, help="报告期数量，默认4")
    ap.add_argument("--json", action="store_true", help="输出JSON")
    args = ap.parse_args()

    try:
        rows = build_payload(args.code, args.periods)
    except Exception as exc:
        sys.exit("错误：网络请求失败（{}）。请稍后重试。".format(exc))

    if args.json:
        out = {
            "code": args.code.lower().strip(),
            "periods": rows,
            "note": "数据来源：东方财富数据中心",
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print_text(args.code, rows)


if __name__ == "__main__":
    main()
