#!/usr/bin/env python3
"""
通用名动态展开模块 — 三层 fallback 机制
将靶点/药物类别查询词展开为 FDA 可查的药品通用名列表

第1层：内置映射表（零延迟）
第2层：openFDA openfda 反查
第3层：ChEMBL API 靶点→药物映射
"""

import sys
import os

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

import json
import time
import re
import requests
from typing import List, Dict, Optional


# 第1层：内置快速映射（高频靶点/药物类别）
BUILTIN_MAP = {
    "GLP-1": ["semaglutide", "liraglutide", "tirzepatide", "dulaglutide", "exenatide", "lixisenatide"],
    "GLP-1RA": ["semaglutide", "liraglutide", "tirzepatide", "dulaglutide", "exenatide", "lixisenatide"],
    "PD-1": ["pembrolizumab", "nivolumab", "cemiplimab", "sintilimab"],
    "PD-L1": ["atezolizumab", "durvalumab", "avelumab"],
    "PD-1/PD-L1": ["pembrolizumab", "nivolumab", "atezolizumab", "durvalumab", "avelumab", "cemiplimab"],
    "ADC": ["trastuzumab emtansine", "trastuzumab deruxtecan", "sacituzumab govitecan", "enalumab"],
    "HER2": ["trastuzumab", "pertuzumab", "trastuzumab emtansine", "trastuzumab deruxtecan", "lapatinib", "tucatinib", "neratinib"],
    "EGFR": ["osimertinib", "erlotinib", "gefitinib", "afatinib", "dacomitinib", "amivantamab"],
    "ALK": ["alectinib", "crizotinib", "lorlatinib", "brigatinib", "ceritinib"],
    "VEGF": ["bevacizumab", "aflibercept", "ramucirumab"],
    "BCMA": ["idecabtagene vicleucel", "ciltacabtagene autoleucel", "belantamab mafodotin"],
    "CD19": ["tisagenlecleucel", "axicabtagene ciloleucel", "lisocabtagene maraleucel"],
    "BTK": ["ibrutinib", "acalabrutinib", "zanubrutinib", "pirtobrutinib"],
    "PARP": ["olaparib", "rucaparib", "niraparib", "talazoparib"],
    "JAK": ["ruxolitinib", "tofacitinib", "baricitinib", "upadacitinib"],
    "IL-6": ["tocilizumab", "siltuximab", "sarilumab"],
    "CDK4/6": ["palbociclib", "ribociclib", "abemaciclib"],
    "CTLA-4": ["ipilimumab", "tremelimumab"],
    "CAR-T": ["tisagenlecleucel", "axicabtagene ciloleucel", "lisocabtagene maraleucel", "idecabtagene vicleucel", "ciltacabtagene autoleucel"],
    "SGLT2": ["empagliflozin", "dapagliflozin", "canagliflozin", "ertugliflozin"],
    "IL-17": ["secukinumab", "ixekizumab", "brodalumab", "guselkumab"],
    "TNF": ["adalimumab", "etanercept", "infliximab", "golimumab", "certolizumab"],
    "IL-23": ["guselkumab", "risankizumab", "tildrakizumab"],
    "IL-4/IL-13": ["dupilumab", "lebrikizumab", "tralokinumab"],
    "BCL-2": ["venetoclax"],
    "PI3K": ["idelalisib", "copanlisib", "duvelisib", "alpelisib"],
    "mTOR": ["everolimus", "temsirolimus", "sirolimus"],
    "HDAC": ["vorinostat", "romidepsin", "panobinostat", "belinostat"],
    "CD20": ["rituximab", "obinutuzumab", "ofatumumab", "ubituximab"],
    "CCR5": ["maraviroc", "leronlimab"],
    "CXCR4": ["plerixafor", "mavorixafor"],
    "TIGIT": ["tiragolumab"],
    "LAG-3": ["relatlimab"],
    "TIM-3": ["sabatolimab"],
    "KRAS": ["sotorasib", "adagrasib"],
    "BRAF": ["vemurafenib", "dabrafenib", "encorafenib"],
    "MEK": ["trametinib", "cobimetinib", "binimetinib"],
    "FGFR": ["erdafitinib", "pemigatinib", "futibatinib", "infigratinib"],
    "MET": ["capmatinib", "tepotinib", "crizotinib", "savolitinib"],
    "RET": ["selpercatinib", "pralsetinib"],
    "NTRK": ["larotrectinib", "entrectinib"],
}

# 缓存：避免同一 session 重复 API 调用
_cache: Dict[str, List[str]] = {}


def _normalize_query(query: str) -> str:
    """标准化查询词用于匹配"""
    return query.upper().strip()


def _layer1_builtin(query: str) -> Optional[List[str]]:
    """第1层：内置映射表快速查找"""
    q = _normalize_query(query)
    # 精确匹配
    if q in BUILTIN_MAP:
        return BUILTIN_MAP[q]
    # 子串匹配（如 "GLP-1 receptor agonist" 包含 "GLP-1"）
    for key, names in BUILTIN_MAP.items():
        if key in q:
            return names
    return None


