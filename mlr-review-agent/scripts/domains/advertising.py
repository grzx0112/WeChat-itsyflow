"""广告促销材料合规规则包（FDA 21 CFR 202 + NMPA 广告法）。

阶段 1a-Task5：从 review.py 原样迁移广告规则（常量 + 辅助函数 + check 函数），
实现完整的 AdvertisingChecker。函数体零变更，只是从 review.py 移到本模块。
review.py 自身的这些函数保留不动（Task 7 才删），AdvertisingChecker 独立可用。
"""
import os
import re
from domains import DomainChecker

# China-specific rules（与 review.py 同样的 import 兜底）
try:
    from china_rules import (
        CHINA_PROHIBITED, CHINA_REQUIRED_DISCLOSURES, CHINA_PRESCRIPTION_RESTRICTION,
        PRESCRIPTION_DRUG_RULES,
    )
except ImportError:
    import importlib.util, os
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "china_rules.py")
    _p = os.path.normpath(_p)
    if os.path.exists(_p):
        _spec = importlib.util.spec_from_file_location("china_rules", _p)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        CHINA_PROHIBITED = _mod.CHINA_PROHIBITED
        CHINA_REQUIRED_DISCLOSURES = _mod.CHINA_REQUIRED_DISCLOSURES
        CHINA_PRESCRIPTION_RESTRICTION = _mod.CHINA_PRESCRIPTION_RESTRICTION
        PRESCRIPTION_DRUG_RULES = getattr(_mod, 'PRESCRIPTION_DRUG_RULES', {})
    else:
        CHINA_PROHIBITED = {}
        CHINA_REQUIRED_DISCLOSURES = {}
        CHINA_PRESCRIPTION_RESTRICTION = {}
        PRESCRIPTION_DRUG_RULES = {}


# ============================================================
# 法规条款溯源（1c-Task2）
# ============================================================
# Task1 收录的广告法原文 markdown（references/regulations/advertising/cn_advertising_law.md）
# heading 结构：## 第九条 / ## 第十六条 / ### 第十六条第一款 / ### 第十六条第二款 /
# ### 第十六条第三款 / ## 第十七条 / ## 第二十八条
_AD_LAW_URL = "https://www.nmpa.gov.cn/xxgk/fgwj/flxzhfg/20230328161808137.html"
_AD_LAW_FILE = "references/regulations/advertising/cn_advertising_law.md"

# 1c2-Task1/2 收录的补充法规语料
# 药品广告审查发布标准（2007 版，司法部法规库）—— required_disclosure 类的溯源
_STANDARDS_URL = "https://www.moj.gov.cn/pub/sfbgw/flfggz/flfggzbmgz/200708/t20070815_144418.html"
_STANDARDS_FILE = "references/regulations/advertising/cn_drug_ad_standards.md"
# 21 CFR Part 202（eCFR）—— FDA fair_balance / prescription_off_label 的溯源
_FDA202_URL = "https://www.ecfr.gov/current/title-21/part-202"
_FDA202_FILE = "references/regulations/advertising/fda_21cfr202.md"

# 1c3-Task1 收录的上位法语料
# 《药品管理法》（2019 修订，NMPA 官网）—— china_prescription_mass_media 的上位法溯源。
# heading 结构：## 第八十九条（审查批准前置）/ ## 第九十条（内容要求及禁止情形）/
# ## 第九十一条（法律适用指引）。处方药大众媒介广告禁止由《广告法》第十六条第一款
# 规定，但第九十条是上位法对药品广告内容/禁止情形的总要求，作为溯源更准确。
_DRUG_ADMIN_URL = "https://www.nmpa.gov.cn/xxgk/fgwj/flxzhfg/20190827083801685.html"
_DRUG_ADMIN_FILE = "references/regulations/advertising/cn_drug_admin_law.md"
# FD&C Act §502(n)（21 U.S.C. §352(n)，Cornell LII）—— required_disclosure FDA 分流的溯源。
# heading 结构：## §502(n) / 21 U.S.C. §352(n) Prescriptions for advertisements ...。
_FDC_URL = "https://www.law.cornell.edu/uscode/text/21/352"
_FDC_FILE = "references/regulations/advertising/fdc_act_502n.md"

# 违规 category → 法规条款溯源。excerpt_key 匹配 cn_advertising_law.md 的 heading。
# china_* category 仅在 NMPA 语境触发（见 check_prohibited_claims 的 China 块），映射安全；
# prohibited_claim / restricted_claim 为通用类别（FDA/NMPA 都会触发），_source_regulation
# 内对这两个类别加 jurisdiction 守卫，仅在 NMPA 语境溯源到《广告法》，FDA 语境保留原 str。
CLAUSE_MAPPING = {
    "china_absolute_terms": {
        "clause": "《广告法》第九条",
        "source": f"{_AD_LAW_FILE}#第九条",
        "url": _AD_LAW_URL, "excerpt_key": "第九条"},
    "china_efficacy_guarantee": {
        "clause": "《广告法》第十六条第一款",
        "source": f"{_AD_LAW_FILE}#第十六条第一款",
        "url": _AD_LAW_URL, "excerpt_key": "第十六条第一款"},
    "china_cure_rate_claim": {
        "clause": "《广告法》第十六条第一款第二项",
        "source": f"{_AD_LAW_FILE}#第十六条第一款",
        "url": _AD_LAW_URL, "excerpt_key": "第十六条第一款"},
    "china_comparison_claim": {
        "clause": "《广告法》第十六条第一款第三项（比较性内容）",
        "source": f"{_AD_LAW_FILE}#第十六条第一款",
        "url": _AD_LAW_URL, "excerpt_key": "第十六条第一款"},
    "china_endorsement_claim": {
        "clause": "《广告法》第十六条第一款第四项（代言人/背书）",
        "source": f"{_AD_LAW_FILE}#第十六条第一款",
        "url": _AD_LAW_URL, "excerpt_key": "第十六条第一款"},
    "prohibited_claim": {
        "clause": "《广告法》第九条",
        "source": f"{_AD_LAW_FILE}#第九条",
        "url": _AD_LAW_URL, "excerpt_key": "第九条"},
    "restricted_claim": {
        "clause": "《广告法》第十六条第一款第三项（比较性内容）",
        "source": f"{_AD_LAW_FILE}#第十六条第一款",
        "url": _AD_LAW_URL, "excerpt_key": "第十六条第一款"},
}

