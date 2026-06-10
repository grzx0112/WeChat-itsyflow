# Entity & Relation Types

## Entity Types (12 + Other)

| Type | ID Prefix | Description | Examples |
|------|-----------|-------------|----------|
| Drug | E_ | 药物（通用名/商品名/INN/化合物编号） | Imatinib, Gleevec, 格列卫, STI-571 |
| Target | E_ | 靶点（基因产物/酶/受体/离子通道） | BCR-ABL, EGFR, PD-1, ACE2 |
| Disease | E_ | 疾病/适应症/综合征 | CML, NSCLC, Type 2 Diabetes |
| Gene | E_ | 基因名称 | ABL1, EGFR, BRAF, KRAS |
| Protein | E_ | 蛋白质（非直接靶点） | Albumin, CYP3A4 |
| Pathway | E_ | 信号通路/代谢通路 | MAPK pathway, JAK-STAT signaling |
| AdverseEvent | E_ | 不良反应/副作用/毒性 | Edema, nausea, QT prolongation |
| ClinicalTrial | E_ | 临床试验编号或描述 | NCT00048488, Phase III trial |
| Biomarker | E_ | 生物标志物/诊断指标 | BCR-ABL1 transcript, HER2+ |
| Dosage | E_ | 剂量/给药方案 | 400mg daily, IV infusion |
| Contraindication | E_ | 禁忌症/警告 | Hepatic impairment, pregnancy |
| Mechanism | E_ | 作用机制 | Tyrosine kinase inhibition |
| Other | E_ | 不属于以上类型 | — |

## Relation Types (15)

| Relation | Source → Target | Inverse | Description |
|----------|-----------------|---------|-------------|
| inhibits | Drug → Target | — | 药物抑制靶点活性 |
| activates | Drug → Target | — | 药物激活靶点 |
| treats | Drug → Disease | treated_by | 药物治疗疾病 |
| causes | Drug → AdverseEvent | caused_by | 药物引起不良反应 |
| associated_with | any → any | — | 广义关联 |
| metabolized_by | Drug → Protein | metabolizes | 药物被蛋白质代谢 |
| contraindicated_with | Drug → Contraindication | — | 药物禁忌 |
| indicated_for | Drug → Disease | — | 药物适应症 |
| resistant_to | Drug → Gene/Mechanism | — | 耐药机制 |
| sensitive_to | Drug → Biomarker | — | 敏感标志物 |
| biomarker_for | Biomarker → Disease | — | 生物标志物对应疾病 |
| combined_with | Drug → Drug | — | 联合用药 |
| precedes | any → any | follows | 时序前驱 |
| interacts_with | Drug → Drug | — | 药物相互作用 |
| participates_in | Target → Pathway | — | 靶点参与通路 |

## Node Colors (for visualization)

```
Drug:            #e74c3c (red)
Target:          #3498db (blue)
Disease:         #2ecc71 (green)
Gene:            #2980b9 (dark blue)
Protein:         #1abc9c (teal)
Pathway:         #16a085 (dark teal)
AdverseEvent:    #e67e22 (orange)
ClinicalTrial:   #9b59b6 (purple)
Biomarker:       #f1c40f (yellow)
Dosage:          #95a5a6 (gray)
Contraindication:#c0392b (dark red)
Mechanism:       #8e44ad (dark purple)
Other:           #7f8c8d (slate)
```
