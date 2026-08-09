---
name: mlr-review-agent
description: 医药市场合规审计 Agent（平台化，4 领域包）。输入市场合规材料（广告促销 / HCP 沟通 / KOL-MSL 医学事务 / 学术赞助），--domain 选领域，自动执行领域规则检查 + 声明证据核验（urllib 接 PubMed/Crossref）+ 法规原文溯源，输出结构化合规风险报告。基于 FDA 21 CFR Part 202 + PhRMA Code + NMPA 广告法/药品管理法/医药代表备案管理办法。
---

# mlr-review-agent — 医药市场合规审计

## Trigger boundary
Use when: 审核医药**市场合规材料**，用 `--domain` 选领域：
- `advertising` — 广告促销材料（DA/PI/宣传页）
- `hcp` — HCP 沟通/医药代表材料（话术/答客问/拜访资料）
- `kol_msl` — KOL 演讲稿/MSL 简报/医学事务材料/外部讲者 slide
- `sponsorship` — 学术赞助/congress/会议材料

Do NOT use for: 医疗建议、疗效判断、法律意见、非医药内容、反腐/阳光法案交易记录审计（本 skill 不覆盖）。

## 架构（三层平台）
- `core/` — 跨领域引擎（engine/models/scoring/report），所有领域共享评分/判定/报告
- `verify/` — 声明核验后端（urllib 接 PubMed + Crossref + 规则评分），跨领域共享，python 自核验不依赖 LLM
- `domains/` — 领域规则包（DomainChecker 接口）：advertising（基础）/ hcp / kol_msl / sponsorship（后三者继承 advertising + 特有检查）
- `references/regulations/{advertising,hcp}/` — 法规语料库（finding 可溯源到条款原文）

`review.py --domain <领域>` 路由到对应 DomainChecker。

## Agent Loop 设计

### Phase 1: Intake（材料接收与结构化）
- 接收材料文本（或 PDF/图片 OCR 提取）
- 识别产品名、通用名、适应症、目标受众、材料类型
- **判断领域**：广告促销→`advertising`；代表/话术→`hcp`；KOL/MSL→`kol_msl`；赞助/congress→`sponsorship`。不确定时默认 `advertising`。

**决策门**：材料为空/非药品 → 终止；< 50 字 → 标记"仅基础检查"。

### Phase 2: Claim Extraction（声明提取）
提取显式/隐式医学声明，分类（疗效/安全/对比/经济），标记强度（fact/comparison/superlative）。

### Phase 3: Compliance Check（领域规则检查）
按 `--domain` 调对应 DomainChecker.check()，跑该领域规则。所有领域共享：fair balance / required disclosure / prohibited-restricted claim / prescription drug rule（继承 advertising）。各领域特有检查见下"领域包"。

### Phase 4: Risk Scoring（风险评分）
汇总 findings，分级 🔴 Critical / 🟡 Major / 🟢 Minor / ℹ️ Info，计算合规评分（0-100）。

### Phase 4.5: Claim Verification（声明证据核验，opt-in）

**触发**：用户要求深度核验（`--verify` / "核验声明"），或材料含高风险待验证声明（对比/超适应症/背书）。默认不运行。

**三步纯 python 管道**（核验由 review.py 自己用 urllib 完成，**不依赖 Claude/autoresearch 泛搜索**）：

1. 规则检查 + 输出待核验清单：
   ```bash
   python3 scripts/review.py --action review --domain <领域> --verify \
     --input "<材料文本或文件>" --format json > report.json
   ```
   `report.json` 含 `claims_needs_verification`（仅高风险类）。

2. 证据核验（urllib 检索 PubMed + Crossref + 规则评分 → verdict/confidence）：
   ```bash
   python3 scripts/review.py --action verify-claims --input report.json --format json > verification.json
   ```
   单条 API 失败 → 该 claim 标 `unverifiable` + low，不阻断。

3. 机械重算判定（核验结果落回评分体系）：
   ```bash
   python3 scripts/review.py --action apply-verification \
     --input report.json --verification verification.json --format markdown
   ```
   判定规则（编码执行，非主观）：`refuted`+high → 升级 🔴 critical；`verified`+high → 降级 ℹ️ info；medium/low/`unverifiable` → 维持规则判定。

最终报告含 `## 声明核验（autoresearch）` 章节，逐条列核验结论 + 证据 + 严重度调整 + **法规原文溯源**（finding.regulation 含 clause/source/url/excerpt）。

