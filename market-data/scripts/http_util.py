#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market-data 取数脚本共用的网络层：直连优先、系统代理兜底。

背景：Windows 注册表代理（如 127.0.0.1:7890）会被 Python urllib 自动采用，实测该代理
转发东财 push2 接口时连接被立即关闭（RemoteDisconnected）。因此所有取数脚本统一先走
无代理直连（ProxyHandler({})），直连连续失败 3 次后回退系统代理；回退后每 20 次请求
重试一次直连，避免代理恢复可用或直连恢复后本进程一直卡在代理上。

约定：各脚本保留自己的 http_get（请求头、超时、解码方式各不相同），只共用本模块的
open_url 作为「谁去发这个请求」的唯一实现。
"""

import json
import sys
import urllib.request

DIRECT_FAIL_LIMIT = 3        # 直连连续失败达到该次数后回退系统代理
DIRECT_RETRY_INTERVAL = 20   # 回退后每 N 次请求重试一次直连

_DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_STATE = {"direct_fails": 0, "since_retry": 0}
_JSON_EMITTED = {"value": False}


def mark_json_emitted():
    """脚本已经把 JSON 报告打到 stdout（随后仍要以非 0 退出码报错）时调用，避免再输出错误对象。"""
    _JSON_EMITTED["value"] = True


def fail(message):
    """失败统一出口：提示写 stderr，退出码 1；--json 时另把结构化错误打到 stdout（若还没打过 JSON）。"""
    text = str(message).rstrip("\n")
    sys.stderr.write(text + "\n")
    if "--json" in sys.argv and not _JSON_EMITTED["value"]:
        print(json.dumps({"error": text}, ensure_ascii=False))
    sys.exit(1)


def run(main_func):
    """脚本入口统一包装：中文报错、不抛 traceback，退出码语义一致。"""
    try:
        main_func()
    except KeyboardInterrupt:
        sys.exit("已中断。")
    except SystemExit as exc:
        if isinstance(exc.code, str):
            fail(exc.code)
        raise
    except Exception as exc:  # noqa: BLE001 统一报错，不静默
        fail("错误：{}".format(exc))


def open_url(req, timeout):
    """优先直连（绕过注册表代理），连续失败后回退系统代理，并周期性重试直连。"""
    fails = _STATE["direct_fails"]
    if fails < DIRECT_FAIL_LIMIT or _STATE["since_retry"] >= DIRECT_RETRY_INTERVAL:
        try:
            resp = _DIRECT_OPENER.open(req, timeout=timeout)
            _STATE["direct_fails"] = 0
            _STATE["since_retry"] = 0
            return resp
        except Exception:  # noqa: BLE001 直连失败时累计并回退
            _STATE["direct_fails"] = fails + 1
            _STATE["since_retry"] = 0
    _STATE["since_retry"] += 1
    return urllib.request.urlopen(req, timeout=timeout)
