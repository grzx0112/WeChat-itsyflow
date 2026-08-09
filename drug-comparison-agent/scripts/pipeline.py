#!/usr/bin/env python3
"""drug-comparison-agent 主入口：Stage 0–8 编排 + CLI。

用法：
  python scripts/pipeline.py --drugs "Ozempic,Wegovy" --out-dir ./output
  echo '{"drugs":["Ozempic","Wegovy"]}' | python scripts/pipeline.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

# 让 `python scripts/pipeline.py` 也能 import scripts.* 包（把 skill 根目录加入 sys.path）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from scripts.fetchers import openfda, ctgov
from scripts.matrix import build_matrix
from scripts.llm_insight import generate_insight
from scripts.citation_check import validate
from scripts.render import render_report
from scripts.env_loader import load_skill_env

# 启动时从 skill 根目录的 .env 加载配置（纯标准库；系统 env 已设的值优先，不覆盖）
load_skill_env()

MAX_DRUGS = 6


def _collect(drug: str) -> dict:
    """对单药跑 Stage 1–5 采集，返回 raw[drug]。失败容错不抛。

    v1.2: CT.gov 只下载一次研究列表（fetch_studies），管线聚合与终点抽取共享，
    避免重复下载两遍 pageSize 条研究（原各自调 fetch_pipeline/fetch_endpoints）。
    """
    norm = openfda.normalize(drug)
    generic = (norm or {}).get("generic_name", drug)
    studies, total = ctgov.fetch_studies(drug)
    return {
        "normalized": norm,
        "label": openfda.fetch_label(drug, generic=generic),
        "faers": openfda.fetch_faers_top(generic),
        "pipeline": ctgov.summarize_pipeline(studies, total),
        "endpoints": ctgov.extract_endpoints(studies),
    }


def run_pipeline(drugs: list, out_dir: str, api_key: str = "",
                 write_files: bool = True) -> dict:
    if not 2 <= len(drugs) <= MAX_DRUGS:
        raise ValueError(f"药名数量须在 2–{MAX_DRUGS} 之间，当前 {len(drugs)}")

    warnings = []
    raw = {}
    for drug in drugs:
        raw[drug] = _collect(drug)
        if raw[drug]["normalized"] is None:
            warnings.append(f"unresolved: {drug}（openFDA NDC 未命中，按原名继续）")

    matrix = build_matrix(drugs, raw)
    insight = generate_insight(matrix, api_key=api_key)
    check = validate(insight, matrix, drugs)
    report = render_report(matrix, insight, check["flagged"])

    if write_files:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "comparison-matrix.json"), "w", encoding="utf-8") as f:
            json.dump(matrix, f, ensure_ascii=False, indent=2)
        with open(os.path.join(out_dir, "comparison-report.md"), "w", encoding="utf-8") as f:
            f.write(report)

    return {"ok": True, "matrix": matrix, "report": report,
            "flagged": check["flagged"], "warnings": warnings}


def main() -> None:
    ap = argparse.ArgumentParser(description="药品竞品对比 / 选药商业分析")
    ap.add_argument("--drugs", help="逗号分隔药名，如 Ozempic,Wegovy")
    ap.add_argument("--out-dir", default=None, help="输出目录")
    ap.add_argument("--api-key", default=None, help="DeepSeek API Key（默认读 env DEEPSEEK_API_KEY）")
    args = ap.parse_args()

    drugs = None
    if args.drugs:
        drugs = [d.strip() for d in args.drugs.split(",") if d.strip()]
    else:
        # stdin JSON 兜底
        data = json.loads(sys.stdin.read())
        drugs = data.get("drugs")

    out_dir = args.out_dir or os.path.join(
        "output", f"drug-comparison-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    result = run_pipeline(drugs, out_dir=out_dir,
                          api_key=args.api_key or os.getenv("DEEPSEEK_API_KEY", ""))
    if result["warnings"]:
        print("⚠️ 警告：", "; ".join(result["warnings"]), file=sys.stderr)
    print(f"✅ 完成。矩阵 {len(result['matrix']['cells'])} cells；"
          f"未验证论断 {len(result['flagged'])} 条；报告 → {out_dir}/comparison-report.md")


if __name__ == "__main__":
    main()
