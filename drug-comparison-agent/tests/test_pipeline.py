import json
from unittest import mock

from scripts import pipeline


def test_run_pipeline_assembles_matrix_and_report(tmp_path):
    drugs = ["Ozempic", "Wegovy"]
    norm = {"generic_name": "semaglutide", "brand_name": "Ozempic",
            "dosage_form": "SOLUTION", "marketing_status": "Prescription"}
    label = {"indications": "type 2 diabetes", "mechanism": "GLP-1 RA", "has_boxed_warning": True}
    faers = ["Nausea"]
    # v1.2: summarize_pipeline / extract_endpoints 是纯函数，用真实 study 样本走一遍
    study = {"protocolSection": {
        "statusModule": {"overallStatus": "RECRUITING"},
        "designModule": {"phases": ["PHASE3"]},
        "conditionsModule": {"conditions": ["T2DM"]},
        "outcomesModule": {"primaryOutcomes": [{"measure": "HbA1c"}]}}}

    with mock.patch("scripts.fetchers.openfda.normalize", return_value=norm), \
         mock.patch("scripts.fetchers.openfda.fetch_label", return_value=label), \
         mock.patch("scripts.fetchers.openfda.fetch_faers_top", return_value=faers), \
         mock.patch("scripts.fetchers.ctgov.fetch_studies", return_value=([study], 1)), \
         mock.patch("scripts.llm_insight.generate_insight", return_value="## 定位洞察\n领先 [来源:1]"):
        result = pipeline.run_pipeline(drugs, out_dir=str(tmp_path), api_key="k")

    assert result["ok"] is True
    assert "cells" in result["matrix"]
    assert len(result["matrix"]["cells"]) == 10  # 2 药 × 5 维度
    assert "对比矩阵" in result["report"]
    assert tmp_path.joinpath("comparison-matrix.json").exists()
    assert tmp_path.joinpath("comparison-report.md").exists()


def test_run_pipeline_caps_at_six_drugs():
    drugs = ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]
    try:
        pipeline.run_pipeline(drugs, out_dir="/tmp/x", api_key="k")
        assert False, "应拒绝 >6 药"
    except ValueError:
        pass


def test_run_pipeline_rejects_single_drug():
    # spec：对比至少 2 药；单药应被拒绝
    drugs = ["Ozempic"]
    try:
        pipeline.run_pipeline(drugs, out_dir="/tmp/x", api_key="k")
        assert False, "应拒绝 <2 药"
    except ValueError:
        pass


def test_run_pipeline_allows_unresolved_drug():
    drugs = ["NoSuchDrug", "SecondBad"]
    with mock.patch("scripts.fetchers.openfda.normalize", return_value=None), \
         mock.patch("scripts.fetchers.openfda.fetch_label", return_value={"indications": "", "mechanism": "", "has_boxed_warning": False}), \
         mock.patch("scripts.fetchers.openfda.fetch_faers_top", return_value=[]), \
         mock.patch("scripts.fetchers.ctgov.fetch_studies", return_value=([], 0)), \
         mock.patch("scripts.llm_insight.generate_insight", return_value="## 定位洞察\n数据不足"):
        result = pipeline.run_pipeline(drugs, out_dir="/tmp/x_skip", api_key="k", write_files=False)
    assert result["ok"] is True
    unresolved = [w for w in result["warnings"] if "unresolved" in w.lower()]
    assert unresolved
