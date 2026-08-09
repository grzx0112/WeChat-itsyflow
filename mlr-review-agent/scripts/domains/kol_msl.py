"""KOL/MSL 医学事务材料合规规则包（关键意见领袖 / 医学科学联络官沟通材料）。

继承 AdvertisingChecker 复用通用广告规则（prohibited/restricted/required_disclosure/
fair_balance/prescription_off_label），并叠加 3 个 KOL/MSL 特有检查：
  1. kol_speaker_fee           — KOL 讲者费/酬金暗示（PhRMA Code §6 Consultants：
                                  公平市场价值 / 书面合同 / 必要服务 / honorarium 规范）
  2. kol_scientific_inaccuracy — 亚组/探索性数据支撑强结论（21 CFR §202.1(e)(4)：
                                  广告推荐须与 labeling 一致，未充分支持的强结论属误导）
  3. kol_unlabeled_inference   — 亚组/探索性表述未标注局限性（21 CFR §202.1(e)(4)：
                                  易被误读为 labeling 支持的独立结论）

KOL/MSL 材料面向医学专业人士、非大众媒介，故过滤掉 advertising 继承来的
china_prescription_mass_media 检查（该检查仅针对大众媒介处方药促销）。

复用现有法规语料（不新收集）：
  - PhRMA Code on Interactions with HCPs（references/regulations/hcp/us_phrma_code.md）
    —— speaker programs 在 PhRMA Code 索引表标"否"未独立收录；§6 Consultants 第 100 行
    明确提及 honorarium 与 fair market value，是讲者费/酬金最贴近的规范根条款。
  - 21 CFR §202.1(e)(4)（references/regulations/advertising/fda_21cfr202.md 第 18 行 heading）
    —— 广告推荐/暗示的适应症必须与 FDA 批准/许可的 labeling 一致。
"""
import os
import re

from domains.advertising import AdvertisingChecker, _detect_jurisdiction, _load_excerpt
from domains.hcp import _load_hcp_excerpt

# ============================================================
# KOL/MSL 法规溯源（复用现有语料，不新收集）
# ============================================================
_PHRMA_URL = ("https://www.phrma.org/codes-and-guidelines/"
              "code-on-interactions-with-health-care-professionals")
_PHRMA_FILE = "references/regulations/hcp/us_phrma_code.md"
_FDA202_URL = "https://www.ecfr.gov/current/title-21/part-202"
_FDA202_FILE = "references/regulations/advertising/fda_21cfr202.md"

# KOL 特有 category → 法规条款溯源（excerpt_key 锚定现有 markdown 的 heading）
# - kol_speaker_fee → PhRMA Code §6 Consultants（hcp 目录；speaker programs 在索引表
#   标"否"未独立收录，§6 是其最贴近的规范根条款 —— honorarium + fair market value）
# - kol_scientific_inaccuracy / kol_unlabeled_inference → 21 CFR §202.1(e)(4)
#   （advertising 目录；广告推荐须与 labeling 一致，亚组/探索性强结论属未充分支持的暗示）
KOL_CLAUSE_MAPPING = {
    "kol_speaker_fee": {
        "clause": "PhRMA Code §6（Consultants — 公平市场价值 / honorarium）",
        "source": f"{_PHRMA_FILE}#Section 6",
        "url": _PHRMA_URL, "excerpt_key": "Section 6",
        "file": "us_phrma_code.md"},
    "kol_scientific_inaccuracy": {
        "clause": "21 CFR §202.1(e)(4) — Labeling/Literature Referencing",
        "source": f"{_FDA202_FILE}#§202.1(e)(4)",
        "url": _FDA202_URL, "excerpt_key": "202.1(e)(4)"},
    "kol_unlabeled_inference": {
        "clause": "21 CFR §202.1(e)(4) — Labeling/Literature Referencing",
        "source": f"{_FDA202_FILE}#§202.1(e)(4)",
        "url": _FDA202_URL, "excerpt_key": "202.1(e)(4)"},
}


