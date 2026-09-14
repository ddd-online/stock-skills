#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股 集合竞价数据报告（腾讯行情 + 东方财富日K公开接口，无需密钥）。

用途: 分析一批股票的当日集合竞价——高开幅度、竞价成交额占昨日全天成交额的比例，
      以及这批股票的集体分布（供昨日涨停股集体竞价表、板块竞价表使用）。

用法:
    python fetch_auction.py --codes "sh600103,sz002970"
    python fetch_auction.py --file auction.txt [--json]
    python fetch_auction.py --file auction.txt --top-board sh600103

输入文件格式（每行，可省略后两项；以 # 开头的行忽略）:
    <代码> [昨日全天成交额(亿元)] [行业/板块]
    例：sh600103 12.34 造纸印刷

输出: 文本报告（集体分布 + 个股竞价明细 + 板块集体竞价 + 规则检查）；
      --json 输出同样内容的完整字段，供上层 skill 解析。

口径:
    高开幅度 = (今开 - 昨收) / 昨收 × 100%
    竞价量占比 = 竞价成交额 ÷ 昨日全天成交额 × 100%
    竞价成交额 = 9:25 撮合后的当日成交额；9:30 后运行会混入连续竞价成交额，
    脚本按行情时间自动标注口径，超过 9:30 时提示"非竞价口径"。
    昨日全天成交额优先取输入文件的值，缺失时用东方财富日K补齐。
    不产生缓存文件。
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

QT_HOSTS = [
    "https://qt.gtimg.cn/q={codes}",
    "http://qt.gtimg.cn/q={codes}",
    "http://sqt.gtimg.cn/q={codes}",
]
KLINE_URL = (
    "{host}/api/qt/stock/kline/get?secid={secid}"
    "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57"
    "&klt=101&fqt=0&end=20500101&lmt=5"
)

KLINE_HOSTS = [
    "https://push2his.eastmoney.com",
    "http://push2his.eastmoney.com",
]

TENCENT_KLINE_URL = (
    "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,5,qfq"
)

EPS = 0.0015
BUCKETS = [
    (0.0, 1.0, "<1%"),
    (1.0, 3.0, "1%-3%"),
    (3.0, 8.0, "3%-8%"),
    (8.0, 15.0, "8%-15%"),
    (15.0, None, ">15%"),
]


def http_get(url, referer):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": referer,
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


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


def fmt_signed(value, digits=2):
    if value is None:
        return "-"
    return "{:+.{d}f}".format(value, d=digits)


def normalize_code(text):
    """sh600410 / 600410 / SH600410 -> sh600410。"""
    code = str(text or "").strip().lower().replace(".", "")
    if code.startswith(("sh", "sz", "bj")):
        digits = code[2:]
        market = code[:2]
    elif code.isdigit() and len(code) == 6:
        digits = code
        if digits[0] == "6":
            market = "sh"
        elif digits[0] in ("4", "8") or digits[:2] == "92":
            market = "bj"
        else:
            market = "sz"
    else:
        return None
    if len(digits) != 6 or not digits.isdigit():
        return None
    return market + digits


def secid_of(code):
    market, digits = code[:2], code[2:]
    return "1." + digits if market == "sh" else "0." + digits


def parse_input_file(path):
    """返回 [(code, prev_amount_yi or None, industry or '-')]。"""
    rows = []
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        sys.exit("错误：读取输入文件失败（{}）。".format(exc))
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens = line.replace("|", " ").replace("\t", " ").split()
        code = normalize_code(tokens[0])
        if code is None:
            continue
        prev_amount = None
        industry = "-"
        for token in tokens[1:]:
            value = to_float(token)
            if value is not None and prev_amount is None:
                prev_amount = value
            elif industry == "-":
                industry = token
        rows.append((code, prev_amount, industry))
    if not rows:
        sys.exit("错误：输入文件中没有可识别的股票代码。")
    return rows


