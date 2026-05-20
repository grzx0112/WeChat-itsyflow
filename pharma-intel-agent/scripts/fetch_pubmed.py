#!/usr/bin/env python3
"""PubMed E-utilities 数据抓取模块"""

import sys
import os

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict
import time


PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def fetch_pubmed(query: str, days: int = 7, retmax: int = 100) -> List[Dict]:
    """通过 E-utilities 检索 PubMed 并获取摘要"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
    now = datetime.now().strftime("%Y/%m/%d")

    # Step 1: esearch 获取 UID 列表
    search_params = {
        "db": "pubmed",
        "term": f"{query}",
        "retmax": retmax,
        "datetype": "pdat",
        "mindate": since,
        "maxdate": now,
        "retmode": "json",
        "usehistory": "y",
    }

    items = []
    try:
        resp = requests.get(PUBMED_ESEARCH, params=search_params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            print("[PubMed] 未找到相关文献")
            return items

        print(f"[PubMed] 找到 {len(id_list)} 条文献")

        # Step 2: efetch 获取详情（分批，每批 20）
        for i in range(0, len(id_list), 20):
            batch = id_list[i:i+20]
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "rettype": "abstract",
                "retmode": "xml",
            }
            fetch_resp = requests.get(PUBMED_EFETCH, params=fetch_params, timeout=30)
            fetch_resp.raise_for_status()

            root = ET.fromstring(fetch_resp.text)
            for article in root.findall(".//PubmedArticle"):
                title_el = article.find(".//ArticleTitle")
                title = title_el.text if title_el is not None and title_el.text else "No title"

                # 提取摘要
                abstract_parts = article.findall(".//AbstractText")
                abstract = " ".join(
                    (part.text or "") for part in abstract_parts if part.text
                )[:500]

                # 提取日期
                date_el = article.find(".//PubDate")
                date_str = ""
                if date_el is not None:
                    year = date_el.findtext("Year", "")
                    month = date_el.findtext("Month", "01")
                    day = date_el.findtext("Day", "01")
                    month_map = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                                 "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
                    month = month_map.get(month, month.zfill(2))
                    date_str = f"{year}-{month}-{day.zfill(2)}"

                # 提取 PMID
                pmid_el = article.find(".//PMID")
                pmid = pmid_el.text if pmid_el is not None else ""

                # 提取 DOI
                doi_el = article.find(".//ArticleId[@IdType='doi']")
                doi = doi_el.text if doi_el is not None else ""

                items.append({
                    "title": title,
                    "source": "PubMed",
                    "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                    "date": date_str,
                    "raw_summary": abstract or "No abstract available",
                    "doi": doi,
                })

            time.sleep(0.4)  # 遵守频率限制

    except Exception as e:
        print(f"[PubMed] Error: {e}")

    print(f"[PubMed] 共获取 {len(items)} 条")
    return items


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PubMed 抓取")
    parser.add_argument("--query", required=True)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--retmax", type=int, default=50)
    args = parser.parse_args()
    import json
    results = fetch_pubmed(args.query, args.days, args.retmax)
    print(json.dumps(results, ensure_ascii=False, indent=2))
