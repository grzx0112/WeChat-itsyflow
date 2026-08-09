"""核验 pipeline：对每条待核验声明检索+评分 → verification.json schema。跨领域共享。"""
from verify import retrieval, score_evidence

_VMAP = {"support": "verified", "refute": "refuted", "insufficient": "unverifiable"}


def verify_claims(claims_needs_verification, jurisdiction="auto"):
    """claims_needs_verification: [{claim_id, claim_text, verification_query, ...}]
    返回 [{claim_id, verdict, confidence, evidence_summary, sources}]"""
    results = []
    for c in claims_needs_verification:
        ev = retrieval.search(c.get("verification_query", ""))
        scored = score_evidence.score(ev, c.get("claim_text", ""))
        results.append({
            "claim_id": c.get("claim_id"),
            "verdict": _VMAP.get(scored["verdict"], "unverifiable"),
            "confidence": scored["confidence"],
            "evidence_summary": scored["summary"],
            "sources": scored["sources"],
        })
    return results