# 1c2-Task3：required_disclosure 类 → 《药品广告审查发布标准》（2007 版原始条号）
# - 第七条：必须标明事项（通用名称/忠告语/广告批准文号/生产批准文号/OTC 标识）
# - 第六条：广告内容以批准的说明书为准（不良反应/禁忌间接覆盖）
# 注意：mapping 里 "file" 字段指定该条款来自哪份 markdown，_source_regulation 读取时
# 优先用 m["file"]，缺省回退到 cn_advertising_law.md（向后兼容现有 7 个 category）。
CLAUSE_MAPPING.update({
    "required_disclosure": {
        "clause": "《药品广告审查发布标准》第七条",
        "source": f"{_STANDARDS_FILE}#第七条",
        "url": _STANDARDS_URL, "excerpt_key": "第七条",
        "file": "cn_drug_ad_standards.md"},
    "china_disclosure_generic_name_cn": {
        "clause": "《药品广告审查发布标准》第七条（通用名称）",
        "source": f"{_STANDARDS_FILE}#第七条",
        "url": _STANDARDS_URL, "excerpt_key": "第七条",
        "file": "cn_drug_ad_standards.md"},
    "china_disclosure_ad_approval_number": {
        "clause": "《药品广告审查发布标准》第七条（广告批准文号）",
        "source": f"{_STANDARDS_FILE}#第七条",
        "url": _STANDARDS_URL, "excerpt_key": "第七条",
        "file": "cn_drug_ad_standards.md"},
    "china_disclosure_adverse_reaction": {
        "clause": "《药品广告审查发布标准》第六条（不良反应/说明书一致性）",
        "source": f"{_STANDARDS_FILE}#第六条",
        "url": _STANDARDS_URL, "excerpt_key": "第六条",
        "file": "cn_drug_ad_standards.md"},
    "china_disclosure_contraindication": {
        "clause": "《药品广告审查发布标准》第六条（禁忌/说明书一致性）",
        "source": f"{_STANDARDS_FILE}#第六条",
        "url": _STANDARDS_URL, "excerpt_key": "第六条",
        "file": "cn_drug_ad_standards.md"},
})

# 1c3-Task2：china_prescription_mass_media → 《药品管理法》第九十条（上位法）
# 该 category 仅在 NMPA 语境触发（check 内 hard-code jurisdiction="NMPA"），无需守卫。
# 第九十条是药品广告内容要求及禁止情形的总规范（《广告法》第十六条第一款为特别法）。
CLAUSE_MAPPING["china_prescription_mass_media"] = {
    "clause": "《药品管理法》第九十条",
    "source": f"{_DRUG_ADMIN_FILE}#第九十条",
    "url": _DRUG_ADMIN_URL, "excerpt_key": "第九十条",
    "file": "cn_drug_admin_law.md"}

# advertising.py 位于 skills/mlr-review-agent/scripts/domains/，两层 .. 到 skill 根
# (skills/mlr-review-agent/)，再进 references/regulations/advertising/
_REG_DIR = os.path.join(os.path.dirname(__file__), "..", "..",
                        "references", "regulations", "advertising")


def _load_excerpt(filename, heading_key, max_chars=300):
    """从法规 markdown 读指定 heading 下的原文片段。

    匹配 ## 或 ### 含 heading_key 的标题行，取其后到下一个 ##/### 之前的内容。
    """
    try:
        path = os.path.join(_REG_DIR, filename)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        # 匹配 2-3 个 # 开头、行内含 heading_key 的标题，捕获其后正文直到下一个标题
        pattern = rf"(#{{2,3}}\s*[^\n]*{re.escape(heading_key)}[^\n]*)\n(.*?)(?=\n#{{2,3}}|\Z)"
        m = re.search(pattern, text, re.DOTALL)
        if m:
            return m.group(2).strip()[:max_chars]
        return ""
    except Exception:
        return ""