def _layer2_openfda(query: str, timeout: int = 15) -> Optional[List[str]]:
    """
    第2层：通过 openFDA 反查关联药品通用名
    搜索 drugsfda 端点，提取返回结果中的 generic_name 和 brand_name
    """
    names = set()
    endpoints = [
        ("drugsfda", "https://api.fda.gov/drug/drugsfda.json",
         lambda q: f'openfda.generic_name:"{q}"+OR+openfda.brand_name:"{q}"'),
        ("label", "https://api.fda.gov/drug/label.json",
         lambda q: f'openfda.generic_name:"{q}"+OR+openfda.brand_name:"{q}"'),
    ]

    for name, url, search_fn in endpoints:
        try:
            search = search_fn(query)
            params = {"search": search, "limit": 20}
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()

            for result in data.get("results", []):
                openfda = result.get("openfda", {})
                # 提取 generic_name
                for g in openfda.get("generic_name", []):
                    if g and len(g) > 2:
                        names.add(g.lower())
                # 提取 brand_name（仅 drugsfda）
                for b in openfda.get("brand_name", []):
                    if b and len(b) > 2:
                        names.add(b.lower())
                # 提取 products 中的 brand_name（drugsfda 格式）
                for product in result.get("products", []):
                    bn = product.get("brand_name", "")
                    if bn and len(bn) > 2:
                        names.add(bn.lower())
        except Exception as e:
            print(f"[Expand] openFDA {name} 查询失败: {e}")

    if names:
        print(f"[Expand] 第2层 openFDA 发现 {len(names)} 个关联名称")
        return list(names)
    return None


def _layer3_chembl(query: str, timeout: int = 15) -> Optional[List[str]]:
    """
    第3层：通过 ChEMBL API 按靶点名称查找关联药物
    1. 搜索 target（靶点）
    2. 获取关联的 molecule（药物）
    3. 过滤已批准药物，返回通用名
    """
    base = "https://www.ebi.ac.uk/chembl/api/data"
    headers = {"Accept": "application/json"}

    # Step 1: 搜索靶点
    try:
        target_resp = requests.get(
            f"{base}/target/search.json",
            params={"q": query, "limit": 5, "target_type": "SINGLE PROTEIN"},
            headers=headers,
            timeout=timeout,
        )
        target_resp.raise_for_status()
        targets = target_resp.json().get("targets", [])
        if not targets:
            # 放宽条件：不限 target_type
            target_resp = requests.get(
                f"{base}/target/search.json",
                params={"q": query, "limit": 5},
                headers=headers,
                timeout=timeout,
            )
            target_resp.raise_for_status()
            targets = target_resp.json().get("targets", [])

        if not targets:
            return None

        target_chembl_ids = [t["target_chembl_id"] for t in targets[:3]]
    except Exception as e:
        print(f"[Expand] ChEMBL target 搜索失败: {e}")
        return None

    # Step 2: 获取关联药物
    names = set()
    for tid in target_chembl_ids:
        try:
            activity_resp = requests.get(
                f"{base}/activity.json",
                params={
                    "target_chembl_id": tid,
                    "type": "IC50",
                    "limit": 20,
                    "max_phase": 4,  # 已批准药物
                },
                headers=headers,
                timeout=timeout,
            )
            activity_resp.raise_for_status()
            activities = activity_resp.json().get("activities", [])

            for act in activities:
                mol_name = act.get("molecule_chembl_id", "")
                pref = act.get("molecule_pref_name", "")
                if pref and len(pref) > 2:
                    names.add(pref.lower())

        except Exception as e:
            print(f"[Expand] ChEMBL activity 查询 {tid} 失败: {e}")
            continue

    if names:
        print(f"[Expand] 第3层 ChEMBL 发现 {len(names)} 个关联药物")
        return list(names)
    return None


def expand_query(query: str, no_expand: bool = False) -> List[str]:
    """
    主入口：三层 fallback 通用名展开

    Args:
        query: 查询词（靶点/药物类别/药物名）
        no_expand: 禁用展开，直接返回原始查询

    Returns:
        展开后的药品通用名列表
    """
    if no_expand:
        print(f"[Expand] 禁用展开，使用原始查询: '{query}'")
        return [query]

    # 检查缓存
    cache_key = _normalize_query(query)
    if cache_key in _cache:
        print(f"[Expand] 缓存命中: '{query}' → {len(_cache[cache_key])} 个名称")
        return _cache[cache_key]

    # 第1层：内置映射
    result = _layer1_builtin(query)
    if result:
        print(f"[Expand] 第1层命中: '{query}' → {result}")
        _cache[cache_key] = result
        return result

    # 第2层：openFDA 反查
    result = _layer2_openfda(query)
    if result:
        _cache[cache_key] = result
        return result

    # 第3层：ChEMBL 靶点→药物
    result = _layer3_chembl(query)
    if result:
        _cache[cache_key] = result
        return result

    # 全部未命中：返回原始查询
    print(f"[Expand] 三层均未命中，使用原始查询: '{query}'")
    _cache[cache_key] = [query]
    return [query]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="通用名展开测试")
    parser.add_argument("--query", required=True, help="查询词")
    parser.add_argument("--no-expand", action="store_true", help="禁用展开")
    args = parser.parse_args()

    result = expand_query(args.query, args.no_expand)
    print(f"\n展开结果 ({len(result)} 个):")
    for name in result:
        print(f"  - {name}")
