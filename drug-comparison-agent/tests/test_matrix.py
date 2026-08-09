from scripts.matrix import build_matrix, DIMENSIONS

RAW = {
    "Ozempic": {
        "normalized": {"generic_name": "semaglutide", "brand_name": "Ozempic",
                       "dosage_form": "SOLUTION", "marketing_status": "Prescription"},
        "label": {"indications": "type 2 diabetes; CV risk reduction",
                  "mechanism": "GLP-1 receptor agonist", "has_boxed_warning": True},
        "faers": ["Nausea", "Vomiting"],
        "pipeline": {"total": 50, "by_phase": {"PHASE3": 10}, "by_status": {"RECRUITING": 5},
                     "top_conditions": ["Diabetes Mellitus, Type 2"]},
        "endpoints": [{"measure": "HbA1c change", "condition": "T2DM"}],
    }
}


def test_dimensions_are_five():
    assert DIMENSIONS == ["profile", "indications", "pipeline", "endpoints", "safety"]


def test_build_matrix_creates_one_cell_per_drug_per_dim():
    m = build_matrix(["Ozempic"], RAW)
    assert m["drugs"] == ["Ozempic"]
    assert len(m["cells"]) == 5
    dims = {c["dim"] for c in m["cells"]}
    assert dims == set(DIMENSIONS)


def test_cell_ids_are_sequential_unique():
    m = build_matrix(["Ozempic"], RAW)
    ids = [c["id"] for c in m["cells"]]
    assert ids == list(range(1, 6))


def test_profile_cell_value_and_sources():
    m = build_matrix(["Ozempic"], RAW)
    prof = next(c for c in m["cells"] if c["dim"] == "profile")
    assert "semaglutide" in prof["value"]
    assert prof["sources"][0]["api"] == "openFDA NDC"


def test_safety_cell_includes_boxed_and_faers():
    m = build_matrix(["Ozempic"], RAW)
    safety = next(c for c in m["cells"] if c["dim"] == "safety")
    assert "boxed_warning=yes" in safety["value"]
    assert "Nausea" in safety["value"]


def test_two_drugs_get_distinct_ids():
    raw2 = dict(RAW)
    raw2["Wegovy"] = dict(RAW["Ozempic"])
    m = build_matrix(["Ozempic", "Wegovy"], raw2)
    assert len(m["cells"]) == 10
    assert {c["id"] for c in m["cells"]} == set(range(1, 11))
