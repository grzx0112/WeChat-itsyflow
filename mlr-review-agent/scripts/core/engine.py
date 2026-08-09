"""跨领域 review pipeline（domain-aware）。"""
import re
from domains import get_domain_checker
from core.scoring import _score_block, _claim_id


def collect_needs_verification(findings, categories):
    """筛出需核验的 findings（用领域自声明的 categories 白名单）。
    回写 claim_id 到 finding（供 apply-verification 对齐）。"""
    result = []
    for f in findings:
        if f.get("category") in categories:
            cid = _claim_id(f)
            f["claim_id"] = cid
            result.append({
                "claim_id": cid,
                "claim_text": f.get("description", ""),
                "category": f.get("category", ""),
                "current_severity": f.get("severity", ""),
                "context": f.get("evidence", ""),
                "verification_query": _build_verification_query(f),
            })
    return result


def _build_verification_query(finding):
    cat = finding.get("category", "")
    desc = finding.get("description") or ""
    m = re.search(r'"([^"]+)"', desc)
    claim_text = m.group(1) if m else desc
    if cat == "restricted_claim":
        return f'supporting evidence for comparative claim "{claim_text}" (pivotal trial / head-to-head)'
    if cat == "prescription_off_label":
        return f'approved indication scope for "{claim_text}" (FDA labeling / NMPA 说明书)'
    if cat == "china_comparison_claim":
        return f'事实核查: "{claim_text}" 是否属实 (首个/首创/独家/唯一 first-in-class timeline)'
    if cat == "china_endorsement_claim":
        return f'事实核查: "{claim_text}" 机构/人士背书是否真实存在'
    return claim_text


def review_material(content, domain="advertising", jurisdiction="auto",
                    include_needs_verification=False):
    checker = get_domain_checker(domain)
    if not content or len(content.strip()) < 10:
        return {"error": "材料内容过少（< 10 字），无法进行有效审核"}
    if jurisdiction == "auto":
        from domains.advertising import _detect_jurisdiction
        jurisdiction = _detect_jurisdiction(content)

    claims = checker.extract_claims(content, jurisdiction)
    findings = checker.check(content, jurisdiction)
    balance = checker.analyze_balance(content) if hasattr(checker, "analyze_balance") else {}
    product_name = ""
    material_type = "unknown"
    try:
        from domains.advertising import _extract_product_name, _detect_material_type
        product_name = _extract_product_name(content)
        material_type = _detect_material_type(content)
    except ImportError:
        pass

    result = {
        "domain": domain,
        "jurisdiction": jurisdiction.upper(),
        "material_type": material_type,
        "product_name": product_name,
        "word_count": len(content.split()),
        "claims_found": len(claims),
        "claims": claims,
        "findings_count": len(findings),
        "findings": findings,
        "fair_balance": balance,
    }
    result.update(_score_block(findings))

    if include_needs_verification:
        result["claims_needs_verification"] = collect_needs_verification(
            findings, checker.needs_verification_categories)

    return result
