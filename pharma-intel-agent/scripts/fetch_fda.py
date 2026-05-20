#!/usr/bin/env python3
"""FDA openFDA 数据抓取模块 — 通过 name_expand 动态展开通用名"""

import sys
import os

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from name_expand import expand_query


def normalize_date(date_str: str) -> str:
    """将各种日期格式标准化为 YYYY-MM-DD"""
    if not date_str:
        return ""
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str[:10] if len(date_str) >= 10 else date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str[:10] if len(date_str) >= 10 else date_str


def fetch_fda_drug_event(query: str, days: int = 7, limit: int = 25) -> List[Dict]:
    """抓取 FDA 不良事件数据"""
    base_url = "https://api.fda.gov/drug/event.json"
    since = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    now_str = datetime.now().strftime("%Y%m%d")
    search = f'patient.drug.medicinalproduct:"{query}"+receivedate:[{since} TO {now_str}]'
    params = {"search": search, "limit": limit}
    items = []
    try:
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for r in data.get("results", []):
            drugs = r.get("patient", {}).get("drug", [])
            drug_name = drugs[0].get("medicinalproduct", query) if drugs else query
            reactions = [re.get("reactionmeddrapt", "") for re in r.get("patient", {}).get("reaction", [])[:3]]
            items.append({
                "title": f"FDA Adverse Event: {drug_name}",
                "source": "FDA",
                "source_url": f"https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:{query}",
                "date": normalize_date(r.get("receivedate", "")),
                "raw_summary": f"Reactions: {', '.join(filter(None, reactions)) or 'N/A'}",
            })
    except Exception as e:
        print(f"[FDA Event] Error for '{query}': {e}")
    return items


def fetch_fda_drugsfda(query: str, days: int = 7, limit: int = 25, use_generic: bool = False) -> List[Dict]:
    """抓取 Drugs@FDA 审批数据"""
    base_url = "https://api.fda.gov/drug/drugsfda.json"
    if use_generic:
        search = f'products.brand_name:"{query}"+openfda.generic_name:"{query}"'
    else:
        search = f'products.brand_name:"{query}"'
    params = {"search": search, "limit": limit}
    items = []
    try:
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for r in data.get("results", []):
            products = r.get("products", [])
            brand = products[0].get("brand_name", query) if products else query
            app_type = r.get("application_type", "N/A")
            app_no = r.get("application_number", "N/A")
            items.append({
                "title": f"FDA Approval: {brand} ({app_type} {app_no})",
                "source": "FDA",
                "source_url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app_no}",
                "date": normalize_date(r.get("submission_status_date", "")),
                "raw_summary": f"Application: {app_type} {app_no}",
            })
    except Exception as e:
        print(f"[Drugs@FDA] Error for '{query}': {e}")
    return items


def fetch_fda_label(query: str, limit: int = 25, use_generic: bool = False) -> List[Dict]:
    """抓取 FDA 药品标签数据"""
    base_url = "https://api.fda.gov/drug/label.json"
    if use_generic:
        search = f'openfda.generic_name:"{query}"'
    else:
        search = f'openfda.brand_name:"{query}"'
    params = {"search": search, "limit": limit}
    items = []
    try:
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for r in data.get("results", []):
            brand = ", ".join(r.get("openfda", {}).get("brand_name", [query]))
            indications = r.get("indications_and_usage", ["N/A"])[0][:200] if r.get("indications_and_usage") else "N/A"
            items.append({
                "title": f"FDA Label Update: {brand}",
                "source": "FDA",
                "source_url": f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{query}",
                "date": normalize_date(r.get("effective_time", "")),
                "raw_summary": indications,
            })
    except Exception as e:
        print(f"[FDA Label] Error for '{query}': {e}")
    return items


def fetch_fda(query: str, days: int = 7, no_expand: bool = False) -> List[Dict]:
    """聚合所有 FDA 数据源，支持动态通用名展开"""
    expanded = expand_query(query, no_expand=no_expand)
    is_mapped = len(expanded) > 1 or (len(expanded) == 1 and expanded[0].lower() != query.lower())

    if is_mapped:
        print(f"[FDA] 查询 '{query}' 展开为: {expanded}")
    else:
        print(f"[FDA] 使用原始查询 '{query}'（未展开，将用 generic_name 回退）")

    items = []
    seen_titles = set()

    for drug_name in expanded:
        use_generic = not is_mapped  # 映射展开的用 brand_name，未映射的用 generic_name 回退

        for fetch_fn in [fetch_fda_drug_event, fetch_fda_drugsfda, fetch_fda_label]:
            try:
                if fetch_fn == fetch_fda_label:
                    new_items = fetch_fn(drug_name, use_generic=use_generic)
                elif fetch_fn == fetch_fda_drugsfda:
                    new_items = fetch_fn(drug_name, days, use_generic=use_generic)
                else:
                    new_items = fetch_fn(drug_name, days)
            except Exception as e:
                print(f"[FDA] {fetch_fn.__name__}('{drug_name}') 失败: {e}")
                continue

            for item in new_items:
                # 去重（按标题）
                if item["title"] not in seen_titles:
                    seen_titles.add(item["title"])
                    items.append(item)

    print(f"[FDA] 共获取 {len(items)} 条")
    return items


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FDA openFDA 抓取")
    parser.add_argument("--query", required=True)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    results = fetch_fda(args.query, args.days)
    print(json.dumps(results, ensure_ascii=False, indent=2))
