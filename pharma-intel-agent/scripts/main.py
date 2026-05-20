#!/usr/bin/env python3
"""
pharma-intel-agent — AI 药品情报聚合工具
单入口脚本：多源抓取 → 去重 → AI 过滤 → 结构化摘要 → 输出

用法:
  python main.py --query "GLP-1" --out-dir /tmp/pharma-intel-test --days 7 --mock-llm
"""

import argparse
import json
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Windows 编码兼容：设置环境变量确保子进程也用 UTF-8
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

# 加载 .env 文件（从 scripts 目录的上一级查找）
_script_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_script_dir, "..", ".env")
if os.path.exists(_env_path):
    from dotenv import load_dotenv
    load_dotenv(_env_path, override=False)

# 将 scripts/ 目录加入 path
sys.path.insert(0, _script_dir)

from fetch_fda import fetch_fda
from fetch_pubmed import fetch_pubmed
from fetch_news import fetch_news
from dedup import dedup
from summarize import score_relevance, generate_summaries, generate_trend_analysis


def build_report(query, generated_at, sources_queried, days_back, total_raw, after_dedup, items, trend_analysis=None):
    """构建输出 JSON"""
    report = {
        "query": query,
        "generated_at": generated_at,
        "sources_queried": sources_queried,
        "days_back": days_back,
        "total_raw": total_raw,
        "after_dedup": after_dedup,
        "items": items,
    }
    if trend_analysis:
        report["trend_analysis"] = trend_analysis
    return report


