#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""个股资金流向报告（东方财富公开接口，无需密钥）。

用法:
    python fetch_capital_flow.py <代码> [--json]

代码: 与 fetch_quote.py 相同，如 sh600410 / sz002491 / bj920002。
输出: 资金流向报告——最新交易日主力/超大单/大单/中单/小单净流入 + 近5日主力净流入趋势，
配合量价判断放量是流入还是出货；不产生缓存文件。
"""

import argparse
import json
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 东方财富 secid：沪市=1，深市/北交所=0（与 fetch_quote.py 一致）
MARKET = {"sh": "1", "sz": "0", "bj": "0"}

HOSTS = [
    "https://push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
]
FFLOW_URL = (
    "{host}/api/qt/stock/fflow/kline/get"
    "?lmt=1&klt=101&secid={secid}"
    "&fields1=f1,f2,f3,f7"
    "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
)
MAIN5_URL = (
    "{host}/api/qt/stock/get"
    "?secid={secid}&fltt=2&fields=f58,f178"
)


def to_secid(code):
    prefix, digits = code[:2], code[2:]
    if prefix not in MARKET or len(digits) != 6 or not digits.isdigit():
        return None
    return MARKET[prefix] + "." + digits


def http_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://data.eastmoney.com/",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_wan(value):
    if value is None:
        return "-"
    return "{:,.0f}".format(value / 1e4)


def fetch_with_fallback(url_tpl, secid):
    last_exc = None
    for host in HOSTS:
        try:
            raw = http_get(url_tpl.format(host=host, secid=secid))
            return json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception as exc:
            last_exc = exc
    if last_exc is not None:
        raise last_exc
    return {}


def fetch(code):
    secid = to_secid(code)
    data = fetch_with_fallback(FFLOW_URL, secid)
    klines = (data.get("data") or {}).get("klines") or []
    latest = None
    if klines:
        b = klines[-1].split(",")
        if len(b) >= 6:
            latest = {
                "date": b[0],
                "main": to_float(b[1]),
                "small": to_float(b[2]),
                "medium": to_float(b[3]),
                "large": to_float(b[4]),
                "super_large": to_float(b[5]),
            }

    data2 = fetch_with_fallback(MAIN5_URL, secid)
    d2 = data2.get("data") or {}
    main5 = []
    try:
        rows = json.loads(d2.get("f178") or "[]")
    except (TypeError, ValueError):
        rows = []
    for r in rows:
        amt = to_float(r.get("mainNetAmt"))
        if amt is not None:
            main5.append({"date": r.get("date"), "main": amt})
    return {
        "name": d2.get("f58"),
        "latest_day": latest,
        "main_5d": main5,
    }


def build_payload(code):
    result = fetch(code)
    if result["latest_day"] is None and not result["main_5d"]:
        sys.exit("错误：未获取到资金流向数据，请稍后重试。")
    return {
        "code": code,
        "name": result["name"],
        "latest_day": result["latest_day"],
        "main_5d": result["main_5d"],
        "note": "数据来源：东方财富资金流公开接口（单位：元）",
    }


def print_text(code, payload):
    print("=" * 84)
    print("个股资金流向 · {}（{}）".format(payload.get("name") or code, code))
    print("=" * 84)
    latest = payload["latest_day"]
    if latest:
        print("最新交易日 {}：".format(latest["date"]))
        print("  主力净流入 {:>12} 万元".format(fmt_wan(latest["main"])))
        print("  超大单净流入 {:>10} 万元    大单净流入 {:>10} 万元".format(
            fmt_wan(latest["super_large"]), fmt_wan(latest["large"])))
        print("  中单净流入 {:>10} 万元    小单净流入 {:>10} 万元".format(
            fmt_wan(latest["medium"]), fmt_wan(latest["small"])))
    else:
        print("最新交易日明细：无数据")
    print("-" * 84)
    main5 = payload["main_5d"]
    if main5:
        print("近5日主力净流入：")
        total = 0
        for r in main5:
            total += r["main"] or 0
            print("  {}  {:>12} 万元".format(r["date"], fmt_wan(r["main"])))
        print("  合计      {:>12} 万元".format(fmt_wan(total)))
    else:
        print("近5日主力净流入：无数据")
    print("=" * 84)
    print("注：数据来源为东方财富资金流公开接口；单位万元，正=净流入，负=净流出。")


def main():
    ap = argparse.ArgumentParser(description="个股资金流向报告")
    ap.add_argument("code", help="如 sh600410 / sz002491")
    ap.add_argument("--json", action="store_true", help="输出JSON")
    args = ap.parse_args()

    code = args.code.lower().strip()
    if to_secid(code) is None:
        sys.exit("错误：代码格式应为 sh/sz/bj + 6位数字，如 sh600410。")

    try:
        payload = build_payload(code)
    except Exception as exc:
        sys.exit("错误：网络请求失败（{}）。请稍后重试。".format(exc))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print_text(code, payload)


if __name__ == "__main__":
    main()
