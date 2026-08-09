# skills/mlr-review-agent/scripts/test_apply_verification.py
import sys
import os
import json
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review
# 兼容别名：review.py 已瘦身为 CLI，旧符号迁到 core/ + domains/，挂回 review 命名空间让旧测试零改动
from core import engine, scoring
from core import report as _report_mod
from domains.advertising import AdvertisingChecker

review._claim_id = scoring._claim_id
review._index_findings_by_claim_id = scoring._index_findings_by_claim_id
review.apply_verification_findings = scoring.apply_verification_findings
review._build_verification_evidence = scoring._build_verification_evidence
review.apply_verification_to_report = scoring.apply_verification_to_report
review._score_block = scoring._score_block
review.calculate_compliance_score = scoring.calculate_compliance_score
review.determine_verdict = scoring.determine_verdict
review._VERDICT_LABELS = scoring._VERDICT_LABELS
# engine.collect_needs_verification 需 (findings, categories)；旧测试只传 findings，
# 用 AdvertisingChecker.needs_verification_categories 注入（与旧 NEEDS_VERIFICATION_CATEGORIES 同集）
review.collect_needs_verification = lambda findings: engine.collect_needs_verification(
    findings, AdvertisingChecker.needs_verification_categories)
review.review_material = lambda *a, **k: engine.review_material(*a, **k)
review.format_report = _report_mod.format_report
review.get_domain_checker = lambda name: __import__('domains').get_domain_checker(name)


class TestCollectNeedsVerification(unittest.TestCase):
    def test_filters_to_verification_categories(self):
        findings = [
            {"category": "restricted_claim", "severity": "major",
             "description": '限制性声明: "首个"', "evidence": "X 是首个 SGLT2"},
            {"category": "prohibited_claim", "severity": "critical",
             "description": '绝对化用语: "治愈"', "evidence": "治愈"},
            {"category": "china_comparison_claim", "severity": "critical",
             "description": '与其他药品比较: "独家"', "evidence": "独家产品"},
            {"category": "required_disclosure", "severity": "major",
             "description": "缺失必须披露信息", "evidence": "(not found)"},
        ]
        result = review.collect_needs_verification(findings)
        self.assertEqual(len(result), 2)
        cats = {r["category"] for r in result}
        self.assertEqual(cats, {"restricted_claim", "china_comparison_claim"})

    def test_claim_id_stable_and_writes_back_to_finding(self):
        findings = [
            {"category": "restricted_claim", "severity": "major",
             "description": '限制性声明: "首选"', "evidence": "首选药物"},
        ]
        result = review.collect_needs_verification(findings)
        cid = result[0]["claim_id"]
        self.assertEqual(len(cid), 8)
        self.assertEqual(findings[0]["claim_id"], cid)
        self.assertEqual(review._claim_id(findings[0]), cid)

    def test_verification_query_contains_claim_text(self):
        findings = [
            {"category": "restricted_claim", "severity": "major",
             "description": '限制性声明: "first-in-class"', "evidence": "first-in-class"},
        ]
        result = review.collect_needs_verification(findings)
        self.assertIn("first-in-class", result[0]["verification_query"])

    def test_verification_query_off_label_branch(self):
        findings = [
            {"category": "prescription_off_label", "severity": "major",
             "description": '超说明书用药: "治疗阿尔茨海默病"', "evidence": "用于阿尔茨海默病"},
        ]
        result = review.collect_needs_verification(findings)
        self.assertEqual(len(result), 1)
        self.assertIn("approved indication", result[0]["verification_query"])

    def test_verification_query_china_comparison_branch(self):
        findings = [
            {"category": "china_comparison_claim", "severity": "critical",
             "description": '与其他药品比较: "国内首个"', "evidence": "国内首个"},
        ]
        result = review.collect_needs_verification(findings)
        self.assertEqual(len(result), 1)
        self.assertIn("事实核查", result[0]["verification_query"])

    def test_verification_query_china_endorsement_branch(self):
        findings = [
            {"category": "china_endorsement_claim", "severity": "critical",
             "description": '机构背书: "中华医学会推荐"', "evidence": "中华医学会推荐"},
        ]
        result = review.collect_needs_verification(findings)
        self.assertEqual(len(result), 1)
        self.assertIn("背书", result[0]["verification_query"])


