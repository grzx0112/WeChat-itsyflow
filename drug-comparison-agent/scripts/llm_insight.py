#!/usr/bin/env python3
"""LLM 定位洞察：矩阵接地生成 4 小节洞察，强制 [来源:N] 引用。

build_prompt() 纯函数（可测）；call_llm() I/O；generate_insight() 编排 + 容错。
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Dict

DEFAULT_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4-flash"

SYSTEM = (
    "你是医药竞品分析专家。基于下方「对比矩阵」生成定位洞察，严格遵守：\n"
    "1. 每条论断必须以 [来源:N] 标注依据，N 为矩阵 cell 的 id。\n"
    "2. 矩阵中无数据支撑的论断一律不得输出；禁止编造数字、试验名或适应症。\n"
    "3. 输出 4 个小节：## 机制差异化 / ## 适应症护城河 / ## 管线领先者 / ## 空白机会。\n"
    "4. 使用中文。若某小节缺乏数据，写「数据不足，无法判断」并不得编造。"
)


def build_prompt(matrix: Dict) -> str:
    cells = [{"id": c["id"], "drug": c["drug"], "dim": c["dim"], "value": c["value"]}
             for c in matrix["cells"]]
    return (
        f"{SYSTEM}\n\n"
        f"对比药品：{', '.join(matrix['drugs'])}\n\n"
        f"对比矩阵（JSON，每条论断引用对应 id）：\n"
        f"{json.dumps(cells, ensure_ascii=False, indent=2)}\n\n"
        f"请输出 4 小节定位洞察。"
    )


def call_llm(prompt: str, api_key: str, model: str, base: str = DEFAULT_BASE) -> str:
    """POST DeepSeek chat/completions，返回 content 文本。失败抛 RuntimeError。"""
    url = f"{base}/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt[len(SYSTEM):].strip()}],
        "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def generate_insight(matrix: Dict, api_key: str = "", model: str = "",
                     base: str = DEFAULT_BASE) -> str:
    api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
    model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
    prompt = build_prompt(matrix)
    if not api_key:
        return "## 定位洞察\n\n（LLM 不可用：未设置 DEEPSEEK_API_KEY；以下为矩阵摘要，请人工分析。）"
    try:
        return call_llm(prompt, api_key, model, base)
    except Exception as e:
        return f"## 定位洞察\n\n（LLM 生成失败：{e}；请人工基于对比矩阵分析。）"
