# pharma-intel-agent

AI 药品情报聚合工具 — 多源自动抓取 + AI 过滤 + 双语摘要 + 结构化报告。

输入关键词（药物名/靶点/适应症），自动从 FDA、PubMed、医药 RSS 并行抓取，经 AI 相关度评分后生成中英双语情报快报。

## 快速开始

```bash
# 1. 安装依赖
pip install requests feedparser

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY

# 3. 运行
python scripts/main.py --query "GLP-1" --days 7
```

输出默认保存到 `scripts/../tmp/pharma-intel-<日期>/`，含 `report.json` 和 `report.md`。

## 使用示例

```bash
# Quick 模式 — 当周情报快报（默认）
python scripts/main.py --query "PD-1" --days 7

# Deep 模式 — 含趋势分析
python scripts/main.py --query "ADC" --days 14 --deep

# 仅查询 FDA 和 PubMed
python scripts/main.py --query "HER2" --sources fda,pubmed

# 使用智谱 LLM
python scripts/main.py --query "BCMA" --llm zai

# 使用 DeepSeek
python scripts/main.py --query "KRAS" --llm deepseek

# 指定具体模型名（覆盖默认）
python scripts/main.py --query "PD-1" --llm openai --model gpt-4o
python scripts/main.py --query "PD-1" --llm deepseek --model deepseek-reasoner
python scripts/main.py --query "PD-1" --llm zai --model glm-4-plus

# 自定义 RSS 源
python scripts/main.py --query "KRAS" --rss-file feeds-example.json

# 禁用通用名展开（直接用原始查询词）
python scripts/main.py --query "sotorasib" --no-expand

# 无 LLM 测试（不需要 API key）
python scripts/main.py --query "GLP-1" --days 7 --mock-llm
```

## 全部参数

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--query` | ✅ | — | 搜索关键词（药物名/靶点/适应症） |
| `--sources` | ❌ | `fda,pubmed,news` | 数据源，逗号分隔 |
| `--days` | ❌ | `7` | 回溯天数 |
| `--llm` | ❌ | `openai` | LLM 提供商：`openai` / `zai` / `deepseek` |
| `--model` | ❌ | 各提供商默认值 | 覆盖默认模型名（如 `gpt-4o` / `deepseek-reasoner` / `glm-4-plus`） |
| `--out-dir` | ❌ | 自动生成 | 输出目录 |
| `--deep` | ❌ | 关闭 | 启用深度趋势分析 |
| `--max-items` | ❌ | `20` | LLM 评分的最大条目数 |
| `--mock-llm` | ❌ | 关闭 | Mock LLM（测试用，无需 API key） |
| `--rss-file` | ❌ | — | 自定义 RSS 源 JSON 文件 |
| `--no-expand` | ❌ | 关闭 | 禁用通用名自动展开 |

## 环境变量配置

复制 `.env.example` 为 `.env` 并填入实际值：

```bash
cp .env.example .env
```

### OpenAI（默认）

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1    # 可选，支持兼容 API
OPENAI_MODEL=gpt-4o-mini                      # 可选
```

`OPENAI_BASE_URL` 支持任何 OpenAI 兼容的 API 端点（如 Azure OpenAI、vLLM、Ollama 等），方便切换不同 LLM 服务。

### 智谱 ZAI

```env
ZAI_API_KEY=xxxxxxxxxxxxxxxx
ZAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZAI_MODEL=glm-4-flash
```

使用时加 `--llm zai` 参数。

### DeepSeek

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

使用时加 `--llm deepseek` 参数。如未设置 `DEEPSEEK_API_KEY`，会回退到 `OPENAI_API_KEY`。

### NCBI（可选）

```env
NCBI_API_KEY=xxxxxxxxxxxxxxxx
```

可将 PubMed 查询速率从 3 req/s 提升到 10 req/s。申请地址：https://www.ncbi.nlm.nih.gov/account/settings/

## 自定义 RSS 源

创建 JSON 文件，格式为 `{"源名称": "RSS URL"}`：

```json
{
  "Pharma Times": "https://www.pharmatimes.com/rss/default.aspx",
  "MedCity News": "https://medcitynews.com/feed/"
}
```

也支持数组格式：

```json
[
  {"name": "Pharma Times", "url": "https://www.pharmatimes.com/rss/default.aspx"}
]
```

运行时通过 `--rss-file` 指定，自定义源会与内置 7 个默认源合并（同名则覆盖）。

## 通用名自动展开

查询靶点/药物类别时，自动展开为具体的 FDA 可查药品通用名：

```
"GLP-1" → semaglutide, liraglutide, tirzepatide, dulaglutide, exenatide, lixisenatide
"PD-1"  → pembrolizumab, nivolumab, cemiplimab, sintilimab
"KRAS"  → sotorasib, adagrasib
```

**三层 fallback 机制：**

1. **内置映射表**（零延迟）— 覆盖 40+ 常见靶点/药物类别
2. **openFDA 反查** — 通过 FDA API 自动发现关联药品
3. **ChEMBL API** — 通过靶点→药物映射查找已批准药物

不在映射表中的查询词会自动走 fallback，无需手动维护。`--no-expand` 可禁用此功能。

## 输出格式

### report.json

```json
{
  "query": "GLP-1",
  "generated_at": "2026-05-20T12:00:00Z",
  "sources_queried": ["fda", "pubmed", "news"],
  "days_back": 7,
  "total_raw": 75,
  "after_dedup": 59,
  "items": [
    {
      "title": "...",
      "source": "FDA|PubMed|BioPharma Dive|...",
      "source_url": "https://...",
      "date": "2026-05-15",
      "relevance_score": 4,
      "summary_zh": "中文摘要（AI 生成）",
      "summary_en": "English summary (AI generated)",
      "tags": ["drug-approval", "oncology"]
    }
  ],
  "trend_analysis": "趋势分析文本（仅 deep 模式）"
}
```

### report.md

人类可读的 Markdown 报告，含概览统计和逐条情报列表。

## 处理流程

```
query 输入
  ├─ 通用名展开（三层 fallback）
  ├─ 并行抓取（FDA + PubMed + RSS）
  ├─ 去重标准化（URL + 标题相似度 ≥ 0.8）
  ├─ AI 相关度评分（LLM 批量 0-5）
  ├─ AI 双语摘要 + 自动标签（score ≥ 3）
  ├─ [Deep] 趋势分析
  └─ 输出报告（JSON + Markdown）
```

## 文件结构

```
pharma-intel-agent/
├── SKILL.md              # Skill 定义（OpenClaw 格式）
├── README.md             # 本文件
├── .env.example          # 环境变量模板
├── requirements.txt      # Python 依赖
├── feeds-example.json    # 自定义 RSS 源模板
├── references/
│   ├── data-sources.md   # 数据源清单 + API 端点
│   ├── output-contract.md # 输出格式规范
│   └── prompt-templates.md # AI prompt 模板
└── scripts/
    ├── main.py           # 单入口脚本
    ├── name_expand.py    # 通用名动态展开
    ├── fetch_fda.py      # FDA openFDA 抓取
    ├── fetch_pubmed.py   # PubMed 抓取
    ├── fetch_news.py     # RSS 新闻聚合
    ├── dedup.py          # 去重标准化
    └── summarize.py      # AI 评分 + 摘要 + 标签
```

## 许可证

Apache 2.0
