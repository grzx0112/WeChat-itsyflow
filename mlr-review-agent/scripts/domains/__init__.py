"""领域规则包注册表。每个领域实现 DomainChecker 接口。"""


class DomainChecker:
    """领域规则包统一接口。"""
    name = ""
    needs_verification_categories = set()

    def extract_claims(self, content: str, jurisdiction: str) -> list:
        raise NotImplementedError

    def check(self, content: str, jurisdiction: str) -> list:
        raise NotImplementedError


# 在 DomainChecker 定义之后导入各领域 Checker，避免循环 import：
# advertising.py / hcp.py 执行 `from domains import DomainChecker` 时，DomainChecker 已就绪。
# hcp.py / kol_msl.py 继承 AdvertisingChecker，须在 advertising 之后导入。
from domains.advertising import AdvertisingChecker
from domains.hcp import HcpChecker
from domains.kol_msl import KolMslChecker
from domains.sponsorship import SponsorshipChecker

DOMAIN_REGISTRY = {
    "advertising": AdvertisingChecker,
    "hcp": HcpChecker,
    "kol_msl": KolMslChecker,
    "sponsorship": SponsorshipChecker,
}


def get_domain_checker(name: str) -> DomainChecker:
    if name not in DOMAIN_REGISTRY:
        raise ValueError(
            f"未知领域: {name}（已注册: {list(DOMAIN_REGISTRY)}）")
    return DOMAIN_REGISTRY[name]()
