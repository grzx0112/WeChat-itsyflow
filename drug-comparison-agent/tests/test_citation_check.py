from scripts.citation_check import validate

MATRIX = {"cells": [
    {"id": 1, "drug": "Ozempic", "dim": "indications",
     "value": "indications: type 2 diabetes; mechanism: GLP-1 receptor agonist"},
    {"id": 2, "drug": "Mounjaro", "dim": "indications",
     "value": "indications: type 2 diabetes; mechanism: GIP/GLP-1 dual agonist"},
]}
DRUGS = ["Ozempic", "Mounjaro"]


def test_well_cited_sentence_passes():
    report = "Ozempic 与 Mounjaro 均获批 type 2 diabetes [来源:1][来源:2]。"
    res = validate(report, MATRIX, DRUGS)
    assert res["flagged"] == []
    assert len(res["ok"]) == 2


def test_unknown_citation_id_is_flagged():
    report = "某药很安全 [来源:99]。"
    res = validate(report, MATRIX, DRUGS)
    assert len(res["flagged"]) == 1
    assert "99" in res["flagged"][0]


def test_uncited_claim_is_flagged():
    # 含药名断言句但无 [来源:N]
    report = "Ozempic 的疗效显著优于 Mounjaro。"
    res = validate(report, MATRIX, DRUGS)
    assert len(res["flagged"]) == 1


def test_plain_sentence_without_drug_or_claim_not_flagged():
    report = "本报告基于公开数据生成。"
    res = validate(report, MATRIX, DRUGS)
    assert res["flagged"] == []
