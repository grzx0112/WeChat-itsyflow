"""报告格式化（跨领域共享）。"""


def format_report(result: dict) -> str:
    """Format review result as readable Markdown report.

    regulation 字段兼容 str（旧）和 dict（新）。
    """
    lines = []
    lines.append("# MLR 合规审核报告")
    lines.append("")
    lines.append(f"**材料类型**: {result.get('material_type', 'unknown')}")
    lines.append(f"**产品名**: {result.get('product_name', '未识别')}")
    lines.append(f"**字数**: {result.get('word_count', 0)}")
    lines.append(f"**声明数**: {result.get('claims_found', 0)}")
    lines.append("")
    lines.append(f"## 总体判定: {result.get('verdict_label', '?')}")
    lines.append(f"**合规评分**: {result.get('compliance_score', 0)}/100")
    lines.append(f"**关键问题**: {result.get('critical_count', 0)} 个 Critical")
    lines.append("")

    balance = result.get("fair_balance", {})
    if balance:
        lines.append("## 公平平衡分析")
        lines.append(f"- 获益信号: {balance.get('benefit_mentions', 0)}")
        lines.append(f"- 风险信号: {balance.get('risk_mentions', 0)}")
        lines.append(f"- 比值: {balance.get('benefit_risk_ratio', 0)}")
        lines.append(f"- 评估: {balance.get('assessment', 'unknown')}")
        lines.append("")

    findings = result.get("findings", [])
    if findings:
        lines.append("## 合规发现")
        for i, f in enumerate(findings, 1):
            severity = f.get("severity", "info")
            severity_emoji = {"critical": "🔴", "major": "🟡", "minor": "🟢", "info": "ℹ️"}.get(severity, "❓")
            lines.append(f"### {i}. {severity_emoji} [{severity.upper()}] {f.get('description', '')}")
            lines.append(f"- **类别**: {f.get('category', '')}")
            lines.append(f"- **证据**: {f.get('evidence', '')}")
            lines.append(f"- **建议**: {f.get('recommendation', '')}")
            reg = f.get("regulation", "")
            if isinstance(reg, dict):
                lines.append(f"- **法规**: {reg.get('clause', '')}（{reg.get('url', '')}）")
            else:
                lines.append(f"- **法规**: {reg}")
            lines.append("")
    else:
        lines.append("## 合规发现: 无问题 ✅")
        lines.append("")

    verification = result.get("verification_evidence")
    if verification:
        lines.append("## 声明核验（autoresearch）")
        v_icon = {"verified": "✅", "refuted": "🔴", "unverifiable": "ℹ️"}
        for v in verification:
            icon = v_icon.get(v.get("verdict"), "❓")
            verdict_s = (v.get("verdict") or "?").upper()
            conf_s = (v.get("confidence") or "?").upper()
            lines.append(f"### {icon} [{verdict_s}/{conf_s}] {v.get('claim_text','')}")
            lines.append(f"- **严重度调整**: {v.get('severity_before','?')} → {v.get('severity_after','?')}")
            if v.get("evidence_summary"):
                lines.append(f"- **证据摘要**: {v['evidence_summary']}")
            if v.get("sources"):
                lines.append(f"- **来源**: {', '.join(v['sources'])}")
            if v.get("judge_consensus"):
                lines.append(f"- **法官共识**: {v['judge_consensus']}")
            lines.append("")

    claims = result.get("claims", [])
    if claims:
        lines.append("## 提取的声明")
        for c in claims:
            lines.append(f"- [{c['claim_type']}/{c['strength']}] \"{c['text']}\"")
        lines.append("")

    lines.append("---")
    lines.append("*本报告由 MLR Review Agent 自动生成，仅作 in silico 合规风险评估参考，不构成法律建议。*")

    return "\n".join(lines)
