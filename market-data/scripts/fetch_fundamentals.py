#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股 财报核心指标报告（东方财富数据中心公开接口，无需密钥）。

用法:
    python fetch_fundamentals.py <代码> [--periods N] [--json]

代码: sh600410 / sz002498 / bj920002
输出: 财报报告——最近N个报告期的营业总收入、净利润、毛利率、净利率、负债率及同比；
不产生缓存文件。

口径说明: 报告期数值为累计值（一季报=第1季度，中报=上半年，年报=全年）；
同比必须和去年同期比，不能拿一季报和年报直接比。取不到的字段一律输出 null/「-」，不填 0。
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import http_util  # noqa: E402 与脚本同目录的网络层（直连优先、系统代理兜底）

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

API_URL = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
    "?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL&filter={filter}"
    "&pageNumber=1&pageSize={size}&sortTypes=-1&sortColumns=REPORT_DATE"
    "&source=HSF10&client=PC"
)

# 网络层统一走 http_util：直连优先（绕过 Windows 注册表代理），连续失败 3 次后回退系统代理。
_open = http_util.open_url


def http_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://emweb.securities.eastmoney.com/",
    })
    with _open(req, timeout=25) as resp:
        return resp.read()


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def yi_or_none(value):
    """元 → 亿元；取不到返回 None（缺失不等于 0）。"""
    num = to_float(value)
    return None if num is None else round(num / 1e8, 2)


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
    elif secucode.startswith("BJ"):
        secucode = secucode[2:] + ".BJ"
    else:
        sys.exit("错误：代码格式应为 sh600410 / sz002498 / bj920002。")
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
            "revenue_yi": yi_or_none(r.get("TOTALOPERATEREVE")),
            "revenue_yoy_pct": to_float(r.get("TOTALOPERATEREVETZ")),
            "net_profit_yi": yi_or_none(r.get("PARENTNETPROFIT")),
            "net_profit_yoy_pct": to_float(r.get("PARENTNETPROFITTZ")),
            "gross_margin_pct": to_float(r.get("XSMLL")),
            "net_margin_pct": to_float(r.get("XSJLL")),
            "debt_ratio_pct": to_float(r.get("ZCFZL")),
            "roe_pct": to_float(r.get("ROEJQ")),
            "net_cash_operate_yi": yi_or_none(r.get("NETCASH_OPERATE_PK")),
            "eps": to_float(r.get("EPSJB")),
        })
    return out


def print_text(code, rows):
    print("=" * 92)
    print("财报核心指标（来源：东方财富数据中心）")
    print("=" * 92)
    print("{:<14}{:>10}{:>9}{:>11}{:>9}{:>9}{:>9}{:>9}{:>9}{:>13}".format(
        "报告期", "营收(亿)", "营收同比%", "净利(亿)", "净利同比%",
        "毛利率%", "净利率%", "负债率%", "ROE%", "经营现金流(亿)"))
    print("-" * 92)
    for r in rows:
        print("{:<14}{:>10}{:>9}{:>11}{:>9}{:>9}{:>9}{:>9}{:>9}{:>13}".format(
            str(r.get("report") or "-")[:14],
            fmt_num(r.get("revenue_yi")),
            fmt_num(r.get("revenue_yoy_pct")),
            fmt_num(r.get("net_profit_yi")),
            fmt_num(r.get("net_profit_yoy_pct")),
            fmt_num(r.get("gross_margin_pct")),
            fmt_num(r.get("net_margin_pct")),
            fmt_num(r.get("debt_ratio_pct")),
            fmt_num(r.get("roe_pct")),
            fmt_num(r.get("net_cash_operate_yi")),
        ))
    print("=" * 92)
    print("口径：数值为报告期累计；同比须与去年同期比（一季报比一季报，年报比年报）。")


def main():
    ap = argparse.ArgumentParser(description="A股 财报核心指标报告")
    ap.add_argument("code", help="如 sh600410 / sz002498 / bj920002")
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
    http_util.run(main)