def _source_kol_regulation(category, jurisdiction, current_reg_str):
    """把 KOL 特有 finding 的 str regulation 升级为可溯源 dict {clause, source, url, excerpt}。

    讲者费溯源读 hcp 目录的 us_phrma_code.md（复用 hcp._load_hcp_excerpt）；
    科学准确性/非独立推论溯源读 advertising 目录的 fda_21cfr202.md（复用 advertising._load_excerpt）。
    """
    m = KOL_CLAUSE_MAPPING.get(category)
    if not m:
        return current_reg_str
    if category == "kol_speaker_fee":
        excerpt = _load_hcp_excerpt(m["file"], m["excerpt_key"])
    else:
        excerpt = _load_excerpt("fda_21cfr202.md", m["excerpt_key"])
    return {"clause": m["clause"], "source": m["source"],
            "url": m["url"], "excerpt": excerpt}


# ============================================================
# KOL/MSL 特有检查的触发短语
# ============================================================

# 讲者费/酬金暗示（PhRMA Code §6）—— 中英文
_SPEAKER_FEE_PHRASES = [
    "speaker fee", "speaker fees", "speaker honorarium",
    "honorarium", "honoraria",
    "讲者费", "演讲费", "演讲酬金", "讲课费",
    "顾问费", "咨询费",
    "consulting fee", "consulting fees",
    "faculty payment",
]

# 亚组/探索性表述（KOL 材料中常见的"基于亚组/post-hoc 得出强结论"过度声明模式）
_SUBGROUP_OVERCLAIM_PHRASES = [
    "based on subgroup", "subgroup analysis", "post-hoc analysis",
    "post hoc analysis", "exploratory analysis", "exploratory endpoint",
    "亚组分析", "亚组结果显示", "事后分析", "探索性分析", "探索性终点",
]

# 强结论词（与亚组/探索性表述组合 → 科学不准确/过度声明）
_STRONG_CLAIM_PHRASES = [
    "improves survival", "improved survival", "increases survival",
    "prolongs survival", "extends survival",
    "cures", "cure rate",
    "effective", "significantly effective",
    "治愈", "根治", "显著有效", "提高生存率", "延长生存",
]

# 局限性标注（出现则视为已合规标注，不再触发 kol_unlabeled_inference）
_LIMITATION_CAVEATS = [
    "limitation", "limitations", "caveat", "caveats",
    "pre-specified", "hypothesis-generating", "hypothesis generating",
    "requires confirmation", "needs further study",
    "局限性", "需谨慎解读", "需进一步验证", "生成假设性", "探索性",
]


# ============================================================
# KOL/MSL 特有检查函数
# ============================================================

def check_kol_speaker_fee(text, jurisdiction):
    """KOL 讲者费/酬金暗示（PhRMA Code §6 Consultants）。

    PhRMA Code 要求咨询/讲者报酬须基于公平市场价值（fair market value）、合理且
    不与处方量挂钩；象征性咨询安排（token consulting）不得作为补偿 HCP 的借口。
    对每个命中短语生成一条 finding（去重），便于人工逐项核实合同/凭证。
    """
    findings = []
    text_l = text.lower()
    seen = set()
    for phrase in _SPEAKER_FEE_PHRASES:
        if phrase.lower() in text_l and phrase not in seen:
            seen.add(phrase)
            findings.append({
                "category": "kol_speaker_fee", "severity": "major",
                "description": f"KOL 讲者费/酬金暗示: \"{phrase}\"",
                "evidence": phrase,
                "recommendation": (f"核实 \"{phrase}\" 是否符合 PhRMA Code §6 —— "
                                   "须基于公平市场价值、有书面合同与正当必要需求，"
                                   "且不得与处方量挂钩"),
                "regulation": "PhRMA Code §6（Consultants）",
                "jurisdiction": jurisdiction.upper(),
            })
    return findings


