# verify/retrieval.py
"""证据检索（urllib 标准库，跨领域共享）。PubMed + Crossref 主源；CT.gov 环境性 403 降级。"""
import urllib.request
import urllib.parse
import json
import ssl

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_HEADERS = {"User-Agent": "mlr-review-agent/1.0"}
_TIMEOUT = 15


def _get_json(url, params=None):
    """GET 请求并解析 JSON。失败抛异常（由调用方捕获降级）。"""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def search_pubmed(query, max_results=8):
    """返回 [{title, abstract, year, pmid, doi, source_db:'pubmed'}]。失败返回 []。"""
    try:
        es = _get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                       {"db": "pubmed", "term": query, "retmax": max_results,
                        "retmode": "json", "sort": "relevance"})
        ids = es["esearchresult"]["idlist"]
        if not ids:
            return []
        ef = _get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                       {"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        out = []
        for pmid in ids:
            a = ef["result"].get(pmid, {})
            out.append({
                "title": a.get("title", ""),
                "abstract": "",
                "year": (a.get("pubdate", "") or "")[:4],
                "pmid": pmid, "doi": "", "source_db": "pubmed",
            })
        return out
    except Exception:
        return []


def search_crossref(query, max_results=8):
    """返回 [{title, abstract, year, doi, source_db:'crossref'}]。失败返回 []。"""
    try:
        d = _get_json("https://api.crossref.org/works",
                      {"query": query, "rows": max_results,
                       "select": "title,abstract,published,DOI"})
        out = []
        for it in d.get("message", {}).get("items", []):
            title = (it.get("title") or [""])[0]
            dp = (it.get("published", {}).get("date-parts") or [[None]])
            year = str(dp[0][0]) if dp and dp[0] and dp[0][0] else ""
            out.append({
                "title": title, "abstract": it.get("abstract", ""),
                "year": year, "doi": it.get("DOI", ""), "source_db": "crossref",
            })
        return out
    except Exception:
        return []


def search_clinical_trials(condition, intervention):
    """CT.gov v2——本环境实测 403，降级返回 []。保留接口供未来/其他环境。"""
    return []


def search(query):
    """聚合检索（PubMed + Crossref）。单源失败不阻断。"""
    return search_pubmed(query) + search_crossref(query)
