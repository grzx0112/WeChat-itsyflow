"""HCP 沟通材料合规规则包（医药代表/销售与 HCP 互动材料）。

继承 AdvertisingChecker 复用通用广告规则（prohibited/restricted/required_disclosure/
fair_balance/prescription_off_label），并叠加 4 个 HCP 特有检查：
  1. hcp_rep_compliance    — 医药代表备案规范违规（NMPA《医药代表备案管理办法》）
  2. hcp_pharma_interaction — PhRMA Code 互动违规（娱乐/高额餐饮/礼品/现金）
  3. hcp_academic_promotion — 学术活动夹带产品推广（PhRMA Code 独立性 / 广告法）
  4. hcp_off_label_verbal   — 软超适应症口头话术（21 CFR §202.1(e)(6) / 药品管理法第九十条）

HCP 材料面向医学专业人士、非大众媒介，故过滤掉 advertising 继承来的
china_prescription_mass_media 检查（该检查仅针对大众媒介处方药促销）。
"""
import os
import re

from domains.advertising import AdvertisingChecker, _detect_jurisdiction, _load_excerpt

# ============================================================
# HCP 法规语料（T1 收录）
# ============================================================
# 《医药代表备案管理办法（试行）》（NMPA）—— hcp_rep_compliance 的溯源
_REP_MEASURES_URL = "https://www.nmpa.gov.cn/xxgk/ggtg/hgfh/20171215174201543.html"
_REP_MEASURES_FILE = "references/regulations/hcp/cn_pharma_rep_measures.md"
# PhRMA Code on Interactions with HCPs —— hcp_pharma_interaction / hcp_academic_promotion 的溯源
_PHRMA_URL = "https://www.phrma.org/codes-and-guidelines/code-on-interactions-with-health-care-professionals"
_PHRMA_FILE = "references/regulations/hcp/us_phrma_code.md"

# HCP 法规 markdown 位于 references/regulations/hcp/（与 advertising 同级）
_HCP_REG_DIR = os.path.join(os.path.dirname(__file__), "..", "..",
                            "references", "regulations", "hcp")


def _load_hcp_excerpt(filename, heading_key, max_chars=300):
    """从 HCP 法规 markdown 读指定 heading 下的原文片段（同 advertising._load_excerpt）。"""
    try:
        path = os.path.join(_HCP_REG_DIR, filename)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        pattern = rf"(#{{2,3}}\s*[^\n]*{re.escape(heading_key)}[^\n]*)\n(.*?)(?=\n#{{2,3}}|\Z)"
        m = re.search(pattern, text, re.DOTALL)
        if m:
            return m.group(2).strip()[:max_chars]
        return ""
    except Exception:
        return ""


# HCP 特有 category → 法规条款溯源（excerpt_key 锚定 HCP 法规 markdown 的 heading）
# - hcp_rep_compliance → 《医药代表备案管理办法》第十三条（医药代表禁止情形）
# - hcp_pharma_interaction → PhRMA Code Section 3（禁止娱乐）+ Section 10（禁止现金/礼品）
# - hcp_academic_promotion → PhRMA Code Section 13（独立性与决策）
# - hcp_off_label_verbal → FDA 21 CFR §202.1(e)(6)（复用 advertising 语料）；NMPA 药品管理法第九十条
HCP_CLAUSE_MAPPING = {
    "hcp_rep_compliance": {
        "clause": "《医药代表备案管理办法》第十三条",
        "source": f"{_REP_MEASURES_FILE}#第十三条",
        "url": _REP_MEASURES_URL, "excerpt_key": "第十三条",
        "file": "cn_pharma_rep_measures.md"},
    "hcp_pharma_interaction": {
        "clause": "PhRMA Code §3 / §10（禁止娱乐与现金礼品）",
        "source": f"{_PHRMA_FILE}#Section 3",
        "url": _PHRMA_URL, "excerpt_key": "Section 3",
        "file": "us_phrma_code.md"},
    "hcp_academic_promotion": {
        "clause": "PhRMA Code §13（独立性与决策）",
        "source": f"{_PHRMA_FILE}#Section 13",
        "url": _PHRMA_URL, "excerpt_key": "Section 13",
        "file": "us_phrma_code.md"},
}


