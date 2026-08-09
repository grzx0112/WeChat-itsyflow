"""学术赞助 / congress 合规规则包（学术会议、医学教育、独立教育活动资助材料）。

继承 AdvertisingChecker 复用通用广告规则（prohibited/restricted/required_disclosure/
fair_balance/prescription_off_label），并叠加 3 个赞助特有检查：
  1. sponsorship_promotion_mixing — 赞助活动夹带产品推广（PhRMA Code §13 Independent
                                    Activities：资助不得成为诱导或奖励处方的手段）
  2. sponsorship_undisclosed      — 声称"独立"但未披露资助方（PhRMA Code §13 透明度
                                    要求：独立教育活动的资助方须公开披露）
  3. sponsorship_entertainment    — 娱乐/旅游赞助（PhRMA Code §3 Prohibition on
                                    Entertainment and Recreation：禁止为 HCP 提供娱乐）

赞助材料面向医学专业人士、非大众媒介，故过滤掉 advertising 继承来的
china_prescription_mass_media 检查（该检查仅针对大众媒介处方药促销）。

复用现有法规语料（不新收集）：
  - PhRMA Code on Interactions with HCPs（references/regulations/hcp/us_phrma_code.md）
    —— §3（禁止娱乐）+ §13（独立性与决策）。§13 是学术/教育资助最贴近的规范根条款：
    "Companies may not provide financial support to underwrite independent medical education
    programs in a manner that constitutes inducement or reward for prescribing"。
"""
import os
import re

from domains.advertising import AdvertisingChecker, _detect_jurisdiction
from domains.hcp import _load_hcp_excerpt

# ============================================================
# 赞助法规溯源（复用现有 PhRMA Code 语料，不新收集）
# ============================================================
_PHRMA_URL = ("https://www.phrma.org/codes-and-guidelines/"
              "code-on-interactions-with-health-care-professionals")
_PHRMA_FILE = "references/regulations/hcp/us_phrma_code.md"

# 赞助特有 category → 法规条款溯源（excerpt_key 锚定 PhRMA Code markdown 的 heading）
# - sponsorship_promotion_mixing / sponsorship_undisclosed → PhRMA Code §13
#   （Section 13 Independence and Decision Making —— 资助不得诱导/奖励处方，独立活动须透明）
# - sponsorship_entertainment → PhRMA Code §3
#   （Section 3 Prohibition on Entertainment and Recreation —— 禁止任何娱乐/休闲）
SPONSOR_CLAUSE_MAPPING = {
    "sponsorship_promotion_mixing": {
        "clause": "PhRMA Code §13（Independent Activities — 资助不得诱导/奖励处方）",
        "source": f"{_PHRMA_FILE}#Section 13",
        "url": _PHRMA_URL, "excerpt_key": "Section 13",
        "file": "us_phrma_code.md"},
    "sponsorship_undisclosed": {
        "clause": "PhRMA Code §13（独立教育活动的资助方透明披露）",
        "source": f"{_PHRMA_FILE}#Section 13",
        "url": _PHRMA_URL, "excerpt_key": "Section 13",
        "file": "us_phrma_code.md"},
    "sponsorship_entertainment": {
        "clause": "PhRMA Code §3（Prohibition on Entertainment and Recreation）",
        "source": f"{_PHRMA_FILE}#Section 3",
        "url": _PHRMA_URL, "excerpt_key": "Section 3",
        "file": "us_phrma_code.md"},
}


def _source_sponsor_regulation(category, current_reg_str):
    """把赞助特有 finding 的 str regulation 升级为可溯源 dict {clause, source, url, excerpt}。

    所有赞助检查均溯源到 PhRMA Code（hcp 目录的 us_phrma_code.md），复用
    hcp._load_hcp_excerpt 读取原文片段。
    """
    m = SPONSOR_CLAUSE_MAPPING.get(category)
    if not m:
        return current_reg_str
    excerpt = _load_hcp_excerpt(m["file"], m["excerpt_key"])
    return {"clause": m["clause"], "source": m["source"],
            "url": m["url"], "excerpt": excerpt}


# ============================================================
# 赞助特有检查的触发短语
# ============================================================

# 赞助/资助语境（出现其一即视为赞助材料语境）
_SPONSOR_CONTEXT = [
    "赞助", "资助", "sponsor", "funding", "support",
    "symposium", "congress", "会议", "研讨会", "医学教育",
]

# 产品推广语言（在赞助语境中夹带即违规 —— PhRMA Code §13）
_PROMOTION_IN_SPONSOR = [
    "首选", "我们的产品", "推荐", "our product", "recommend",
    "唯一选择", "最佳选择", "clinical首选",
]

# 娱乐/旅游赞助（PhRMA Code §3 一律禁止）
_ENTERTAINMENT_PHRASES = [
    "entertainment", "resort", "vacation", "luxury trip",
    "娱乐", "旅游", "度假", "度假村", "休闲",
]

# 声称"独立"但未披露资助方 —— PhRMA Code §13 透明度要求
_UNDISCLOSED_INDEPENDENT_HINT = ["独立", "independent"]
_DISCLOSURE_HINT = [
    "funded by", "资助方", "supported by", "disclosure",
    "披露", "sponsored by", "赞助方",
]


# ============================================================
# 赞助特有检查函数
# ============================================================

