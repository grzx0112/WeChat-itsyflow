"""规则评分（无 LLM）：基于检索结果的文献数 / 方向 / 相关性 → verdict + confidence。"""
import re

_NEG_KEYWORDS = ["no benefit", "not effective", "refute", "contradict",
                 "no evidence", "fail to", "无效", "不一致", "未能"]


def _relevant(evidence_list, claim):
    """简单相关性过滤：claim 关键词命中 title/abstract。"""
    words = [w for w in re.findall(r"[A-Za-z一-鿿]{2,}", (claim or "").lower()) if len(w) >= 2]
    if not words:
        return list(evidence_list)
    out = []
    for ev in evidence_list:
        text = (ev.get("title", "") + " " + ev.get("abstract", "")).lower()
        if any(w in text for w in words):
            out.append(ev)
    return out


def score(evidence_list, claim):
    """返回 {verdict, confidence, summary, sources}。
    verdict: support | refute | insufficient
    confidence: high | medium | low"""
    relevant = _relevant(evidence_list, claim)
    n = len(relevant)
    sources = [f"{e.get('source_db','?')}:{e.get('pmid') or e.get('doi') or '?'}"
               for e in relevant[:5]]
    if n < 2:
        return {"verdict": "insufficient", "confidence": "low",
                "summary": f"仅检索到 {n} 篇相关文献，证据不足",
                "sources": sources}
    neg = sum(1 for e in relevant
              if any(k in (e.get("title", "") + e.get("abstract", "")).lower() for k in _NEG_KEYWORDS))
    if neg >= 2:
        return {"verdict": "refute", "confidence": "medium",
                "summary": f"{n} 篇相关，其中 {neg} 篇呈负向/反驳",
                "sources": sources}
    confidence = "high" if n >= 4 else "medium"
    return {"verdict": "support", "confidence": confidence,
            "summary": f"{n} 篇相关文献支持该声明",
            "sources": sources}
