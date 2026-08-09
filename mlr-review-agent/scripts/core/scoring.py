"""评分 + apply-verification 重算（跨领域共享）。"""
import hashlib
import sys


# verdict → 显示标签（review_material / apply_verification_to_report 共用）
_VERDICT_LABELS = {
    "pass": "✅ 通过",
    "conditional_pass": "⚠️ 有条件通过",
    "fail": "❌ 不通过",
}


def calculate_compliance_score(findings: list) -> int:
    """Calculate compliance score (0-100, higher is better).

    P1-4 FIX: Staggered penalty + diversity penalty for better differentiation.
    Previously every critical was -25, causing 6/8 cases to get 0/100.
    Now uses diminishing penalties so different violation profiles get different scores.

    Maximum penalty per severity tier is capped to prevent all-heavy cases
    from being indistinguishable.
    """
    score = 100
    # Count by severity
    critical_count = sum(1 for f in findings if f.get("severity") == "critical")
    major_count = sum(1 for f in findings if f.get("severity") == "major")
    minor_count = sum(1 for f in findings if f.get("severity") == "minor")
    info_count = sum(1 for f in findings if f.get("severity") == "info")

    # P1-4: Diminishing penalties + caps for better differentiation
    # critical: first -18, each subsequent -8, capped at -50
    crit_penalty = 0
    for i in range(critical_count):
        if i == 0:
            crit_penalty += 18
        elif i < 5:
            crit_penalty += 8
        else:
            crit_penalty += 3  # beyond 5th, diminishing further
    crit_penalty = min(crit_penalty, 50)

    # major: first -7, each subsequent -3, capped at -35
    major_penalty = 0
    for i in range(major_count):
        if i == 0:
            major_penalty += 7
        elif i < 6:
            major_penalty += 3
        else:
            major_penalty += 2  # beyond 6th, minimal
    major_penalty = min(major_penalty, 35)

    # minor: -2 each, capped at -10
    minor_penalty = min(minor_count * 2, 10)

    # info: -1 each, capped at -5
    info_penalty = min(info_count * 1, 5)

    # Diversity penalty: materials with diverse violation types are worse
    violation_types = set()
    for f in findings:
        violation_types.add(f.get("category", "unknown"))
    diversity_penalty = 0
    if len(violation_types) >= 5:
        diversity_penalty = 5

    score -= (crit_penalty + major_penalty + minor_penalty + info_penalty + diversity_penalty)
    return max(score, 0)


def determine_verdict(score: int, critical_count: int) -> str:
    """Determine overall verdict based on score and critical findings."""
    if critical_count > 0 or score < 50:
        return "fail"
    elif score < 80:
        return "conditional_pass"
    else:
        return "pass"


def _score_block(findings: list) -> dict:
    """计算 score/critical_count/verdict/verdict_label 四件套。"""
    score = calculate_compliance_score(findings)
    critical_count = sum(1 for f in findings if f.get("severity") == "critical")
    verdict = determine_verdict(score, critical_count)
    return {
        "compliance_score": score,
        "critical_count": critical_count,
        "verdict": verdict,
        "verdict_label": _VERDICT_LABELS.get(verdict, verdict),
    }


def _claim_id(finding: dict) -> str:
    """生成稳定 claim_id: description+evidence 的 md5 前 8 位。"""
    raw = ((finding.get("description") or "") + "|" + (finding.get("evidence") or "")).encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:8]


def _index_findings_by_claim_id(findings: list) -> dict:
    """按 claim_id 索引 findings（fallback _claim_id；同 id 首条胜出）。"""
    by_id = {}
    for f in findings:
        cid = f.get("claim_id") or _claim_id(f)
        if cid not in by_id:
            by_id[cid] = f
    return by_id


def apply_verification_findings(findings: list, verification_results: list) -> list:
    """据核验结果原地调整 findings 的 severity 并附加 verification 元数据。

    判定规则:
      - high + refuted   → severity = critical
      - high + verified  → severity = info
      - 其余(medium/low/unverifiable) → severity 不变
    未匹配 claim_id 的核验结果: 写 stderr warning 并忽略。
    """
    by_id = _index_findings_by_claim_id(findings)
    for vr in verification_results:
        cid = vr.get("claim_id")
        f = by_id.get(cid)
        if f is None:
            sys.stderr.write(f"[warn] 核验结果 claim_id={cid} 未匹配任何 finding，已忽略\n")
            continue
        verdict = vr.get("verdict")
        confidence = vr.get("confidence")
        f["verification"] = {
            "verdict": verdict,
            "confidence": confidence,
            "severity_before": f.get("severity"),
            "evidence_summary": vr.get("evidence_summary", ""),
            "sources": vr.get("sources", []),
            "judge_consensus": vr.get("judge_consensus", ""),
        }
        if confidence == "high":
            if verdict == "refuted":
                f["severity"] = "critical"
            elif verdict == "verified":
                f["severity"] = "info"
        # medium/low/unverifiable → severity 不变
    return findings


def _build_verification_evidence(findings: list, verification_results: list) -> list:
    """构建 verification_evidence 章节（仅含成功匹配 claim_id 的核验）。"""
    by_id = _index_findings_by_claim_id(findings)
    evidence = []
    for vr in verification_results:
        f = by_id.get(vr.get("claim_id"))
        if f is None:
            continue
        v = f.get("verification", {})
        evidence.append({
            "claim_id": vr.get("claim_id"),
            "claim_text": f.get("description", ""),
            "verdict": vr.get("verdict"),
            "confidence": vr.get("confidence"),
            "severity_before": v.get("severity_before"),
            "severity_after": f.get("severity"),
            "evidence_summary": vr.get("evidence_summary", ""),
            "sources": vr.get("sources", []),
            "judge_consensus": vr.get("judge_consensus", ""),
        })
    return evidence


def apply_verification_to_report(report: dict, verification_results: list) -> dict:
    """据核验结果重算 report 的 score/verdict 并附 verification_evidence。原地修改并返回。"""
    findings = report.get("findings", [])
    apply_verification_findings(findings, verification_results)
    report["findings"] = findings
    report.update(_score_block(findings))
    report["verification_evidence"] = _build_verification_evidence(findings, verification_results)
    report["verification_applied"] = True
    return report
