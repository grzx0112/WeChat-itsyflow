#!/usr/bin/env python3
"""
pharma-wiki query: graph traversal + LLM-based Q&A

Usage:
  python3 scripts/query.py <project_root> "question" [--mock]
"""

import json
import sys
import os
import re
import urllib.request
from pathlib import Path
from collections import deque

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_MODEL = os.environ.get("KG_EXTRACT_MODEL", "gpt-4o-mini")
DEFAULT_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def find_entity(entities: dict, query: str) -> list[str]:
    """Find entity IDs matching a query string (name or alias)."""
    query_lower = query.lower().strip()
    matches = []
    for eid, ent in entities.items():
        if ent["name"].lower() == query_lower:
            matches.append(eid)
        elif query_lower in [a.lower() for a in ent.get("aliases", [])]:
            matches.append(eid)
        elif query_lower in ent["name"].lower():
            matches.append(eid)
    return list(set(matches))


def get_entity_relations(relations: dict, eid: str) -> list[dict]:
    """Get all relations involving an entity."""
    result = []
    for rid, rel in relations.items():
        if rel["source"] == eid or rel["target"] == eid:
            result.append(rel)
    return result


def find_paths(relations: dict, start_eid: str, end_eid: str, max_depth: int = 5) -> list[list[str]]:
    """BFS to find paths between two entities. Returns list of entity ID paths."""
    # Build adjacency list
    adj = {}
    for rid, rel in relations.items():
        adj.setdefault(rel["source"], []).append((rel["target"], rel["relation"]))
        adj.setdefault(rel["target"], []).append((rel["source"], f"_{rel['relation']}"))

    paths = []
    queue = deque([(start_eid, [start_eid])])
    visited = {start_eid}

    while queue:
        current, path = queue.popleft()
        if len(path) > max_depth:
            continue
        if current == end_eid:
            paths.append(path)
            continue
        for neighbor, _ in adj.get(current, []):
            if neighbor not in visited or neighbor == end_eid:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return paths[:5]  # Return top 5 paths


def format_subgraph(entities: dict, relations: dict, eids: set[str]) -> str:
    """Format a subgraph as readable text for LLM context."""
    lines = ["## Knowledge Graph Data\n"]
    lines.append("### Entities:")
    for eid in eids:
        if eid in entities:
            ent = entities[eid]
            aliases = ", ".join(ent.get("aliases", []))
            lines.append(f"- [{ent['type']}] {ent['name']} (aliases: {aliases})")
            if ent.get("description"):
                lines.append(f"  Description: {ent['description']}")

    lines.append("\n### Relations:")
    for rid, rel in relations.items():
        if rel["source"] in eids and rel["target"] in eids:
            src_name = entities.get(rel["source"], {}).get("name", rel["source"])
            tgt_name = entities.get(rel["target"], {}).get("name", rel["target"])
            lines.append(f"- {src_name} —[{rel['relation']}]→ {tgt_name}")
            if rel.get("description"):
                lines.append(f"  Evidence: {rel['description']}")

    return "\n".join(lines)


def detect_query_type(question: str) -> str:
    """Detect the type of question."""
    q = question.lower()
    if any(w in q for w in ["路径", "path", "怎么到", "如何到", "from"]):
        return "path"
    if any(w in q for w in ["哪些", "什么", "what", "which", "all"]):
        return "expand"
    if any(w in q for w in ["比较", "对比", "compare", "difference", "vs"]):
        return "compare"
    return "expand"


def answer_with_graph(entities: dict, relations: dict, question: str, mock: bool = False) -> str:
    """Answer a question using the knowledge graph."""
    # Extract entity names from the question
    # Try to find mentioned entities
    mentioned_eids = set()
    for eid, ent in entities.items():
        # Check if entity name or aliases appear in the question
        names_to_check = [ent["name"]] + ent.get("aliases", [])
        for name in names_to_check:
            if name.lower() in question.lower() and len(name) > 1:
                mentioned_eids.add(eid)
                break

    if not mentioned_eids:
        return "未在知识图谱中找到相关实体。请尝试使用完整名称或已知别名。"

    query_type = detect_query_type(question)

    # For expand queries: get all relations for mentioned entities + 1-hop neighbors
    relevant_eids = set(mentioned_eids)
    for eid in list(mentioned_eids):
        for rid, rel in relations.items():
            if rel["source"] == eid:
                relevant_eids.add(rel["target"])
            elif rel["target"] == eid:
                relevant_eids.add(rel["source"])

    context = format_subgraph(entities, relations, relevant_eids)

    if mock:
        # Simple template-based answer
        lines = [f"基于知识图谱，以下是与问题相关的信息：\n"]
        for eid in mentioned_eids:
            ent = entities[eid]
            lines.append(f"**{ent['name']}** ({ent['type']})")
            if ent.get("description"):
                lines.append(f"  {ent['description']}")
            rels = get_entity_relations(relations, eid)
            if rels:
                lines.append("  关系：")
                for rel in rels:
                    if rel["source"] == eid:
                        target = entities.get(rel["target"], {}).get("name", rel["target"])
                        lines.append(f"    → [{rel['relation']}] {target}")
                    else:
                        source = entities.get(rel["source"], {}).get("name", rel["source"])
                        lines.append(f"    ← [{rel['relation']}] {source}")
            lines.append("")
        return "\n".join(lines)

    # Use LLM for real answers
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return context  # Fallback to raw context

    prompt_file = SKILL_DIR / "references" / "extraction-prompt.md"
    query_system = "You are a pharmaceutical knowledge assistant. Answer the user's question based ONLY on the provided knowledge graph data. Use Chinese for the response. Cite specific entities and relations."

    messages = [
        {"role": "system", "content": query_system},
        {"role": "user", "content": f"{context}\n\nQuestion: {question}"},
    ]

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 2000,
    }
    url = f"{DEFAULT_BASE_URL}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode())
    return result["choices"][0]["message"]["content"]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Query the pharma knowledge graph")
    parser.add_argument("project_root", help="Project root directory")
    parser.add_argument("question", help="Question to ask")
    parser.add_argument("--mock", action="store_true", help="Mock mode (no LLM)")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    entities = load_json(str(project_root / "graph" / "entities.json"))
    relations = load_json(str(project_root / "graph" / "relations.json"))

    if not entities:
        print("知识图谱为空。请先运行 ingest 添加文档。", file=sys.stderr)
        sys.exit(1)

    answer = answer_with_graph(entities, relations, args.question, mock=args.mock)
    print(answer)


if __name__ == "__main__":
    main()
