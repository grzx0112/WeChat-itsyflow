#!/usr/bin/env python3
"""MLR Review Agent — CLI 入口（domain 路由）。逻辑在 core/ + domains/。"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from domains import get_domain_checker as _get_domain_checker, DOMAIN_REGISTRY
from core import engine
from core.scoring import apply_verification_to_report, calculate_compliance_score
from core.report import format_report


def get_domain_checker(name):
    """转发（兼容现有测试 review.get_domain_checker）。"""
    return _get_domain_checker(name)


def _load_json_arg(s):
    if os.path.isfile(s):
        with open(s, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    return json.loads(s)


def main():
    # Windows 控制台默认 GBK，含 emoji 的 JSON/print 会 UnicodeEncodeError；强制 utf-8
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="MLR Review Agent — 医药市场合规审计（平台化）")
    parser.add_argument("--action", required=True,
                        choices=["review", "extract-claims", "fair-balance", "score",
                                 "check-prohibited", "check-disclosures",
                                 "apply-verification", "verify-claims"],
                        help="Action to perform")
    parser.add_argument("--input", required=True, help="Input text or file path")
    parser.add_argument("--format", default="json", choices=["json", "markdown"])
    parser.add_argument("--jurisdiction", default="auto", choices=["auto", "fda", "nmpa"])
    parser.add_argument("--domain", default="advertising",
                        choices=list(DOMAIN_REGISTRY.keys()),
                        help="合规领域（默认 advertising）")
    parser.add_argument("--verify", action="store_true",
                        help="review 时额外输出 claims_needs_verification")
    parser.add_argument("--verification", default=None,
                        help="核验结果 JSON（apply-verification 必填）")
    args = parser.parse_args()

    checker = get_domain_checker(args.domain)

    if os.path.isfile(args.input):
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        text = args.input

    if args.action == "review":
        result = engine.review_material(text, domain=args.domain,
                                        jurisdiction=args.jurisdiction,
                                        include_needs_verification=args.verify)
    elif args.action == "extract-claims":
        result = {"claims": checker.extract_claims(text, args.jurisdiction)}
    elif args.action == "fair-balance":
        result = (checker.analyze_balance(text) if hasattr(checker, "analyze_balance")
                  else {"error": "该领域不支持 fair-balance"})
    elif args.action == "score":
        findings = checker.check(text, args.jurisdiction)
        result = {"score": calculate_compliance_score(findings)}
    elif args.action == "check-prohibited":
        result = {"findings": checker.check(text, args.jurisdiction)}
    elif args.action == "check-disclosures":
        result = {"findings": checker.check(text, args.jurisdiction)}
    elif args.action == "apply-verification":
        if not args.verification:
            sys.exit("错误: --action apply-verification 需要 --verification 参数")
        report = _load_json_arg(args.input)
        verification = _load_json_arg(args.verification)
        result = apply_verification_to_report(report, verification)
    elif args.action == "verify-claims":
        from verify.pipeline import verify_claims
        report = _load_json_arg(args.input)
        claims = report.get("claims_needs_verification", [])
        result = verify_claims(claims, args.jurisdiction)
    else:
        sys.exit(f"未知 action: {args.action}")

    if args.format == "markdown" and args.action in ("review", "apply-verification"):
        print(format_report(result))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
