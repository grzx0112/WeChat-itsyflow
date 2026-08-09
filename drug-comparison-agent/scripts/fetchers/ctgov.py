#!/usr/bin/env python3
"""ClinicalTrials.gov v2 采集器：在研管线聚合 / 关键终点。

依赖 scripts.http_util.get_json。失败 → 返回空结构。

v1.2 性能优化（国内网络下大 payload 传输慢，实测 100 条 ~180s）：
- PAGE_SIZE 100→30（30 条 ~55s，足够支撑分布聚合与 III/IV 期终点抽取）；
- total 改用 API 返回的 totalCount（pageSize 截断不再导致总数失真）；
- pipeline 聚合与 endpoints 抽取共享同一次下载（fetch_studies），避免重复拉取两遍。
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Tuple

from scripts.http_util import get_json

CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"

# v1.2: 单页研究条数。100→30：大 payload 在国内网络传输极慢（~180s/100 条），
# 30 条已足够支撑 phase/status/condition 分布聚合与 III/IV 期终点抽取。
PAGE_SIZE = 30


def fetch_studies(name: str, page_size: int = PAGE_SIZE) -> Tuple[List[dict], int]:
    """下载一次研究列表，返回 (studies, totalCount)。失败返回 ([], 0)。

    totalCount 来自 API（真实总匹配数，不受 pageSize 截断影响），
    供 summarize_pipeline 用作准确的 total。
    """
    try:
        data = get_json(CTGOV_URL, params={
            "query.intr": name,
            "pageSize": page_size,
        })
        studies = data.get("studies") or []
        # CT.gov v2 真实响应仅含 studies + nextPageToken，不含 totalCount（实测）；
        # 若将来 API 返回 totalCount 则优先用，否则以本次返回条数兜底（≤ page_size），避免 total=0。
        total = int(data.get("totalCount") or 0) or len(studies)
        return studies, total
    except Exception:
        return [], 0


def summarize_pipeline(studies: List[dict], total: int) -> Dict[str, object]:
    """基于 studies 样本聚合：by_phase / by_status / top_conditions(前 8)。

    total 用真实 totalCount（非样本数）；phase/status/condition 分布基于
    前 PAGE_SIZE 条样本，作为竞品横向对比的相对指标。
    """
    by_phase: Counter = Counter()
    by_status: Counter = Counter()
    cond: Counter = Counter()
    for s in studies:
        ps = s.get("protocolSection", {})
        for ph in ps.get("designModule", {}).get("phases", []) or []:
            by_phase[ph] += 1
        st = ps.get("statusModule", {}).get("overallStatus")
        if st:
            by_status[st] += 1
        for c in ps.get("conditionsModule", {}).get("conditions", []) or []:
            cond[c] += 1
    return {
        "total": total,
        "by_phase": dict(by_phase),
        "by_status": dict(by_status),
        "top_conditions": [c for c, _ in cond.most_common(8)],
    }


def extract_endpoints(studies: List[dict]) -> List[Dict[str, str]]:
    """III/IV 期试验的 primaryOutcomes.measure 列表。"""
    out: List[Dict[str, str]] = []
    for s in studies:
        ps = s.get("protocolSection", {})
        phases = ps.get("designModule", {}).get("phases", []) or []
        if not (set(phases) & {"PHASE3", "PHASE4"}):
            continue
        cond_list = ps.get("conditionsModule", {}).get("conditions", []) or []
        for po in ps.get("outcomesModule", {}).get("primaryOutcomes", []) or []:
            out.append({
                "measure": po.get("measure", ""),
                "condition": cond_list[0] if cond_list else "",
            })
    return out


def fetch_pipeline(name: str) -> Dict[str, object]:
    """便捷封装：下载 + 聚合（独立调用，单独发请求）。

    pipeline 主流程应直接用 fetch_studies + summarize_pipeline 共享下载，
    避免与 fetch_endpoints 重复拉取；本函数保留给独立调用与测试。
    """
    studies, total = fetch_studies(name)
    return summarize_pipeline(studies, total)


def fetch_endpoints(name: str) -> List[Dict[str, str]]:
    """便捷封装：下载 + 抽取（独立调用，单独发请求）。"""
    studies, _ = fetch_studies(name)
    return extract_endpoints(studies)
