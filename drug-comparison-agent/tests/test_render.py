from scripts.render import render_matrix_table, render_report

MATRIX = {"drugs": ["Ozempic", "Wegovy"], "dimensions": ["profile", "safety"], "cells": [
    {"id": 1, "drug": "Ozempic", "dim": "profile", "value": "generic=semaglutide",
     "sources": [{"api": "openFDA NDC", "query": "q", "field": "f"}]},
    {"id": 2, "drug": "Ozempic", "dim": "safety", "value": "boxed_warning=yes",
     "sources": [{"api": "openFDA Label", "query": "q", "field": "boxed_warning"}]},
    {"id": 3, "drug": "Wegovy", "dim": "profile", "value": "generic=semaglutide",
     "sources": [{"api": "openFDA NDC", "query": "q", "field": "f"}]},
    {"id": 4, "drug": "Wegovy", "dim": "safety", "value": "boxed_warning=yes",
     "sources": [{"api": "openFDA Label", "query": "q", "field": "boxed_warning"}]},
]}


def test_matrix_table_has_header_and_drugs():
    tbl = render_matrix_table(MATRIX)
    assert "| 维度" in tbl and "Ozempic" in tbl and "Wegovy" in tbl
    assert "profile" in tbl and "safety" in tbl


def test_matrix_table_truncates_long_values():
    big = dict(MATRIX)
    big["cells"] = [{**c, "value": c["value"] * 50} for c in MATRIX["cells"]]
    tbl = render_matrix_table(big)
    assert "…" in tbl  # 超长截断标记


def test_render_report_assembles_sections():
    rep = render_report(MATRIX, insight_md="## 定位洞察\nOzempic 领先 [来源:1]",
                        flagged=["[无引用] 某句"])
    assert "# 药品竞品对比报告" in rep
    assert "## 对比矩阵" in rep
    assert "## 定位洞察" in rep
    assert "## ⚠️ 未验证论断" in rep
    assert "某句" in rep


def test_render_report_omits_warning_section_when_clean():
    rep = render_report(MATRIX, insight_md="## 定位洞察\n文本", flagged=[])
    assert "⚠️ 未验证论断" not in rep
