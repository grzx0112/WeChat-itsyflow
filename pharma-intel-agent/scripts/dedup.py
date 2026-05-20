#!/usr/bin/env python3
"""去重 + 标准化模块"""

import re
from difflib import SequenceMatcher
from typing import List, Dict
from urllib.parse import urlparse


def _normalize_title(title: str) -> str:
    """标准化标题：小写 + 去标点 + 去多余空格"""
    title = title.lower()
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def _title_similarity(a: str, b: str) -> float:
    """计算标题相似度"""
    return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


def _url_dedup_key(url: str) -> str:
    """提取 URL 的去重 key（域名 + 路径，忽略参数）"""
    if not url:
        return ""
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path.rstrip('/')}"


def dedup(items: List[Dict], sim_threshold: float = 0.8) -> List[Dict]:
    """
    去重 + 标准化
    - URL 去重：相同 url_key 保留第一条
    - 标题去重：相似度 ≥ threshold 保留评分来源更优的（优先 FDA/PubMed > News）
    """
    if not items:
        return []

    # 来源优先级
    source_priority = {
        "FDA": 0, "PubMed": 1, "BioPharma Dive": 2,
        "Fierce Pharma": 3, "STAT News": 4, "Endpoints News": 5,
        "BioSpace": 6, "Pink Sheet": 7, "FDA News Release": 8,
    }

    # URL 去重
    seen_urls = set()
    url_deduped = []
    for item in items:
        url_key = _url_dedup_key(item.get("source_url", ""))
        if url_key and url_key in seen_urls:
            continue
        if url_key:
            seen_urls.add(url_key)
        url_deduped.append(item)

    # 标题相似度去重
    deduped = []
    for item in url_deduped:
        is_dup = False
        for existing in deduped:
            sim = _title_similarity(item.get("title", ""), existing.get("title", ""))
            if sim >= sim_threshold:
                # 保留来源优先级更高的
                item_pri = source_priority.get(item.get("source", ""), 99)
                exist_pri = source_priority.get(existing.get("source", ""), 99)
                if item_pri < exist_pri:
                    deduped.remove(existing)
                    deduped.append(item)
                is_dup = True
                break
        if not is_dup:
            deduped.append(item)

    # 标准化日期
    for item in deduped:
        date = item.get("date", "")
        if date:
            # 确保是 YYYY-MM-DD 格式
            date = re.sub(r'[^\d-]', '', date[:10])
            if len(date) == 8 and date.isdigit():
                date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        item["date"] = date

    # 按日期降序排序
    deduped.sort(key=lambda x: x.get("date", ""), reverse=True)

    print(f"[Dedup] 原始: {len(items)} → URL去重: {len(url_deduped)} → 标题去重: {len(deduped)}")
    return deduped


if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description="去重测试")
    parser.add_argument("--input", required=True, help="输入 JSON 文件")
    parser.add_argument("--threshold", type=float, default=0.8)
    args = parser.parse_args()
    with open(args.input) as f:
        data = json.load(f)
    result = dedup(data, args.threshold)
    print(json.dumps(result, ensure_ascii=False, indent=2))