### Phase 5: Report Generation（报告生成）
结构化合规报告（JSON + Markdown），逐条风险标记 + **法规条款原文依据**（可溯源到 references/regulations/） + 修改建议 + 执行摘要（通过/有条件通过/不通过）。

## 领域包

| 领域 | 检查覆盖 | 法规语料 |
|---|---|---|
| `advertising` | 公平平衡 / 必须披露 / 禁止-限制声明 / 处方药专项 / 中国处方药大众媒介限制 | 广告法 + 药品广告审查发布标准 + 药品管理法（中）；21 CFR 202 + FD&C 502(n)（美） |
| `hcp` | 继承 advertising（过滤大众媒介）+ 医药代表备案规范 / PhRMA 互动暗示 / 学术推广混淆 / 口头超适应症 | + 医药代表备案管理办法 + PhRMA Code |
| `kol_msl` | 继承 advertising + 讲者费/演讲酬金 / 科学准确性（亚组强结论）/ 未标注非独立推论 | 复用 PhRMA Code + 21 CFR 202 |
| `sponsorship` | 继承 advertising + 赞助推广混淆 / 未披露独立性 / 娱乐旅游赞助（PhRMA 禁止） | 复用 PhRMA Code |

## Decision Matrix（信号→优先级→动作）

| 信号 | 优先级 | 动作 |
|------|--------|------|
| 绝对化用语（"治愈""100%""根治""包治百病"） | 🔴 Critical | 直接标记 |
| 超适应症声明（含口头软话术 "may also be used for"/"还可用于"） | 🔴 Critical | 需 FDA/NMPA labeling 支持 |
| 疗效承诺（"速效""特效""一盒见效"） | 🔴 Critical | NMPA 禁止 |
| 安全性承诺（"无毒副作用""纯天然安全"） | 🔴 Critical | 误导性 |
| PhRMA 互动违规（娱乐/豪华餐饮/高额咨询费/现金赠送） | 🔴 Critical | PhRMA Code 禁止 |
| 处方药大众媒介促销（仅 advertising） | 🔴 Critical | 广告法第十六条第一款 |
| 获益/风险比 > 3:1 | 🟡 Major | 补充安全性信息 |
| 缺少通用名/批准文号/不良反应/禁忌 | 🟡 Major | NMPA/FDA 必须标注 |
| 对比声明（"优于""首选""首个"） | 🟡 Major | 需支持文献（可 --verify 核验） |
| 名人/机构背书（"院士推荐""三甲医院"） | 🟡 Major | 需核实真实性 |
| 讲者费/赞助推广混淆/亚组强结论 | 🟡 Major | PhRMA Code / 科学准确性 |
| 拼写/格式 | 🟢 Minor | 记录但不影响评分 |

## Tool 函数

```bash
# 规则审核（--domain 选领域，默认 advertising）
python3 scripts/review.py --action review --domain advertising --input "材料文本或文件" --format json

# 提取 claims / fair-balance / 评分（均支持 --domain）
python3 scripts/review.py --action extract-claims --domain hcp --input "材料"
python3 scripts/review.py --action fair-balance --domain kol_msl --input "材料"
python3 scripts/review.py --action score --domain sponsorship --input "材料"

# Phase 4.5 声明核验三步
python3 scripts/review.py --action review --domain <领域> --verify --input "材料" --format json > report.json
python3 scripts/review.py --action verify-claims --input report.json --format json > verification.json
python3 scripts/review.py --action apply-verification --input report.json --verification verification.json --format markdown
```

## 合规声明
本 Skill 生成的是 in silico 合规风险评估，不构成法律建议。声明核验基于 urllib 公开文献检索（PubMed/Crossref）+ 规则评分，可能遗漏或误判；所有 refuted 结论须经 MLR 团队人工复核。所有材料必须经有资质的 MLR 团队人工审核后方可使用。

## 参考
- FDA 21 CFR Part 202（处方药广告）/ FD&C Act §502(n)
- FDA OPDP Bad Ad Program
- PhRMA Code on Interactions with Health Care Professionals
- 《中华人民共和国广告法》（第九/十六/十七/二十八条）
- 《中华人民共和国药品管理法》（第八十九/九十/九十一条）
- 《药品广告审查发布标准》（第五/六/七/八/十/十一/十二条）
- 《医药代表备案管理办法》（2020 试行）
- NMPA《药品广告审查管理办法》