def _source_regulation(category, jurisdiction, current_reg_str):
    """把 str regulation 升级为可溯源 dict {clause, source, url, excerpt}。

    无映射则保留原 str（向后兼容）。
    Jurisdiction 路由：
      - prohibited/restricted：NMPA 语境溯源到《广告法》，FDA 语境保留原 str
        （避免给 FDA 材料错误挂中国法规）。
      - required_disclosure：NMPA → 《药品广告审查发布标准》第七条（下方 CLAUSE_MAPPING
        通用路径）；FDA → FD&C Act §502(n)（上位法，单独分流）。
      - china_prescription_mass_media：仅 NMPA 语境触发，→ 《药品管理法》第九十条。
      - fair_balance：NMPA → 《广告法》第十六条；FDA → 21 CFR §202.1(e)(5)。
      - prescription_off_label：FDA → 21 CFR §202.1(e)(6)；NMPA 保留 str（药品管理法未收集）。
    jurisdiction 形态兼容大小写（findings 写入用 .upper()，直接调用测试用小写）。
    """
    jur = (jurisdiction or "").lower()

    # fair_balance：按 jurisdiction 分流到广告法或 21 CFR
    if category == "fair_balance":
        if jur == "nmpa":
            return {"clause": "《广告法》第十六条",
                    "source": f"{_AD_LAW_FILE}#第十六条",
                    "url": _AD_LAW_URL,
                    "excerpt": _load_excerpt("cn_advertising_law.md", "第十六条")}
        # FDA/其他 → 21 CFR §202.1(e)(5)
        return {"clause": "21 CFR §202.1(e)(5) — Fair Balance",
                "source": f"{_FDA202_FILE}#§202.1(e)(5)",
                "url": _FDA202_URL,
                "excerpt": _load_excerpt("fda_21cfr202.md", "202.1(e)(5)")}

    # prescription_off_label：FDA → 21 CFR §202.1(e)(6)；NMPA 保留原 str
    if category == "prescription_off_label":
        if jur == "nmpa":
            return current_reg_str
        return {"clause": "21 CFR §202.1(e)(6) — False/misleading/off-label",
                "source": f"{_FDA202_FILE}#§202.1(e)(6)",
                "url": _FDA202_URL,
                "excerpt": _load_excerpt("fda_21cfr202.md", "202.1(e)(6)")}

    # required_disclosure：NMPA → 审查标准第七条（下方 CLAUSE_MAPPING 通用路径）；
    # FDA → FD&C Act §502(n)（上位法，单独分流）。
    if category == "required_disclosure" and jur != "nmpa":
        return {"clause": "FD&C Act §502(n)",
                "source": f"{_FDC_FILE}#§502(n)",
                "url": _FDC_URL,
                "excerpt": _load_excerpt("fdc_act_502n.md", "§502(n)")}

    m = CLAUSE_MAPPING.get(category)
    if not m:
        return current_reg_str  # 无映射，保留原 str
    # 通用类别（FDA/NMPA 都会触发）：仅 NMPA 语境溯源到中国法规
    if category in ("prohibited_claim", "restricted_claim") and jur != "nmpa":
        return current_reg_str  # FDA 语境不动
    # mapping 可指定 file（新加的审查标准/药品管理法条目来自不同 markdown），
    # 缺省回退到 cn_advertising_law.md（向后兼容现有 7 个 category）
    filename = m.get("file", "cn_advertising_law.md")
    excerpt = _load_excerpt(filename, m["excerpt_key"])
    return {"clause": m["clause"], "source": m["source"],
            "url": m["url"], "excerpt": excerpt}


# ============================================================
# Constants — Compliance rules from public regulations
# ============================================================

# 绝对化用语 — 中英文（FDA OPDP + NMPA《药品广告审查发布标准》）
PROHIBITED_PHRASES = [
    # 绝对化疗效
    "cure", "cures", "cured", "治愈", "根治", "根除",
    "100% effective", "100% safe", "guaranteed",
    "miracle", "miraculous", "奇迹", "神药", "特效药",
    "no side effects", "zero side effects", "无副作用", "零副作用", "没有任何副作用",
    "completely safe", "完全安全", "绝对安全",
    "risk-free", "无风险", "万无一失",
    "safest", "最安全",
    "number one", "#1 choice", "unsurpassed", "unmatched",
    # 超适应症暗示
    "treats all", "works for everything", "包治百病", "有病治病无病强身",
    # 情绪操纵
    "breakthrough cure", "revolutionary cure",
    # NMPA 特有禁止
    "最新技术", "最先进", "国家级", "世界领先", "国际首创",
    "疗效最佳", "疗效确切", "药到病除", "一针见效", "一盒见效",
    "保险公司承保", "无效退款", "无效退钱",
    "官方推荐", "国家推荐", "行政部门推荐",
    "最新科学", "最新研究成果",
    "速效", "强效", "特效", "奇效", "显效",  # NMPA 禁止的疗效承诺
    "纯天然", "无毒副作用", "绿色安全",  # 误导性安全性声明
    "专治", "主治",  # 暗示治疗一切
    "买二送一", "健康保险", "社保报销",  # 诱导性/保险暗示
    "国家保密配方", "三天见效", "七天见效", "即时见效", "马上见效",
    "国家级新药", "国家中药保护品种",
]

# 限制性声明 — 中英文（需要文献/数据支持）
RESTRICTED_PHRASES = [
    # 英文
    "first", "only", "leading", "#1",
    "superior", "best", "strongest", "fastest",
    "more effective than", "better than", "safer than",
    "breakthrough", "revolutionary", "game-changer",
    "innovative", "novel",
    # 中文
    "首选", "唯一", "领先", "第一", "首创",
    "优于", "最强", "最快", "最佳", "最好", "最高",
    "突破性", "革命性", "创新性",
    "国内首个", "全球首个", "独家",
    "医保目录", "基药目录",  # 需要核实是否真在目录中
    "院士推荐", "专家推荐", "三甲医院",  # 名人/机构背书需核实
    "医学会", "分会推荐", "权威推荐",  # 医学学会/机构背书
    "康复患者", "真实反馈",  # 患者证言
    "临床治愈",  # 需要核实治愈率数据
]

