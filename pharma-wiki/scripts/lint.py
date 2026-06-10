#!/usr/bin/env python3
"""
pharma-wiki lint: health check for the knowledge base.

Checks:
  1. Entity reference integrity (relation endpoints exist)
  2. Alias conflicts (same alias on different entities)
  3. Orphan entities (no relations)
  4. Index consistency (wiki/index.md vs actual files)
  5. Duplicate relations
  6. Missing descriptions

Usage:
  python3 scripts/lint.py <project_root>
"""

import json
import sys
import os
import re
from pathlib import Path


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def lint(project_root: str) -> tuple[list[str], list[str]]:
    """Run all lint checks. Returns (issues, warnings)."""
    issues = []
    warnings = []
    root = Path(project_root)

    # Check structure exists
    if not (root / "graph" / "entities.json").exists():
        issues.append("CRITICAL: graph/entities.json not found. Run scaffold first.")
        return issues, warnings
    if not (root / "graph" / "relations.json").exists():
        issues.append("CRITICAL: graph/relations.json not found. Run scaffold first.")
        return issues, warnings

    entities = load_json(str(root / "graph" / "entities.json"))
    relations = load_json(str(root / "graph" / "relations.json"))

    entity_ids = set(entities.keys())

    # 1. Entity reference integrity
    for rid, rel in relations.items():
        if rel.get("source") not in entity_ids:
            issues.append(f"REF: Relation {rid} references missing source entity: {rel.get('source')}")
        if rel.get("target") not in entity_ids:
            issues.append(f"REF: Relation {rid} references missing target entity: {rel.get('target')}")

    # 2. Alias conflicts
    alias_map = {}  # alias_lower → eid
    for eid, ent in entities.items():
        name_lower = ent.get("name", "").lower()
        if name_lower in alias_map and alias_map[name_lower] != eid:
            issues.append(
                f"ALIAS: Name conflict: '{ent.get('name')}' ({eid}) vs "
                f"'{entities[alias_map[name_lower]].get('name')}' ({alias_map[name_lower]})"
            )
        alias_map[name_lower] = eid
        for alias in ent.get("aliases", []):
            al = alias.lower()
            if al in alias_map and alias_map[al] != eid:
                warnings.append(
                    f"ALIAS: '{alias}' appears in both {eid} ({ent.get('name')}) "
                    f"and {alias_map[al]} ({entities[alias_map[al]].get('name')})"
                )
            alias_map[al] = eid

    # 3. Orphan entities
    connected = set()
    for rid, rel in relations.items():
        connected.add(rel.get("source"))
        connected.add(rel.get("target"))
    orphans = entity_ids - connected
    for eid in orphans:
        ent = entities[eid]
        warnings.append(f"ORPHAN: {ent.get('name')} ({eid}) has no relations")

    # 4. Duplicate relations
    seen_rels = {}
    for rid, rel in relations.items():
        key = (rel.get("source"), rel.get("target"), rel.get("relation"))
        if key in seen_rels:
            warnings.append(
                f"DUP: Duplicate relation {rid} = {seen_rels[key]}: "
                f"{rel.get('source')} —{rel.get('relation')}→ {rel.get('target')}"
            )
        seen_rels[key] = rid

    # 5. Missing descriptions
    for eid, ent in entities.items():
        if not ent.get("description"):
            warnings.append(f"DESC: {ent.get('name')} ({eid}) missing description")

    # 6. Index consistency
    wiki_dir = root / "wiki"
    if wiki_dir.exists():
        index_path = wiki_dir / "index.md"
        if index_path.exists():
            index_content = index_path.read_text(encoding="utf-8")
            # Check entity/relation counts
            import re as _re
            m = _re.search(r'Entities:\s*(\d+)', index_content)
            if m and int(m.group(1)) != len(entities):
                warnings.append(f"INDEX: Entity count mismatch: index says {m.group(1)}, actual {len(entities)}")
            m = _re.search(r'Relations:\s*(\d+)', index_content)
            if m and int(m.group(1)) != len(relations):
                warnings.append(f"INDEX: Relation count mismatch: index says {m.group(1)}, actual {len(relations)}")

    return issues, warnings


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <project-root>", file=sys.stderr)
        sys.exit(1)

    project_root = sys.argv[1]
    print(f"Linting pharma-wiki at {project_root}")

    entities = load_json(str(Path(project_root) / "graph" / "entities.json"))
    relations = load_json(str(Path(project_root) / "graph" / "relations.json"))
    print(f"  Entities: {len(entities)}")
    print(f"  Relations: {len(relations)}")

    issues, warnings = lint(project_root)

    print()
    if issues:
        print(f"❌ Issues ({len(issues)}):")
        for issue in issues:
            print(f"  ⚠ {issue}")
    if warnings:
        print(f"⚠️  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  💡 {w}")

    if not issues and not warnings:
        print("✅ All checks passed!")

    # Append to log
    import datetime
    log_path = Path(project_root) / "wiki" / "log.md"
    if log_path.parent.exists():
        today = datetime.date.today().isoformat()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n## [{today}] lint | {len(issues)} issues, {len(warnings)} warnings\n")

    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