def parse_codes(text):
    rows = []
    for part in str(text or "").replace("，", ",").split(","):
        code = normalize_code(part)
        if code:
            rows.append((code, None, "-"))
    if not rows:
        sys.exit("错误：--codes 中没有可识别的股票代码（如 sh600103,sz002970）。")
    return rows


def fetch_quotes(codes):
    """腾讯批量行情（多源重试）；返回 ({代码: dict}, 未取到的代码列表)。"""
    result = {}
    failed = []
    for i in range(0, len(codes), 40):
        chunk = codes[i:i + 40]
        raw = None
        for tpl in QT_HOSTS:
            for _ in range(2):
                try:
                    raw = http_get(tpl.format(codes=",".join(chunk)),
                                   "http://finance.qq.com").decode("gbk", errors="ignore")
                    break
                except Exception:  # noqa: BLE001 接口抖动时换源重试
                    raw = None
            if raw:
                break
        if not raw:
            failed.extend(chunk)
            continue
        for line in raw.splitlines():
            if not line.startswith("v_"):
                continue
            body = line.split('"', 2)[1]
            f = body.split("~")
            if len(f) < 49:
                continue
            code = (f[2] or "").strip()
            full = None
            for prefix in ("sh", "sz", "bj"):
                if prefix + code in chunk:
                    full = prefix + code
                    break
            if full is None:
                continue
            result[full] = {
                "name": f[1],
                "price": to_float(f[3]),
                "prev_close": to_float(f[4]),
                "open": to_float(f[5]),
                "high": to_float(f[33]),
                "low": to_float(f[34]),
                "pct": to_float(f[32]),
                "amount_wan": to_float(f[37]),
                "limit_up": to_float(f[47]),
                "limit_down": to_float(f[48]),
                "quote_time": f[30],
            }
    return result, failed


def _pick_bar(bars, before_date, date_index):
    picked = None
    for bar in bars:
        parts = bar.split(",")
        if len(parts) <= date_index:
            continue
        day = parts[date_index].replace("-", "")
        if before_date and day < before_date:
            picked = parts
    if picked is None and bars:
        picked = bars[-1].split(",")
    return picked


def fetch_prev_amount_eastmoney(code, before_date):
    """东方财富日K取“昨日全天成交额”（亿元）；失败返回 None。"""
    for host in KLINE_HOSTS:
        for _ in range(2):
            try:
                url = KLINE_URL.format(host=host, secid=secid_of(code))
                data = json.loads(http_get(url, "https://quote.eastmoney.com/").decode(
                    "utf-8", errors="ignore"))
            except Exception:  # noqa: BLE001 接口抖动时换源/重试
                continue
            node = (data.get("data") or {})
            picked = _pick_bar(node.get("klines") or [], before_date, 0)
            if picked is None or len(picked) < 7:
                continue
            amount = to_float(picked[6])
            if amount is None:
                continue
            return round(amount / 1e8, 2), picked[0]
    return None


def fetch_prev_amount_tencent(code, before_date):
    """腾讯日K兜底：成交额 ≈ 成交量(手) × 100 × 收盘价，返回 (亿元, 日期)。"""
    url = TENCENT_KLINE_URL.format(code=code)
    try:
        raw = http_get(url, "http://finance.qq.com").decode("utf-8", errors="ignore")
        node = (json.loads(raw).get("data") or {}).get(code) or {}
        bars = node.get("qfqday") or node.get("day") or []
    except Exception:  # noqa: BLE001 兜底失败即返回 None
        return None
    picked = _pick_bar([",".join(str(x) for x in b[:6]) for b in bars], before_date, 0)
    if picked is None or len(picked) < 6:
        return None
    volume_hands = to_float(picked[5])
    close = to_float(picked[2])
    if volume_hands is None or close is None:
        return None
    return round(volume_hands * 100 * close / 1e8, 2), picked[0]


