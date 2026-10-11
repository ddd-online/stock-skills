#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股 板块行情榜数据报告（东方财富为主、腾讯为备用源，均为公开接口，无需密钥）。

用法:
    python fetch_sector_boards.py [--type industry|concept|all] [--sort change|flow|amount|gain5|gain10]
                                  [--top N] [--min-up N] [--search 关键词]
                                  [--source auto|eastmoney|tencent] [--json]

输出: 板块行情榜——按所选排序返回 Top N 行业/概念板块，含板块指数、当日涨跌幅、
近5日/近10日累计涨跌幅、领涨股（名称/代码/涨幅）、上涨/下跌家数、成交额、换手率
与主力净流入；不产生缓存文件。

数据源: 东方财富板块行情（push2 clist）优先；该接口不可用时自动切换腾讯板块行情
（板块榜 pt/getRank + 板块指数日K），主力净流入等字段照常给出、不再退回“未获取”。
备用源下板块代码为腾讯板块代码（非东财 BK 代码）、主力净流入为腾讯主力口径、
10日涨幅按板块指数收盘价回算；报告里标注实际数据源与口径，跨源数值不混用同一张对比表。
"""

import argparse
import difflib
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import http_util  # noqa: E402 与脚本同目录的网络层（直连优先、系统代理兜底）

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

USER_AGENT = "Mozilla/5.0"

# ---------------- 东方财富板块行情（主源） ----------------

EASTMONEY_HOSTS = [
    "https://push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
    "https://push2test.eastmoney.com",  # 本地定制（2026-10-09）：主节点被限流时的可用镜像
]
EASTMONEY_REFERER = "https://data.eastmoney.com/"
EASTMONEY_PAGE_SIZE = 100
EASTMONEY_MAX_PAGES = 12
GAIN10_PRESORT_CAP = 100     # 腾讯源按 10 日涨幅排序时的候选上限（逐板块一次日K，防限流）  # 行业+概念合计约 600 个板块，12 页足够

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

# ---------------- 腾讯板块行情（备用源） ----------------

TENCENT_HOST = "https://proxy.finance.qq.com"
TENCENT_REFERER = "https://gu.qq.com/"

TENCENT_RANK_URL = (
    "{host}/cgi/cgi-bin/rank/pt/getRank"
    "?board_type={board_type}&sort_type=price&direct=down&offset={offset}&count={count}"
)
TENCENT_KLINE_URL = (
    "{host}/ifzqgtimg/appstock/app/newfqkline/get?param={code},day,,,{days},qfq"
)

# 腾讯板块类型：hy=行业板块、gn=概念板块
TENCENT_BOARD_TYPES = {
    "industry": ["hy"],
    "concept": ["gn"],
    "all": ["hy", "gn"],
}
TENCENT_PAGE_SIZE = 200  # 腾讯单页上限
TENCENT_MAX_PAGES = 8    # 概念板块约 800 个，8 页足够
TENCENT_KLINE_DAYS = 12  # 回算近10日涨幅需要 11 根以上日K

SOURCE_NAMES = {
    "eastmoney": "东方财富板块行情（push2 clist）",
    "tencent": "腾讯板块行情（板块榜 + 板块指数日K）",
}

SOURCE_ORDER = {
    "auto": ["eastmoney", "tencent"],
    "eastmoney": ["eastmoney"],
    "tencent": ["tencent"],
}


# 网络层统一走 http_util：直连优先（绕过 Windows 注册表代理），连续失败 3 次后回退系统代理。
_open = http_util.open_url


def http_get(url, referer=EASTMONEY_REFERER):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Referer": referer,
    })
    with _open(req, timeout=20) as resp:
        return resp.read()


def decode_json(raw):
    """接口编码不稳定（UTF-8/GB18030 混用）：先按 UTF-8 解析，乱码则回退 GB18030。"""
    text = raw.decode("utf-8", errors="replace")
    if "\ufffd" in text:
        text = raw.decode("gb18030", errors="replace")
    return json.loads(text)


def get_json(url, referer):
    """拉取并解析 JSON：UTF-8 解析失败时按 GB18030 重试（腾讯接口中文段为 GBK）。"""
    raw = http_get(url, referer=referer)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return decode_json(raw)


def to_float(value):
    try:
        if isinstance(value, str):
            value = value.replace(",", "")
        return float(value)
    except (TypeError, ValueError):
        return None


def wan_to_yi(value):
    num = to_float(value)
    return None if num is None else round(num / 10000.0, 2)


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
    # 领涨股市场：1=沪市、0=深市；北交所按代码前缀识别（92/4/8 开头）
    if market == "1":
        return "sh" + digits
    if digits[:2] == "92" or digits[:1] in ("4", "8"):
        return "bj" + digits
    return "sz" + digits


def yi_or_none(value):
    """元 → 亿元；取不到返回 None（缺失不等于 0）。"""
    num = to_float(value)
    return None if num is None else round(num / 1e8, 2)


def fetch_eastmoney_page(board_type, sort, page_no, page_size):
    last_error = None
    url_tpl = (
        "{host}/api/qt/clist/get?pn={pn}&pz={pz}&po=1&np=1&fltt=2&invt=2"
        "&fid={fid}&fs={fs}&fields={fields}"
    )
    for host in EASTMONEY_HOSTS:
        try:
            url = url_tpl.format(
                host=host, pn=page_no, pz=page_size,
                fid=SORTS[sort], fs=BOARD_FS[board_type], fields=FIELDS,
            )
            data = get_json(url, EASTMONEY_REFERER)
            node = data.get("data") or {}
            diff = node.get("diff") or []
            if data.get("rc") != 0:
                last_error = "第 {} 页接口无数据 rc={}".format(page_no, data.get("rc"))
                continue
            return diff   # 空列表＝已翻到末页，不算失败（板块数恰为整页倍数时不报错）
        except Exception as exc:  # noqa: BLE001 网络或解析失败时换下一个东财域名
            last_error = str(exc)
            continue
    raise RuntimeError("东方财富板块接口第 {} 页拉取失败：{}".format(page_no, last_error))


def normalize_eastmoney_rows(diff):
    rows = []
    for raw in diff:
        bk_code = str(raw.get("f12") or "")
        if not bk_code.startswith("BK"):
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
            "up_count": to_float(raw.get("f104")),
            "down_count": to_float(raw.get("f105")),
            "amount_yi": yi_or_none(raw.get("f6")),
            "turnover_pct": to_float(raw.get("f8")),
            "main_inflow_yi": yi_or_none(raw.get("f62")),
            "main_inflow5_yi": None,
            "main_inflow20_yi": None,
            "ts": to_float(raw.get("f124")),
            "quote_date": None,
        })
    return rows


def fetch_eastmoney_rows(args):
    diff = []
    for page_no in range(1, EASTMONEY_MAX_PAGES + 1):
        page = fetch_eastmoney_page(args.type, args.sort, page_no, EASTMONEY_PAGE_SIZE)
        if not page:
            break
        diff.extend(page)
        if len(page) < EASTMONEY_PAGE_SIZE:
            break
        if not args.search and len(diff) >= args.top + EASTMONEY_PAGE_SIZE:
            break
    return normalize_eastmoney_rows(diff)


def fetch_tencent_page(board_type, offset, page_size=TENCENT_PAGE_SIZE):
    url = TENCENT_RANK_URL.format(
        host=TENCENT_HOST, board_type=board_type, offset=offset, count=page_size)
    data = get_json(url, TENCENT_REFERER)
    rows = (data.get("data") or {}).get("rank_list") or []
    if data.get("code") != 0 or not rows:
        raise RuntimeError("腾讯板块榜无数据（board_type={} offset={} msg={}）".format(
            board_type, offset, data.get("msg")))
    return rows


def fetch_tencent_boards(board_type):
    boards = []
    for tencent_type in TENCENT_BOARD_TYPES[board_type]:
        for page_no in range(TENCENT_MAX_PAGES):
            page = fetch_tencent_page(tencent_type, page_no * TENCENT_PAGE_SIZE)
            boards.extend(page)
            if len(page) < TENCENT_PAGE_SIZE:
                break
    return boards


def split_updown(text):
    """腾讯字段 zgb 形如“36/122”，即板块内上涨家数/下跌家数。"""
    up_s, _, down_s = str(text or "").partition("/")
    return to_float(up_s), to_float(down_s)


def normalize_tencent_rows(raw_rows):
    rows = []
    for raw in raw_rows:
        code = str(raw.get("code") or "")
        if not code:
            continue
        up_count, down_count = split_updown(raw.get("zgb"))
        leader = raw.get("lzg") or {}
        rows.append({
            "code": code,
            "name": str(raw.get("name") or "-"),
            "index": to_float(raw.get("zxj")),
            "change_pct": to_float(raw.get("zdf")),
            "change5_pct": to_float(raw.get("zdf_d5")),
            "change10_pct": None,  # 腾讯没有 10 日字段，由板块指数日K回算
            "leader_name": str(leader.get("name") or "-"),
            "leader_code": str(leader.get("code") or "") or None,
            "leader_change_pct": to_float(leader.get("zdf")),
            "up_count": up_count,
            "down_count": down_count,
            "amount_yi": wan_to_yi(raw.get("turnover")),
            "turnover_pct": to_float(raw.get("hsl")),
            "main_inflow_yi": wan_to_yi(raw.get("zljlr")),
            "main_inflow5_yi": wan_to_yi(raw.get("zljlr_d5")),
            "main_inflow20_yi": wan_to_yi(raw.get("zljlr_d20")),
            "ts": None,
            "quote_date": None,
        })
    return rows


def fetch_tencent_kline(code, days=TENCENT_KLINE_DAYS):
    url = TENCENT_KLINE_URL.format(host=TENCENT_HOST, code=code, days=days)
    data = get_json(url, TENCENT_REFERER)
    node = (data.get("data") or {}).get(code) or {}
    return node.get("day") or []


def fill_tencent_multiday(rows, workers=8):
    """备用源没有 10 日涨幅字段：按板块指数日K收盘价回算，并回填最新交易日。"""
    pending = [r for r in rows if r.get("change10_pct") is None]
    if not pending:
        return

    def worker(row):
        try:
            klines = fetch_tencent_kline(row["code"])
        except Exception:  # noqa: BLE001 单个板块取数失败不影响其余板块
            return row["code"], None, None
        closes = [c for c in (to_float(k[2]) for k in klines if len(k) > 2) if c]
        date = str(klines[-1][0]) if klines else None
        pct = None
        if len(closes) >= 11 and closes[-11]:
            pct = round((closes[-1] / closes[-11] - 1) * 100, 2)
        return row["code"], pct, date

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(worker, pending))
    fetched = {code: (pct, date) for code, pct, date in results}
    for row in pending:
        pct, date = fetched.get(row["code"], (None, None))
        row["change10_pct"] = pct
        row["quote_date"] = date


def fetch_tencent_rows(args):
    return normalize_tencent_rows(fetch_tencent_boards(args.type))


def filter_rows(rows, min_up, search):
    if min_up > 0:
        rows = [r for r in rows
                if r["up_count"] is not None and r["up_count"] >= min_up]
    keyword = (search or "").strip().lower()
    if keyword:
        rows = [r for r in rows if keyword in r["name"].lower()]
    return rows


def sort_rows(rows, sort):
    key = SORT_VALUES[sort]
    rows.sort(key=lambda r: (r[key] is None, -(r[key] if r[key] is not None else 0)))
    return rows


def no_match_reason(rows, args):
    """按板块名过滤后为空时给出可用提示：列出最接近的板块名，不静默兜底。"""
    keyword = args.search.strip()
    if not keyword:
        return "过滤后无板块（检查 --type / --min-up）"
    matched = [r for r in rows if keyword.lower() in r["name"].lower()]
    if matched:
        return ("名称包含“{kw}”的板块有 {n} 个（{names}），但它们都被 --min-up {mu} 等过滤条件"
                "剔除了；请放宽 --min-up 后重试（本数据源共 {total} 个板块）").format(
                    kw=keyword, n=len(matched),
                    names="、".join(r["name"] for r in matched[:5]),
                    mu=args.min_up, total=len(rows))
    tips = difflib.get_close_matches(keyword, [r["name"] for r in rows], n=5, cutoff=0.3)
    if tips:
        return ("没有名称包含“{kw}”的板块（本数据源共 {n} 个板块）；"
                "最接近的板块名：{tips}（改用近似板块时必须在报告里写明替代关系与数据源）").format(
                    kw=keyword, n=len(rows), tips="、".join(tips))
    return ("没有名称包含“{kw}”的板块（本数据源共 {n} 个板块），也没有相近名称；"
            "可换关键词、加 --type all（概念板块需 --type concept/all）重试，"
            "或等东财板块接口恢复").format(
                kw=keyword, n=len(rows))


def prepare_rows(args):
    """返回 (数据源, 行, meta)：auto 先东财、失败或为空再切腾讯；行已过滤、排序并截断到 --top。"""
    errors = []
    for source in SOURCE_ORDER[args.source]:
        try:
            fetched = (fetch_eastmoney_rows(args) if source == "eastmoney"
                       else fetch_tencent_rows(args))
            rows = filter_rows(fetched, args.min_up, args.search)
            if not rows:
                raise RuntimeError(no_match_reason(fetched, args))
            meta = {"gain10_partial": False}
            if source == "tencent" and args.sort == "gain10":
                # 逐板块取指数日K，只在前 N 个候选里回算 10 日涨幅，避免数百次请求触发限流
                prelim = sort_rows([r for r in rows if r.get("change5_pct") is not None],
                                   "gain5")[:GAIN10_PRESORT_CAP]
                meta["gain10_partial"] = len(prelim) < len(rows)
                fill_tencent_multiday(prelim)
                rows = prelim
            rows = sort_rows(rows, args.sort)[:args.top]
            if source == "tencent":
                fill_tencent_multiday(rows)  # 展示行补齐 10 日涨幅与最新交易日
            if source == "eastmoney" and rows:
                pairs = [(r["change5_pct"], r["change10_pct"]) for r in rows]
                meta["same_5_10"] = all(a is not None and a == b for a, b in pairs)
            return source, rows, meta
        except Exception as exc:  # noqa: BLE001 主源失败切备用源，两源全失败才报错
            errors.append("{}：{}".format(SOURCE_NAMES[source], exc))
    raise RuntimeError("板块榜取数失败（{}）".format("；".join(errors)))


def quote_label(source, rows):
    if source == "eastmoney":
        ts = next((r.get("ts") for r in rows if r.get("ts")), None)
        return fmt_dt(ts) if ts else None   # 取不到行情时间写未获取，不用本机时间冒充
    dates = sorted({str(r.get("quote_date")) for r in rows if r.get("quote_date")})
    return dates[-1] if dates else None


def source_note(source):
    if source == "eastmoney":
        return ("数据源：东方财富板块行情公开接口（push2 clist）；今日/近5日/近10日涨跌幅"
                "为东方财富板块行情口径。")
    return ("数据源：腾讯板块行情（东财板块接口不可用时的备用源，板块榜 + 板块指数日K）；"
            "主力净流入与成交额为腾讯口径（万元换算亿）、近5日涨幅取自腾讯、"
            "近10日涨幅按板块指数收盘价回算；板块代码为腾讯板块代码（非东财 BK 代码），"
            "下钻成分股需要东财接口可用；与东财口径数值不可混用于同一张对比表。")


def render_text(rows, args, source, quote_time, meta=None):
    meta = meta or {}
    lines = []
    lines.append("# 板块行情榜（{board} · 排序：{sort} · Top {top} · 数据时间 {time}）".format(
        board=BOARD_TYPE_NAMES[args.type], sort=SORT_NAMES[args.sort],
        top=args.top, time=quote_time or "未获取"))
    lines.append("")
    lines.append(source_note(source))
    if meta.get("same_5_10"):
        lines.append("口径提示：东财接口本次返回的近10日涨幅与近5日涨幅逐行同值（字段 f160 与 f109 同值），"
                     "10 日维度不可用；需要 10 日口径请用 --source tencent。")
    if meta.get("gain10_partial"):
        lines.append("口径提示：腾讯源按 10 日涨幅排序时只在前 {} 个候选板块内用指数日K回算"
                     "（逐板块一次请求，避免限流），未覆盖全量板块。".format(GAIN10_PRESORT_CAP))
    if args.min_up > 0:
        lines.append("口径：上涨家数低于 {min_up} 的板块已剔除。数据未经验证，仅供板块扫描。".format(
            min_up=args.min_up))
    if args.search.strip():
        lines.append("关键词：仅显示名称包含“{kw}”的板块。".format(kw=args.search.strip()))
    if len(rows) < args.top:
        lines.append("注：过滤后实际返回 {n} 个板块（请求 {top} 个）。".format(
            n=len(rows), top=args.top))
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
    lines.append("数据来源：{}；行情时间为当日实时/延迟数据或最近交易日收盘数据，"
                 "使用时以交易所数据为准。不构成投资建议。".format(SOURCE_NAMES[source]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="A股 板块行情榜数据报告（东方财富为主、腾讯为备用源）")
    ap.add_argument("--type", choices=sorted(BOARD_FS), default="industry",
                    help="板块类型：industry 行业 / concept 概念 / all 全部（默认 industry）")
    ap.add_argument("--sort", choices=sorted(SORTS), default="change",
                    help="排序字段（默认 change 当日涨跌幅）")
    ap.add_argument("--top", type=int, default=20, help="榜单数量（默认 20）")
    ap.add_argument("--min-up", type=int, default=0,
                    help="最低上涨家数过滤，如 5 表示剔除上涨家数<5 的小板块（默认不过滤）")
    ap.add_argument("--search", type=str, default="",
                    help="按板块名称关键词定位（如 --search 液冷；会翻完整板块列表后过滤）")
    ap.add_argument("--source", choices=sorted(SOURCE_ORDER), default="auto",
                    help="数据源：auto 先东财、不可用切腾讯（默认）；可强制 eastmoney / tencent")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.top <= 0:
        sys.exit("错误：--top 必须为正整数。")

    try:
        source, rows, meta = prepare_rows(args)
    except Exception as exc:  # noqa: BLE001 统一报错，不静默
        sys.exit("错误：{}".format(exc))

    quote_time = quote_label(source, rows)

    if args.json:
        payload = {
            "board_type": args.type,
            "board_type_name": BOARD_TYPE_NAMES[args.type],
            "sort": args.sort,
            "sort_name": SORT_NAMES[args.sort],
            "top": args.top,
            "min_up": args.min_up,
            "search": args.search.strip(),
            "source": source,
            "source_name": SOURCE_NAMES[source],
            "quote_time": quote_time,
            "rows": rows,
            "limitations": [text for text in (
                "东财接口 f160 与 f109 同值，近10日涨幅不可用（10 日维度请用 --source tencent）"
                if meta.get("same_5_10") else None,
                "腾讯源 10 日涨幅只在前 {} 个候选板块内回算，未覆盖全量".format(GAIN10_PRESORT_CAP)
                if meta.get("gain10_partial") else None,
                "行情接口未返回数据时间时 quote_time 为 null" if quote_time is None else None,
            ) if text],
            "note": source_note(source),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not rows:
        sys.exit("错误：板块榜为空（请调整 --type / --sort / --top / --min-up / --search 后重试）。")
    print(render_text(rows, args, source, quote_time, meta))


if __name__ == "__main__":
    http_util.run(main)
