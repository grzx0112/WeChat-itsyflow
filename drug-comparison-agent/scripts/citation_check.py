#!/usr/bin/env python3
"""后置引用校验器：核对报告里 [来源:N] 的真实性与论断是否有据。

规则：
1. 解析每个 [来源:N]，N 必须存在于 cell ids；否则标红。
2. 含药名（≥1 个）的陈述句若无任何 [来源:N]，视为无据论断，标红。
3. 纯说明性句（无药名）不校验。
"""
from __future__ import annotations

import re
from typing import Dict, List

CITE_RE = re.compile(r"\[来源:(\d+)\]")


def _split_sentences(text: str) -> List[str]:
    # 按中英文句号/换行切句，保留分隔
    parts = re.split(r"(?<=[。.！!？?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def validate(report_md: str, matrix: Dict, drugs: List[str]) -> Dict[str, List]:
    valid_ids = {c["id"] for c in matrix.get("cells", [])}
    drug_set = set(drugs)
    ok: List[str] = []
    flagged: List[str] = []

    for sent in _split_sentences(report_md):
        cites = CITE_RE.findall(sent)
        mentions_drug = any(d in sent for d in drug_set)
        if not mentions_drug and not cites:
            continue  # 纯说明句，跳过
        if cites:
            bad = [n for n in cites if int(n) not in valid_ids]
            if bad:
                flagged.append(f"[无效引用 {bad}] {sent}")
            else:
                # ok 记录"通过校验的有效引用"（每条 [来源:N] 计一次），
                # 与模块职责"核对 [来源:N] 真实性"一致；不是句子集合。
                ok.extend(cites)
        else:
            # 含药名但无引用 → 无据论断
            flagged.append(f"[无引用] {sent}")
    return {"ok": ok, "flagged": flagged}