# Required disclosures (必须披露信息)
REQUIRED_ELEMENTS = {
    "generic_name": {
        "patterns": [r'\b(?:generic name|nonproprietary name)\b',
                     r'通用名', r'非专利名', r'国际非专利名称', r'INN'],
        "description": "非专利名/通用名",
        "severity": "major",
    },
    "rx_symbol": {
        "patterns": [r'\bRx\b', r'℞', r'处方药'],
        "description": "处方药标识",
        "severity": "major",
    },
    "pi_reference": {
        "patterns": [r'(?:please see|see|refer to)(?:\s+the\s+|\s+)?(?:full|complete|prescribing)?(?:\s+)?(?:Prescribing Information)',
                     r'完整处方信息', r'请参阅完整说明书', r'参阅完整处方信息'],
        "description": "完整处方信息/说明书引用",
        "severity": "major",
    },
    "boxed_warning_ref": {
        "patterns": [r'boxed warning', r'black box warning', r'黑框警告'],
        "description": "黑框警告引用（如适用）",
        "severity": "info",
    },
    # NMPA 特有要求
    "ad_approval_number": {
        "patterns": [r'广告审查准予文号', r'广告批准文号', r'药广审\(', r'广告审查批准文号'],
        "description": "广告审查批准文号（中国 NMPA 必须）",
        "severity": "major",
    },
    "adverse_event_notice": {
        "patterns": [r'不良反应', r'adverse reaction', r'本品不良反应'],
        "description": "不良反应提示",
        "severity": "major",
    },
    "contraindication_notice": {
        "patterns": [r'禁忌', r'contraindication', r'禁忌症', r'本品禁忌'],
        "description": "禁忌提示",
        "severity": "major",
    },
}

# Benefit/risk keywords for Fair Balance analysis
BENEFIT_KEYWORDS = [
    # English
    "effective", "efficacy", "proven", "improvement", "reduction",
    "benefit", "response", "remission", "survival", "cure", "treat",
    "works", "work", "action", "targets", "blocks", "inhibits",
    "convenient", "reliable", "consistent", "simple", "simplest",
    "protect", "protection", "protects",
    # 中文
    "疗效", "有效", "改善", "降低", "减少", "获益", "缓解", "生存",
    "显著", "提升", "优于", "好转", "消退", "控制", "稳定",
    "保护", "修复", "增强", "提高", "恢复", "消除", "阻止",
    "方便", "可靠", "简单",  # 隐性获益语言
    "作用", "阻断", "靶向", "抑制",  # MOA 语言
    "告别", "摆脱",  # 获益暗示
]

RISK_KEYWORDS = [
    # English
    "adverse", "side effect", "risk", "warning", "caution", "contraindication",
    "precaution", "death", "serious", "fatal", "toxicity",
    "monitor", "monitoring", "laboratory",
    "pregnancy", "nursing", "lactation",
    "hepatic", "renal", "elderly", "geriatric", "pediatric",
    "dose adjustment", "dose reduction",
    "drug interaction", "drug-drug interaction",
    "bleeding", "hemorrhage", "infection",
    # 中文
    "不良反应", "副作用", "风险", "警告", "禁忌", "注意", "致死", "严重", "毒性",
    "慎用", "禁用", "孕妇", "哺乳期", "儿童", "肝肾功能", "过敏",
    "头晕", "恶心", "呕吐", "腹泻", "皮疹", "肝损伤", "肾损伤",
    "出血", "感染", "心脏毒性", "神经毒性",
    "监测", "肝功能", "肾功能", "老年", "剂量调整",
    "药物相互作用", "相互作用",
]


# ============================================================
# Helper functions
# ============================================================

def _has_chinese(chars):
    """Check if a string contains Chinese characters."""
    return bool(re.search(r'[\u4e00-\u9fff]', chars))


def _match_phrase(text: str, phrase: str) -> bool:
    """Match a phrase in text with appropriate boundary handling.

    For English-only phrases, use \\b word boundaries.
    For phrases containing Chinese characters, use direct substring match
    (since \\b doesn't work with CJK characters).
    """
    if _has_chinese(phrase):
        # Direct substring match for Chinese/mixed phrases
        return phrase.lower() in text.lower()
    else:
        # Word boundary match for English-only phrases
        pattern = r'\b' + re.escape(phrase) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))


def _is_china_phrase(phrase: str) -> bool:
    """Check if a phrase is China-specific (NMPA rules only).

    Returns True for phrases that are NMPA-specific and should NOT be
    checked against FDA materials. These are phrases that only appear
    in NMPA regulations.

    P1-1 FIX: International universal prohibited terms are explicitly
    excluded from this list. Terms like "治愈" or "无副作用" are also
    prohibited under FDA regulations and must be checked in all modes.
    """
    # International universal prohibited phrases — also banned by FDA
    # These must NEVER be in china_only, so FDA mode still catches them
    INTERNATIONAL_UNIVERSAL = {
        "治愈", "根治", "无副作用", "完全安全", "绝对安全",
        "100%有效", "特效", "速效", "奇效",
        "零副作用", "没有任何副作用", "最安全",
        "包治百病", "有病治病无病强身", "根除",
        "奇迹", "神药", "特效药", "万无一失", "无风险",
    }
    if phrase in INTERNATIONAL_UNIVERSAL:
        return False  # Not China-specific; check in all jurisdictions

    china_only = [
        # NMPA-specific prohibited terms (not applicable to FDA)
        "最新技术", "最先进", "国家级", "世界领先", "国际首创",
        "疗效最佳", "疗效确切", "药到病除", "一针见效", "一盒见效",
        "保险公司承保", "无效退款", "无效退钱",
        "官方推荐", "国家推荐", "行政部门推荐",
        "最新科学", "最新研究成果",
        "强效", "显效",
        "纯天然", "无毒副作用", "绿色安全",
        "专治", "主治", "买二送一", "健康保险", "社保报销",
        "国家保密配方", "三天见效", "七天见效", "即时见效", "马上见效",
        "国家级新药", "国家中药保护品种",
        "医保目录", "基药目录", "院士推荐", "专家推荐", "三甲医院",
        "医学会", "分会推荐", "权威推荐", "康复患者", "真实反馈",
        "国内首个", "全球首个", "独家", "首创",
        "首选", "唯一", "领先", "第一", "最强", "最快", "最佳", "最好", "最高",
        "突破性", "革命性", "创新性",
        "优于",
        "临床治愈",
        "有效率", "治愈率", "好转率", "显效率",
        "保险公司",
    ]
    return phrase in china_only