class TestReviewMaterialVerifyFlag(unittest.TestCase):
    def test_default_excludes_needs_verification(self):
        text = "X 是首个 SGLT2 抑制剂，疗效显著，优于传统药物。" * 3
        result = review.review_material(text)
        self.assertNotIn("claims_needs_verification", result)

    def test_verify_flag_includes_needs_verification(self):
        text = "X 是首个 SGLT2 抑制剂，优于传统药物，疗效显著降低 HbA1c。" * 3
        result = review.review_material(text, include_needs_verification=True)
        self.assertIn("claims_needs_verification", result)
        cats = {c["category"] for c in result["claims_needs_verification"]}
        self.assertTrue(cats & {"restricted_claim", "china_comparison_claim"})
        verified_findings = [f for f in result["findings"] if f.get("claim_id")]
        self.assertGreater(len(verified_findings), 0)


class TestApplyVerificationFindings(unittest.TestCase):
    def _finding(self, category="restricted_claim", severity="major",
                 desc="限制性声明: \"首个\"", evidence="首个"):
        return {"category": category, "severity": severity,
                "description": desc, "evidence": evidence}

    def test_high_refuted_upgrades_to_critical(self):
        f = self._finding()
        cid = review._claim_id(f)
        f["claim_id"] = cid
        findings = [f]
        review.apply_verification_findings(findings, [{
            "claim_id": cid, "verdict": "refuted", "confidence": "high",
            "evidence_summary": "并非首个", "sources": ["FDA"], "judge_consensus": "3/3",
        }])
        self.assertEqual(f["severity"], "critical")
        self.assertEqual(f["verification"]["severity_before"], "major")
        # 附带 A (I-1): verification 元数据 5 字段正确写入
        self.assertEqual(f["verification"]["evidence_summary"], "并非首个")
        self.assertEqual(f["verification"]["sources"], ["FDA"])
        self.assertEqual(f["verification"]["judge_consensus"], "3/3")
        self.assertEqual(f["verification"]["verdict"], "refuted")
        self.assertEqual(f["verification"]["confidence"], "high")

    def test_high_verified_downgrades_to_info(self):
        f = self._finding()
        cid = review._claim_id(f)
        f["claim_id"] = cid
        review.apply_verification_findings([f], [{
            "claim_id": cid, "verdict": "verified", "confidence": "high",
            "evidence_summary": "确为首个", "sources": ["FDA NDA"],
        }])
        self.assertEqual(f["severity"], "info")

    def test_medium_refuted_keeps_severity(self):
        f = self._finding()
        cid = review._claim_id(f)
        f["claim_id"] = cid
        review.apply_verification_findings([f], [{
            "claim_id": cid, "verdict": "refuted", "confidence": "medium",
        }])
        self.assertEqual(f["severity"], "major")

    def test_unverifiable_keeps_severity(self):
        f = self._finding()
        cid = review._claim_id(f)
        f["claim_id"] = cid
        review.apply_verification_findings([f], [{
            "claim_id": cid, "verdict": "unverifiable", "confidence": "low",
        }])
        self.assertEqual(f["severity"], "major")

    def test_unknown_claim_id_warns_and_ignored(self):
        f = self._finding()
        cid = review._claim_id(f)
        f["claim_id"] = cid
        review.apply_verification_findings([f], [{
            "claim_id": "nonexistent", "verdict": "refuted", "confidence": "high",
        }])
        self.assertEqual(f["severity"], "major")  # 未被改

    def test_fallback_claim_id_when_not_written(self):
        # 附带 A (I-2): finding 不设 claim_id 键，靠 apply_verification_findings 内部 fallback 对齐
        f = self._finding()  # 不设 claim_id
        cid = review._claim_id(f)
        review.apply_verification_findings([f], [{
            "claim_id": cid, "verdict": "refuted", "confidence": "high",
        }])
        self.assertEqual(f["severity"], "critical")


