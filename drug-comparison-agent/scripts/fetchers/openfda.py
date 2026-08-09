#!/usr/bin/env python3
"""openFDA 采集器：名字标准化 / 标签 / FAERS top AE。

依赖 scripts.http_util.get_json。任一请求失败 → 返回 None / 空，绝不抛出（管线容错）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from scripts.http_util import get_json

LABEL_URL = "https://api.fda.gov/drug/label.json"
NDC_URL = "https://api.fda.gov/drug/ndc.json"
EVENT_URL = "https://api.fda.gov/drug/event.json"


def normalize(name: str) -> Optional[Dict[str, str]]:
    """品牌/通用名 → NDC 首条命中（generic/brand/dosage_form/marketing_status）。失败返 None。"""
    # v1.1: 先精确品牌名查（避免 generic 命中兄弟产品的虚假记录），未命中再回退通用名
    for search in (f'brand_name:"{name}"', f'generic_name:"{name}"'):
        try:
            data = get_json(NDC_URL, params={"search": search, "limit": 1})
            results = data.get("results") or []
            if results:
                r = results[0]
                return {
                    "generic_name": r.get("generic_name", ""),
                    "brand_name": r.get("brand_name", "") or name,
                    "dosage_form": r.get("dosage_form", ""),
                    "marketing_status": r.get("marketing_status", ""),
                }
        except Exception:
            continue
    return None


def _join(lst):
    return "; ".join(lst) if isinstance(lst, list) else (lst or "")


def fetch_label(name: str, generic: str = "") -> Dict[str, object]:
    """标签 → {indications, mechanism, has_boxed_warning}。失败返空值结构。"""
    empty = {"indications": "", "mechanism": "", "has_boxed_warning": False}
    # v1.1: 标签先精确品牌名查（拿该药自己的 SPL，避免 generic 命中兄弟产品合并标签），未命中再回退通用名
    searches = [f'openfda.brand_name:"{name}"']
    if generic:
        searches.append(f'openfda.generic_name:"{generic}"')
    for terms in searches:
        try:
            # v1.2: limit 10→3（label payload 大，国内大包传输慢；3 条足够挑选单品牌 SPL）
            data = get_json(LABEL_URL, params={"search": terms, "limit": 3})
            results = data.get("results") or []
            if not results:
                continue
            # v1.1: 优先单品牌 SPL，避免合并标签污染（如 Rybelsus+Ozempic 口服片剂标签冒充 Ozempic）
            r = results[0]
            for cand in results:
                bn = ((cand.get("openfda") or {}).get("brand_name") or [])
                if len(bn) == 1:
                    r = cand
                    break
            return {
                "indications": _join(r.get("indications_and_usage")),
                "mechanism": _join(r.get("mechanism_of_action")),
                "has_boxed_warning": bool(r.get("boxed_warning")),
            }
        except Exception:
            continue
    return empty


def fetch_faers_top(generic: str, n: int = 8) -> List[str]:
    """FAERS top n 高频不良反应术语（MedDRA PT）。失败返 []。"""
    try:
        data = get_json(EVENT_URL, params={
            "search": f'patient.drug.medicinalproduct:"{generic}"',
            "count": "patient.reaction.reactionmeddrapt.exact",
            "limit": n,
        })
        return [item["term"] for item in (data.get("results") or [])]
    except Exception:
        return []
