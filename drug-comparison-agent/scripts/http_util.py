#!/usr/bin/env python3
"""唯一 HTTP I/O 点：GET JSON，带 retry / timeout / rate-limit。

所有 fetcher 只准通过 get_json() 访问网络，便于单测 monkeypatch。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

TIMEOUT_S = 30
RETRY_MAX = 2
RETRY_SLEEP_S = 2
RATE_LIMIT_S = 0.2

_last_request_ts = 0.0

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "openclaw-drug-comparison/0.1 (+https://example.invalid)",
}


def _reset_rate_limit() -> None:
    """测试用：重置全局节流时间戳。"""
    global _last_request_ts
    _last_request_ts = 0.0


def _rate_limit() -> None:
    global _last_request_ts
    now = time.time()
    wait = RATE_LIMIT_S - (now - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.time()


def get_json(url: str,
             params: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """GET url 并解析 JSON。瞬时错误重试 RETRY_MAX 次；最终失败抛 RuntimeError。"""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    hdrs = {**HEADERS, **(headers or {})}
    last_err: Optional[Exception] = None
    for attempt in range(RETRY_MAX + 1):
        try:
            _rate_limit()
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt < RETRY_MAX:
                time.sleep(RETRY_SLEEP_S)
    raise RuntimeError(f"GET {url} failed after {RETRY_MAX + 1} attempts: {last_err}")
