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
from typing import List, Dict

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


def _search_field(base_url: str, search: str, limit: int) -> List[Dict]:
    """通用 openFDA 搜索，返回原始 JSON results 或空列表"""
    try:
        resp = requests.get(base_url, params={"search": search, "limit": limit}, timeout=30)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception:
        return []


def fetch_fda_drug_event(query: str, days: int = 7, limit: int = 25) -> List[Dict]:
    """抓取 FDA 不良事件数据 — 分别搜 generic/brand 再合并"""
    base_url = "https://api.fda.gov/drug/event.json"
    since = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    now_str = datetime.now().strftime("%Y%m%d")
    date_filter = f"+receivedate:[{since} TO {now_str}]"

    # 分别用 medicinalproduct 搜索（该字段同时包含通用名和商品名）
    search_strategies = [
        f'patient.drug.medicinalproduct:"{query}"{date_filter}',
    ]

    items = []
    seen = set()
    for search in search_strategies:
        for r in _search_field(base_url, search, limit):
            drugs = r.get("patient", {}).get("drug", [])
            drug_name = drugs[0].get("medicinalproduct", query) if drugs else query
            reactions = [re.get("reactionmeddrapt", "") for re in r.get("patient", {}).get("reaction", [])[:3]]
            title = f"FDA Adverse Event: {drug_name}"
            if title not in seen:
                seen.add(title)
                items.append({
                    "title": title,
                    "source": "FDA",
                    "source_url": f"https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:{query}",
                    "date": normalize_date(r.get("receivedate", "")),
                    "raw_summary": f"Reactions: {', '.join(filter(None, reactions)) or 'N/A'}",
                })
    return items


def fetch_fda_drugsfda(query: str, days: int = 7, limit: int = 25) -> List[Dict]:
    """抓取 Drugs@FDA 审批数据 — 分别搜 generic_name / brand_name 再合并"""
    base_url = "https://api.fda.gov/drug/drugsfda.json"

    search_strategies = [
        f'openfda.generic_name:"{query}"',
        f'products.brand_name:"{query}"',
    ]

    items = []
    seen_app_no = set()
    for search in search_strategies:
        for r in _search_field(base_url, search, limit):
            app_no = r.get("application_number", "")
            if app_no in seen_app_no:
                continue
            seen_app_no.add(app_no)
            products = r.get("products", [])
            brand = products[0].get("brand_name", query) if products else query
            app_type = r.get("application_type", "N/A")
            items.append({
                "title": f"FDA Approval: {brand} ({app_type} {app_no})",
                "source": "FDA",
                "source_url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app_no}",
                "date": normalize_date(r.get("submission_status_date", "")),
                "raw_summary": f"Application: {app_type} {app_no}",
            })
    return items


def fetch_fda_label(query: str, limit: int = 25) -> List[Dict]:
    """抓取 FDA 药品标签数据 — 分别搜 generic_name / brand_name 再合并"""
    base_url = "https://api.fda.gov/drug/label.json"

    search_strategies = [
        f'openfda.generic_name:"{query}"',
        f'openfda.brand_name:"{query}"',
    ]

    items = []
    seen_brands = set()
    for search in search_strategies:
        for r in _search_field(base_url, search, limit):
            brand = ", ".join(r.get("openfda", {}).get("brand_name", [query]))
            if brand in seen_brands:
                continue
            seen_brands.add(brand)
            indications = r.get("indications_and_usage", ["N/A"])[0][:200] if r.get("indications_and_usage") else "N/A"
            items.append({
                "title": f"FDA Label Update: {brand}",
                "source": "FDA",
                "source_url": f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{query}",
                "date": normalize_date(r.get("effective_time", "")),
                "raw_summary": indications,
            })
    return items


def fetch_fda(query: str, days: int = 7, no_expand: bool = False) -> List[Dict]:
    """聚合所有 FDA 数据源，支持动态通用名展开"""
    expanded = expand_query(query, no_expand=no_expand)
    is_mapped = len(expanded) > 1 or (len(expanded) == 1 and expanded[0].lower() != query.lower())

    if is_mapped:
        print(f"[FDA] 查询 '{query}' 展开为: {expanded}")
    else:
        print(f"[FDA] 使用原始查询 '{query}'")

    items = []
    seen_titles = set()

    for drug_name in expanded:
        for fetch_fn in [fetch_fda_drug_event, fetch_fda_drugsfda, fetch_fda_label]:
            try:
                if fetch_fn == fetch_fda_label:
                    new_items = fetch_fn(drug_name)
                else:
                    new_items = fetch_fn(drug_name, days)
            except Exception as e:
                print(f"[FDA] {fetch_fn.__name__}('{drug_name}') 失败: {e}")
                continue

            for item in new_items:
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
