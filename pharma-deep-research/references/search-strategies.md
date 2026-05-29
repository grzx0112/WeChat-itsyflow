# 搜索策略与查询模板

> 本文档为 Step 1（补充信息收集）提供具体的搜索策略和查询模板。
> 按对象类型和搜索场景组织。

## 通用原则

1. **先窄后宽**：从精确名称开始搜，搜不到再逐步放宽（通用名→商品名→机制类名→适应症）
2. **多源交叉验证**：关键数据点至少两个独立来源确认
3. **时间敏感**：注意数据时效性，优先最新数据，标注采集日期

## 按对象类型的搜索策略

### Drug（药物）

**核心查询组合**：
```
# 临床数据
"{drug_name}" + (phase III OR pivotal OR registrational) + trial results
"{drug_name}" + ORR OR PFS OR OS + clinical trial

# 监管
"{drug_name}" + FDA approval OR EMA opinion OR NMPA
"{drug_name}" + advisory committee OR complete response letter

# 安全性
"{drug_name}" + safety OR adverse events OR black box warning
"{drug_name}" + REMS OR risk evaluation

# 商业
"{drug_name}" + peak sales OR revenue + forecast
"{drug_name}" + market share OR competitive landscape
"{drug_name}" + patent expiry OR exclusivity

# BD
"{drug_name}" + licensing deal OR partnership OR acquisition
"{drug_name}" + milestone payment OR royalty
```

**API 查询模板**：
```
# ClinicalTrials.gov
query.intr = "{drug_name}"
query.cond = "{indication}"  # 用于找同适应症竞品

# PubMed
term = "{drug_name}" AND (clinical trial[pt] OR review[pt])
term = "{drug_name}" AND (mechanism OR pharmacology)

# openFDA
search = openfda.generic_name:"{drug_name}"
search = openfda.pharm_class_epc:"{pharm_class}"  # 找同类药物
```

### Target（靶点）

**核心查询组合**：
```
# 靶点生物学
"{target_name}" + druggability OR "drug target"
"{target_name}" + structure OR crystal structure OR binding site
"{target_name}" + pathway OR signaling

# 临床验证
"{target_name}" + clinical validation OR human genetics
"{target_name}" + GWAS OR Mendelian randomization

# 管线竞争
"{target_name}" + pipeline OR "drug development"
"{target_name}" + inhibitors OR agonists OR antibodies
```

**API 查询模板**：
```
# PubMed
term = "{target_name}" AND (drug target OR druggability OR pharmacology)
term = "{target_name}" AND (clinical trial OR drug development)

# ClinicalTrials.gov（靶点名通常不出现在干预字段，用通用搜索）
query.term = "{target_name}"
```

### Indication（适应症）

**核心查询组合**：
```
# 疾病机制与指南
"{indication}" + treatment guidelines OR standard of care
"{indication}" + treatment landscape OR current therapy
"{indication}" + unmet need OR treatment gap

# 市场规模
"{indication}" + market size OR epidemiology OR prevalence
"{indication}" + incidence + forecast

# 管线
"{indication}" + pipeline OR drugs in development
"{indication}" + emerging therapies OR novel mechanisms
```

**API 查询模板**：
```
# ClinicalTrials.gov
query.cond = "{indication}"

# PubMed
term = "{indication}" AND (treatment OR therapy OR guideline)
term = "{indication}" AND (epidemiology OR burden)

# openFDA（找已批准的药物）
search = indications_and_usage:"{indication}"
```

### Company（企业）

**核心查询组合**：
```
# 财务与战略
"{company_name}" + annual report OR 10-K OR earnings
"{company_name}" + pipeline OR R&D strategy
"{company_name}" + investor presentation OR pipeline review

# BD 与合作
"{company_name}" + licensing deal OR partnership OR collaboration
"{company_name}" + acquisition OR merger

# 竞争
"{company_name}" + competitive position OR market share
"{company_name}" + vs + "{competitor_name}"
```

**API 查询模板**：
```
# ClinicalTrials.gov
query.spons = "{company_name}"

# PubMed
term = "{company_name}" AND (drug development OR clinical trial)
```

### Platform（技术平台）

**核心查询组合**：
```
# 技术验证
"{platform_name}" + proof of concept OR validation
"{platform_name}" + technology review OR benchmark
"{platform_name}" + generation OR evolution OR iteration

# 应用
"{platform_name}" + applications OR therapeutic area
"{platform_name}" + pipeline OR products

# 竞争
"{platform_name}" + vs OR comparison OR competing technology
```

## 特殊场景搜索策略

### BD 交易先例搜索

用于报告第 4.2 节"BD 交易先例"。

```
# 通用 BD 搜索
"{therapeutic_area}" + licensing deal + 2024 OR 2025
"{drug_class}" + acquisition OR partnership
"{mechanism}" + biotech deal + upfront + milestone

# 特定来源
site:evaluate.com "{topic}"
site:statnews.com "{topic}" deal
site:fiercebiotech.com "{topic}" deal OR acquisition
```

### 专利/独占期搜索

用于报告第 4.3 节"专利与独占期时间线"。

```
# FDA Orange Book（美国）
"{drug_name}" + orange book + patent + exclusivity

# EPO（欧洲）
"{drug_name}" + EPO patent + SPC + supplementary protection

# 中国
"{drug_name}" + 中国专利 OR 专利到期
"{drug_name}" + 上市药品目录集 + 专利信息
```

### 估值参考搜索

用于报告第 4.4 节"估值锚点"。

```
# 分析师报告
"{company_name}" + analyst report OR price target
"{drug_name}" + peak sales consensus OR rNPV

# 可比交易
"{therapeutic_area}" + M&A valuation multiples
"{stage}" + biotech valuation benchmark
```

## 数据源优先级

| 可信度 | 来源类型 | 示例 |
|--------|---------|------|
| 一手 | 监管机构官网 | FDA.gov, EMA.europa.eu, NMPA.gov.cn |
| 一手 | 试验注册 | ClinicalTrials.gov, chinadrugtrials.org.cn |
| 一手 | 公司披露 | SEC EDGAR, 年报, 投资者演示 |
| 二手 | 权威期刊 | NEJM, Lancet, JAMA, BMJ |
| 二手 | 行业媒体 | STAT, Endpoints, FierceBiotech |
| 二手 | 分析师报告 | Evaluate, GlobalData, IQVIA |
| 线索 | 社区/论坛 | Reddit, 患者社区, KOL 社交媒体 |

**线索级信息**可以引用但不可作为结论依据，引用时标注来源性质。
