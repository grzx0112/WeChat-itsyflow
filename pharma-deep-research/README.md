# pharma-deep-research

医药横纵分析法深度研究 Skill。对药物、靶点、适应症、企业、技术平台做系统性研究——纵轴沿医药全生命周期追因果链，横轴做竞品证据包对比，交叉产出格局演变判断与未来三剧本。

## 核心方法论

**纵轴**追时间深度（因果链叙事），**横轴**追同期广度（证据包对比），**交叉**出新判断。

适配医药领域：
- 纵轴 = 全生命周期因果链（靶点发现 → 临床 → 监管 → 上市后 → 竞争反应）
- 横轴 = 多维证据包横向比较（疗效终点 / 安全性 / 标签 / 可及性 / 商业）

## 工作流

```
Step 0  脚本数据采集（CT.gov + PubMed + openFDA）
Step 1  联网补充信息收集（行业报告、管理层表态、监管争议）
Step 2  纵向分析（全生命周期因果链叙事）
Step 3  横向分析（三层竞品识别 + 证据包对比矩阵）
Step 4  横纵交汇洞察（历史路径 → 拐点 → 未来三剧本）
Step 5  输出报告（8000-20000 字中文研报）
```

## 快速开始

```bash
# 运行数据采集管线
python skills/pharma-deep-research/scripts/research_pipeline.py \
  --type {drug|target|indication|company|platform} \
  --name "对象英文名" \
  --out-dir tmp/deep-research-<slug>

# 示例
python skills/pharma-deep-research/scripts/research_pipeline.py \
  --type drug --name "semaglutide"
```

### 输出文件

| 文件 | 内容 |
|------|------|
| `full_report.json` | 完整结构化数据（临床试验 / 文献 / 监管 / 竞品） |
| `data_summary.md` | 数据采集摘要 |
| `clinical_trials.json` | ClinicalTrials.gov 试验数据 |
| `literature.json` | PubMed 文献数据 |
| `regulatory.json` | openFDA 监管数据（标签 + 召回） |
| `competitors.json` | 三层方法学竞品识别结果 |

脚本产出原始数据，之后的 Step 1-4 分析由 Claude 完成。

## 支持的对象类型

| 类型 | 纵向重点 | 横向重点 |
|------|---------|---------|
| `drug` | 靶点机制 → 临床各期 → 监管审评 → 上市后演变 | 同机制 + 同适应症竞品对比 |
| `target` | 发现史 → 通路验证 → 成药性评估 → 管线竞争 | 技术路线分歧（小分子 vs 抗体 vs 其他） |
| `indication` | SoC 演进 → 指南变化 → 关键证据 → 未满足需求 | 治疗格局中各疗法对比 |
| `company` | 战略演进 → 管线布局 → BD/融资 → 竞争位置 | 同领域企业对标 |
| `platform` | 技术代际 → 验证里程碑 → 工程边界 → 扩展潜力 | 竞品平台对比 |

## 数据源

| 维度 | 数据源 | 用途 |
|------|--------|------|
| 临床试验 | ClinicalTrials.gov API v2 | 试验设计 / 终点 / 阶段 / 状态 |
| 文献 | PubMed E-utilities | 机制证据 / 临床结果 / 综述 |
| 监管标签 | openFDA Drug Label | 适应症 / 黑框警示 / 给药方案 |
| 安全召回 | openFDA Enforcement | 召回记录 / 安全警报 |
| 竞品机制 | openFDA pharm_class | 同药理分类药物发现 |

可选：设置 `NCBI_API_KEY` 环境变量可将 PubMed 查询频率从 3 次/秒提升至 10 次/秒。

## 目录结构

```
pharma-deep-research/
├── SKILL.md                        # 技能定义（YAML frontmatter + 工作流指令）
├── README.md                       # 本文件
├── scripts/
│   └── research_pipeline.py        # 数据采集管线（纯标准库，零外部依赖）
├── references/
│   ├── search-strategies.md        # 搜索策略与 API 查询模板
│   └── report-template.md          # 8000-20000 字研报结构模板
└── evals/
    └── evals.json                  # 质量评估用例（3 个典型场景）
```

## 写作风格

- 叙事驱动：用故事线串联数据，不是数据堆砌
- 敢下判断：有明显倾向时直接说，不和稀泥
- 数字先行：用具体数字而非形容词（"ORR 45%" 而不是"疗效显著"）
- 搜不到就写搜不到：不确定就标注可信度等级

## 许可证

Apache 2.0