class TestApplyVerificationToReport(unittest.TestCase):
    def test_recomputes_score_and_verdict_on_refuted(self):
        findings = [{"category": "restricted_claim", "severity": "major",
                     "description": '限制性声明: "首个"', "evidence": "首个"}]
        cid = review._claim_id(findings[0])
        findings[0]["claim_id"] = cid
        report = {
            "findings": findings,
            "compliance_score": 93,
            "critical_count": 0,
            "verdict": "conditional_pass",
            "verdict_label": "⚠️ 有条件通过",
        }
        out = review.apply_verification_to_report(report, [{
            "claim_id": cid, "verdict": "refuted", "confidence": "high",
            "evidence_summary": "并非首个", "sources": ["FDA"],
        }])
        self.assertEqual(out["verdict"], "fail")
        self.assertEqual(out["critical_count"], 1)
        self.assertEqual(out["verdict_label"], "❌ 不通过")
        self.assertTrue(out["verification_applied"])
        self.assertEqual(len(out["verification_evidence"]), 1)
        ve = out["verification_evidence"][0]
        self.assertEqual(ve["severity_before"], "major")
        self.assertEqual(ve["severity_after"], "critical")

    def test_unmatched_claim_id_excluded_from_evidence(self):
        findings = [{"category": "restricted_claim", "severity": "major",
                     "description": '限制性声明: "首选"', "evidence": "首选"}]
        report = {"findings": findings, "compliance_score": 90,
                  "critical_count": 0, "verdict": "conditional_pass"}
        out = review.apply_verification_to_report(report, [{
            "claim_id": "ghost", "verdict": "refuted", "confidence": "high",
        }])
        self.assertEqual(out["verification_evidence"], [])

    def test_verified_downgrade_recomputes(self):
        # I-3: verified+high 降级 info 后重算 score 升高、critical_count=0、verdict=pass
        findings = [{"category": "restricted_claim", "severity": "major",
                     "description": '限制性声明: "首选"', "evidence": "首选"}]
        cid = review._claim_id(findings[0])
        findings[0]["claim_id"] = cid
        report = {"findings": findings, "compliance_score": 93,
                  "critical_count": 0, "verdict": "conditional_pass"}
        out = review.apply_verification_to_report(report, [{
            "claim_id": cid, "verdict": "verified", "confidence": "high",
            "evidence_summary": "确有头对头研究支持", "sources": ["NEJM"],
        }])
        self.assertEqual(out["findings"][0]["severity"], "info")
        self.assertEqual(out["critical_count"], 0)
        self.assertEqual(out["verdict"], "pass")  # major 清零 → score≥80 → pass
        self.assertEqual(out["verification_evidence"][0]["severity_after"], "info")


class TestFormatReportVerification(unittest.TestCase):
    def test_renders_verification_section(self):
        report = {
            "material_type": "PI", "product_name": "X", "word_count": 100,
            "claims_found": 1, "verdict_label": "❌ 不通过", "compliance_score": 40,
            "critical_count": 1, "fair_balance": {}, "findings": [],
            "claims": [],
            "verification_evidence": [{
                "claim_id": "abc12345",
                "claim_text": '限制性声明: "首个"',
                "verdict": "refuted", "confidence": "high",
                "severity_before": "major", "severity_after": "critical",
                "evidence_summary": "并非首个 SGLT2 抑制剂",
                "sources": ["FDA NDA 202293"],
                "judge_consensus": "3/3",
            }],
        }
        md = review.format_report(report)
        self.assertIn("## 声明核验（autoresearch）", md)
        self.assertIn("🔴", md)
        self.assertIn("REFUTED/HIGH", md)
        self.assertIn("major → critical", md)
        self.assertIn("并非首个 SGLT2 抑制剂", md)
        self.assertIn("FDA NDA 202293", md)


class TestApplyVerificationMarkdownCLI(unittest.TestCase):
    def test_apply_verification_markdown_renders_section(self):
        # 端到端 CLI 测试：--action apply-verification --format markdown 应走 format_report
        import subprocess, json, tempfile, os
        finding = {'category': 'restricted_claim', 'severity': 'major',
                   'description': '限制性声明: "首选"', 'evidence': '首选'}
        cid = review._claim_id(finding)
        finding['claim_id'] = cid
        report = {'findings': [finding], 'compliance_score': 90,
                  'critical_count': 0, 'verdict': 'conditional_pass'}
        d = tempfile.mkdtemp()
        rp = os.path.join(d, 'r.json')
        open(rp, 'w', encoding='utf-8').write(json.dumps(report, ensure_ascii=False))
        vp = os.path.join(d, 'v.json')
        open(vp, 'w', encoding='utf-8').write(json.dumps(
            [{'claim_id': cid, 'verdict': 'refuted', 'confidence': 'high',
              'evidence_summary': '非首个', 'sources': ['FDA']}], ensure_ascii=False))
        out = subprocess.run(
            ['python', 'skills/mlr-review-agent/scripts/review.py',
             '--action', 'apply-verification', '--input', rp,
             '--verification', vp, '--format', 'markdown'],
            capture_output=True, text=True, cwd='D:/we-skills/weskills', encoding='utf-8')
        self.assertIn('声明核验', out.stdout)
        self.assertIn('REFUTED/HIGH', out.stdout)


