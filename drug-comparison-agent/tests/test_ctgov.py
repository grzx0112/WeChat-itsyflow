import json
import os
from unittest import mock

from scripts.fetchers import ctgov

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def test_fetch_pipeline_aggregates_by_phase_status_condition():
    data = _load("ctgov_semaglutide.json")
    with mock.patch("scripts.fetchers.ctgov.get_json", return_value=data):
        pipe = ctgov.fetch_pipeline("semaglutide")
    assert pipe["total"] == 2
    assert "PHASE3" in pipe["by_phase"]
    assert "RECRUITING" in pipe["by_status"]
    assert "Diabetes Mellitus, Type 2" in pipe["top_conditions"]


def test_fetch_pipeline_empty_on_error():
    with mock.patch("scripts.fetchers.ctgov.get_json", side_effect=RuntimeError("x")):
        pipe = ctgov.fetch_pipeline("semaglutide")
    assert pipe["total"] == 0 and pipe["by_phase"] == {}


def test_fetch_endpoints_returns_phase3_4_measures():
    data = _load("ctgov_semaglutide.json")
    with mock.patch("scripts.fetchers.ctgov.get_json", return_value=data):
        eps = ctgov.fetch_endpoints("semaglutide")
    measures = {e["measure"] for e in eps}
    assert "HbA1c change from baseline" in measures
    assert "Body weight change" in measures


def test_fetch_endpoints_empty_on_error():
    with mock.patch("scripts.fetchers.ctgov.get_json", side_effect=RuntimeError("x")):
        assert ctgov.fetch_endpoints("semaglutide") == []


def test_fetch_uses_query_intr_not_intervention():
    # 回归：CT.gov v2 干预参数为 query.intr（query.intervention 会 HTTP 400）
    captured = {}
    def fake(url, params=None, headers=None):
        captured["params"] = params
        return {"studies": []}
    with mock.patch("scripts.fetchers.ctgov.get_json", side_effect=fake):
        ctgov.fetch_pipeline("semaglutide")
    assert "query.intr" in captured["params"]
    assert "query.intervention" not in captured["params"]


def test_fetch_studies_returns_studies_and_totalcount():
    # v1.2: fetch_studies 返回 (studies, totalCount)；total 不受 pageSize 截断影响
    data = _load("ctgov_semaglutide.json")
    with mock.patch("scripts.fetchers.ctgov.get_json", return_value=data):
        studies, total = ctgov.fetch_studies("semaglutide")
    assert len(studies) == 2
    assert total == 2  # 来自 API totalCount，非 len(studies)


def test_fetch_studies_empty_on_error():
    with mock.patch("scripts.fetchers.ctgov.get_json", side_effect=RuntimeError("x")):
        assert ctgov.fetch_studies("semaglutide") == ([], 0)


def test_fetch_uses_page_size_thirty():
    # v1.2 回归：pageSize 100→30（大 payload 提速），且暴露为模块常量
    captured = {}
    def fake(url, params=None, headers=None):
        captured["params"] = params
        return {"studies": [], "totalCount": 0}
    with mock.patch("scripts.fetchers.ctgov.get_json", side_effect=fake):
        ctgov.fetch_studies("semaglutide")
    assert captured["params"]["pageSize"] == ctgov.PAGE_SIZE == 30


def test_fetch_studies_total_fallback_without_totalcount():
    # CT.gov v2 真实响应不含 totalCount（实测仅 studies + nextPageToken），
    # 应以返回条数兜底，避免 total=0（回归 v1.2 初版的 total=0 bug）
    data = {"studies": [{"protocolSection": {}}, {"protocolSection": {}}]}  # 无 totalCount
    with mock.patch("scripts.fetchers.ctgov.get_json", return_value=data):
        studies, total = ctgov.fetch_studies("semaglutide")
    assert len(studies) == 2
    assert total == 2  # 无 totalCount 时回退 len(studies)
