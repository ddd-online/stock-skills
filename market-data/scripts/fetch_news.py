#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公司新闻与公告报告（东方财富新闻搜索 + 东方财富公告，公开接口，无需密钥）。

用法:
    python fetch_news.py <代码> [--news N] [--ann N] [--json]

代码: 与 fetch_quote.py 相同，如 sh600410 / sz002491 / bj920002。
输出: 新闻公告报告——最近N条新闻（东财，按股票名称关键词）与最近N条公告（东财），
供“逻辑证伪”检查；不产生缓存文件。
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

from fetch_quote import fetch_quote as fetch_quote_name

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 东方财富 secid：沪市=1，深市/北交所=0（与 fetch_quote.py 一致）
MARKET = {"sh": "1", "sz": "0", "bj": "0"}

NEWS_URL = (
    "https://search-api-web.eastmoney.com/search/jsonp?cb=cb&param={param}"
)
ANN_URL = (
    "https://np-anotice-stock.eastmoney.com/api/security/ann"
    "?sr=-1&page_size={num}&page_index=1&ann_type=A"
    "&stock_list={code}&f_node=0&s_node=0"
)
ANN_PAGE = "https://data.eastmoney.com/notices/detail/{code}/{art}.html"


def to_secid(code):
    prefix, digits = code[:2], code[2:]
    if prefix not in MARKET or len(digits) != 6 or not digits.isdigit():
        return None
    return MARKET[prefix] + "." + digits


def http_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn/",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def fetch_news(code, num):
    quote = fetch_quote_name(code)
    keyword = (quote or {}).get("name") or code[2:]
    payload = {
        "uid": "",
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": num,
                "preTag": "",
                "postTag": "",
            }
        },
    }
    url = NEWS_URL.format(param=urllib.parse.quote(json.dumps(payload, ensure_ascii=False)))
    raw = http_get(url)
    text = raw.decode("utf-8", errors="ignore")
    if text.startswith("cb(") and text.endswith(")"):
        text = text[3:-1]
    data = json.loads(text)
    items = (data.get("result") or {}).get("cmsArticleWebOld") or []
    result = []
    for it in items:
        title = it.get("title")
        if not title:
            continue
        result.append({
            "time": str(it.get("date") or "")[:16],
            "title": title,
            "source": it.get("mediaName") or "东方财富",
            "url": it.get("url", ""),
        })
    return keyword, result


def fetch_announcements(code, num):
    digits = code[2:]
    url = ANN_URL.format(code=digits, num=num)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://data.eastmoney.com/",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8", errors="replace"))
    items = (data.get("data") or {}).get("list") or []
    result = []
    for it in items:
        title = it.get("title")
        if not title:
            continue
        types = [c.get("column_name") for c in it.get("columns") or [] if c.get("column_name")]
        result.append({
            "date": str(it.get("display_time") or it.get("notice_date") or "")[:16],
            "type": "/".join(types) if types else "-",
            "title": title,
            "url": ANN_PAGE.format(code=digits, art=it.get("art_code") or ""),
        })
    return result


def build_payload(code, news_num, ann_num):
    name, news = fetch_news(code, news_num)
    anns = fetch_announcements(code, ann_num)
    return {
        "code": code,
        "name": name,
        "news": news,
        "announcements": anns,
        "note": "数据来源：东方财富新闻搜索 + 公告公开接口",
    }


def print_text(code, payload):
    news = payload["news"]
    anns = payload["announcements"]
    print("=" * 72)
    print("公司新闻与公告 · {}（{}）".format(payload.get("name") or code, code))
    print("=" * 72)
    print("新闻（东方财富，最近{}条）：".format(len(news)))
    if not news:
        print("  （无）")
    for it in news:
        print("  {}  {}".format(it["time"], it["title"]))
    print("-" * 72)
    print("公告（东方财富，最近{}条）：".format(len(anns)))
    if not anns:
        print("  （无）")
    for it in anns:
        print("  {}  [{}] {}".format(it["date"], it["type"], it["title"]))
        if it["url"]:
            print("      {}".format(it["url"]))
    print("=" * 72)
    print("注：数据来源为东方财富新闻搜索与公告公开接口；用于“逻辑证伪”检查。")


def main():
    ap = argparse.ArgumentParser(description="公司新闻与公告报告")
    ap.add_argument("code", help="如 sh600410 / sz002491")
    ap.add_argument("--news", type=int, default=5, help="新闻条数，默认5")
    ap.add_argument("--ann", type=int, default=5, help="公告条数，默认5")
    ap.add_argument("--json", action="store_true", help="输出JSON")
    args = ap.parse_args()

    code = args.code.lower().strip()
    if to_secid(code) is None:
        sys.exit("错误：代码格式应为 sh/sz/bj + 6位数字，如 sh600410。")

    try:
        payload = build_payload(code, args.news, args.ann)
    except Exception as exc:
        sys.exit("错误：网络请求失败（{}）。请稍后重试。".format(exc))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print_text(code, payload)


if __name__ == "__main__":
    main()