class TestDomainRegistry(unittest.TestCase):
    def test_unknown_domain_raises(self):
        with self.assertRaises(ValueError) as cm:
            review.get_domain_checker("nonexistent")
        self.assertIn("nonexistent", str(cm.exception))

    def test_advertising_registered(self):
        from domains import AdvertisingChecker, DOMAIN_REGISTRY
        checker = review.get_domain_checker("advertising")
        self.assertIsInstance(checker, AdvertisingChecker)
        self.assertEqual(checker.name, "advertising")
        self.assertIn("restricted_claim", checker.needs_verification_categories)


class TestAdvertisingCheckerMigration(unittest.TestCase):
    def test_checker_findings_equivalent_to_legacy(self):
        from domains.advertising import AdvertisingChecker
        text = "X 是首个 SGLT2 抑制剂，优于传统药物。疗效显著降低 HbA1c。安全性良好。" * 3
        checker = AdvertisingChecker()
        checker_findings = checker.check(text, "auto")
        legacy = review.review_material(text)
        legacy_findings = legacy["findings"]
        # AdvertisingChecker.check 与 review.review_material 的 findings 数量等价
        self.assertEqual(len(checker_findings), len(legacy_findings),
                         f"checker={len(checker_findings)} vs legacy={len(legacy_findings)}")
        # severity 分布一致
        def sev_dist(fs):
            from collections import Counter
            return Counter(f.get("severity") for f in fs)
        self.assertEqual(sev_dist(checker_findings), sev_dist(legacy_findings))

    def test_checker_extract_claims_works(self):
        from domains.advertising import AdvertisingChecker
        text = "X 显著降低 HbA1c，优于传统药物。" * 3
        claims = AdvertisingChecker().extract_claims(text, "auto")
        self.assertIsInstance(claims, list)


class TestDomainAwareEngine(unittest.TestCase):
    def test_engine_advertising_equivalent_to_legacy(self):
        from core import engine
        text = "X 是首个 SGLT2 抑制剂，优于传统药物。疗效显著降低 HbA1c。" * 3
        result = engine.review_material(text, domain="advertising")
        legacy = review.review_material(text)
        self.assertEqual(result["verdict"], legacy["verdict"])
        self.assertEqual(result["compliance_score"], legacy["compliance_score"])
        self.assertEqual(len(result["findings"]), len(legacy["findings"]))
        self.assertEqual(result["domain"], "advertising")

    def test_engine_needs_verification_uses_checker_categories(self):
        from core import engine
        text = "X 是首个 SGLT2 抑制剂，优于传统药物。" * 3
        result = engine.review_material(text, domain="advertising", include_needs_verification=True)
        self.assertIn("claims_needs_verification", result)
        # 声明的 category 应都在 advertising 的 needs_verification_categories 内
        from domains.advertising import AdvertisingChecker
        allowed = AdvertisingChecker.needs_verification_categories
        for c in result["claims_needs_verification"]:
            self.assertIn(c["category"], allowed)


class TestCLIDomainRouting(unittest.TestCase):
    def test_default_domain_is_advertising(self):
        import subprocess, json
        out = subprocess.run(
            ['python', 'skills/mlr-review-agent/scripts/review.py',
             '--action', 'review', '--input', 'X 治疗糖尿病，疗效显著。', '--format', 'json'],
            capture_output=True, text=True, cwd='D:/we-skills/weskills', encoding='utf-8')
        r = json.loads(out.stdout)
        self.assertEqual(r.get("domain", "advertising"), "advertising")

    def test_explicit_domain_advertising(self):
        import subprocess, json
        out = subprocess.run(
            ['python', 'skills/mlr-review-agent/scripts/review.py',
             '--action', 'review', '--domain', 'advertising',
             '--input', 'X 治疗糖尿病，安全有效。', '--format', 'json'],
            capture_output=True, text=True, cwd='D:/we-skills/weskills', encoding='utf-8')
        self.assertEqual(json.loads(out.stdout)["domain"], "advertising")

    def test_unknown_domain_exits_nonzero(self):
        import subprocess
        out = subprocess.run(
            ['python', 'skills/mlr-review-agent/scripts/review.py',
             '--action', 'review', '--domain', 'ghost',
             '--input', 'X', '--format', 'json'],
            capture_output=True, text=True, cwd='D:/we-skills/weskills', encoding='utf-8')
        self.assertNotEqual(out.returncode, 0)


