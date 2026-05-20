---
name: pharma-intel-agent
description: >
  AI 药品情报聚合 Skill — 多源自动抓取 + AI 过滤 + 结构化摘要。
  输入关键词（药物名/靶点/适应症），自动从 FDA openFDA、PubMed、医药 RSS 新闻
  并行抓取，去重后经 LLM 相关度评分和中英双语摘要生成，输出 JSON + Markdown 情报快报。
  支持 Deep 模式（趋势分析）和 mock 模式（无 LLM 测试）。
  当用户提到以下场景时触发本 skill：药品情报、药物资讯聚合、pharma intelligence、
  AI 情报监控、药品监控、药物监控、FDA 动态、PubMed 监控、医药新闻聚合、
  pharma intel、drug pipeline news、drug news roundup、
  药物新闻周报、药品动态追踪、竞品情报、医药热点追踪。
  即使没有明确说"情报聚合"，只要用户想了解某药物/靶点/领域的最新动态、新闻、
  FDA 审批进展或文献更新，都应使用本 skill。
metadata:
  openclaw:
    requires:
      env:
        - OPENAI_API_KEY
      optional-env:
        - ZAI_API_KEY
        - ZAI_BASE_URL
        - DEEPSEEK_API_KEY
        - DEEPSEEK_BASE_URL
        - NCBI_API_KEY
---

# pharma-intel-agent

> AI 药品情报聚合 — 多源抓取 → 去重 → AI 过滤 → 双语摘要 → 报告输出

## 快速开始

```bash
# Quick 模式（默认）— 当周情报快报
python scripts/main.py --query "GLP-1" --out-dir tmp/pharma-intel-2026-05-20 --days 7

# Deep 模式 — 含趋势分析
python scripts/main.py --query "PD-1" --out-dir tmp/pharma-intel-2026-05-20 --days 14 --deep

# 无 LLM 测试
python scripts/main.py --query "ADC" --days 7 --mock-llm

# 使用智谱 LLM
python scripts/main.py --query "HER2" --llm zai --days 7

# 自定义 RSS 源
python scripts/main.py --query "BCMA" --rss-file my-feeds.json --days 7
```

## 参数

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--query` | ✅ | — | 搜索关键词（药物名/靶点/适应症） |
| `--sources` | ❌ | `fda,pubmed,news` | 数据源选择，逗号分隔 |
| `--days` | ❌ | `7` | 回溯天数 |
| `--llm` | ❌ | `openai` | LLM 提供商：`openai` / `zai` / `deepseek` |
| `--model` | ❌ | 各提供商默认值 | 覆盖默认模型名（如 `gpt-4o` / `deepseek-reasoner` / `glm-4-plus`） |
| `--out-dir` | ❌ | 自动生成 | 输出目录 |
| `--deep` | ❌ | 关闭 | 启用深度分析（趋势 + 详细摘要） |
| `--max-items` | ❌ | `20` | 进入 LLM 评分的最大条目数 |
| `--mock-llm` | ❌ | 关闭 | Mock LLM 调用（测试用，无需 API key） |
| `--rss-file` | ❌ | — | 自定义 RSS 源 JSON 文件路径 |
| `--no-expand` | ❌ | 关闭 | 禁用通用名自动展开（仅用原始查询） |

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | ✅（非 mock） | OpenAI API 密钥 |
| `OPENAI_BASE_URL` | ❌ | 自定义 API 地址（默认 `https://api.openai.com/v1`） |
| `OPENAI_MODEL` | ❌ | 模型名（默认 `gpt-4o-mini`） |
| `ZAI_API_KEY` | ❌ | 智谱 API 密钥（`--llm zai` 时使用） |
| `ZAI_BASE_URL` | ❌ | 智谱 API 地址（默认 `https://open.bigmodel.cn/api/paas/v4`） |
| `ZAI_MODEL` | ❌ | 智谱模型（默认 `glm-4-flash`） |
| `DEEPSEEK_API_KEY` | ❌ | DeepSeek API 密钥（`--llm deepseek` 时使用） |
| `DEEPSEEK_BASE_URL` | ❌ | DeepSeek API 地址（默认 `https://api.deepseek.com/v1`） |
| `DEEPSEEK_MODEL` | ❌ | DeepSeek 模型（默认 `deepseek-chat`） |
| `NCBI_API_KEY` | ❌ | NCBI API key（加速 PubMed 查询：3→10 req/s） |

## 依赖安装

```bash
pip install requests feedparser
```

## 通用名自动展开

当查询词是靶点/药物类别（如 `GLP-1`、`PD-1`）时，自动展开为具体的 FDA 可查药品通用名。
采用三层 fallback 机制，无需手动维护：

```
查询词 "X"
  ├─ 第1层：内置映射表（零延迟快速路径）
  ├─ 第2层：openFDA openfda 反查（免费 API 自动发现）
  └─ 第3层：ChEMBL API 靶点→药物映射
```

用 `--no-expand` 可禁用展开，仅使用原始查询词。

## 流程

```
query 输入
  │
  ├─ 通用名展开（三层 fallback）
  │
  ├─ 并行抓取（FDA + PubMed + RSS News + 自定义源）
  │
  ├─ 去重标准化（URL 去重 + 标题相似度 ≥ 0.8）
  │
  ├─ AI 相关度评分（LLM 批量打分 0-5）
  │
  ├─ AI 双语摘要 + 自动标签（score ≥ 3）
  │
  ├─ [Deep] 趋势分析
  │
  └─ 输出报告（JSON + Markdown）
```

## Non-negotiables

1. 所有数据必须来自真实 API/RSS，不允许编造任何条目
2. 必须标注每条情报的来源（source）和时间（date）
3. AI 摘要必须注明是 AI 生成
4. 去重必须覆盖跨源重复（标题相似度 ≥ 0.8）
5. `summary_en` 必须是 AI 生成的真实英文摘要，而非 raw_summary 截断

## 输出

- `report.json` — 结构化 JSON 报告
- `report.md` — Markdown 可读报告
- 详见 [output-contract.md](references/output-contract.md)

## 文件结构

```
skills/pharma-intel-agent/
├── SKILL.md
├── requirements.txt
├── references/
│   ├── data-sources.md
│   ├── output-contract.md
│   └── prompt-templates.md
├── scripts/
│   ├── main.py          # 单入口
│   ├── fetch_fda.py      # FDA openFDA 抓取
│   ├── fetch_pubmed.py   # PubMed E-utilities 抓取
│   ├── fetch_news.py     # RSS 新闻聚合
│   ├── name_expand.py    # 通用名动态展开（新增）
│   ├── dedup.py          # 去重标准化
│   └── summarize.py      # AI 评分 + 摘要 + 标签
└── tmp/                  # 运行时输出（.gitignore）
```

## 参考

- [data-sources.md](references/data-sources.md) — 数据源清单 + API 端点 + 配额
- [output-contract.md](references/output-contract.md) — 输出格式规范
- [prompt-templates.md](references/prompt-templates.md) — AI 过滤/摘要 prompt 模板