def check_sponsorship_promotion_mixing(text, jurisdiction):
    """赞助活动夹带产品推广（PhRMA Code §13 Independent Activities）。

    PhRMA Code §13 明确：公司可资助独立医学教育活动，但资助不得成为诱导或奖励处方的
   手段。一旦在赞助/symposium 语境中出现产品推广语言（首选/推荐/我们的产品），
    即违反独立性原则。对每个命中短语生成一条 finding（去重），便于人工逐项核实。
    """
    findings = []
    text_l = text.lower()
    has_sponsor = any(p.lower() in text_l for p in _SPONSOR_CONTEXT)
    if not has_sponsor:
        return findings
    seen = set()
    for phrase in _PROMOTION_IN_SPONSOR:
        if phrase.lower() in text_l and phrase not in seen:
            seen.add(phrase)
            findings.append({
                "category": "sponsorship_promotion_mixing", "severity": "major",
                "description": f"赞助活动夹带产品推广: \"{phrase}\"",
                "evidence": phrase,
                "recommendation": (f"学术/赞助活动应独立，删除 \"{phrase}\" —— "
                                   "PhRMA Code §13 禁止借资助诱导或奖励处方"),
                "regulation": "PhRMA Code §13 Independent Activities",
                "jurisdiction": jurisdiction.upper(),
            })
    return findings


def check_sponsorship_undisclosed(text, jurisdiction):
    """声称独立但未披露资助方（PhRMA Code §13 透明度要求）。

    资助独立医学教育活动时，须公开披露资助方以确保独立性透明。
    声称"independent/独立"但未出现 funded by / 资助方 / 披露 等披露语，触发违规。
    """
    findings = []
    text_l = text.lower()
    has_independent_claim = any(p.lower() in text_l
                                for p in _UNDISCLOSED_INDEPENDENT_HINT)
    has_disclosure = any(p.lower() in text_l for p in _DISCLOSURE_HINT)
    if has_independent_claim and not has_disclosure:
        findings.append({
            "category": "sponsorship_undisclosed", "severity": "major",
            "description": "声称独立但未披露资助方",
            "evidence": "independent claim without funding disclosure",
            "recommendation": "披露资助方/支持方（funded by / 资助方），确保独立性透明",
            "regulation": "PhRMA Code §13 透明度要求",
            "jurisdiction": jurisdiction.upper(),
        })
    return findings


def check_sponsorship_entertainment(text, jurisdiction):
    """娱乐/旅游赞助（PhRMA Code §3 Prohibition on Entertainment and Recreation）。

    PhRMA Code §3 一律禁止为 HCP 提供娱乐、度假或休闲活动。即使在学术会议/symposium
    语境下，任何娱乐/旅游元素的赞助都属严重违规。severity=critical。
    """
    findings = []
    text_l = text.lower()
    seen = set()
    for phrase in _ENTERTAINMENT_PHRASES:
        if phrase.lower() in text_l and phrase not in seen:
            seen.add(phrase)
            findings.append({
                "category": "sponsorship_entertainment", "severity": "critical",
                "description": f"娱乐/旅游赞助: \"{phrase}\"",
                "evidence": phrase,
                "recommendation": (f"PhRMA Code §3 一律禁止娱乐 —— 删除 \"{phrase}\""),
                "regulation": "PhRMA Code §3 Prohibition on Entertainment",
                "jurisdiction": jurisdiction.upper(),
            })
    return findings


# ============================================================
# DomainChecker 实现
# ============================================================

class SponsorshipChecker(AdvertisingChecker):
    """学术赞助 / congress 材料合规检查。

    继承 AdvertisingChecker 复用通用规则（prohibited/restricted/required_disclosure/
    fair_balance/prescription_off_label），然后：
      1. 过滤 china_prescription_mass_media（赞助材料面向专业人士，非大众媒介）
      2. 叠加 3 个赞助特有检查（promotion_mixing / undisclosed / entertainment）
      3. 对赞助特有 finding 做法规溯源（str regulation → 可溯源 dict）
    """
    name = "sponsorship"
    # 复用 advertising 的 needs_verification_categories；
    # 赞助特有检查均为短语硬匹配，无需人工验证分流。
    needs_verification_categories = AdvertisingChecker.needs_verification_categories

    def check(self, content, jurisdiction):
        if jurisdiction == "auto":
            jurisdiction = _detect_jurisdiction(content)
        # 1. 继承 advertising 全部规则（含末尾 _source_regulation 溯源）
        findings = super().check(content, jurisdiction)
        # 2. 过滤大众媒介检查（赞助材料面向专业人士，不适用《广告法》第十六条第一款大众媒介限制）
        findings = [f for f in findings
                    if f.get("category") != "china_prescription_mass_media"]
        # 3. 叠加 3 个赞助特有检查
        sponsor_findings = (
            check_sponsorship_promotion_mixing(content, jurisdiction)
            + check_sponsorship_undisclosed(content, jurisdiction)
            + check_sponsorship_entertainment(content, jurisdiction)
        )
        # 4. 赞助特有 finding 法规溯源（str → 可溯源 dict）
        for f in sponsor_findings:
            if isinstance(f.get("regulation"), str):
                f["regulation"] = _source_sponsor_regulation(
                    f.get("category", ""), f["regulation"])
        findings += sponsor_findings
        return findings