class TestRetrieval(unittest.TestCase):
    def test_search_pubmed_parses(self):
        from unittest.mock import patch, MagicMock
        from verify import retrieval
        fake_esearch = {"esearchresult": {"idlist": ["111", "222"]}}
        fake_esummary = {"result": {"111": {"title": "Drug X efficacy", "pubdate": "2023-01-01"},
                                     "222": {"title": "Drug X safety", "pubdate": "2022-01-01"}}}
        with patch("urllib.request.urlopen") as mock_urlopen:
            cm = MagicMock()
            cm.__enter__.return_value.read.side_effect = [
                json.dumps(fake_esearch).encode(),
                json.dumps(fake_esummary).encode(),
            ]
            cm.__exit__.return_value = None
            mock_urlopen.return_value = cm
            out = retrieval.search_pubmed("drug X", max_results=2)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["pmid"], "111")
        self.assertEqual(out[0]["year"], "2023")
        self.assertEqual(out[0]["source_db"], "pubmed")

    def test_search_clinical_trials_returns_empty(self):
        from verify import retrieval
        self.assertEqual(retrieval.search_clinical_trials("cancer", "drugX"), [])

    def test_search_aggregates_pubmed_and_crossref(self):
        from unittest.mock import patch
        from verify import retrieval
        with patch("verify.retrieval.search_pubmed", return_value=[{"title": "a", "source_db": "pubmed"}]), \
             patch("verify.retrieval.search_crossref", return_value=[{"title": "b", "source_db": "crossref"}]):
            out = retrieval.search("drug X")
        self.assertEqual(len(out), 2)


class TestScoreEvidence(unittest.TestCase):
    def test_insufficient_when_few_papers(self):
        from verify import score_evidence
        out = score_evidence.score([{"title": "only one", "abstract": "", "source_db": "pubmed"}], "drug X")
        self.assertEqual(out["verdict"], "insufficient")
        self.assertEqual(out["confidence"], "low")

    def test_support_high_when_many_papers(self):
        from verify import score_evidence
        ev = [{"title": f"Drug X {i} efficacy", "abstract": "effective", "source_db": "pubmed"} for i in range(5)]
        out = score_evidence.score(ev, "drug X efficacy")
        self.assertEqual(out["verdict"], "support")
        self.assertEqual(out["confidence"], "high")

    def test_refute_when_negative_papers(self):
        from verify import score_evidence
        ev = [{"title": "Drug X no benefit", "abstract": "not effective", "source_db": "pubmed"},
              {"title": "Drug X contradict", "abstract": "refute claim", "source_db": "crossref"},
              {"title": "Drug X study", "abstract": "drug X", "source_db": "pubmed"}]
        out = score_evidence.score(ev, "drug X")
        self.assertEqual(out["verdict"], "refute")


class TestVerifyPipeline(unittest.TestCase):
    def test_verify_claims_maps_verdicts(self):
        from unittest.mock import patch
        from verify import pipeline
        claims = [{"claim_id":"c1","claim_text":"drug X 首个","verification_query":"drug X first"},
                  {"claim_id":"c2","claim_text":"drug Y 无效","verification_query":"drug Y"}]
        def fake_search(q):
            if "first" in q:
                return [{"title":f"drug X {i}","abstract":"efficacy","source_db":"pubmed"} for i in range(5)]
            return [{"title":"drug Y no benefit","abstract":"not effective","source_db":"pubmed"},
                    {"title":"drug Y contradict","abstract":"refute","source_db":"crossref"},
                    {"title":"drug Y","abstract":"drug Y","source_db":"pubmed"}]
        with patch("verify.pipeline.retrieval.search", side_effect=fake_search):
            out = pipeline.verify_claims(claims)
        self.assertEqual(out[0]["claim_id"], "c1")
        self.assertEqual(out[0]["verdict"], "verified")      # support→verified
        self.assertEqual(out[0]["confidence"], "high")
        self.assertEqual(out[1]["verdict"], "refuted")       # refute→refuted

    def test_verify_claims_empty_input(self):
        from verify import pipeline
        self.assertEqual(pipeline.verify_claims([]), [])


