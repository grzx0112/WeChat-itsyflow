#!/usr/bin/env python3
"""渲染器：矩阵 Markdown 表 + 报告组装（中文）。"""
from __future__ import annotations

from typing import Dict, List

MAX_CELL_LEN = 80


def _truncate(s: str) -> str:
    s = s.replace("|", "/").replace("\n", " ")
    return s if len(s) <= MAX_CELL_LEN else s[:MAX_CELL_LEN - 1] + "…"


def render_matrix_table(matrix: Dict) -> str:
    drugs = matrix["drugs"]
    dims = matrix["dimensions"]
    # 按 (drug, dim) 索引 value
    idx = {(c["drug"], c["dim"]): c["value"] for c in matrix["cells"]}
    header = "| 维度 | " + " | ".join(drugs) + " |"
    sep = "|" + "---|" * (len(drugs) + 1)
    lines = [header, sep]
    for d in dims:
        row = [d] + [_truncate(idx.get((drug, d), "-")) for drug in drugs]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_report(matrix: Dict, insight_md: str, flagged: List[str]) -> str:
    parts = [
        "# 药品竞品对比报告",
        f"对比药品：{', '.join(matrix['drugs'])}",
        "",
        "## 对比矩阵",
        render_matrix_table(matrix),
        "",
        "## 定位洞察",
        insight_md.strip(),
    ]
    if flagged:
        parts += ["", "## ⚠️ 未验证论断",
                  "以下论断缺乏数据源引用或引用无效，请人工复核：", ""]
        parts += [f"- {f}" for f in flagged]
    parts += ["", "---", "*数据源：openFDA (Label/NDC/FAERS) + ClinicalTrials.gov v2；本报告仅供竞品分析参考，非临床决策依据。*"]
    return "\n".join(parts)