def _extract_context(text: str, phrase: str, width: int = 40) -> str:
    """Extract surrounding context of a phrase."""
    idx = text.lower().find(phrase.lower())
    if idx == -1:
        return phrase
    start = max(0, idx - width)
    end = min(len(text), idx + len(phrase) + width)
    return "..." + text[start:end] + "..."


def _extract_product_name(text: str) -> str:
    """Try to extract product/brand name from text."""
    # Look for patterns like "DrugName®" or "(DrugName)"
    patterns = [
        r'([A-Z][a-zA-Z]+)®',
        r'([A-Z][a-zA-Z]+)\(.*?\)',
        r'品牌名[:：]\s*(\S+)',
        r'商品名[:：]\s*(\S+)',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return ""


def _detect_material_type(text: str) -> str:
    """Detect material type from content."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ['disease awareness', '疾病教育', 'unbranded', '疾病认知']):
        return "Disease_Awareness"
    if any(kw in text_lower for kw in ['journal ad', 'print ad', '杂志广告', '平面广告']):
        return "Print_Ad"
    if any(kw in text_lower for kw in ['slide', 'deck', 'presentation', '幻灯', '推广资料', '产品资料']):
        return "Sales_Aid"
    if any(kw in text_lower for kw in ['website', 'dot com', '.com', '网页', '官网']):
        return "Website"
    if any(kw in text_lower for kw in ['video', 'tv', 'dtc', '视频', '电视', '短视频']):
        return "Video"
    if any(kw in text_lower for kw in ['患教', '患者教育', 'patient education']):
        return "Patient_Education"
    return "Promotional_Material"


def _detect_jurisdiction(text: str) -> str:
    """Auto-detect regulatory jurisdiction from text language/content."""
    # Count Chinese characters
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text)

    if total_chars == 0:
        return "fda"

    chinese_ratio = chinese_chars / total_chars

    if chinese_ratio > 0.3:
        return "nmpa"
    return "fda"


# ============================================================
# Rule functions
# ============================================================

def extract_claims(text: str) -> list:
    """Extract medical claims from promotional material text.

    Uses pattern matching to identify efficacy, safety, comparison claims.
    """
    claims = []
    text_lower = text.lower()

    # Efficacy claim patterns
    efficacy_patterns = [
        r'(?:effective|efficacious|proven|demonstrated)\s+(?:in|for|to|at)',
        r'(?:reduced|reduces|reduction\s+of)\s+\d+',
        r'(?:improved|improves|improvement\s+of)\s+\d+',
        r'(?:significantly|significant)\s+(?:reduced|improved|increased|decreased)',
        r'(?:治疗|疗效|有效率|缓解率|改善)\s*\d+\s*[%％]',
        r'(?:显著\s*)?(?:降低|提高|改善|减少)\s*\d+',
    ]

    # Comparison claim patterns
    comparison_patterns = [
        r'(?:superior|better|more effective|faster|safer)\s+(?:than|compared to|vs)',
        r'(?:first|only|leading|#1)\s+(?:drug|treatment|therapy|option|choice)',
        r'(?:优于|首选|唯一|领先|第一)\s*(?:的)?(?:药物|治疗方案|选择)',
    ]

    # Superlative patterns
    superlative_patterns = [
        r'(?:most|best|fastest|safest|strongest|highest)',
        r'(?:最强|最好|最快|最安全|最高)',
    ]

    for pattern in efficacy_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            claims.append({
                "text": match.group(),
                "claim_type": "efficacy",
                "strength": "fact",
                "position": match.start(),
            })

    for pattern in comparison_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            claims.append({
                "text": match.group(),
                "claim_type": "comparison",
                "strength": "comparison",
                "position": match.start(),
            })

    for pattern in superlative_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            claims.append({
                "text": match.group(),
                "claim_type": "efficacy",
                "strength": "superlative",
                "position": match.start(),
            })

    # 中文 efficacy patterns
    efficacy_patterns += [
        r'(?:有效率|缓解率|控制率|反应率)\s*[:：]?\s*\d+\s*[%％]',
        r'(?:ORR|DCR|CR|PR)\s*[:：]?\s*\d+\s*[%％]',
        r'(?:PFS|OS|DFS)\s*[:：]?\s*\d+\.?\d*\s*(?:月|months?)',
        r'(?:显著|明显)(?:降低|减少|改善|提高|缩短)\s*\d+\.?\d*\s*[%％]?',
        r'对比(?:安慰剂|对照组|标准治疗)(?:.*?)(?:降低|减少|改善|提高)\s*\d+',
    ]

    # 中文 comparison patterns
    comparison_patterns += [
        r'(?:优于|首选|唯一|领先于|超越)(?:.*?)(?:药物|方案|治疗|产品|竞品)',
        r'(?:国内首个|全球首个|国内首个获批|全球首个获批)',
        r'(?:独家|首创新药|first-in-class|best-in-class)',
        r'医保目录(?:内|甲类|乙类)',
    ]

    # 中文 superlative patterns
    superlative_patterns += [
        r'(?:最强|最好|最快|最安全|最高|首个)',
        r'(?:唯一获批|唯一批准|独家品种)',
    ]
    seen_positions = set()
    deduped = []
    for c in sorted(claims, key=lambda x: x["position"]):
        if not any(abs(c["position"] - p) < 5 for p in seen_positions):
            deduped.append(c)
            seen_positions.add(c["position"])

    return deduped


def check_prohibited_claims(text: str, jurisdiction: str = "auto") -> list:
    """Check for prohibited/restricted phrases.

    Args:
        text: Promotional material text.
        jurisdiction: 'auto' (detect), 'fda', or 'nmpa'.
    """
    findings = []
    text_lower = text.lower()

    # Auto-detect jurisdiction
    orig_jurisdiction = jurisdiction
    if jurisdiction == "auto":
        jurisdiction = _detect_jurisdiction(text)

    # --- PROHIBITED_PHRASES (通用禁止用语) ---
    # FDA mode: only run English/international phrases (skip China-specific)
    # NMPA mode: run all phrases + China-specific additions
    for phrase in PROHIBITED_PHRASES:
        # P0-2: skip NMPA-only phrases when in FDA mode
        if jurisdiction == "fda" and _is_china_phrase(phrase):
            continue
        if _match_phrase(text, phrase):
            findings.append({
                "category": "prohibited_claim",
                "severity": "critical",
                "description": f"绝对化/禁止性用语: \"{phrase}\"",
                "evidence": _extract_context(text, phrase),
                "recommendation": f"删除或修改 \"{phrase}\"",
                "regulation": "NMPA: 《广告法》第十六条 / 《药品广告审查发布标准》第五条"
                    if jurisdiction in ("nmpa", "auto") and _is_china_phrase(phrase)
                    else "FDA 21 CFR 202.1(e)(6)",
                "jurisdiction": jurisdiction.upper(),
            })

    # --- RESTRICTED_PHRASES ---
    for phrase in RESTRICTED_PHRASES:
        # P0-2: skip NMPA-only restricted phrases in FDA mode
        if jurisdiction == "fda" and _is_china_phrase(phrase):
            continue
        if _match_phrase(text, phrase):
            findings.append({
                "category": "restricted_claim",
                "severity": "major",
                "description": f"限制性声明: \"{phrase}\"",
                "evidence": _extract_context(text, phrase),
                "recommendation": f"\"{phrase}\" 需要提供临床试验文献支持",
                "regulation": "NMPA: 《广告法》第十六条第四款"
                    if jurisdiction in ("nmpa", "auto") and _is_china_phrase(phrase)
                    else "FDA 21 CFR 202.1(e)(6); OPDP Enforcement Priority",
                "jurisdiction": jurisdiction.upper(),
            })

    # --- China-specific checks ---
    # P0-2: only run when NMPA jurisdiction (not for FDA cases, even in 'auto' mode
    #        the CHINA_PROHIBITED rules are specific to China regulations)
    if jurisdiction in ("nmpa", "auto") and CHINA_PROHIBITED:
        for category_id, category in CHINA_PROHIBITED.items():
            for phrase in category["phrases"]:
                if _match_phrase(text, phrase):
                    # 避免与通用 PROHIBITED_PHRASES 重复
                    if not any(phrase in f.get("evidence", "") for f in findings):
                        findings.append({
                            "category": f"china_{category_id}",
                            "severity": category["severity"],
                            "description": f"{category['label']}: \"{phrase}\"",
                            "evidence": _extract_context(text, phrase),
                            "recommendation": f"删除或修改 \"{phrase}\" — 违反{category['law']}",
                            "regulation": category["law"],
                            "jurisdiction": "NMPA",
                        })

    return findings


def check_required_disclosures(text: str, jurisdiction: str = "auto") -> list:
    """Check for required disclosure elements.

    Args:
        text: Promotional material text.
        jurisdiction: 'auto' (detect), 'fda', or 'nmpa'.
    """
    findings = []

    if jurisdiction == "auto":
        jurisdiction = _detect_jurisdiction(text)

    # P0-2: jurisdiction-aware disclosure check elements
    # Only check elements relevant to the detected jurisdiction
    for element, config in REQUIRED_ELEMENTS.items():
        # Skip NMPA-specific disclosures when in FDA mode
        is_nmpa_only = element in ("ad_approval_number", "adverse_event_notice",
                                    "contraindication_notice")
        if jurisdiction == "fda" and is_nmpa_only:
            continue
        # Skip FDA-specific disclosures when in NMPA mode
        is_fda_only = element in ("generic_name", "rx_symbol", "pi_reference", "boxed_warning_ref")
        # Actually for NMPA, we still check for generic name and RX symbol
        # but PI reference is FDA-specific
        if jurisdiction == "nmpa" and element in ("pi_reference", "boxed_warning_ref"):
            continue

        found = False
        for pattern in config["patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                found = True
                break

        if not found:
            reg_text = "NMPA: 《药品广告审查发布标准》第十条" if is_nmpa_only else "FDA 21 CFR 202.1(b); FD&C Act 502(n)"
            findings.append({
                "category": "required_disclosure",
                "severity": config["severity"],
                "description": f"缺失必须披露信息: {config['description']}",
                "evidence": "(not found)",
                "recommendation": f"添加 {config['description']}",
                "regulation": reg_text,
                "jurisdiction": jurisdiction.upper(),
            })

    # China-specific disclosures — only when NMPA jurisdiction
    if jurisdiction == "nmpa" and CHINA_REQUIRED_DISCLOSURES:
        for element_id, element in CHINA_REQUIRED_DISCLOSURES.items():
            found = False
            for pattern in element["patterns"]:
                if re.search(pattern, text, re.IGNORECASE):
                    found = True
                    break

            if not found:
                # 避免与通用检查重复
                desc = element["description"]
                if not any(desc in f.get("description", "") for f in findings):
                    findings.append({
                        "category": f"china_disclosure_{element_id}",
                        "severity": element["severity"],
                        "description": f"缺失: {element['label']} ({element['description']})",
                        "evidence": "(not found)",
                        "recommendation": f"添加{element['description']}",
                        "regulation": element["law"],
                        "jurisdiction": "NMPA",
                    })

    return findings


def analyze_fair_balance(text: str) -> dict:
    """Analyze fair balance — benefit vs risk information ratio.

    FDA requires that drug ads present a fair balance between effectiveness
    information and risk information (21 CFR 202.1(e)(5)).

    P0-4 fix: expanded keywords + better logic for no-risk-info detection.
    """
    text_lower = text.lower()
    word_count = len(text.split())

    # Count benefit signals (use _match_phrase for consistent boundary handling)
    benefit_hits = 0
    for kw in BENEFIT_KEYWORDS:
        if _has_chinese(kw):
            benefit_hits += text_lower.count(kw.lower())
        else:
            benefit_hits += len(re.findall(r'\b' + re.escape(kw) + r'\b', text_lower))

    # Count risk signals
    risk_hits = 0
    for kw in RISK_KEYWORDS:
        if _has_chinese(kw):
            risk_hits += text_lower.count(kw.lower())
        else:
            risk_hits += len(re.findall(r'\b' + re.escape(kw) + r'\b', text_lower))

    # P0-4: ensure ratio handles division by zero safely
    ratio = benefit_hits / max(risk_hits, 1)

    result = {
        "benefit_mentions": benefit_hits,
        "risk_mentions": risk_hits,
        "benefit_risk_ratio": round(ratio, 2),
        "word_count": word_count,
        "assessment": "balanced",
    }

    # P0-4: improved logic
    # If material has benefit claims but ZERO risk mentions, flag as no_risk_info
    if risk_hits == 0 and benefit_hits >= 3:
        result["assessment"] = "no_risk_info"
    elif ratio > 3.0 and benefit_hits > 3:
        result["assessment"] = "benefit_heavy"
    elif benefit_hits == 0 and risk_hits == 0:
        result["assessment"] = "no_assessment"

    return result


def check_prescription_drug_rules(text: str, jurisdiction: str = "auto") -> list:
    """Check prescription drug-specific compliance rules.

    Triggered when material is identified as prescription drug promotion.
    """
    findings = []
    text_lower = text.lower()

    if not PRESCRIPTION_DRUG_RULES:
        return findings

    # Check off-label promotion red flags
    off_label = PRESCRIPTION_DRUG_RULES.get("off_label_check", {})
    # P0-3: expanded off-label detection keywords
    off_label_flags = [
        "also effective for", "may help with", "还可用于", "对.*?也有效",
        "off-label", "超适应症", "unapproved use", "emerging use",
        "也可用于", "还可治疗", "also indicated for",
        # P0-3 additions: indirect off-label hints
        "effectively treats", "shown to be effective in",
        "real-world evidence suggests", "case reports indicate",
        "临床上发现", "实践表明", "观察性研究显示",
        "shown to work for", "may provide benefit in",
        "发现对.*?有效",
    ]
    # P1-2 FIX: These phrases can appear in on-label context.
    # Demoted from critical to major — needs human verification.
    off_label_major_flags = [
        "can help manage", "可用于治疗",
    ]
    for flag in off_label_flags:
        if re.search(flag, text, re.IGNORECASE):
            findings.append({
                "category": "prescription_off_label",
                "severity": "critical",
                "description": f"疑似超适应症推广: \"{flag}\"",
                "evidence": _extract_context(text, flag),
                "recommendation": "处方药推广必须严格在批准适应症范围内，删除超适应症暗示",
                "regulation": off_label.get("law_cn", "《药品管理法》第九十条") if jurisdiction == "nmpa" else off_label.get("law_fda", "FDA 21 CFR 202.1(e)(6)"),
                "jurisdiction": jurisdiction.upper() if isinstance(jurisdiction, str) else jurisdiction.upper(),
            })
    for flag in off_label_major_flags:
        if re.search(flag, text, re.IGNORECASE):
            findings.append({
                "category": "prescription_off_label",
                "severity": "major",
                "description": f"需核实在批准适应症范围内: \"{flag}\"（可能在 on-label 语境中合规）",
                "evidence": _extract_context(text, flag),
                "recommendation": f"请人工核实 '{flag}' 表述是否在批准适应症范围内",
                "regulation": off_label.get("law_cn", "《药品管理法》第九十条") if jurisdiction == "nmpa" else off_label.get("law_fda", "FDA 21 CFR 202.1(e)(6)"),
                "jurisdiction": jurisdiction.upper() if isinstance(jurisdiction, str) else jurisdiction.upper(),
            })

    # Check DTC red flags in prescription drug materials
    hcp_check = PRESCRIPTION_DRUG_RULES.get("hcp_audience_check", {})
    for flag in hcp_check.get("red_flags", []):
        if flag.lower() in text_lower:
            findings.append({
                "category": "prescription_dtc_language",
                "severity": "major",
                "description": f"处方药推广中的 DTC 语言: \"{flag}\"",
                "evidence": _extract_context(text, flag),
                "recommendation": "处方药推广应面向 HCP，删除面向患者的直接推广语言",
                "regulation": hcp_check.get("law_cn", "《广告法》第十六条") if jurisdiction == "nmpa" else hcp_check.get("law_fda", "FDCA 502(n)"),
                "jurisdiction": jurisdiction.upper() if isinstance(jurisdiction, str) else jurisdiction.upper(),
            })

    return findings


# ============================================================
# DomainChecker 实现
# ============================================================

class AdvertisingChecker(DomainChecker):
    name = "advertising"
    needs_verification_categories = {
        "restricted_claim", "prescription_off_label",
        "china_comparison_claim", "china_endorsement_claim",
    }

    def extract_claims(self, content, jurisdiction):
        return extract_claims(content)  # 模块级函数

    def check(self, content, jurisdiction):
        """与 review.review_material 的 findings 生成逻辑等价。

        顺序复刻 review_material：
        prohibited + required + prescription → China mass-media 块 → dedup → fair_balance。
        """
        if jurisdiction == "auto":
            jurisdiction = _detect_jurisdiction(content)

        all_findings = (
            check_prohibited_claims(content, jurisdiction)
            + check_required_disclosures(content, jurisdiction)
            + check_prescription_drug_rules(content, jurisdiction)
        )

        # P1-3 FIX: Check China prescription drug mass media restriction
        # 处方药不得在大众传播媒介发布广告（《广告法》第十六条第一款）
        # —— 原样复制自 review.py review_material 的同一段
        if jurisdiction in ("nmpa", "auto") and CHINA_PRESCRIPTION_RESTRICTION:
            text_lower2 = content.lower()
            # Detect prescription drug markers
            rx_markers = ["rx", "℞", "处方药", "处方用药", "凭处方"]
            has_rx = any(marker.lower() in text_lower2 for marker in rx_markers)
            # If no explicit RX marker, check if material references prescription-only usage
            if not has_rx:
                rx_hints = ["本品为处方药", "处方药信息", "处方药品", "遵医嘱", "医师处方"]
                has_rx = any(hint in content for hint in rx_hints)

            # Detect mass media promotion language
            mass_media_flags = [
                "立即购买", "马上购买", "点击购买", "在线购买",
                "限时优惠", "限时折扣", "抢购", "热销", "限量",
                "咨询热线", "订购热线", "免费热线", "400",
                "全国包邮", "货到付款", "免费配送",
                "买就送", "买.*送", "赠品", "抽奖",
                "团购", "秒杀", "爆款", "新品上市",
            ]
            has_mass_media = False
            matched_flag = ""
            for flag in mass_media_flags:
                if re.search(flag, content, re.IGNORECASE):
                    has_mass_media = True
                    matched_flag = flag
                    break
            # Also check if there's no HCP-only disclaimer
            hcp_only_hints = [
                "仅供医学药学专业人士", "请按药品说明书或在药师指导下",
                "本广告仅供", "面向医学专业人士", "仅供HCP",
            ]
            is_hcp_only = any(hint in content for hint in hcp_only_hints)

            if has_rx and has_mass_media and not is_hcp_only:
                all_findings.append({
                    "category": "china_prescription_mass_media",
                    "severity": "critical",
                    "description": f"处方药不得在大众传播媒介发布广告: 检测到处方药标识 + 大众媒介促销语言 \"{matched_flag}\"",
                    "evidence": _extract_context(content, matched_flag),
                    "recommendation": f"处方药仅可在医学药学专业刊物上作广告（{CHINA_PRESCRIPTION_RESTRICTION.get('rule', '')}）。删除面向大众的促销语言，或添加'本广告仅供医学药学专业人士阅读'忠告语",
                    "regulation": CHINA_PRESCRIPTION_RESTRICTION.get("law", "《广告法》第十六条第一款"),
                    "jurisdiction": "NMPA",
                })

        # Deduplicate findings (same phrase from different rule sets)
        # —— 与 review_material 的 dedup 逻辑一致，保证 findings 等价
        seen_evidence = set()
        deduped_findings = []
        for f in all_findings:
            key = f.get("description", "") + f.get("evidence", "")
            if key not in seen_evidence:
                deduped_findings.append(f)
                seen_evidence.add(key)
        all_findings = deduped_findings

        # Fair balance finding
        balance = analyze_fair_balance(content)
        if balance["assessment"] in ("benefit_heavy", "no_risk_info"):
            fb_law = ("《广告法》第十六条第二款" if jurisdiction == "nmpa"
                      else "FDA 21 CFR 202.1(e)(5) — Fair Balance")
            all_findings.append({
                "category": "fair_balance",
                "severity": "major",
                "description": f"公平平衡问题: 获益提及 {balance['benefit_mentions']} 次 vs 风险提及 {balance['risk_mentions']} 次（比值 {balance['benefit_risk_ratio']}）",
                "evidence": f"benefit_risk_ratio = {balance['benefit_risk_ratio']}",
                "recommendation": "补充安全性信息（不良反应、禁忌、警告），确保获益与风险信息比例平衡",
                "regulation": fb_law,
                "jurisdiction": jurisdiction.upper(),
            })

        # 法规溯源（1c-Task2）：regulation str → 可溯源 dict（含 excerpt，锚定广告法条款原文）
        # 仅升级有 CLAUSE_MAPPING 映射且 jurisdiction 匹配的 finding；其余保留 str（向后兼容）
        for f in all_findings:
            if isinstance(f.get("regulation"), str):
                f["regulation"] = _source_regulation(
                    f.get("category", ""), f.get("jurisdiction", ""), f["regulation"])

        return all_findings

    def analyze_balance(self, content):
        """供 engine 取 fair_balance 详情。"""
        return analyze_fair_balance(content)