class TestVerifyClaimsCLI(unittest.TestCase):
    def test_verify_claims_in_action_choices(self):
        import subprocess
        out = subprocess.run(['python', 'skills/mlr-review-agent/scripts/review.py', '--help'],
                             capture_output=True, text=True, cwd='D:/we-skills/weskills', encoding='utf-8')
        self.assertIn('verify-claims', out.stdout)

    def test_verify_claims_pipeline_integration(self):
        # 直接测 pipeline 逻辑（CLI 分发调用它），mock retrieval 避免 live 联网
        from unittest.mock import patch
        from verify import pipeline
        claims = [{"claim_id":"c1","claim_text":"drug X efficacy","verification_query":"drug X"}]
        with patch("verify.pipeline.retrieval.search",
                   return_value=[{"title":f"drug X {i} efficacy","abstract":"effective","source_db":"pubmed"} for i in range(5)]):
            out = pipeline.verify_claims(claims)
        self.assertEqual(out[0]["verdict"], "verified")
        self.assertEqual(out[0]["confidence"], "high")

    def test_verify_claims_output_list_for_apply_verification(self):
        # 全链路衔接：verify-claims 输出 list 可被 apply-verification 读
        # 注：patch 不能跨子进程生效，故 verify_claims 在进程内跑（mock 生效），
        # 再把 list 写文件喂给 apply-verification 子进程，验证衔接。
        import subprocess, json, tempfile, os
        from unittest.mock import patch
        from verify import pipeline
        report = {'findings':[{'category':'restricted_claim','severity':'major',
                               'description':'d','evidence':'e','claim_id':'c1'}],
                  'compliance_score':90,'critical_count':0,'verdict':'conditional_pass',
                  'claims_needs_verification':[{'claim_id':'c1','claim_text':'x efficacy','verification_query':'x'}]}
        d = tempfile.mkdtemp()
        rp = os.path.join(d,'r.json')
        open(rp,'w',encoding='utf-8').write(json.dumps(report,ensure_ascii=False))
        # Phase 1: verify_claims in-process（mock retrieval 避免 live 联网）→ 直接输出 list
        with patch('verify.pipeline.retrieval.search',
                   return_value=[{'title':f'x {i} efficacy','abstract':'effective','source_db':'pubmed'} for i in range(5)]):
            verification = pipeline.verify_claims(report['claims_needs_verification'])
        self.assertIsInstance(verification, list)   # 直接 list，非 {"verification":[...]}
        self.assertEqual(verification[0]['claim_id'], 'c1')
        self.assertEqual(verification[0]['verdict'], 'verified')
        # Phase 2: list 写文件 → apply-verification (subprocess) 正常读，衔接成功
        vp = os.path.join(d, 'v.json')
        open(vp, 'w', encoding='utf-8').write(json.dumps(verification, ensure_ascii=False))
        out = subprocess.run(['python','skills/mlr-review-agent/scripts/review.py',
                              '--action','apply-verification','--input',rp,
                              '--verification',vp,'--format','json'],
                             capture_output=True, text=True, cwd='D:/we-skills/weskills', encoding='utf-8')
        result = json.loads(out.stdout)
        self.assertTrue(result.get('verification_applied'))


class TestRegulationSourcing(unittest.TestCase):
    """1c-Task2: finding.regulation 从 str 升级为可溯源 dict {clause, source, url, excerpt}。"""

    def test_finding_regulation_is_dict_with_excerpt(self):
        from domains.advertising import AdvertisingChecker
        # 触发广告法相关违规（绝对化用语"治愈"）；中文材料 → NMPA 语境
        text = "X 药品治愈糖尿病，疗效100%。" * 3
        findings = AdvertisingChecker().check(text, "nmpa")
        dict_findings = [f for f in findings if isinstance(f.get("regulation"), dict)]
        self.assertGreater(len(dict_findings), 0, "应有 regulation 为 dict 的 finding")
        f = dict_findings[0]
        self.assertIn("clause", f["regulation"])
        self.assertIn("source", f["regulation"])
        self.assertIn("url", f["regulation"])
        self.assertIn("excerpt", f["regulation"])
        self.assertTrue(len(f["regulation"]["excerpt"]) > 5, "excerpt 非空")

    def test_clause_mapping_covers_main_categories(self):
        from domains.advertising import CLAUSE_MAPPING
        for cat in ["china_absolute_terms", "china_efficacy_guarantee",
                    "china_comparison_claim", "china_endorsement_claim"]:
            self.assertIn(cat, CLAUSE_MAPPING, f"CLAUSE_MAPPING 缺 {cat}")