def _source_hcp_regulation(category, jurisdiction, current_reg_str):
    """把 HCP 特有 finding 的 str regulation 升级为可溯源 dict。

    FDA 语境的 hcp_off_label_verbal → 21 CFR §202.1(e)(6)（复用 advertising 的 fda_21cfr202.md）。
    NMPA 语境的 hcp_off_label_verbal → 《药品管理法》第九十条（str 保留，药品管理法原文由
    advertising 模块管理，此处仅标法规名）。
    其余 HCP category 走 HCP_CLAUSE_MAPPING 通用路径。
    """
    # hcp_off_label_verbal 按 jurisdiction 分流
    if category == "hcp_off_label_verbal":
        jur = (jurisdiction or "").lower()
        if jur != "nmpa":
            return {"clause": "21 CFR §202.1(e)(6) — False/misleading/off-label",
                    "source": "references/regulations/advertising/fda_21cfr202.md#§202.1(e)(6)",
                    "url": "https://www.ecfr.gov/current/title-21/part-202",
                    "excerpt": _load_excerpt("fda_21cfr202.md", "202.1(e)(6)")}
        # NMPA 语境保留 str（药品管理法第九十条原文由 advertising 管理）
        return current_reg_str

    m = HCP_CLAUSE_MAPPING.get(category)
    if not m:
        return current_reg_str
    excerpt = _load_hcp_excerpt(m["file"], m["excerpt_key"])
    return {"clause": m["clause"], "source": m["source"],
            "url": m["url"], "excerpt": excerpt}


# ============================================================
# HCP 特有检查的触发短语
# ============================================================

# 医药代表违规行为（NMPA《医药代表备案管理办法》第十三条）
_REP_VIOLATION_PHRASES = [
    "承诺疗效", "保证疗效", "保证治疗效果",
    "赠送", "送礼", "回扣", "提成",
    "误导医生", "误导医师", "夸大疗效",
    "未备案", "非医药代表", "无备案号",
    "擅自组织", "未经备案",
]

# PhRMA Code 互动违规（费用/礼品/娱乐暗示）—— 中英文
_PHARMA_INTERACTION_PHRASES = [
    "free travel", "免费旅游", "免费旅行",
    "luxurious dinner", "豪华餐饮", "豪华晚宴", "奢华餐饮",
    "高额咨询费", "高额讲课费",
    "entertainment", "娱乐活动", "休闲娱乐",
    "gift card", "礼品卡",
    "cash gift", "现金赠送", "现金礼品", "cash payment",
    "resort", "度假村", "spa",
    "recreational event", "休闲活动",
]

# 学术/推广混淆（学术语境 + 产品推广）—— PhRMA Code §13 / 广告法
_ACADEMIC_PROMOTION_PHRASES = [
    "首选", "我们的产品", "临床首选", "本公司的产品",
    "唯一选择", "最佳选择",
]

# 软超适应症口头话术 —— 21 CFR §202.1(e)(6) / 药品管理法第九十条
_OFF_LABEL_VERBAL_PHRASES = [
    "还可用于", "也可治疗", "也可用于", "还可治疗",
    "临床上发现", "实践表明", "观察性研究显示",
    "real-world evidence suggests", "may also be used for",
    "may help with", "also effective for",
    "emerging use", "case reports indicate",
    "off-label use", "超说明书使用",
]


# ============================================================
# HCP 特有检查函数
# ============================================================

def check_hcp_rep_compliance(text, jurisdiction):
    """医药代表备案规范违规（NMPA《医药代表备案管理办法》第十三条）。

    仅 NMPA 语境触发；医药代表不得承诺疗效、赠送财物、误导医师、未备案从事学术推广等。
    """
    findings = []
    if jurisdiction != "nmpa":
        return findings
    for phrase in _REP_VIOLATION_PHRASES:
        if phrase in text:
            findings.append({
                "category": "hcp_rep_compliance", "severity": "major",
                "description": f"医药代表违规行为: \"{phrase}\"",
                "evidence": phrase,
                "recommendation": f"删除/修改 \"{phrase}\"——违反《医药代表备案管理办法》第十三条",
                "regulation": "《医药代表备案管理办法》第十三条",
                "jurisdiction": "NMPA",
            })
    return findings


def check_hcp_phrma_interaction(text, jurisdiction):
    """PhRMA Code 互动违规（娱乐/高额餐饮/礼品/现金）。

    仅 FDA 语境触发；PhRMA Code 禁止娱乐、要求适度/当地餐饮、禁止现金与礼品券。
    """
    findings = []
    if jurisdiction != "fda":
        return findings
    text_l = text.lower()
    for phrase in _PHARMA_INTERACTION_PHRASES:
        if phrase.lower() in text_l:
            findings.append({
                "category": "hcp_pharma_interaction", "severity": "critical",
                "description": f"与 HCP 互动违规暗示: \"{phrase}\"",
                "evidence": phrase,
                "recommendation": (f"删除 \"{phrase}\"——违反 PhRMA Code"
                                   "（禁止娱乐/适度餐饮/公平咨询/禁止现金礼品）"),
                "regulation": "PhRMA Code on Interactions with HCPs §3/§10",
                "jurisdiction": "FDA",
            })
    return findings


