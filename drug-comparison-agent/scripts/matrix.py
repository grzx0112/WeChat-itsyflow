#!/usr/bin/env python3
"""矩阵装配器：每个 drug × dim → 一个 cell（value + sources）。

cell schema 见实现计划头部。value 一律字符串；sources 标注数据来源。
"""
from __future__ import annotations

from typing import Dict, List

DIMENSIONS = ["profile", "indications", "pipeline", "endpoints", "safety"]


def _profile_cell(drug: str, raw: dict) -> dict:
    n = raw.get("normalized") or {}
    val = (f"generic={n.get('generic_name','')}; brand={n.get('brand_name', drug)}; "
           f"form={n.get('dosage_form','')}; status={n.get('marketing_status','')}")
    return {"value": val, "sources": [{"api": "openFDA NDC", "query": f"name:{drug}", "field": "marketing_status"}]}


def _indications_cell(drug: str, raw: dict) -> dict:
    lab = raw.get("label") or {}
    mech = lab.get("mechanism", "")
    val = f"indications: {lab.get('indications','')}; mechanism: {mech}"
    return {"value": val, "sources": [{"api": "openFDA Label", "query": f"name:{drug}", "field": "indications_and_usage"}]}


def _pipeline_cell(drug: str, raw: dict) -> dict:
    p = raw.get("pipeline") or {}
    val = (f"total_trials={p.get('total',0)}; by_phase={p.get('by_phase',{})}; "
           f"top_conditions={p.get('top_conditions',[])}")
    return {"value": val, "sources": [{"api": "ClinicalTrials.gov", "query": f"intervention:{drug}", "field": "studies"}]}


def _endpoints_cell(drug: str, raw: dict) -> dict:
    eps = raw.get("endpoints") or []
    measures = "; ".join(f"{e['measure']}({e.get('condition','')})" for e in eps[:6])
    return {"value": measures or "(无 III/IV 期终点)",
            "sources": [{"api": "ClinicalTrials.gov", "query": f"intervention:{drug}", "field": "primaryOutcomes"}]}


def _safety_cell(drug: str, raw: dict) -> dict:
    lab = raw.get("label") or {}
    faers = raw.get("faers") or []
    boxed = "yes" if lab.get("has_boxed_warning") else "no"
    val = f"boxed_warning={boxed}; top_AE={', '.join(faers[:6])}"
    src = [{"api": "openFDA Label", "query": f"name:{drug}", "field": "boxed_warning"},
           {"api": "openFDA FAERS", "query": f"generic:{drug}", "field": "reactionmeddrapt"}]
    return {"value": val, "sources": src}


_BUILDERS = {
    "profile": _profile_cell,
    "indications": _indications_cell,
    "pipeline": _pipeline_cell,
    "endpoints": _endpoints_cell,
    "safety": _safety_cell,
}


def build_matrix(drugs: List[str], raw: Dict[str, dict]) -> Dict[str, object]:
    """raw[drug] = {normalized, label, faers, pipeline, endpoints}。返回矩阵 dict。"""
    cells: List[dict] = []
    cid = 0
    for drug in drugs:
        draw = raw.get(drug, {})
        for dim in DIMENSIONS:
            cid += 1
            cell = _BUILDERS[dim](drug, draw)
            cells.append({"id": cid, "drug": drug, "dim": dim,
                          "value": cell["value"], "sources": cell["sources"]})
    return {"drugs": list(drugs), "dimensions": list(DIMENSIONS), "cells": cells}