class TestClauseMappingExtended(unittest.TestCase):
    """1c2-Task3: CLAUSE_MAPPING 扩展审查标准 + 21 CFR 202 + jurisdiction 路由。"""

    def test_required_disclosure_sourced_to_standards(self):
        from domains.advertising import AdvertisingChecker
        text = "X 药品疗效显著，无副作用。" * 5  # NMPA，缺通用名/批准文号/不良反应标注
        findings = AdvertisingChecker().check(text, "nmpa")
        disc = [f for f in findings
                if f.get("category") in ("required_disclosure", "china_disclosure_generic_name_cn",
                                         "china_disclosure_ad_approval_number",
                                         "china_disclosure_adverse_reaction",
                                         "china_disclosure_contraindication")
                and isinstance(f.get("regulation"), dict)]
        self.assertGreater(len(disc), 0, "required_disclosure 类应溯源到审查标准")
        self.assertIn("审查发布标准", disc[0]["regulation"]["clause"])  # 药品广告审查发布标准

    def test_fair_balance_fda_sourced_to_21cfr202(self):
        from domains.advertising import _source_regulation
        # FDA fair_balance → 21 CFR §202.1(e)(5)
        reg = _source_regulation("fair_balance", "fda", "FDA 21 CFR 202.1(e)(5) — Fair Balance")
        self.assertIsInstance(reg, dict)
        self.assertIn("202.1(e)(5)", reg["clause"])
        self.assertTrue(len(reg["excerpt"]) > 5, "21 CFR excerpt 非空")

    def test_fair_balance_nmpa_sourced_to_ad_law(self):
        # fair_balance NMPA 语境仍溯源到广告法第十六条（保留原有路由）
        from domains.advertising import _source_regulation
        reg = _source_regulation("fair_balance", "NMPA", "《广告法》第十六条第二款")
        self.assertIsInstance(reg, dict)
        self.assertIn("第十六条", reg["clause"])
        self.assertTrue(len(reg["excerpt"]) > 5, "广告法 excerpt 非空")

    def test_prescription_off_label_fda_sourced(self):
        from domains.advertising import _source_regulation
        reg = _source_regulation("prescription_off_label", "fda", "FDA 21 CFR 202.1(e)(6)")
        self.assertIsInstance(reg, dict)
        self.assertIn("202.1(e)(6)", reg["clause"])

    def test_prescription_off_label_nmpa_keeps_str(self):
        # NMPA 语境 prescription_off_label 保留 str（药品管理法未收集）
        from domains.advertising import _source_regulation
        reg = _source_regulation("prescription_off_label", "NMPA", "《药品管理法》第九十条")
        self.assertIsInstance(reg, str)
        self.assertIn("药品管理法", reg)

    def test_clause_mapping_includes_standards_and_fda(self):
        from domains.advertising import CLAUSE_MAPPING
        for cat in ["required_disclosure",
                    "china_disclosure_generic_name_cn",
                    "china_disclosure_ad_approval_number",
                    "china_disclosure_adverse_reaction",
                    "china_disclosure_contraindication"]:
            self.assertIn(cat, CLAUSE_MAPPING, f"CLAUSE_MAPPING 缺 {cat}")
            self.assertIn("审查发布标准", CLAUSE_MAPPING[cat]["clause"])


class TestClauseMappingUpperLaw(unittest.TestCase):
    """1c3-Task2: CLAUSE_MAPPING 扩展上位法（药品管理法 + FD&C 502n）。"""

    def test_china_prescription_mass_media_sourced_to_drug_admin_law(self):
        from domains.advertising import _source_regulation
        reg = _source_regulation("china_prescription_mass_media", "nmpa",
                                 "《广告法》第十六条第一款")
        self.assertIsInstance(reg, dict)
        self.assertIn("药品管理法", reg["clause"])
        self.assertTrue(len(reg["excerpt"]) > 5, "药品管理法第九十条 excerpt 非空")

    def test_fda_required_disclosure_sourced_to_fdc_502n(self):
        from domains.advertising import _source_regulation
        reg = _source_regulation("required_disclosure", "fda",
                                 "FDA 21 CFR 202.1(b); FD&C Act 502(n)")
        self.assertIsInstance(reg, dict)
        self.assertIn("502", reg["clause"])
        self.assertTrue(len(reg["excerpt"]) > 5, "FD&C 502(n) excerpt 非空")