def check_hcp_academic_promotion(text, jurisdiction):
    """学术活动夹带产品推广（PhRMA Code §13 独立性 / 广告法）。

    仅在学术语境（学术会议/研究/symposium 等）中检测产品推广语言。
    """
    findings = []
    academic_context = any(k in text for k in [
        "学术会议", "研究", "学术", "academic", "research", "symposium",
        "研讨会", "年会", "学术报告"])
    if not academic_context:
        return findings
    for phrase in _ACADEMIC_PROMOTION_PHRASES:
        if phrase in text:
            findings.append({
                "category": "hcp_academic_promotion", "severity": "major",
                "description": f"学术活动夹带产品推广: \"{phrase}\"",
                "evidence": phrase,
                "recommendation": "学术活动应独立，删除产品推广语言（PhRMA Code §13）",
                "regulation": "PhRMA Code §13 / 《广告法》",
                "jurisdiction": jurisdiction.upper(),
            })
    return findings


def check_hcp_off_label_verbal(text, jurisdiction):
    """软超适应症口头话术（HCP 推广中常见的暗示性超适应症语言）。

    区别于 advertising 的 prescription_off_label（硬超适应症关键词），此处聚焦
    HCP 口头沟通中的软暗示话术（real-world evidence suggests / 临床上发现 等）。
    severity=critical：口头超适应症是 FDA OPDP 执法重点。
    """
    findings = []
    text_l = text.lower()
    for phrase in _OFF_LABEL_VERBAL_PHRASES:
        if phrase.lower() in text_l:
            reg = ("21 CFR §202.1(e)(6)" if jurisdiction != "nmpa"
                   else "《药品管理法》第九十条")
            findings.append({
                "category": "hcp_off_label_verbal", "severity": "critical",
                "description": f"疑似口头超适应症: \"{phrase}\"",
                "evidence": phrase,
                "recommendation": f"HCP 推广话术不得暗示超适应症——删除 \"{phrase}\"",
                "regulation": reg, "jurisdiction": jurisdiction.upper(),
            })
    return findings


# ============================================================
# DomainChecker 实现
# ============================================================

class HcpChecker(AdvertisingChecker):
    """HCP 沟通材料合规检查。

    继承 AdvertisingChecker 复用通用规则（prohibited/restricted/required_disclosure/
    fair_balance/prescription_off_label），然后：
      1. 过滤 china_prescription_mass_media（HCP 面向专业人士，非大众媒介）
      2. 叠加 4 个 HCP 特有检查
      3. 对 HCP 特有 finding 做法规溯源（str regulation → 可溯源 dict）
    """
    name = "hcp"
    # 继承 advertising 的 needs_verification_categories；
    # 加 hcp_off_label_verbal（口头超适应症声明可核验是否在批准适应症范围内）
    needs_verification_categories = (AdvertisingChecker.needs_verification_categories
                                     | {"hcp_off_label_verbal"})

    def check(self, content, jurisdiction):
        if jurisdiction == "auto":
            jurisdiction = _detect_jurisdiction(content)
        # 1. 继承 advertising 全部规则（含末尾 _source_regulation 溯源）
        findings = super().check(content, jurisdiction)
        # 2. 过滤大众媒介检查（HCP 材料面向专业人士，不适用《广告法》第十六条第一款大众媒介限制）
        findings = [f for f in findings
                    if f.get("category") != "china_prescription_mass_media"]
        # 3. 叠加 4 个 HCP 特有检查
        hcp_findings = (
            check_hcp_rep_compliance(content, jurisdiction)
            + check_hcp_phrma_interaction(content, jurisdiction)
            + check_hcp_academic_promotion(content, jurisdiction)
            + check_hcp_off_label_verbal(content, jurisdiction)
        )
        # 4. HCP 特有 finding 法规溯源（str → 可溯源 dict）
        for f in hcp_findings:
            if isinstance(f.get("regulation"), str):
                f["regulation"] = _source_hcp_regulation(
                    f.get("category", ""), f.get("jurisdiction", ""), f["regulation"])
        findings += hcp_findings
        return findings
