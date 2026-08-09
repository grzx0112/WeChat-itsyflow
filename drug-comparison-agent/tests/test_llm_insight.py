import json
from unittest import mock

from scripts import llm_insight

MATRIX = {"drugs": ["Ozempic"], "dimensions": ["profile", "indications", "pipeline", "endpoints", "safety"],
          "cells": [{"id": 1, "drug": "Ozempic", "dim": "indications",
                     "value": "indications: type 2 diabetes; mechanism: GLP-1 RA", "sources": [{"api": "openFDA Label"}]}]}


def test_build_prompt_contains_matrix_and_rules():
    prompt = llm_insight.build_prompt(MATRIX)
    assert "type 2 diabetes" in prompt
    assert "[来源:" in prompt or "[来源:N]" in prompt
    assert "机制差异化" in prompt and "空白机会" in prompt
    assert "无数据支撑" in prompt  # 禁止臆测规则


def test_build_prompt_includes_cell_ids():
    prompt = llm_insight.build_prompt(MATRIX)
    assert "id: 1" in prompt or "\"id\": 1" in prompt


def test_generate_insight_calls_llm_with_prompt():
    with mock.patch("scripts.llm_insight.call_llm", return_value="## 定位洞察\n机制差异 [来源:1]") as m:
        out = llm_insight.generate_insight(MATRIX, api_key="k", model="deepseek-v4-flash")
    assert "机制差异" in out
    m.assert_called_once()
    # 传给 call_llm 的 prompt 应含矩阵
    args = m.call_args[0]
    assert "type 2 diabetes" in args[0]


def test_generate_insight_returns_fallback_on_error():
    with mock.patch("scripts.llm_insight.call_llm", side_effect=RuntimeError("api down")):
        out = llm_insight.generate_insight(MATRIX, api_key="k", model="deepseek-v4-flash")
    assert "LLM 不可用" in out or "生成失败" in out