def fetch_prev_amount(code, before_date):
    """取昨日全天成交额；返回 (亿元, 是否腾讯估算, 数据日期)。"""
    result = fetch_prev_amount_eastmoney(code, before_date)
    if result is not None:
        return result[0], False, result[1]
    result = fetch_prev_amount_tencent(code, before_date)
    if result is not None:
        return result[0], True, result[1]
    return None, False, None


def session_scope(quote_time):
    """按行情时间判断口径：竞价 / 盘中 / 收盘后。"""
    raw = str(quote_time or "")
    if len(raw) < 14:
        return "unknown", "行情时间缺失，无法判断口径", None
    date_str = raw[:8]
    clock = raw[8:12]
    today = datetime.now().strftime("%Y%m%d")
    if date_str != today:
        return "after_close", "行情日期 {} 非今日，为收盘后/历史口径".format(date_str), date_str
    if clock <= "0930":
        return "auction", "竞价口径（9:25 撮合后、9:30 连续竞价前，成交额即竞价成交额）", date_str
    if clock <= "1500":
        return "intraday", "盘中口径（已含连续竞价成交额，竞价量占比不可用，仅供收盘后复盘参考）", date_str
    return "after_close", "收盘后口径（成交额为全天成交额，仅作事后复盘）", date_str


def bucket_of(ratio):
    if ratio is None:
        return "-"
    for low, high, label in BUCKETS:
        if high is None:
            if ratio > low:
                return label
        elif low < ratio <= high:
            return label
    return "<1%"


def build_rows(entries, quotes, data_date):
    rows = []
    missing_prev = []
    for code, prev_amount, industry in entries:
        quote = quotes.get(code)
        if quote is None:
            rows.append({
                "code": code, "name": "-", "industry": industry,
                "prev_amount_yi": prev_amount, "missing_quote": True,
            })
            continue
        if prev_amount is None:
            missing_prev.append(code)
        rows.append({
            "code": code,
            "name": quote["name"],
            "industry": industry,
            "prev_amount_yi": prev_amount,
            "quote_time": quote["quote_time"],
            "amount_wan": quote["amount_wan"],
            "open": quote["open"],
            "prev_close": quote["prev_close"],
            "price": quote["price"],
            "pct": quote["pct"],
            "high": quote["high"],
            "low": quote["low"],
            "limit_up": quote["limit_up"],
            "limit_down": quote["limit_down"],
        })
    for row in rows:
        if row.get("missing_quote"):
            continue
        open_px = row["open"]
        prev_close = row["prev_close"]
        row["gap_pct"] = (round((open_px - prev_close) * 100.0 / prev_close, 2)
                          if open_px and prev_close else None)
        row["auction_amount_yi"] = (round(row.get("amount_wan", 0) / 1e4, 3)
                                    if row.get("amount_wan") is not None else None)
        row.pop("amount_wan", None)
    if missing_prev:
        for row in rows:
            if row.get("missing_quote") or row["prev_amount_yi"] is not None:
                continue
            amount, estimated, amount_date = fetch_prev_amount(row["code"], data_date)
            row["prev_amount_yi"] = amount
            row["prev_amount_estimated"] = estimated
            row["prev_amount_date"] = amount_date
    for row in rows:
        if row.get("missing_quote"):
            continue
        prev_amount = row.get("prev_amount_yi")
        auction_amount = row.get("auction_amount_yi")
        row["amount_ratio_pct"] = (
            round(auction_amount * 100.0 / prev_amount, 2)
            if auction_amount is not None and prev_amount else None)
        row["ratio_bucket"] = bucket_of(row["amount_ratio_pct"])
        limit_up = row.get("limit_up")
        limit_down = row.get("limit_down")
        row["open_at_ceiling"] = bool(
            limit_up and row.get("open") and row["open"] >= limit_up - EPS)
        row["limit_down_now"] = bool(
            limit_down and row.get("price") and row["price"] <= limit_down + EPS)
        row["sky_ground"] = bool(
            limit_up and limit_down and row.get("high") and row.get("low")
            and row["high"] >= limit_up - EPS and row["low"] <= limit_down + EPS)
        marks = []
        if row["open_at_ceiling"]:
            marks.append("竞价涨停开")
        if row["sky_ground"]:
            marks.append("天地板")
        elif row["limit_down_now"]:
            marks.append("跌停")
        if row.get("gap_pct") is not None and row["gap_pct"] <= -9.0 and not row["limit_down_now"]:
            marks.append("接近跌停开")
        row["marks"] = "、".join(marks) if marks else "-"
    return rows