class TestHcpChecker(unittest.TestCase):
    """HCP-T2: HcpChecker 继承 AdvertisingChecker + 4 个 HCP 特有检查。"""

    def test_hcp_inherits_advertising_rules(self):
        from domains.hcp import HcpChecker
        from domains.advertising import AdvertisingChecker
        self.assertTrue(issubclass(HcpChecker, AdvertisingChecker))
        c = HcpChecker()
        self.assertEqual(c.name, "hcp")
        # 继承 advertising 的规则（prohibited 等）
        text = "X 治愈糖尿病，100%有效。" * 3
        findings = c.check(text, "nmpa")
        self.assertTrue(any(f["category"] == "prohibited_claim" or "china_" in f["category"] for f in findings))

    def test_hcp_filters_mass_media(self):
        from domains.hcp import HcpChecker
        # HCP 面向专业人士，不应触发 china_prescription_mass_media（大众媒介检查）
        text = "X 是处方药，治疗糖尿病，立即购买，货到付款。" * 2
        findings = HcpChecker().check(text, "nmpa")
        self.assertFalse(any(f["category"] == "china_prescription_mass_media" for f in findings),
                         "HCP 不应触发大众媒介检查")

    def test_hcp_rep_compliance_check(self):
        from domains.hcp import HcpChecker
        text = "我们的医药代表承诺疗效，并向医生赠送礼品。" * 2
        findings = HcpChecker().check(text, "nmpa")
        self.assertTrue(any(f["category"] == "hcp_rep_compliance" for f in findings))

    def test_hcp_phrma_interaction_check(self):
        from domains.hcp import HcpChecker
        text = "We offer free travel and luxurious dinners for physicians." * 2
        findings = HcpChecker().check(text, "fda")
        self.assertTrue(any(f["category"] == "hcp_pharma_interaction" for f in findings))

    def test_hcp_off_label_verbal_check(self):
        from domains.hcp import HcpChecker
        text = "Our drug may also be used for Alzheimer, real-world evidence suggests." * 2
        findings = HcpChecker().check(text, "fda")
        self.assertTrue(any(f["category"] == "hcp_off_label_verbal" for f in findings))

    def test_hcp_registered_in_domain_registry(self):
        from domains import DOMAIN_REGISTRY, get_domain_checker
        self.assertIn("hcp", DOMAIN_REGISTRY)
        self.assertEqual(get_domain_checker("hcp").name, "hcp")


class TestKolMslChecker(unittest.TestCase):
    """KOL-Task1: KolMslChecker 继承 AdvertisingChecker + 3 个 KOL 特有检查。"""

    def test_kol_inherits_advertising(self):
        from domains.kol_msl import KolMslChecker
        from domains.advertising import AdvertisingChecker
        self.assertTrue(issubclass(KolMslChecker, AdvertisingChecker))
        self.assertEqual(KolMslChecker().name, "kol_msl")

    def test_kol_filters_mass_media(self):
        from domains.kol_msl import KolMslChecker
        text = "X 是处方药，治疗糖尿病，立即购买，货到付款。" * 2
        self.assertFalse(any(f["category"] == "china_prescription_mass_media"
                             for f in KolMslChecker().check(text, "nmpa")))

    def test_kol_speaker_fee_check(self):
        from domains.kol_msl import KolMslChecker
        text = "We pay speaker fees and honorarium to KOL physicians." * 2
        findings = KolMslChecker().check(text, "fda")
        self.assertTrue(any(f["category"] == "kol_speaker_fee" for f in findings))

    def test_kol_scientific_inaccuracy_check(self):
        from domains.kol_msl import KolMslChecker
        text = "Our drug significantly improves survival based on subgroup." * 2
        findings = KolMslChecker().check(text, "fda")
        self.assertTrue(any(f["category"] == "kol_scientific_inaccuracy"
                            for f in findings))

    def test_kol_registered(self):
        from domains import DOMAIN_REGISTRY
        self.assertIn("kol_msl", DOMAIN_REGISTRY)


class TestSponsorshipChecker(unittest.TestCase):
    """阶段3-2: SponsorshipChecker 继承 AdvertisingChecker + 3 个赞助特有检查。"""

    def test_sponsorship_inherits_advertising(self):
        from domains.sponsorship import SponsorshipChecker
        from domains.advertising import AdvertisingChecker
        self.assertTrue(issubclass(SponsorshipChecker, AdvertisingChecker))
        self.assertEqual(SponsorshipChecker().name, "sponsorship")

    def test_sponsorship_filters_mass_media(self):
        from domains.sponsorship import SponsorshipChecker
        text = "X 是处方药，立即购买，货到付款。" * 2
        self.assertFalse(any(f["category"] == "china_prescription_mass_media"
                             for f in SponsorshipChecker().check(text, "nmpa")))

    def test_sponsorship_promotion_mixing(self):
        from domains.sponsorship import SponsorshipChecker
        text = "We sponsor the medical conference and recommend our product as 首选." * 2
        findings = SponsorshipChecker().check(text, "fda")
        self.assertTrue(any(f["category"] == "sponsorship_promotion_mixing" for f in findings))

    def test_sponsorship_entertainment(self):
        from domains.sponsorship import SponsorshipChecker
        text = "We provide resort vacation and entertainment for the symposium." * 2
        findings = SponsorshipChecker().check(text, "fda")
        self.assertTrue(any(f["category"] == "sponsorship_entertainment" for f in findings))

    def test_sponsorship_registered(self):
        from domains import DOMAIN_REGISTRY
        self.assertIn("sponsorship", DOMAIN_REGISTRY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