def check_kol_scientific_inaccuracy(text, jurisdiction):
    """亚组/探索性数据支撑强结论（科学不准确 / 过度声明）。

    KOL 医学事务材料常以亚组分析 / post-hoc / 探索性结果暗示生存或治愈获益，
    但此类证据等级不足以支撑强结论。21 CFR §202.1(e)(4) 要求广告推荐须与
    labeling 一致 —— 未在标签充分支持的强结论属误导性暗示。
    """
    findings = []
    text_l = text.lower()
    has_subgroup = any(p in text_l for p in _SUBGROUP_OVERCLAIM_PHRASES)
    has_strong = any(p in text_l for p in _STRONG_CLAIM_PHRASES)
    if has_subgroup and has_strong:
        findings.append({
            "category": "kol_scientific_inaccuracy", "severity": "major",
            "description": "亚组/探索性数据支撑强结论（科学不准确/过度声明）",
            "evidence": "subgroup/exploratory + strong claim (survival/cure/effective)",
            "recommendation": ("亚组/post-hoc/探索性分析结果不得作为主要结论，"
                               "须降级表述并显式标注局限性（hypothesis-generating）"),
            "regulation": "21 CFR §202.1(e)(4)",
            "jurisdiction": jurisdiction.upper(),
        })
    return findings


def check_kol_unlabeled_inference(text, jurisdiction):
    """亚组/探索性表述未标注局限性（labeling 范围外的独立推论暗示）。

    在 KOL 材料中引用亚组/post-hoc/探索性表述时，若未显式标注 limitation/caveat，
    易被误读为 labeling 支持的独立结论。21 CFR §202.1(e)(4) 要求广告推荐须与
    批准 labeling 一致。
    """
    findings = []
    text_l = text.lower()
    if any(c in text_l for c in _LIMITATION_CAVEATS):
        return findings  # 已标注局限性，合规
    for phrase in _SUBGROUP_OVERCLAIM_PHRASES:
        if phrase in text_l:
            findings.append({
                "category": "kol_unlabeled_inference", "severity": "minor",
                "description": f"亚组/探索性表述未标注局限性: \"{phrase}\"",
                "evidence": phrase,
                "recommendation": ("显式标注局限性（如 hypothesis-generating / 需进一步验证），"
                                   "避免被误读为 labeling 支持的独立结论"),
                "regulation": "21 CFR §202.1(e)(4)",
                "jurisdiction": jurisdiction.upper(),
            })
            break  # 一条提醒即可，避免噪音
    return findings


# ============================================================
# DomainChecker 实现
# ============================================================

class KolMslChecker(AdvertisingChecker):
    """KOL/MSL 医学事务材料合规检查。

    继承 AdvertisingChecker 复用通用规则（prohibited/restricted/required_disclosure/
    fair_balance/prescription_off_label），然后：
      1. 过滤 china_prescription_mass_media（KOL/MSL 面向专业人士，非大众媒介）
      2. 叠加 3 个 KOL 特有检查（speaker_fee / scientific_inaccuracy / unlabeled_inference）
      3. 对 KOL 特有 finding 做法规溯源（str regulation → 可溯源 dict）
    """
    name = "kol_msl"
    # 亚组/探索性强结论可核验是否在 labeling 支持范围内 → 列入需人工验证类别
    needs_verification_categories = (AdvertisingChecker.needs_verification_categories
                                     | {"kol_scientific_inaccuracy"})

    def check(self, content, jurisdiction):
        if jurisdiction == "auto":
            jurisdiction = _detect_jurisdiction(content)
        # 1. 继承 advertising 全部规则（含末尾 _source_regulation 溯源）
        findings = super().check(content, jurisdiction)
        # 2. 过滤大众媒介检查（KOL/MSL 材料面向专业人士，不适用《广告法》第十六条第一款大众媒介限制）
        findings = [f for f in findings
                    if f.get("category") != "china_prescription_mass_media"]
        # 3. 叠加 3 个 KOL 特有检查
        kol_findings = (
            check_kol_speaker_fee(content, jurisdiction)
            + check_kol_scientific_inaccuracy(content, jurisdiction)
            + check_kol_unlabeled_inference(content, jurisdiction)
        )
        # 4. KOL 特有 finding 法规溯源（str → 可溯源 dict）
        for f in kol_findings:
            if isinstance(f.get("regulation"), str):
                f["regulation"] = _source_kol_regulation(
                    f.get("category", ""), f.get("jurisdiction", ""), f["regulation"])
        findings += kol_findings
        return findings
