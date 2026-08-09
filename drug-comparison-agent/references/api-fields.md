# drug-comparison-agent 用到的 API 字段



## openFDA Drug Label API
- `GET https://api.fda.gov/drug/label.json?search=openfda.brand_name:"<药>"+OR+openfda.generic_name:"<通用名>"&limit=1`
- 取用：`indications_and_usage`（适应症）、`mechanism_of_action`（机制）、`boxed_warning`（黑框警告，存在即 yes）

## openFDA Drug NDC API
- `GET https://api.fda.gov/drug/ndc.json?search=brand_name:"<药>"+OR+generic_name:"<药>"&limit=1`
- 取用：`generic_name`、`brand_name`、`dosage_form`、`marketing_status`
- 用途：Stage 0 名字标准化 + Stage 1 基本档案

## openFDA Drug Event (FAERS)
- `GET https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:"<通用名>"&count=patient.reaction.reactionmeddrapt.exact&limit=8`
- 取用：top 高频不良反应（MedDRA PT）

## ClinicalTrials.gov API v2
- `GET https://clinicaltrials.gov/api/v2/studies?query.intervention=<药>&pageSize=100`
- Stage 3 管线聚合：`protocolSection.designModule.phases` × `statusModule.overallStatus` × `conditionsModule.conditions`
- Stage 4 终点：III/IV 期 `protocolSection.outcomesModule.primaryOutcomes[].measure`
