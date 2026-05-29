#!/usr/bin/env python3
"""
pharma-deep-research 医词元工作流数据采集管线

从 ClinicalTrials.gov / PubMed / openFDA 自动拉取结构化数据，
供 pharma-deep-research SKILL 工作流的纵向/横向分析使用。

用法:
    python research_pipeline.py --type drug --name "semaglutide"
    python research_pipeline.py --type target --name "GLP1R" --out-dir tmp/glp1r
    python research_pipeline.py --type indication --name "obesity" --out-dir tmp/obesity
    python research_pipeline.py --type company --name "Novo Nordisk"
    python research_pipeline.py --type platform --name "ADC"

环境变量（可选）:
    NCBI_API_KEY — PubMed 加速密钥（3→10 req/s）
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from collections import Counter

# ── 配置 ──────────────────────────────────────────────
DELAY = 0.4
TIMEOUT = 30
MAX_RETRIES = 2
USER_AGENT = "pharma-deep-research/1.0"
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
CTGOV_BASE = "https://clinicaltrials.gov/api/v2"
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
FDA_BASE = "https://api.fda.gov/drug"


# ══════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════

def api_get(url, params=None, timeout=TIMEOUT):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                time.sleep(2 ** (attempt + 1))
                continue
            if e.code == 404:
                return None
            raise
        except Exception:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                raise
    return None


def safe_get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


def save_json(data, path):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════
# ClinicalTrials.gov API v2
# ══════════════════════════════════════════════════════

def ctgov_search(query_term=None, query_cond=None, query_intr=None,
                 query_spons=None, page_size=50, max_pages=5):
    all_studies = []
    params = {"format": "json", "pageSize": str(page_size)}

    if query_term:
        params["query.term"] = query_term
    if query_cond:
        params["query.cond"] = query_cond
    if query_intr:
        params["query.intr"] = query_intr
    if query_spons:
        params["query.spons"] = query_spons

    # CT.gov v2 在有分页时不返回 totalCount，用 countTotal=true 请求
    params["countTotal"] = "true"

    total_count = 0
    for page_idx in range(max_pages):
        if page_idx > 0:
            time.sleep(DELAY)
        data = api_get(f"{CTGOV_BASE}/studies", params)
        if not data:
            break
        studies = data.get("studies", [])
        # totalCount 仅在首次请求中返回
        if total_count == 0:
            total_count = data.get("totalCount", len(all_studies) + len(studies))
        all_studies.extend(studies)
        next_token = data.get("nextPageToken")
        if not next_token or len(studies) < page_size:
            break
        params["pageToken"] = next_token

    return {"total_count": total_count, "studies": all_studies}


def extract_trial(study):
    p = study.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    status = p.get("statusModule", {})
    design = p.get("designModule", {})
    arms = p.get("armsInterventionsModule", {})
    cond = p.get("conditionsModule", {})
    sponsor = p.get("sponsorCollaboratorsModule", {})
    elig = p.get("eligibilityModule", {})

    interventions = []
    for iv in arms.get("interventions", []):
        interventions.append({
            "type": iv.get("type"),
            "name": iv.get("name"),
        })

    return {
        "nct_id": ident.get("nctId"),
        "title": ident.get("briefTitle"),
        "status": status.get("overallStatus"),
        "phase": design.get("phases", []),
        "study_type": design.get("studyType"),
        "enrollment": safe_get(design, "enrollmentInfo", "count"),
        "start_date": safe_get(status, "startDateStruct", "date"),
        "completion_date": safe_get(status, "completionDateStruct", "date"),
        "conditions": cond.get("conditions", []),
        "interventions": interventions,
        "lead_sponsor": safe_get(sponsor, "leadSponsor", "name"),
        "sex": elig.get("sex"),
        "min_age": elig.get("minimumAge"),
    }


def summarize_trials(raw):
    trials = [extract_trial(s) for s in raw.get("studies", [])]
    phase_c = Counter()
    status_c = Counter()
    sponsor_c = Counter()
    cond_c = Counter()
    drug_c = Counter()

    for t in trials:
        for ph in (t["phase"] or ["N/A"]):
            phase_c[ph] += 1
        status_c[t["status"] or "Unknown"] += 1
        if t["lead_sponsor"]:
            sponsor_c[t["lead_sponsor"]] += 1
        for c in (t["conditions"] or []):
            cond_c[c] += 1
        for iv in (t["interventions"] or []):
            if iv.get("type") == "DRUG":
                drug_c[iv["name"]] += 1

    return {
        "total_found": raw["total_count"],
        "total_fetched": len(trials),
        "phase_distribution": dict(phase_c.most_common(10)),
        "status_distribution": dict(status_c.most_common(10)),
        "top_sponsors": sponsor_c.most_common(10),
        "top_conditions": cond_c.most_common(15),
        "top_interventions": drug_c.most_common(15),
        "trials": trials,
    }


# ══════════════════════════════════════════════════════
# PubMed E-utilities
# ══════════════════════════════════════════════════════

def pubmed_search(term, retmax=25):
    params = {
        "db": "pubmed", "term": term,
        "retmax": str(retmax), "retmode": "json", "sort": "relevance",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    time.sleep(DELAY)
    search_data = api_get(f"{PUBMED_BASE}/esearch.fcgi", params)
    if not search_data:
        return {"total_found": 0, "publications": []}

    ids = safe_get(search_data, "esearchresult", "idlist", default=[])
    total = safe_get(search_data, "esearchresult", "count", default="0")
    if not ids:
        return {"total_found": int(total), "publications": []}

    params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    time.sleep(DELAY)
    summary_data = api_get(f"{PUBMED_BASE}/esummary.fcgi", params)
    if not summary_data:
        return {"total_found": int(total), "publications": []}

    pubs = []
    result = summary_data.get("result", {})
    for uid in result.get("uids", []):
        item = result.get(uid, {})
        pubs.append({
            "pmid": uid,
            "title": item.get("title"),
            "journal": item.get("fulljournalname"),
            "pub_date": item.get("pubdate"),
            "authors": [a.get("name") for a in item.get("authors", [])[:5]],
            "doi": item.get("elocationid"),
        })

    return {"total_found": int(total), "publications": pubs}


# ══════════════════════════════════════════════════════
# openFDA
# ══════════════════════════════════════════════════════

def openfda_search(drug_name, endpoint="label", limit=5):
    name_clean = urllib.parse.quote(drug_name.strip(), safe="")
    search_q = f"openfda.brand_name:{name_clean}+OR+openfda.generic_name:{name_clean}"
    url = f"{FDA_BASE}/{endpoint}.json?search={search_q}&limit={limit}"

    time.sleep(DELAY)
    data = api_get(url)
    if not data:
        return []

    results = []
    for r in data.get("results", []):
        item = {}
        ofda = r.get("openfda", {})
        item["brand_names"] = ofda.get("brand_name", [])
        item["generic_names"] = ofda.get("generic_name", [])
        item["manufacturer"] = ofda.get("manufacturer_name", [])
        item["pharm_class"] = ofda.get("pharm_class_epc", [])
        item["route"] = ofda.get("route", [])
        item["approval_year"] = []

        if endpoint == "label":
            for date_str in ofda.get("product_ndc", []):
                pass  # NDC 不含日期，跳过
            item["indications"] = r.get("indications_and_usage", [])
            item["boxed_warning"] = r.get("boxed_warning", [])
            item["mechanism_of_action"] = r.get("mechanism_of_action", [])
            item["adverse_reactions"] = r.get("adverse_reactions", [])
            item["contraindications"] = r.get("contraindications", [])
        elif endpoint == "enforcement":
            item["recall_reason"] = r.get("reason_for_recall", "")
            item["recall_date"] = r.get("recall_initiation_date", "")
            item["classification"] = r.get("classification", "")

        results.append(item)
    return results


# ══════════════════════════════════════════════════════
# 竞品识别（三层方法学）
# ══════════════════════════════════════════════════════

def identify_competitors(drug_name, main_conditions, top_n=8):
    """
    Layer 1 — 同适应症：从 CT.gov 找同病种的不同药物
    Layer 2 — 同机制：从 openFDA 药理分类找同类
    Layer 3 — 汇总排序，按试验数加权
    """
    competitors = {}

    # Layer 1: 同适应症竞品
    for cond in main_conditions[:3]:
        time.sleep(DELAY)
        trials = ctgov_search(query_cond=cond, page_size=50, max_pages=2)
        summary = summarize_trials(trials)
        for name, count in summary["top_interventions"]:
            if name.lower() != drug_name.lower():
                if name not in competitors:
                    competitors[name] = {"indications": set(), "trial_count": 0, "sources": set()}
                competitors[name]["indications"].add(cond)
                competitors[name]["trial_count"] += count
                competitors[name]["sources"].add("同适应症")

    # Layer 2: 同机制竞品
    labels = openfda_search(drug_name, endpoint="label", limit=1)
    if labels and labels[0].get("pharm_class"):
        for pc in labels[0]["pharm_class"][:3]:
            time.sleep(DELAY)
            pc_enc = urllib.parse.quote(f'"{pc}"', safe="")
            url = f"{FDA_BASE}/label.json?search=openfda.pharm_class_epc:{pc_enc}&limit=10"
            try:
                data = api_get(url)
                if data:
                    for r in data.get("results", []):
                        gn = r.get("openfda", {}).get("generic_name", [None])
                        gn = gn[0] if gn else None
                        if gn and gn.lower() != drug_name.lower():
                            if gn not in competitors:
                                competitors[gn] = {"indications": set(), "trial_count": 0, "sources": set()}
                            competitors[gn]["sources"].add(f"同机制({pc})")
            except Exception:
                pass  # openFDA 机制搜索失败不影响整体流程

    # 过滤噪音：去除 Placebo、标准治疗对照等
    skip_names = {"placebo", "standard of care", "usual care", "active control",
                  "vehicle", "sham", "observation", "no intervention"}
    filtered = {
        k: v for k, v in competitors.items()
        if k.lower().strip() not in skip_names
    }

    # 合并大小写重复项
    merged = {}
    for name, info in filtered.items():
        key = name.lower()
        if key in merged:
            merged[key]["trial_count"] += info["trial_count"]
            merged[key]["indications"].update(info["indications"])
            merged[key]["sources"].update(info["sources"])
        else:
            merged[key] = {
                "display_name": name,
                "indications": set(info["indications"]),
                "trial_count": info["trial_count"],
                "sources": set(info["sources"]),
            }

    ranked = sorted(merged.items(), key=lambda x: x[1]["trial_count"], reverse=True)[:top_n]
    return [
        {
            "name": info["display_name"],
            "indications": list(info["indications"]),
            "trial_count": info["trial_count"],
            "identification_sources": list(info["sources"]),
        }
        for _, info in ranked
    ]


# ══════════════════════════════════════════════════════
# 对象类型管线
# ══════════════════════════════════════════════════════

def run_drug_pipeline(name, out_dir):
    print(f"[1/5] 采集 {name} 的临床试验数据...")
    trials = ctgov_search(query_intr=name, page_size=50, max_pages=5)
    trial_summary = summarize_trials(trials)
    save_json(trial_summary, os.path.join(out_dir, "clinical_trials.json"))
    print(f"   -> {trial_summary['total_found']} 项试验，获取 {trial_summary['total_fetched']} 项")

    main_conditions = [c for c, _ in trial_summary["top_conditions"][:5]]

    print(f"[2/5] 采集 PubMed 文献...")
    literature = pubmed_search(name, retmax=25)
    save_json(literature, os.path.join(out_dir, "literature.json"))
    print(f"   -> {literature['total_found']} 篇，获取 {len(literature['publications'])} 篇")

    print(f"[3/5] 采集 openFDA 监管数据...")
    labels = openfda_search(name, endpoint="label", limit=5)
    enforcements = openfda_search(name, endpoint="enforcement", limit=10)
    regulatory = {"labels": labels, "enforcements": enforcements}
    save_json(regulatory, os.path.join(out_dir, "regulatory.json"))
    print(f"   -> {len(labels)} 个标签，{len(enforcements)} 条召回")

    print(f"[4/5] 识别竞品（三层方法学）...")
    competitors = identify_competitors(name, main_conditions, top_n=8)
    save_json(competitors, os.path.join(out_dir, "competitors.json"))
    print(f"   -> {len(competitors)} 个竞品")

    report = {
        "meta": {"object_type": "drug", "object_name": name,
                 "query_time": datetime.now(timezone.utc).isoformat(),
                 "data_sources": ["clinicaltrials.gov", "pubmed", "openfda"]},
        "clinical_trials": trial_summary,
        "literature": literature,
        "regulatory": regulatory,
        "competitors": competitors,
        "main_conditions": main_conditions,
    }

    print(f"[5/5] 生成汇总...")
    save_json(report, os.path.join(out_dir, "full_report.json"))
    write_md(report, out_dir)
    return report


def run_indication_pipeline(name, out_dir):
    print(f"[1/4] 采集 {name} 的临床试验数据...")
    trials = ctgov_search(query_cond=name, page_size=50, max_pages=5)
    trial_summary = summarize_trials(trials)
    save_json(trial_summary, os.path.join(out_dir, "clinical_trials.json"))
    print(f"   -> {trial_summary['total_found']} 项试验")

    print(f"[2/4] 采集 PubMed 文献...")
    literature = pubmed_search(name, retmax=25)
    save_json(literature, os.path.join(out_dir, "literature.json"))
    print(f"   -> {literature['total_found']} 篇")

    print(f"[3/4] 构建治疗格局...")
    landscape = [{"drug": n, "trial_count": c} for n, c in trial_summary["top_interventions"][:15]]
    save_json(landscape, os.path.join(out_dir, "treatment_landscape.json"))

    report = {
        "meta": {"object_type": "indication", "object_name": name,
                 "query_time": datetime.now(timezone.utc).isoformat(),
                 "data_sources": ["clinicaltrials.gov", "pubmed"]},
        "clinical_trials": trial_summary,
        "literature": literature,
        "treatment_landscape": landscape,
    }

    print(f"[4/4] 生成汇总...")
    save_json(report, os.path.join(out_dir, "full_report.json"))
    write_md(report, out_dir)
    return report


def run_target_pipeline(name, out_dir):
    print(f"[1/3] 采集 {name} 相关临床试验...")
    trials = ctgov_search(query_term=name, page_size=50, max_pages=3)
    trial_summary = summarize_trials(trials)
    save_json(trial_summary, os.path.join(out_dir, "clinical_trials.json"))
    print(f"   -> {trial_summary['total_found']} 项试验")

    print(f"[2/3] 采集 PubMed 文献...")
    literature = pubmed_search(
        f"{name} AND (druggability OR pharmacology OR mechanism OR target)", retmax=25
    )
    save_json(literature, os.path.join(out_dir, "literature.json"))
    print(f"   -> {literature['total_found']} 篇")

    report = {
        "meta": {"object_type": "target", "object_name": name,
                 "query_time": datetime.now(timezone.utc).isoformat(),
                 "data_sources": ["clinicaltrials.gov", "pubmed"]},
        "clinical_trials": trial_summary,
        "literature": literature,
    }

    print(f"[3/3] 生成汇总...")
    save_json(report, os.path.join(out_dir, "full_report.json"))
    write_md(report, out_dir)
    return report


def run_company_pipeline(name, out_dir):
    print(f"[1/4] 采集 {name} 申办的临床试验...")
    trials = ctgov_search(query_spons=name, page_size=50, max_pages=5)
    trial_summary = summarize_trials(trials)
    save_json(trial_summary, os.path.join(out_dir, "clinical_trials.json"))
    print(f"   -> {trial_summary['total_found']} 项试验")

    print(f"[2/4] 采集 PubMed 文献...")
    literature = pubmed_search(name, retmax=20)
    save_json(literature, os.path.join(out_dir, "literature.json"))

    print(f"[3/4] 提取管线概况...")
    pipeline = {}
    for t in trial_summary["trials"]:
        for cond in (t["conditions"] or ["Unknown"]):
            if cond not in pipeline:
                pipeline[cond] = {"phases": Counter(), "trials": []}
            for ph in (t["phase"] or ["N/A"]):
                pipeline[cond]["phases"][ph] += 1
            pipeline[cond]["trials"].append(t["nct_id"])

    pipeline_list = [
        {"indication": cond, "phases": dict(info["phases"]),
         "trial_count": len(info["trials"])}
        for cond, info in sorted(
            pipeline.items(),
            key=lambda x: sum(x[1]["phases"].values()),
            reverse=True,
        )[:20]
    ]
    save_json(pipeline_list, os.path.join(out_dir, "pipeline.json"))

    report = {
        "meta": {"object_type": "company", "object_name": name,
                 "query_time": datetime.now(timezone.utc).isoformat(),
                 "data_sources": ["clinicaltrials.gov", "pubmed"]},
        "clinical_trials": trial_summary,
        "literature": literature,
        "pipeline": pipeline_list,
    }

    print(f"[4/4] 生成汇总...")
    save_json(report, os.path.join(out_dir, "full_report.json"))
    write_md(report, out_dir)
    return report


def run_platform_pipeline(name, out_dir):
    print(f"[1/3] 采集 {name} 相关临床试验...")
    trials = ctgov_search(query_term=name, page_size=50, max_pages=3)
    trial_summary = summarize_trials(trials)
    save_json(trial_summary, os.path.join(out_dir, "clinical_trials.json"))
    print(f"   -> {trial_summary['total_found']} 项试验")

    print(f"[2/3] 采集 PubMed 文献...")
    literature = pubmed_search(name, retmax=25)
    save_json(literature, os.path.join(out_dir, "literature.json"))

    report = {
        "meta": {"object_type": "platform", "object_name": name,
                 "query_time": datetime.now(timezone.utc).isoformat(),
                 "data_sources": ["clinicaltrials.gov", "pubmed"]},
        "clinical_trials": trial_summary,
        "literature": literature,
    }

    print(f"[3/3] 生成汇总...")
    save_json(report, os.path.join(out_dir, "full_report.json"))
    write_md(report, out_dir)
    return report


# ══════════════════════════════════════════════════════
# Markdown 数据摘要（供 SKILL 分析用的中间产物）
# ══════════════════════════════════════════════════════

def write_md(report, out_dir):
    meta = report["meta"]
    lines = [
        f"# 数据采集摘要：{meta['object_name']}（{meta['object_type']}）",
        f"",
        f"- 采集时间：{meta['query_time'][:19]}",
        f"- 数据源：{', '.join(meta['data_sources'])}",
        "",
    ]

    ct = report.get("clinical_trials", {})
    if ct:
        lines += ["## 临床试验",
                   f"- 总数：{ct.get('total_found', 'N/A')}",
                   f"- 获取：{ct.get('total_fetched', 'N/A')}", ""]
        lines.append("### 阶段分布")
        for ph, n in ct.get("phase_distribution", {}).items():
            lines.append(f"- {ph}: {n}")
        lines.append("### 主要申办方")
        for s, n in (ct.get("top_sponsors", []) or []):
            lines.append(f"- {s}: {n}")
        lines.append("### 主要适应症")
        for c, n in (ct.get("top_conditions", []) or []):
            lines.append(f"- {c}: {n}")
        lines.append("")

    lit = report.get("literature", {})
    if lit:
        lines += ["## 文献", f"- 总数：{lit.get('total_found', 'N/A')}", ""]

    reg = report.get("regulatory", {})
    if reg:
        lines.append("## 监管数据")
        lines.append(f"- 标签：{len(reg.get('labels', []))}")
        lines.append(f"- 召回：{len(reg.get('enforcements', []))}")
        if reg.get("labels"):
            lb = reg["labels"][0]
            if lb.get("pharm_class"):
                lines.append(f"- 药理分类：{', '.join(lb['pharm_class'])}")
            if lb.get("boxed_warning"):
                lines.append("- [!] 含黑框警示")
        lines.append("")

    comp = report.get("competitors", [])
    if comp:
        lines += ["## 竞品", "", "| 名称 | 试验数 | 来源 |",
                   "|------|--------|------|"]
        for c in comp:
            lines.append(f"| {c['name']} | {c['trial_count']} | {', '.join(c['identification_sources'])} |")
        lines.append("")

    pipe = report.get("pipeline", [])
    if pipe:
        lines += ["## 管线", "", "| 适应症 | 阶段 | 试验数 |",
                   "|--------|------|--------|"]
        for p in pipe:
            phases = ", ".join(f"{k}:{v}" for k, v in p["phases"].items())
            lines.append(f"| {p['indication']} | {phases} | {p['trial_count']} |")
        lines.append("")

    tl = report.get("treatment_landscape", [])
    if tl:
        lines += ["## 治疗格局", "", "| 药物 | 试验数 |",
                   "|------|--------|"]
        for t in tl:
            lines.append(f"| {t['drug']} | {t['trial_count']} |")
        lines.append("")

    path = os.path.join(out_dir, "data_summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"   -> 摘要：{path}")


# ══════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════

PIPELINES = {
    "drug": run_drug_pipeline,
    "target": run_target_pipeline,
    "indication": run_indication_pipeline,
    "company": run_company_pipeline,
    "platform": run_platform_pipeline,
}


def main():
    ap = argparse.ArgumentParser(description="pharma-deep-research 数据采集管线")
    ap.add_argument("--type", required=True, choices=list(PIPELINES.keys()),
                    help="研究对象类型")
    ap.add_argument("--name", required=True, help="研究对象名称（英文名优先）")
    ap.add_argument("--out-dir", default=None, help="输出目录")
    args = ap.parse_args()

    out_dir = args.out_dir or f"tmp/deep-research-{args.name.lower().replace(' ', '-')}"
    os.makedirs(out_dir, exist_ok=True)

    print(f"{'=' * 50}")
    print(f"pharma-deep-research 数据采集")
    print(f"对象：{args.name}（{args.type}）")
    print(f"输出：{out_dir}")
    print(f"{'=' * 50}\n")

    report = PIPELINES[args.type](args.name, out_dir)

    print(f"\n{'=' * 50}")
    print(f"完成！")
    print(f"  完整数据：{os.path.join(out_dir, 'full_report.json')}")
    print(f"  摘要：{os.path.join(out_dir, 'data_summary.md')}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
