# Prompt 模板

## 1. 相关度评分 Prompt

```
You are a pharmaceutical intelligence analyst. Rate the relevance of the following item to the query on a scale of 0-5.

Query: "{query}"

Item:
- Title: {title}
- Source: {source}
- Date: {date}
- Abstract: {abstract}

Scoring criteria:
- 5: Directly about the query topic (drug name, mechanism, indication)
- 4: Closely related (same drug class, competing therapy, regulatory action)
- 3: Moderately related (adjacent therapeutic area, general industry trend)
- 2: Tangentially related (mentioned in passing, broader context)
- 1: Minimally related (same industry, different topic)
- 0: Not related

Respond with ONLY a single integer 0-5, no explanation.
```

## 2. 中文摘要 Prompt

```
你是一名医药行业情报分析师。请为以下条目生成结构化中文摘要（150字以内）。

查询主题：{query}

条目：
- 标题：{title}
- 来源：{source}
- 日期：{date}
- 原文摘要：{abstract}

输出格式（直接输出，不要 JSON）：
- 核心内容：一句话概述
- 关键信息：2-3 个要点
- 行业影响：对医药从业者的意义（如有）
```

## 3. 趋势分析 Prompt（Deep 模式）

```
你是一名医药行业情报分析师。基于以下去重后的情报条目，生成趋势分析报告。

查询主题：{query}
时间范围：最近 {days} 天
条目数量：{count}

条目列表（JSON）：
{items_json}

请输出以下内容（中文）：
1. 整体趋势概述（100字）
2. 关键发现（3-5 个要点，每个要点含数据支撑）
3. 值得关注的信号（潜在机会或风险）
4. 一周展望（可能的发展方向）
5. 自动标签建议（5-10 个标签）

注意：所有分析必须基于提供的真实数据，不得编造任何信息。
```

## 4. 标签生成 Prompt

```
Based on the following pharmaceutical intelligence item, suggest 3-5 tags from this controlled vocabulary:
- drug-approval, clinical-trial, regulatory, safety, oncology, immunology, cardiology, neurology,
  rare-disease, biosimilar, generic, biotech, m-a, pipeline, fda, ema, ama, pricing, reimbursement,
  manufacturing, supply-chain, digital-health, ai-ml, biomarker, companion-diagnostic, combination-therapy

Item: {title} — {abstract}

Respond with ONLY comma-separated tags, no explanation.
```
