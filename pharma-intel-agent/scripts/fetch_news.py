#!/usr/bin/env python3
"""RSS 新闻聚合模块 — 扩展源 + 改进关键词过滤 + 自定义源支持"""

import sys
import os

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

import requests
import json
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict
import re


RSS_FEEDS = {
    "BioPharma Dive": "https://www.biopharmadive.com/feeds/news/",
    "Fierce Pharma": "https://www.fiercepharma.com/rss/xml",
    "STAT News": "https://www.statnews.com/feed/",
    "Endpoints News": "https://endpts.com/feed/",
    "BioSpace": "https://www.biospace.com/rss.xml",
    "Pink Sheet": "https://subscriber.politico.com/f/?id=fef42880-cb69-11ea-80c1-05bc91cf9a4e",
    "FDA News Release": "https://www.fda.gov/about-fda/contact-us/fda-news-rss-feed",
}

# 可选 RSS 源（可能需要特定访问或响应较慢，默认不启用）
OPTIONAL_RSS_FEEDS = {
    "Pharma Times": "https://www.pharmatimes.com/rss/default.aspx",
    "Drug Discovery Online": "https://www.drugdiscoveryonline.com/rss.xml",
}


def _expand_keywords(query: str) -> List[str]:
    """将查询展开为关键词列表，支持连字符变体"""
    # 分割 query
    base_keywords = [k.strip().lower() for k in re.split(r'[,\s]+', query) if len(k.strip()) > 1]
    expanded = set(base_keywords)
    for kw in base_keywords:
        # 添加无连字符版本
        expanded.add(kw.replace("-", ""))
        expanded.add(kw.replace("-", " "))
        # 添加带连字符版本（如果原始无连字符）
        if "-" not in kw:
            # 常见模式：GLP1 → GLP-1
            expanded.add(re.sub(r'(\d)', r'-\1', kw))
    return list(expanded)


def _keyword_match(text: str, query: str) -> bool:
    """检查文本是否匹配关键词（支持多词 query，模糊匹配）"""
    text_lower = text.lower()
    keywords = _expand_keywords(query)
    # 任一关键词匹配即通过
    for kw in keywords:
        if len(kw) > 2 and kw in text_lower:
            return True
    return False


def fetch_news(query: str, days: int = 7, rss_file: str = None) -> List[Dict]:
    """从 RSS 源抓取医药新闻并按关键词过滤，支持自定义 RSS 源"""
    since = datetime.now() - timedelta(days=days)
    items = []

    # 合并默认源和自定义源
    feeds = dict(RSS_FEEDS)
    if rss_file:
        try:
            with open(rss_file, "r", encoding="utf-8") as f:
                custom = json.load(f)
            if isinstance(custom, dict):
                feeds.update(custom)
            elif isinstance(custom, list):
                for item in custom:
                    if isinstance(item, dict) and "name" in item and "url" in item:
                        feeds[item["name"]] = item["url"]
            print(f"[News] 已加载自定义 RSS 源: {rss_file}")
        except Exception as e:
            print(f"[News] 加载自定义 RSS 源失败: {e}")

    for source_name, feed_url in feeds.items():
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                print(f"[News] {source_name}: feed 解析失败 ({feed.bozo_exception})")
                continue

            entry_count = 0
            for entry in feed.entries:
                # 日期处理
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6])

                if pub_date and pub_date < since:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                # 清理 HTML 标签
                summary_clean = re.sub(r'<[^>]+>', '', summary)[:500]

                # 关键词过滤：搜索 title + summary（不再只搜 title）
                combined_text = f"{title} {summary_clean}"
                if not _keyword_match(combined_text, query):
                    continue

                link = entry.get("link", "")
                date_str = pub_date.strftime("%Y-%m-%d") if pub_date else ""

                items.append({
                    "title": title,
                    "source": source_name,
                    "source_url": link,
                    "date": date_str,
                    "raw_summary": summary_clean or "No summary available",
                })
                entry_count += 1

            print(f"[News] {source_name}: {entry_count} 条匹配")

        except Exception as e:
            print(f"[News] {source_name} Error: {e}")

    print(f"[News] 共获取 {len(items)} 条（过滤后）")
    return items


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RSS 新闻抓取")
    parser.add_argument("--query", required=True)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    import json
    results = fetch_news(args.query, args.days)
    print(json.dumps(results, ensure_ascii=False, indent=2))
