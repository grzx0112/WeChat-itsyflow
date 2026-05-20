#!/usr/bin/env python3
"""AI 过滤 + 双语摘要 + 标签生成模块（JSON 批量版）"""

import sys
import os

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

import os
import json
import re
import requests
from typing import List, Dict, Optional


def _get_api_key(llm: str = "openai") -> Optional[str]:
    """获取 API key，按 provider 优先级查找"""
    key_map = {
        "zai": ["ZAI_API_KEY", "OPENAI_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY", "OPENAI_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
    }
    for env_var in key_map.get(llm, ["OPENAI_API_KEY"]):
        val = os.environ.get(env_var)
        if val:
            return val
    return None


def _get_base_url(llm: str = "openai") -> str:
    """获取 API base URL"""
    url_map = {
        "zai": ("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        "deepseek": ("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "openai": ("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    }
    env_var, default = url_map.get(llm, ("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    return os.environ.get(env_var, default)


def _get_model(llm: str = "openai") -> str:
    """获取默认模型名"""
    model_map = {
        "zai": ("ZAI_MODEL", "glm-4-flash"),
        "deepseek": ("DEEPSEEK_MODEL", "deepseek-chat"),
        "openai": ("OPENAI_MODEL", "gpt-4o-mini"),
    }
    env_var, default = model_map.get(llm, ("OPENAI_MODEL", "gpt-4o-mini"))
    return os.environ.get(env_var, default)


def _call_llm(prompt: str, llm: str = "openai", model: str = "", max_tokens: int = 500) -> str:
    """调用 LLM API"""
    api_key = _get_api_key(llm)
    if not api_key:
        raise ValueError(f"未找到 API key（{llm}）。请设置环境变量。")

    base_url = _get_base_url(llm)
    actual_model = model or _get_model(llm)
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": actual_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def score_relevance(items: List[Dict], query: str, llm: str = "openai", model: str = "", mock: bool = False) -> List[Dict]:
    """批量打分：每批 10 条，一次 LLM 调用处理"""
    if mock:
        for item in items:
            text = f"{item.get('title', '')} {item.get('raw_summary', '')}".lower()
            keywords = [k.lower() for k in query.split() if len(k) > 2]
            matches = sum(1 for k in keywords if k in text)
            item["relevance_score"] = min(5, max(1, matches))
        return items

    BATCH = 10
    for start in range(0, len(items), BATCH):
        batch = items[start:start + BATCH]
        lines = []
        for idx, item in enumerate(batch):
            lines.append(f"{idx+1}. [{item.get('source','')}] {item.get('title','')} | {item.get('raw_summary','')[:120]}")
        items_text = '\n'.join(lines)

        prompt = f"""你是医药情报分析师。对以下 {len(batch)} 条条目按与查询"{query}"的相关性打分（0-5）。

条目：
{items_text}

标准：5=直接相关 4=密切 3=中度 2=边缘 1=微弱 0=无关
只输出{len(batch)}个数字，逗号分隔，不要解释。"""

        try:
            result = _call_llm(prompt, llm, model=model, max_tokens=100)
            scores = [int(s.strip()) for s in result.split(',') if s.strip().isdigit()]
            for i, item in enumerate(batch):
                item["relevance_score"] = max(0, min(5, scores[i])) if i < len(scores) else 3
            print(f"[Score] 批次 {start//BATCH+1}: {len(batch)} 条 → {scores}")
        except Exception as e:
            print(f"[Score] 批次 {start//BATCH+1} 失败: {e}")
            for item in batch:
                item["relevance_score"] = 3

    return items


def _parse_json_summaries(text: str, expected_count: int) -> List[str]:
    """从 LLM 返回文本中解析 JSON 摘要数组，带回退策略"""
    # 策略 1：直接解析整个文本为 JSON
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [item.get("summary", "") if isinstance(item, dict) else str(item) for item in data]
    except (json.JSONDecodeError, TypeError):
        pass

    # 策略 2：提取 JSON 代码块
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            if isinstance(data, list):
                return [item.get("summary", "") if isinstance(item, dict) else str(item) for item in data]
        except (json.JSONDecodeError, TypeError):
            pass

    # 策略 3：提取方括号内容
    bracket_match = re.search(r'\[[\s\S]*\]', text)
    if bracket_match:
        try:
            data = json.loads(bracket_match.group(0))
            if isinstance(data, list):
                return [item.get("summary", "") if isinstance(item, dict) else str(item) for item in data]
        except (json.JSONDecodeError, TypeError):
            pass

    # 策略 4：提取所有 {...} 对象，逐个解析
    json_objects = re.findall(r'\{[^{}]*"summary"[^{}]*\}', text)
    if json_objects and len(json_objects) == expected_count:
        results = []
        for obj_str in json_objects:
            try:
                obj = json.loads(obj_str)
                results.append(obj.get("summary", ""))
            except (json.JSONDecodeError, TypeError):
                results.append(obj_str)
        if len(results) == expected_count:
            print(f"[Summary] 通过逐对象解析成功提取 {len(results)} 条")
            return results

    # 策略 5：回退到 --- 分割
    print(f"[Summary] JSON 解析失败，回退到 --- 分割")
    parts = re.split(r'\n---+\n?', text)
    return [p.strip() for p in parts if p.strip()]


def generate_summaries(items: List[Dict], query: str, llm: str = "openai", model: str = "", mock: bool = False) -> List[Dict]:
    """批量生成双语摘要 + 自动标签：每批 5 条，使用 JSON 格式确保一一对应"""
    high_rel = [i for i in items if i.get("relevance_score", 0) >= 3]

    if mock:
        for item in items:
            if item.get("relevance_score", 0) >= 3:
                raw = item.get('raw_summary', '')[:100]
                item["summary_zh"] = f"[Mock 摘要] {raw}（AI 生成）"
                item["summary_en"] = f"[Mock summary] {raw} (AI generated)"
                item["tags"] = _mock_tags(item)
            else:
                item["summary_zh"] = ""
                item["summary_en"] = ""
                item["tags"] = []
        return items

    # 低分条目跳过
    for item in items:
        if item.get("relevance_score", 0) < 3:
            item["summary_zh"] = ""
            item["summary_en"] = ""
            item["tags"] = []

    # 批量摘要高分条目（JSON 格式，含中英双语 + 标签）
    BATCH = 5
    for start in range(0, len(high_rel), BATCH):
        batch = high_rel[start:start + BATCH]
        entry_list = []
        for idx, item in enumerate(batch):
            entry_list.append({
                "index": idx + 1,
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "raw_summary": item.get("raw_summary", "")[:200]
            })
        items_json = json.dumps(entry_list, ensure_ascii=False, indent=2)

        prompt = f"""你是医药情报分析师。为以下 {len(batch)} 条与"{query}"相关的情报逐条生成：
1. 中文结构化摘要
2. 英文结构化摘要
3. 自动标签

条目列表：
{items_json}

严格要求：
1. 返回 JSON 数组，长度必须为 {len(batch)}
2. 每个元素格式：{{"summary_zh": "中文摘要", "summary_en": "English summary", "tags": ["tag1","tag2"]}}
3. 中文摘要 150 字以内，包含：核心内容（一句话）、关键信息（2-3 个要点）、行业影响，末尾标注"（AI 生成）"
4. 英文摘要 100 words 以内，包含：core finding (1 sentence)、key points (2-3 bullets)、industry impact，末尾标注 "(AI generated)"
5. 标签从以下受控词汇中选择（3-5 个）：
   drug-approval, clinical-trial, regulatory, safety, oncology, immunology, cardiology, neurology,
   rare-disease, biosimilar, generic, biotech, m-a, pipeline, fda, ema, pricing, reimbursement,
   manufacturing, supply-chain, digital-health, ai-ml, biomarker, companion-diagnostic, combination-therapy
6. 必须严格针对该条目的内容生成，不要混入其他条目的信息
7. 只输出 JSON 数组，不要输出其他文字"""

        try:
            result = _call_llm(prompt, llm, model=model, max_tokens=2000)
            parsed = _parse_batch_result(result, len(batch))

            for i, item in enumerate(batch):
                if i < len(parsed) and parsed[i]:
                    p = parsed[i]
                    item["summary_zh"] = p.get("summary_zh", "")
                    item["summary_en"] = p.get("summary_en", "")
                    item["tags"] = p.get("tags", [])
                    if not item["summary_zh"]:
                        item["summary_zh"] = _generate_single_summary(item, query, llm, model)
                    if not item["summary_en"]:
                        item["summary_en"] = _generate_single_en_summary(item, query, llm, model)
                else:
                    print(f"[Summary] 条目 {i+1} 摘要缺失，逐条补生成")
                    item["summary_zh"] = _generate_single_summary(item, query, llm, model)
                    item["summary_en"] = _generate_single_en_summary(item, query, llm, model)
                    item["tags"] = _mock_tags(item)

            print(f"[Summary] 批次 {start//BATCH+1}: {len(batch)} 条双语摘要 + 标签已生成")
        except Exception as e:
            print(f"[Summary] 批次 {start//BATCH+1} 失败: {e}")
            for item in batch:
                try:
                    item["summary_zh"] = _generate_single_summary(item, query, llm, model)
                    item["summary_en"] = _generate_single_en_summary(item, query, llm, model)
                    item["tags"] = _mock_tags(item)
                except Exception:
                    item["summary_zh"] = ""
                    item["summary_en"] = ""
                    item["tags"] = []

    return items


def _generate_single_summary(item: Dict, query: str, llm: str = "openai", model: str = "") -> str:
    """逐条生成中文摘要（回退方案）"""
    title = item.get("title", "")
    raw = item.get("raw_summary", "")[:300]

    prompt = f"""为以下医药情报生成中文摘要（150字以内）。

标题：{title}
来源：{item.get('source', '')}
内容：{raw}

格式要求：
- 首行重复标题（如"【{title}】"）
- 核心内容（一句话）+ 关键信息（2-3 个要点）+ 行业影响
- 末尾标注（AI 生成）"""

    result = _call_llm(prompt, llm, model=model, max_tokens=200)
    return result


def _generate_single_en_summary(item: Dict, query: str, llm: str = "openai", model: str = "") -> str:
    """逐条生成英文摘要"""
    title = item.get("title", "")
    raw = item.get("raw_summary", "")[:300]

    prompt = f"""Generate a structured English summary (max 100 words) for this pharmaceutical intelligence item.

Title: {title}
Source: {item.get('source', '')}
Content: {raw}

Format:
- Core finding (1 sentence)
- Key points (2-3 bullet points)
- Industry impact (if applicable)
- End with "(AI generated)" """

    result = _call_llm(prompt, llm, model=model, max_tokens=200)
    return result


def _mock_tags(item: Dict) -> List[str]:
    """基于关键词的规则标签生成（mock/回退方案）"""
    text = f"{item.get('title', '')} {item.get('raw_summary', '')}".lower()
    tag_keywords = {
        "clinical-trial": ["clinical trial", "phase", "randomized", "study"],
        "drug-approval": ["approval", "fda approves", "approved", "nda", "bla"],
        "regulatory": ["regulatory", "fda", "ema", "submission", "review"],
        "safety": ["safety", "adverse", "side effect", "toxicity", "warning"],
        "oncology": ["cancer", "tumor", "oncology", "carcinoma", "melanoma"],
        "biotech": ["biotech", "biologics", "antibody", "biosimilar"],
        "pipeline": ["pipeline", "candidate", "discovery", "preclinical"],
        "fda": ["fda", "food and drug"],
        "biomarker": ["biomarker", "companion diagnostic", "mutation"],
    }
    tags = []
    for tag, keywords in tag_keywords.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags[:5] if tags else ["pipeline"]


def _parse_batch_result(text: str, expected_count: int) -> List[Dict]:
    """从 LLM 返回文本中解析包含 summary_zh/summary_en/tags 的 JSON 数组"""
    # 策略 1：直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    # 策略 2：提取 JSON 代码块
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, TypeError):
            pass

    # 策略 3：提取方括号内容
    bracket_match = re.search(r'\[[\s\S]*\]', text)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(0))
        except (json.JSONDecodeError, TypeError):
            pass

    # 策略 4：回退 — 将原始摘要解析结果包装为 dict
    print(f"[Summary] JSON 解析失败，回退到简单模式")
    parts = re.split(r'\n---+\n?', text)
    return [{"summary_zh": p.strip(), "summary_en": "", "tags": []} for p in parts if p.strip()]


def generate_trend_analysis(items: List[Dict], query: str, days: int, llm: str = "openai", model: str = "", mock: bool = False) -> str:
    """生成趋势分析（Deep 模式）"""
    if mock:
        return f"[Mock 趋势分析] 基于 {len(items)} 条情报的初步分析。共发现 {sum(1 for i in items if i.get('relevance_score',0)>=4)} 条高相关条目。（AI 生成）"

    high_rel = [i for i in items if i.get("relevance_score", 0) >= 3]
    if not high_rel:
        return "未发现足够高相关的条目以生成趋势分析。"

    items_json = json.dumps([{
        "title": i["title"], "source": i["source"], "date": i["date"],
        "score": i["relevance_score"], "summary": i.get("raw_summary", "")[:200]
    } for i in high_rel[:20]], ensure_ascii=False, indent=2)

    prompt = f"""你是医药行业情报分析师。基于以下情报条目，生成趋势分析报告。

查询主题：{query}
时间范围：最近 {days} 天
条目数量：{len(high_rel)}

条目列表（JSON）：
{items_json}

输出（中文）：
1. 整体趋势概述（100字）
2. 关键发现（3-5 个要点）
3. 值得关注的信号
4. 一周展望

所有分析必须基于真实数据，不得编造。末尾注明（AI 生成）。"""

    try:
        return _call_llm(prompt, llm, model=model, max_tokens=1000)
    except Exception as e:
        return f"趋势分析生成失败: {e}"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI 摘要测试")
    parser.add_argument("--input", required=True, help="输入 JSON 文件")
    parser.add_argument("--query", required=True)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    with open(args.input) as f:
        data = json.load(f)
    scored = score_relevance(data, args.query, mock=args.mock)
    summarized = generate_summaries(scored, args.query, mock=args.mock)
    print(json.dumps(summarized, ensure_ascii=False, indent=2))
