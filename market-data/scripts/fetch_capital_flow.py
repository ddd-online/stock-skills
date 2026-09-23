#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""个股资金流向报告（东方财富为主、新浪为备用源，均为公开接口，无需密钥）。

用法:
    python fetch_capital_flow.py <代码> [--source auto|eastmoney|sina] [--json]

代码: 与 fetch_quote.py 相同，如 sh600410 / sz002491 / bj920002。
输出: 资金流向报告——最新交易日主力/超大单/大单/中单/小单净流入 + 近5日主力净流入趋势，
配合量价判断放量是流入还是出货；不产生缓存文件。

数据源: 东方财富资金流接口优先；该接口不可用时自动切新浪个股资金流
（MoneyFlow.ssl_qsfx_zjlrqs，主力净额＝大单+超大单口径）——备用源给主力净额、主动净额与
近5日主力净额，超大单/大单/中单/小单拆分标「未获取」，报告里标注实际数据源与口径差异。
"""

import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fallback_sources as fb  # noqa: E402 与脚本同目录的备用取数模块

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SOURCE_ORDER = {
    "auto": ["eastmoney", "sina"],
    "eastmoney": ["eastmoney"],
    "sina": ["sina"],
}

SOURCE_NAMES = {
    "eastmoney": "东方财富资金流公开接口（超大单/大单/中单/小单拆分）",
    "sina": "新浪个股资金流（主力净额＝大单+超大单；拆分未获取）",
}

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


def fetch_sina(code):
    """备用源：新浪个股资金流（主力净额＝大单+超大单），给主力净额与近5日历史。"""
    history = fb.fetch_sina_stock_flow_history(code, days=6)
    if not history:
        raise RuntimeError("新浪资金流未返回该股数据")
    latest = history[0]
    name = None
    quotes = fb.fetch_tencent_quotes([code])
    if code in quotes:
        name = quotes[code].get("name")
    return {
        "name": name,
        "latest_day": {
            "date": latest["date"],
            "main": latest["main_yuan"],
            "small": None,
            "medium": None,
            "large": None,
            "super_large": None,
            "net": latest["net_yuan"],
        },
        "main_5d": [{"date": row["date"], "main": row["main_yuan"]}
                    for row in reversed(history[:5])],
    }


def build_payload(code, source="auto"):
    errors = []
    for candidate in SOURCE_ORDER[source]:
        try:
            result = fetch(code) if candidate == "eastmoney" else fetch_sina(code)
            if result.get("latest_day") is None and not result.get("main_5d"):
                raise RuntimeError("接口无数据")
            return {
                "code": code,
                "name": result.get("name"),
                "latest_day": result.get("latest_day"),
                "main_5d": result.get("main_5d") or [],
                "source": candidate,
                "source_name": SOURCE_NAMES[candidate],
                "note": "数据来源：{}（单位：元）".format(SOURCE_NAMES[candidate]),
            }
        except Exception as exc:  # noqa: BLE001 主源失败切备用源，两源都失败才报错
            errors.append("{}：{}".format(SOURCE_NAMES[candidate], exc))
    raise RuntimeError("；".join(errors))


def print_text(code, payload):
    print("=" * 84)
    print("个股资金流向 · {}（{}）".format(payload.get("name") or code, code))
    print("=" * 84)
    latest = payload["latest_day"]
    if latest:
        print("最新交易日 {}：".format(latest["date"]))
        print("  主力净流入 {:>12} 万元".format(fmt_wan(latest["main"])))
        if latest.get("net") is not None:
            print("  主动净额   {:>12} 万元".format(fmt_wan(latest["net"])))
        if latest.get("super_large") is None and latest.get("large") is None:
            print("  超大单/大单/中单/小单拆分：未获取（{}）".format(
                payload.get("source_name") or "备用源"))
        else:
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
    print("注：数据来源为{}；单位万元，正=净流入，负=净流出。不构成投资建议。".format(
        payload.get("source_name") or "-"))


def main():
    ap = argparse.ArgumentParser(description="个股资金流向报告")
    ap.add_argument("code", help="如 sh600410 / sz002491")
    ap.add_argument("--source", choices=sorted(SOURCE_ORDER), default="auto",
                    help="数据源：auto 先东财、不可用切新浪（默认）；可强制 eastmoney / sina")
    ap.add_argument("--json", action="store_true", help="输出JSON")
    args = ap.parse_args()

    code = args.code.lower().strip()
    if to_secid(code) is None:
        sys.exit("错误：代码格式应为 sh/sz/bj + 6位数字，如 sh600410。")

    try:
        payload = build_payload(code, args.source)
    except Exception as exc:
        sys.exit("错误：资金流向取数失败（{}）。".format(exc))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print_text(code, payload)


if __name__ == "__main__":
    main()
