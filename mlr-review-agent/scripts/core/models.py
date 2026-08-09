"""跨领域数据模型。"""
from dataclasses import dataclass, field


@dataclass
class Claim:
    text: str
    claim_type: str
    strength: str
    position: int


@dataclass
class Finding:
    """regulation 兼容 str（旧）和 dict（新，可溯源）。
    阶段 1a：advertising 仍用 str；1c 法规语料库后升级 dict。"""
    category: str
    severity: str
    description: str
    evidence: str
    recommendation: str
    regulation: object  # str | dict


@dataclass
class ReviewResult:
    material_type: str = "unknown"
    product_name: str = ""
    generic_name: str = ""
    claims: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    compliance_score: int = 100
    verdict: str = "pass"
    benefit_risk_ratio: float = 0.0
    summary: str = ""
