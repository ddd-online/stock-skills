#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market-data 备用数据源：东财行情中心（push2 clist）不可用时使用。

只用标准库，无需密钥。三个来源：

- 腾讯行情：批量个股快照（qt.gtimg.cn）与板块/个股日K（回算近5日/近10日涨幅）；
- 新浪行情：全市场/分板块排行榜（Market_Center.getHQNodeData）与个股资金流
  （MoneyFlow.ssl_qsfx_zjlrqs，主力净额为「大单+超大单」口径，与东财不一致）；
- 东方财富数据中心 F10：按 BK 代码取板块成分股（RPT_F10_CORETHEME_BOARDTYPE，
  代码口径）与个股所属行业（BOARD_RANK=1 为一级行业）。

约定：金额一律以「元」返回，比率以百分数返回，由调用方负责格式化与口径标注。
"""

import json
import urllib.parse
import urllib.request

USER_AGENT = "Mozilla/5.0"
TENCENT_REFERER = "https://gu.qq.com/"
SINA_REFERER = "https://finance.sina.com.cn/"
EASTMONEY_REFERER = "https://data.eastmoney.com/"

TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={codes}"
TENCENT_KLINE_URL = (
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
    "?param={code},day,,,{days},qfq"
)

SINA_HOST = "https://vip.stock.finance.sina.com.cn"
SINA_RANK_URL = (
    SINA_HOST + "/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    "?page={page}&num={num}&sort=changepercent&asc=0&node={node}"
)
SINA_FLOW_URL = (
    SINA_HOST + "/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs"
    "?page=1&num={num}&sort=opendate&asc=0&daima={code}"
)

F10_URL = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
    "?reportName=RPT_F10_CORETHEME_BOARDTYPE&columns={columns}"
    "&pageSize={size}&pageNumber={page}&filter={filter}"
)
F10_BOARD_COLUMNS = "SECURITY_CODE,SECURITY_NAME_ABBR,BOARD_CODE,BOARD_NAME,NEW_BOARD_CODE,IS_PRECISE,BOARD_RANK"
F10_INDUSTRY_COLUMNS = "SECURITY_CODE,SECURITY_NAME_ABBR,BOARD_NAME,NEW_BOARD_CODE,BOARD_RANK"

TENCENT_QUOTE_CHUNK = 50


def http_get(url, referer, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Referer": referer,
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def decode_text(raw):
    """接口编码不稳定（UTF-8/GBK 混用）：先按 UTF-8 解析，失败或乱码则回退 GB18030。"""
    text = raw.decode("utf-8", errors="replace")
    if "\ufffd" in text:
        text = raw.decode("gb18030", errors="replace")
    return text


def get_json(url, referer, timeout=20):
    return json.loads(decode_text(http_get(url, referer, timeout=timeout)))


def to_float(value):
    try:
        if isinstance(value, str):
            value = value.replace(",", "")
        return float(value)
    except (TypeError, ValueError):
        return None


def to_yuan_is_wan(value):
    num = to_float(value)
    return None if num is None else num * 10000.0


def infer_sec_code(digits):
    """6 位数字代码 → sh/sz/bj 前缀（与 market-data 其他脚本一致）。"""
    digits = str(digits)
    if len(digits) != 6 or not digits.isdigit():
        return None
    if digits[0] == "6":
        return "sh" + digits
    if digits[:2] == "92" or digits[0] in ("4", "8"):
        return "bj" + digits
    return "sz" + digits


def is_bj_code(digits):
    digits = str(digits)
    return digits[:2] == "92" or digits[:1] in ("4", "8")


# ---------------- 腾讯行情 ----------------


def parse_tencent_quote(code, body):
    """腾讯快照字段位次与 fetch_quote.py 一致，另用 [37]成交额(万)、[49]量比。"""
    f = body.split("~")
    if len(f) < 50:
        return None
    return {
        "code": code,
        "name": f[1],
        "price": to_float(f[3]),
        "prev_close": to_float(f[4]),
        "change_pct": to_float(f[32]),
        "high": to_float(f[33]),
        "low": to_float(f[34]),
        "amount_yuan": to_yuan_is_wan(f[37]),
        "turnover_pct": to_float(f[38]),
        "pe": to_float(f[39]),
        "amplitude_pct": to_float(f[43]),
        "float_cap_yi": to_float(f[44]),
        "total_cap_yi": to_float(f[45]),
        "volume_ratio": to_float(f[49]),
        "datetime": f[30],
    }


def fetch_tencent_quotes(codes, chunk=TENCENT_QUOTE_CHUNK):
    """批量个股快照：返回 {带前缀代码: 字段字典}，单次请求失败只跳过该批。"""
    quotes = {}
    codes = list(codes)
    for start in range(0, len(codes), chunk):
        batch = codes[start:start + chunk]
        try:
            raw = http_get(TENCENT_QUOTE_URL.format(codes=",".join(batch)),
                           TENCENT_REFERER).decode("gbk", errors="ignore")
        except Exception:  # noqa: BLE001 单批失败不影响其余批次
            continue
        for line in raw.splitlines():
            if not line.startswith("v_"):
                continue
            code = line.split("=")[0][2:].strip()
            try:
                body = line.split('"', 2)[1]
            except IndexError:
                continue
            quote = parse_tencent_quote(code, body)
            if quote:
                quotes[code] = quote
    return quotes


def fetch_tencent_kline(code, days=15):
    url = TENCENT_KLINE_URL.format(code=code, days=days)
    data = get_json(url, TENCENT_REFERER)
    node = (data.get("data") or {}).get(code) or {}
    # 个股前复权返回 qfqday，板块指数返回 day
    return node.get("qfqday") or node.get("day") or []


def kline_change_pct(klines, span):
    """按收盘价回算近 span 个交易日涨幅（%）。"""
    closes = [c for c in (to_float(k[2]) for k in klines if len(k) > 2) if c]
    if len(closes) < span + 1 or not closes[-span - 1]:
        return None
    return round((closes[-1] / closes[-span - 1] - 1) * 100, 2)


def fetch_tencent_multiday_pct(code, days=15):
    """返回 (近5日%, 近10日%, 最新交易日)；取不到的行返回 None。"""
    try:
        klines = fetch_tencent_kline(code, days=days)
    except Exception:  # noqa: BLE001 单只失败不影响其余
        return None, None, None
    if not klines:
        return None, None, None
    return (kline_change_pct(klines, 5), kline_change_pct(klines, 10),
            str(klines[-1][0]))


# ---------------- 新浪行情与资金流 ----------------


def fetch_sina_rank(node, page=1, num=100):
    """新浪排行榜（按涨跌幅降序）：node 取 hs_a / sh_a / sz_a / cyb / kcb / hs_bjs。"""
    url = SINA_RANK_URL.format(page=page, num=num, node=node)
    data = get_json(url, SINA_REFERER)
    return data if isinstance(data, list) else []


def fetch_sina_stock_flow_history(code, days=5):
    """个股资金流（新浪口径，最新在前）：主力净额＝大单+超大单，与东财口径不一致。"""
    url = SINA_FLOW_URL.format(num=max(int(days), 1), code=code)
    rows = get_json(url, SINA_REFERER)
    if not isinstance(rows, list):
        return []
    history = []
    for row in rows:
        history.append({
            "date": str(row.get("opendate") or "") or None,
            "main_yuan": to_float(row.get("r0_net")),
            "net_yuan": to_float(row.get("netamount")),
        })
    return history


def fetch_sina_stock_flow(code):
    """最新一日的 (交易日, 主力净额元, 主动净额元)。"""
    history = fetch_sina_stock_flow_history(code, days=1)
    if not history:
        return None, None, None
    latest = history[0]
    return latest["date"], latest["main_yuan"], latest["net_yuan"]


# ---------------- 东方财富数据中心 F10 ----------------


def fetch_f10_board_members(bk_code, page_size=500, max_pages=10):
    """按 BK 代码取板块成分股（东财 F10 所属板块口径，代码匹配，非名称匹配）。"""
    filter_expr = urllib.parse.quote(
        '(NEW_BOARD_CODE="{}")'.format(bk_code), safe="()")
    members = []
    for page_no in range(1, max_pages + 1):
        url = F10_URL.format(columns=F10_BOARD_COLUMNS, size=page_size,
                             page=page_no, filter=filter_expr)
        data = get_json(url, EASTMONEY_REFERER)
        result = data.get("result") or {}
        rows = result.get("data") or []
        members.extend(rows)
        if len(rows) < page_size:
            break
    return members


def fetch_f10_industry_map(codes, page_size=500, max_pages=6):
    """按代码集合取东财一级行业（BOARD_RANK=1）：返回 {6位代码: 行业名}。"""
    codes = [str(c) for c in codes if str(c).isdigit() and len(str(c)) == 6]
    if not codes:
        return {}
    quoted = ",".join('"{}"'.format(c) for c in codes)
    filter_expr = urllib.parse.quote(
        "(SECURITY_CODE in ({}))".format(quoted), safe="()")
    industry = {}
    for page_no in range(1, max_pages + 1):
        url = F10_URL.format(columns=F10_INDUSTRY_COLUMNS, size=page_size,
                             page=page_no, filter=filter_expr)
        data = get_json(url, EASTMONEY_REFERER)
        result = data.get("result") or {}
        rows = result.get("data") or []
        for row in rows:
            if str(row.get("BOARD_RANK")) != "1":
                continue
            code = str(row.get("SECURITY_CODE") or "")
            name = str(row.get("BOARD_NAME") or "")
            if code and name and code not in industry:
                industry[code] = name
        if len(rows) < page_size or len(industry) >= len(codes):
            break
    return industry
