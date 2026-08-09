---
name: drug-comparison-agent
description: 多药横向竞品对比（药品对比/选药/竞品分析/商业分析）。输入 2–6 个药名（品牌或通用名），用 openFDA + ClinicalTrials.gov 拉数据装配对比矩阵（档案/适应症+机制/在研管线/关键终点/安全概览），再用 DeepSeek 生成可溯源的定位洞察报告（机制差异化/适应症护城河/管线领先者/空白机会），每条结论强制 [来源:N] 引用并经后置校验。触发词：药品对比、竞品对比、选药分析、药物比较、竞品分析、drug comparison、competitive analysis、head-to-head、GLP-1 对比、同类药对比、机制对比、管线对比、某药 vs 某药。
---

# Drug Comparison Agent

**多药进 → 竞品对比矩阵 + 定位洞察出。**

输入 2–6 个药名，用公开 API 做**横向竞品对比**：openFDA 取档案/适应症/机制/黑框警告/FAERS 不良反应，ClinicalTrials.gov 取在研管线/关键终点，装配成对比矩阵；再用 DeepSeek 基于**矩阵接地**生成定位洞察（机制差异化 / 适应症护城河 / 管线领先者 / 空白机会），**每条结论强制 `[来源:N]` 引用并经后置校验器核对**，无据论断标红剔除。

## 核心机制：矩阵接地 + 引用校验（防臆测）

```
药名 → openFDA + CT.gov → 对比矩阵（每 cell 带 source）
                          ↓
          DeepSeek 只看矩阵 → 定位洞察（每条带 [来源:N]）
                          ↓
          后置校验器核对引用真实性 → 标红/剔除无据论断
```

## API Requirements

| Database | Key Required? | Notes |
|----------|---------------|-------|
| openFDA (Label/NDC/FAERS) | ❌（建议申请 API Key 提额） | 公开匿名 |
| ClinicalTrials.gov v2 | ❌ | 公开 |
| DeepSeek | ✅ `DEEPSEEK_API_KEY` | 写入 skill 根目录 `.env`（复制 `.env.example`），启动自动加载；未设则输出矩阵摘要 |

**数据层零第三方依赖（纯标准库 urllib/json）。** Cost: $0（除 LLM）。

## Usage

```bash
# CLI
python scripts/pipeline.py --drugs "Ozempic,Wegovy,Mounjaro,Zepbound" --out-dir ./output

# 或 stdin JSON
echo '{"drugs":["Ozempic","Wegovy"]}' | python scripts/pipeline.py
```

> 配置：把 DeepSeek key 写入 skill 根目录 `.env`（复制 `.env.example` 改），启动自动加载，无需手动 `export`；系统 env 已设的同名变量优先。

输出：
- `comparison-matrix.json` — 结构化矩阵（每 cell 带 sources）
- `comparison-report.md` — 中文报告：对比矩阵表 + LLM 定位洞察 + ⚠️未验证论断（若有）

## Output

对比矩阵 5 维度：① 基本档案+上市状态 ② 适应症+机制 ③ 全球在研管线 ④ 关键临床终点 ⑤ 安全概览。

洞察 4 小节：机制差异化 / 适应症护城河 / 管线领先者 / 空白机会。

## Limitations

- 上市格局默认 US（openFDA）。
- 「机制」取自 Label 药理文本，非结构化靶点。
- 限速：openFDA 匿名 ~240 req/min；脚本内置 retry + 0.2s 节流。
- 报告供竞品分析参考，**非临床决策依据**。

## 数据源字段清单

见 `references/api-fields.md`。
