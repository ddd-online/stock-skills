#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股/ETF 真实行情数据报告（腾讯公开接口，无需密钥）。

用法:
    python fetch_quote.py <代码> [--days N] [--json]

代码: 沪市 sh + 6位数字，深市 sz + 6位数字，如:
    sh600410  华胜天成
    sz002491  通鼎互联
    sh510300  沪深300ETF

输出: 行情报告——实时报价 + 最近N根日K + MA5/10/20/60；不产生缓存文件。
"""

import argparse
import json
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

QT_URL = "http://qt.gtimg.cn/q={code}"
KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq"


def http_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "http://finance.qq.com",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
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


def fmt_int(value):
    if value is None:
        return "-"
    return format(int(value), ",")


def fetch_quote(code):
    raw = http_get(QT_URL.format(code=code)).decode("gbk", errors="ignore")
    for line in raw.splitlines():
        if line.startswith("v_"):
            body = line.split('"', 2)[1]
            f = body.split("~")
            if len(f) < 49:
                return None
            return {
                "code": code,
                "name": f[1],
                "price": to_float(f[3]),
                "prev_close": to_float(f[4]),
                "open": to_float(f[5]),
                "high": to_float(f[33]),
                "low": to_float(f[34]),
                "change": to_float(f[31]),
                "change_pct": to_float(f[32]),
                "volume_hands": to_float(f[6]),
                "turnover_pct": to_float(f[38]),
                "pe": to_float(f[39]),
                "amplitude_pct": to_float(f[43]),
                "float_cap_yi": to_float(f[44]),
                "total_cap_yi": to_float(f[45]),
                "pb": to_float(f[46]),
                "limit_up": to_float(f[47]),
                "limit_down": to_float(f[48]),
                "datetime": f[30],
            }
    return None


def fetch_kline(code, days):
    raw = http_get(KLINE_URL.format(code=code, days=days))
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    node = data.get("data", {}).get(code, {})
    bars = node.get("qfqday") or node.get("day") or []
    result = []
    for b in bars:
        result.append({
            "date": b[0],
            "open": to_float(b[1]),
            "close": to_float(b[2]),
            "high": to_float(b[3]),
            "low": to_float(b[4]),
            "volume": to_float(b[5]),
        })
    return result


def compute_ma(closes, n):
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 3)


def format_dt(dt):
    if not dt or len(dt) < 14:
        return dt or "-"
    return "{}-{}-{} {}:{}:{}".format(dt[0:4], dt[4:6], dt[6:8], dt[8:10], dt[10:12], dt[12:14])


def build_payload(code, days):
    quote = fetch_quote(code)
    if quote is None:
        sys.exit("错误：无法获取行情，请检查代码格式（sh/sz + 6位数字）。")
    kline = fetch_kline(code, days)
    closes = [b["close"] for b in kline if b["close"] is not None]
    mas = {n: compute_ma(closes, n) for n in (5, 10, 20, 60)}
    return {
        "quote": quote,
        "kline": kline[-30:],
        "ma": mas,
        "note": "数据来源：腾讯行情公开接口",
    }


def print_text(code, payload):
    q = payload["quote"]
    mas = payload["ma"]
    kline = payload["kline"]
    print("=" * 66)
    print("{} ({}) · 数据时间 {}".format(q["name"], code, format_dt(q["datetime"])))
    print("=" * 66)
    print("现价 {}    涨跌 {} ({})%    昨收 {}".format(
        fmt_num(q["price"]), fmt_num(q["change"]), fmt_num(q["change_pct"]), fmt_num(q["prev_close"])))
    print("今开 {}    最高 {}    最低 {}".format(fmt_num(q["open"]), fmt_num(q["high"]), fmt_num(q["low"])))
    print("成交量 {}手    换手率 {}%    振幅 {}%".format(
        fmt_int(q["volume_hands"]), fmt_num(q["turnover_pct"]), fmt_num(q["amplitude_pct"])))
    print("PE {}    PB {}    流通市值 {}亿    总市值 {}亿".format(
        fmt_num(q["pe"]), fmt_num(q["pb"]), fmt_num(q["float_cap_yi"]), fmt_num(q["total_cap_yi"])))
    print("涨停 {}    跌停 {}".format(fmt_num(q["limit_up"]), fmt_num(q["limit_down"])))
    print("MA5 {}    MA10 {}    MA20 {}    MA60 {}".format(
        fmt_num(mas.get(5), 3), fmt_num(mas.get(10), 3),
        fmt_num(mas.get(20), 3), fmt_num(mas.get(60), 3)))
    print("-" * 66)
    print("最近{}根日K（日期 开 收 高 低 量）".format(min(len(kline), 15)))
    for b in kline[-15:]:
        print("{} {} {} {} {} {}".format(
            b["date"], fmt_num(b["open"]), fmt_num(b["close"]),
            fmt_num(b["high"]), fmt_num(b["low"]), fmt_int(b["volume"])))
    print("=" * 66)
    print("注：数据来源为腾讯行情公开接口；ETF 的 PE/PB 通常不适用。")


def main():
    ap = argparse.ArgumentParser(description="A股/ETF 真实行情报告")
    ap.add_argument("code", help="如 sh600410 / sz002491 / sh510300")
    ap.add_argument("--days", type=int, default=60, help="日K根数，默认60")
    ap.add_argument("--json", action="store_true", help="输出JSON")
    args = ap.parse_args()

    code = args.code.lower().strip()
    try:
        payload = build_payload(code, args.days)
    except Exception as exc:
        sys.exit("错误：网络请求失败（{}）。请稍后重试。".format(exc))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print_text(code, payload)


if __name__ == "__main__":
    main()