def json_to_markdown(report):
    """将 JSON 报告转换为 Markdown"""
    lines = [
        f"# 药品情报报告：{report['query']}",
        f"> 生成时间：{report['generated_at']} | 回溯：{report['days_back']} 天 | 数据源：{', '.join(report['sources_queried'])}",
        "",
        "## 概览",
        f"- 原始条目：{report['total_raw']}",
        f"- 去重后：{report['after_dedup']}",
        f"- 高相关（score ≥ 3）：{sum(1 for i in report['items'] if i.get('relevance_score', 0) >= 3)}",
        "",
        "## 情报列表",
        "",
    ]

    for idx, item in enumerate(report["items"], 1):
        score = item.get("relevance_score", "N/A")
        summary = item.get("summary_zh", "") or item.get("raw_summary", "N/A")
        tags = ", ".join(item.get("tags", []))
        lines.extend([
            f"### {idx}. {item['title']}",
            f"- **来源**：{item['source']} | **日期**：{item.get('date', 'N/A')}",
            f"- **相关度**：{score}/5",
        ])
        if summary:
            lines.append(f"- **摘要**：{summary}")
        if item.get("source_url"):
            lines.append(f"- **链接**：{item['source_url']}")
        if tags:
            lines.append(f"- **标签**：{tags}")
        lines.append("")
        lines.append("---")
        lines.append("")

    if report.get("trend_analysis"):
        lines.extend([
            "## 趋势分析（Deep 模式）",
            "",
            report["trend_analysis"],
            "",
        ])

    lines.extend([
        "---",
        '> ⚠️ 本报告由 AI 辅助生成，数据来自公开 API/RSS。摘要标注为"AI 生成"。',
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="pharma-intel-agent — AI 药品情报聚合工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --query "GLP-1" --days 7 --mock-llm
  python main.py --query "PD-1" --sources fda,pubmed --deep --out-dir tmp/pd1-report
        """,
    )
    parser.add_argument("--query", required=True, help="搜索关键词（必填）")
    parser.add_argument("--sources", default="fda,pubmed,news", help="数据源选择，默认 fda,pubmed,news")
    parser.add_argument("--days", type=int, default=7, help="回溯天数，默认 7")
    parser.add_argument("--llm", default="openai", help="LLM 提供商：openai / zai / deepseek")
    parser.add_argument("--model", default=None, help="覆盖默认模型名（如 gpt-4o / glm-4-plus / deepseek-reasoner）")
    parser.add_argument("--out-dir", default=None, help="输出目录")
    parser.add_argument("--deep", action="store_true", help="启用深度分析（趋势 + 详细摘要）")
    parser.add_argument("--mock-llm", action="store_true", help="Mock LLM 调用（测试用）")
    parser.add_argument("--max-items", type=int, default=20, help="进入 LLM 评分的最大条目数，默认 20")
    parser.add_argument("--rss-file", default=None, help="自定义 RSS 源 JSON 文件路径")
    parser.add_argument("--no-expand", action="store_true", help="禁用通用名自动展开")
    args = parser.parse_args()

    # 输出目录
    if not args.out_dir:
        date_str = datetime.now().strftime("%Y-%m-%d")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.out_dir = os.path.join(script_dir, "..", "tmp", f"pharma-intel-{date_str}")
    os.makedirs(args.out_dir, exist_ok=True)

    sources = [s.strip() for s in args.sources.split(",")]
    print(f"=== pharma-intel-agent ===")
    print(f"Query: {args.query} | Sources: {sources} | Days: {args.days} | LLM: {args.llm} | Mock: {args.mock_llm}")
    print(f"Output: {args.out_dir}")
    print()

    # Step 1: 并行抓取
    all_items = []
    fetchers = {"fda": fetch_fda, "pubmed": fetch_pubmed, "news": fetch_news}

    # fetch_limit: 给去重留余量
    fetch_limit = args.max_items * 3

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for src in sources:
            fn = fetchers.get(src)
            if fn:
                if src == "fda":
                    futures[executor.submit(fn, args.query, args.days, args.no_expand)] = src
                elif src == "pubmed":
                    futures[executor.submit(fn, args.query, args.days, fetch_limit)] = src
                elif src == "news":
                    futures[executor.submit(fn, args.query, args.days, args.rss_file)] = src
                else:
                    futures[executor.submit(fn, args.query, args.days)] = src

        for future in as_completed(futures):
            src = futures[future]
            try:
                items = future.result()
                all_items.extend(items)
            except Exception as e:
                print(f"[{src}] 抓取失败: {e}")

    total_raw = len(all_items)
    print(f"\n[Total] 原始条目: {total_raw}")

    if total_raw == 0:
        print("未获取到任何数据，退出。")
        report = build_report(args.query, datetime.now().isoformat() + "Z", sources, args.days, 0, 0, [])
        with open(os.path.join(args.out_dir, "report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return

    # Step 2: 去重
    deduped = dedup(all_items)
    after_dedup = len(deduped)

    # 截断到 max_items（按日期降序排列，保留最新）
    deduped.sort(key=lambda x: x.get('date', ''), reverse=True)
    if len(deduped) > args.max_items:
        print(f"[Limit] 截断：{len(deduped)} → {args.max_items} 条（保留最新）")
        deduped = deduped[:args.max_items]

    # Step 3: AI 相关度评分
    print("\n[AI] 评分中...")
    model_override = args.model or ""
    scored = score_relevance(deduped, args.query, llm=args.llm, model=model_override, mock=args.mock_llm)

    # Step 4: AI 摘要
    print("[AI] 生成摘要...")
    summarized = generate_summaries(scored, args.query, llm=args.llm, model=model_override, mock=args.mock_llm)

    # Step 5: 趋势分析（Deep 模式）
    trend = None
    if args.deep:
        print("[AI] 生成趋势分析...")
        trend = generate_trend_analysis(summarized, args.query, args.days, llm=args.llm, model=model_override, mock=args.mock_llm)

    # Step 6: 输出
    generated_at = datetime.now().isoformat() + "Z"
    report = build_report(args.query, generated_at, sources, args.days, total_raw, after_dedup, summarized, trend)

    # 保存 JSON
    json_path = os.path.join(args.out_dir, "report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[JSON] 已保存: {json_path}")

    # 保存 Markdown
    md_path = os.path.join(args.out_dir, "report.md")
    md_content = json_to_markdown(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[MD]   已保存: {md_path}")

    # 打印摘要
    high_rel = sum(1 for i in summarized if i.get("relevance_score", 0) >= 3)
    print(f"\n=== 完成 ===")
    print(f"原始: {total_raw} → 去重: {after_dedup} → 高相关: {high_rel}")
    print(f"输出: {args.out_dir}")


if __name__ == "__main__":
    main()