def summarize(rows, quotes):
    valid = [r for r in rows if r.get("gap_pct") is not None]
    gaps = [r["gap_pct"] for r in valid]
    ratios = [r["amount_ratio_pct"] for r in valid if r.get("amount_ratio_pct") is not None]
    buckets = {}
    for _, _, label in BUCKETS:
        buckets[label] = 0
    for ratio in ratios:
        buckets[bucket_of(ratio)] = buckets.get(bucket_of(ratio), 0) + 1
    summary = {
        "sample": len(rows),
        "quoted": len(valid),
        "missing_quote": len(rows) - len(valid),
        "up_open": sum(1 for g in gaps if g > 0),
        "flat_open": sum(1 for g in gaps if g == 0),
        "down_open": sum(1 for g in gaps if g < 0),
        "avg_gap_pct": round(sum(gaps) / len(gaps), 2) if gaps else None,
        "median_gap_pct": round(sorted(gaps)[len(gaps) // 2], 2) if gaps else None,
        "flat_or_up": sum(1 for g in gaps if g >= 0),
        "avg_amount_ratio_pct": round(sum(ratios) / len(ratios), 2) if ratios else None,
        "ratio_available": len(ratios),
        "ratio_missing": len(valid) - len(ratios),
        "ratio_buckets": buckets,
    }
    summary["open_distribution_text"] = "{} 只中，高开 {} / 平开 {} / 低开 {}".format(
        summary["quoted"], summary["up_open"], summary["flat_open"], summary["down_open"])
    return summary


def summarize_boards(rows):
    groups = {}
    for row in rows:
        if row.get("gap_pct") is None:
            continue
        board = row.get("industry") or "-"
        if board == "-":
            board = "未标注板块"
        item = groups.setdefault(board, {"board": board, "count": 0, "gaps": [], "ratios": []})
        item["count"] += 1
        item["gaps"].append(row["gap_pct"])
        if row.get("amount_ratio_pct") is not None:
            item["ratios"].append(row["amount_ratio_pct"])
    out = []
    for item in groups.values():
        gaps = item.pop("gaps")
        ratios = item.pop("ratios")
        item["up_open"] = sum(1 for g in gaps if g > 0)
        item["down_open"] = sum(1 for g in gaps if g < 0)
        item["avg_gap_pct"] = round(sum(gaps) / len(gaps), 2) if gaps else None
        item["avg_amount_ratio_pct"] = round(sum(ratios) / len(ratios), 2) if ratios else None
        out.append(item)
    out.sort(key=lambda x: (-x["count"], -(x["avg_gap_pct"] or -999)))
    return out


def eval_top_board(top_code, rows):
    if not top_code:
        return None
    row = next((r for r in rows if r["code"] == top_code), None)
    if row is None:
        return {"code": top_code, "found": False}
    info = {
        "code": row["code"],
        "name": row.get("name"),
        "found": True,
        "gap_pct": row.get("gap_pct"),
        "pct": row.get("pct"),
        "price": row.get("price"),
        "limit_down": row.get("limit_down"),
        "sky_ground": bool(row.get("sky_ground")),
        "limit_down_now": bool(row.get("limit_down_now")),
        "open_at_ceiling": bool(row.get("open_at_ceiling")),
    }
    info["no_trade"] = info["sky_ground"] or info["limit_down_now"]
    if info["no_trade"]:
        info["note"] = "命中硬规则：昨日最高板今日天地板或跌停 → 当天不做任何打板动作，只观察"
    elif info["open_at_ceiling"]:
        info["note"] = "昨日最高板竞价涨停开，未命中硬规则，但高位一字打开风险最高"
    elif (info["gap_pct"] or 0) <= -5:
        info["note"] = "昨日最高板大幅低开，硬规则待确认（开盘后若触及跌停/天地板即停止打板）"
    else:
        info["note"] = "昨日最高板竞价未命中硬规则"
    return info


def render_text(payload):
    lines = []
    quote_time = payload["quote_time"]
    lines.append("# 竞价数据报告（行情时间 {} · {}）".format(quote_time, payload["session_label"]))
    lines.append("")
    lines.append("样本 {} 只；口径说明：{}。".format(payload["summary"]["sample"], payload["session_note"]))
    lines.append("")
    summary = payload["summary"]
    lines.append("## 一、集体分布（昨日涨停股整体）")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---|")
    lines.append("| 高开 / 平开 / 低开 | {} / {} / {} |".format(
        summary["up_open"], summary["flat_open"], summary["down_open"]))
    lines.append("| 平均高开幅度 | {}% |".format(fmt_signed(summary["avg_gap_pct"])))
    lines.append("| 高开幅度中位数 | {}% |".format(fmt_signed(summary["median_gap_pct"])))
    lines.append("| 竞价量占比平均 | {}%（可用 {} 只，缺 {} 只） |".format(
        fmt_num(summary["avg_amount_ratio_pct"]), summary["ratio_available"],
        summary["ratio_missing"]))
    lines.append("| 竞价量占比分档 | {} |".format("；".join(
        "{} {} 只".format(label, count)
        for label, count in summary["ratio_buckets"].items())))
    lines.append("")
    lines.append("## 二、个股竞价明细")
    lines.append("")
    lines.append("| 代码 | 名称 | 高开% | 竞价额(亿) | 昨日额(亿) | 竞价量占比% | 分档 | 现价 | 涨跌% | 备注 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for row in payload["rows"]:
        if row.get("missing_quote"):
            lines.append("| {} | - | - | - | {} | - | - | - | - | 未取到行情 |".format(
                row["code"], fmt_num(row.get("prev_amount_yi"))))
            continue
        lines.append("| {code} | {name} | {gap} | {amt} | {prev} | {ratio} | {bucket} | {price} | {pct} | {marks} |".format(
            code=row["code"], name=row["name"], gap=fmt_signed(row.get("gap_pct")),
            amt=fmt_num(row.get("auction_amount_yi"), 3),
            prev="{}{}".format(
                fmt_num(row.get("prev_amount_yi")),
                "≈" if row.get("prev_amount_estimated") else ""),
            ratio=fmt_num(row.get("amount_ratio_pct")), bucket=row.get("ratio_bucket", "-"),
            price=fmt_num(row.get("price")), pct=fmt_signed(row.get("pct")),
            marks=row.get("marks", "-")))
    lines.append("")
    if payload["boards"]:
        lines.append("## 三、板块集体竞价")
        lines.append("")
        lines.append("| 板块 | 涨停家数 | 高开/低开 | 平均高开% | 平均竞价量占比% |")
        lines.append("|---|---|---|---|---|")
        for board in payload["boards"][:15]:
            lines.append("| {} | {} | {} / {} | {} | {} |".format(
                board["board"], board["count"], board["up_open"], board["down_open"],
                fmt_signed(board["avg_gap_pct"]), fmt_num(board["avg_amount_ratio_pct"])))
        lines.append("")
    lines.append("## 四、规则检查")
    lines.append("")
    lines.append("- 竞价量占比 = 竞价成交额 ÷ 昨日全天成交额，可用 {} 只；经验区间 3%-8% 活跃、>15% 警惕、<1% 无人关心。".format(
        summary["ratio_available"]))
    top = payload.get("top_board")
    if top:
        if not top.get("found"):
            lines.append("- 昨日最高板 {}：不在本次样本中，未做判定。".format(top["code"]))
        else:
            lines.append("- 昨日最高板 {}（{}）：竞价开 {}%，现价 {}%，{}。".format(
                top["name"], top["code"], fmt_signed(top.get("gap_pct")),
                fmt_signed(top.get("pct")), top.get("note")))
    lines.append("- 硬规则：若昨日最高板今日天地板或跌停 → 当天不做任何打板动作，只观察。当前判定：{}".format(
        "触发" if payload.get("no_trade_flag") else "未触发"))
    lines.append("")
    lines.append("数据来源：腾讯行情（批量报价）+ 东方财富日K公开接口"
                 "（东方财富不可用时用腾讯日K估算昨日成交额，标 ≈）；不构成投资建议。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="A股 集合竞价数据报告（高开幅度 + 竞价量占比 + 集体分布）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("输入文件每行：<代码> [昨日全天成交额(亿)] [行业/板块]\n"
                "示例：sh600103 12.34 造纸印刷"))
    ap.add_argument("--codes", type=str, default="",
                    help="逗号分隔代码，如 sh600103,sz002970（昨日成交额自动补齐）")
    ap.add_argument("--file", type=str, default="",
                    help="代码清单文件：每行 <代码> [昨日成交额(亿)] [行业/板块]")
    ap.add_argument("--top-board", type=str, default="",
                    help="昨日最高板代码（硬规则检查对象）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if not args.codes and not args.file:
        ap.error("需要 --codes 或 --file 之一")

    entries = parse_input_file(args.file) if args.file else parse_codes(args.codes)
    top_code = normalize_code(args.top_board)
    if args.top_board and not top_code:
        sys.exit("错误：--top-board 代码无法识别（如 sh600410 / sz002970）。")
    codes = []
    for code, _, _ in entries:
        if code not in codes:
            codes.append(code)
    # 硬规则检查对象必须能被判定：最高板不在清单里时补进来，避免“未判定”放过风险
    if top_code and top_code not in codes:
        entries.append((top_code, None, "最高板"))
        codes.append(top_code)

    quotes, failed_codes = fetch_quotes(codes)
    if not quotes:
        sys.exit("错误：行情接口拉取失败（批量报价全部失败，已尝试备用源）。请稍后重试。")
    if failed_codes:
        print("提示：以下代码本次未取到行情（报错不脑补）：{}".format(
            ",".join(failed_codes)), file=sys.stderr)

    quote_time = next((q["quote_time"] for q in quotes.values() if q["quote_time"]), "")
    scope, note, data_date = session_scope(quote_time)
    rows = build_rows(entries, quotes, data_date)
    payload = {
        "quote_time": "{}-{}-{} {}:{}:{}".format(
            quote_time[0:4], quote_time[4:6], quote_time[6:8],
            quote_time[8:10], quote_time[10:12], quote_time[12:14]) if len(quote_time) >= 14 else quote_time,
        "data_date": data_date,
        "session": scope,
        "session_note": note,
        "session_label": {"auction": "竞价口径", "intraday": "盘中口径",
                          "after_close": "收盘后口径"}.get(scope, "口径未知"),
        "rows": rows,
        "summary": summarize(rows, quotes),
        "boards": summarize_boards(rows),
        "top_board": eval_top_board(normalize_code(args.top_board), rows),
        "note": "竞价量占比 = 竞价成交额 ÷ 昨日全天成交额；数据来源：腾讯行情 + 东方财富日K",
    }
    payload["no_trade_flag"] = bool(payload["top_board"] and payload["top_board"].get("no_trade"))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(render_text(payload))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("已中断。")