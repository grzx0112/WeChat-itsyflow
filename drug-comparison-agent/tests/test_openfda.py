import json
import os
from unittest import mock

from scripts.fetchers import openfda

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def test_normalize_returns_first_hit():
    data = _load("openfda_ndc_ozempic.json")
    with mock.patch("scripts.fetchers.openfda.get_json", return_value=data):
        n = openfda.normalize("Ozempic")
    assert n["generic_name"] == "semaglutide"
    assert n["brand_name"] == "Ozempic"
    assert n["dosage_form"] == "SOLUTION"
    assert n["marketing_status"] == "Prescription"


def test_normalize_returns_none_on_error():
    with mock.patch("scripts.fetchers.openfda.get_json", side_effect=RuntimeError("404")):
        assert openfda.normalize("NoSuchDrug") is None


def test_fetch_label_extracts_fields():
    data = _load("openfda_label_ozempic.json")
    with mock.patch("scripts.fetchers.openfda.get_json", return_value=data):
        lab = openfda.fetch_label("Ozempic", generic="semaglutide")
    assert "type 2 diabetes" in lab["indications"]
    assert "GLP-1 receptor agonist" in lab["mechanism"]
    assert lab["has_boxed_warning"] is True


def test_fetch_label_empty_on_error():
    with mock.patch("scripts.fetchers.openfda.get_json", side_effect=RuntimeError("404")):
        lab = openfda.fetch_label("X", generic="x")
    assert lab["indications"] == "" and lab["has_boxed_warning"] is False


def test_fetch_faers_top_returns_terms():
    data = _load("openfda_faers_ozempic.json")
    with mock.patch("scripts.fetchers.openfda.get_json", return_value=data):
        terms = openfda.fetch_faers_top("semaglutide", n=3)
    assert terms == ["Nausea", "Vomiting", "Diarrhoea"]


def test_fetch_faers_top_empty_on_error():
    with mock.patch("scripts.fetchers.openfda.get_json", side_effect=RuntimeError("boom")):
        assert openfda.fetch_faers_top("x") == []


def test_normalize_tries_brand_before_generic():
    # v1.1: 先精确品牌名查，避免 generic 命中兄弟产品虚假记录
    searches = []
    def fake(url, params=None, headers=None):
        searches.append(params["search"])
        return {"results": [{"generic_name": "semaglutide", "brand_name": "Wegovy",
                             "dosage_form": "INJECTION", "marketing_status": "Prescription"}]}
    with mock.patch("scripts.fetchers.openfda.get_json", side_effect=fake):
        openfda.normalize("Wegovy")
    assert searches[0] == 'brand_name:"Wegovy"'


def test_normalize_falls_back_to_generic_on_brand_miss():
    # 品牌未命中 → 回退通用名
    calls = []
    def fake(url, params=None, headers=None):
        calls.append(params["search"])
        if "brand_name" in calls[-1]:
            return {"results": []}  # 品牌无命中
        return {"results": [{"generic_name": "metformin", "brand_name": "Glucophage",
                             "dosage_form": "TABLET", "marketing_status": "Prescription"}]}
    with mock.patch("scripts.fetchers.openfda.get_json", side_effect=fake):
        n = openfda.normalize("metformin")
    assert n is not None and n["generic_name"] == "metformin"
    assert len(calls) == 2  # brand + generic


def test_fetch_label_prefers_brand_label():
    # v1.1: 标签先精确品牌查（拿该药自己 SPL），命中即用不回退
    searches = []
    def fake(url, params=None, headers=None):
        searches.append(params["search"])
        return {"results": [{"indications_and_usage": ["weight management"],
                             "mechanism_of_action": ["GLP-1"], "boxed_warning": []}]}
    with mock.patch("scripts.fetchers.openfda.get_json", side_effect=fake):
        lab = openfda.fetch_label("Wegovy", generic="semaglutide")
    assert searches[0] == 'openfda.brand_name:"Wegovy"'
    assert "weight management" in lab["indications"]
    assert len(searches) == 1  # 品牌命中，不再查 generic


def test_fetch_label_prefers_single_brand_spl():
    # v1.1: 合并 SPL 排在前时，优先单品牌 SPL（Ozempic 而非 Rybelsus+Ozempic 合并标签）
    data = {"results": [
        {"openfda": {"brand_name": ["OZEMPIC", "RYBELSUS"]},
         "indications_and_usage": ["RYBELSUS and OZEMPIC tablets are indicated"]},
        {"openfda": {"brand_name": ["Ozempic"]},
         "indications_and_usage": ["OZEMPIC injection is indicated for type 2 diabetes"]},
    ]}
    with mock.patch("scripts.fetchers.openfda.get_json", return_value=data):
        lab = openfda.fetch_label("Ozempic", generic="semaglutide")
    assert "OZEMPIC injection" in lab["indications"]
    assert "RYBELSUS and OZEMPIC tablets" not in lab["indications"]
