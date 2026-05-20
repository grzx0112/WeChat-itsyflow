# 输出契约

## JSON 输出格式

文件名：`report.json`

```json
{
  "query": "GLP-1 receptor agonist",
  "generated_at": "2026-05-18T12:00:00Z",
  "sources_queried": ["fda", "pubmed", "news"],
  "days_back": 7,
  "total_raw": 45,
  "after_dedup": 38,
  "items": [
    {
      "title": "...",
      "source": "FDA|PubMed|BioPharma Dive|Fierce Pharma|STAT News|Endpoints News",
      "source_url": "https://...",
      "date": "2026-05-15",
      "relevance_score": 4,
      "summary_zh": "中文摘要（AI 生成）",
      "summary_en": "English summary (AI generated)",
      "tags": ["drug-approval", "oncology", "clinical-trial"]
    }
  ],
  "trend_analysis": "可选：LLM 生成的趋势分析（仅 deep 模式）"
}
```

## Markdown 输出格式

文件名：`report.md`

```markdown
# 药品情报报告：{query}
> 生成时间：{generated_at} | 回溯：{days_back} 天 | 数据源：{sources}

## 概览
- 原始条目：{total_raw}
- 去重后：{after_dedup}
- 高相关（score ≥ 3）：{high_relevance_count}

## 情报列表

### 1. {title}
- **来源**：{source} | **日期**：{date}
- **相关度**：{relevance_score}/5
- **摘要**：{summary_zh}
- **链接**：{source_url}
- **标签**：{tags}

---

（重复每条）

## 趋势分析（Deep 模式）
{trend_analysis}

---
> ⚠️ 本报告由 AI 辅助生成，数据来自公开 API/RSS。摘要标注为"AI 生成"。
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | ✅ | 条目标题 |
| source | string | ✅ | 来源标识 |
| source_url | string | ✅ | 原始链接 |
| date | string | ✅ | ISO-8601 日期 |
| relevance_score | int | ✅ | AI 相关度评分 0-5 |
| summary_zh | string | ❌ | 中文摘要（score ≥ 3 时生成） |
| summary_en | string | ❌ | 英文摘要（score ≥ 3 时生成） |
| tags | string[] | ❌ | 自动标签 |
