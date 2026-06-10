#!/usr/bin/env python3
"""Scaffold a pharma-wiki project with raw/, wiki/, and graph/ directories."""

import os
import sys
import json
import datetime

INDEX_TEMPLATE = """# Knowledge Base Index

> Initialized: {date}

## Stats

- Articles: 0
- Entities: 0
- Relations: 0
- Last updated: {date}
"""

LOG_TEMPLATE = """# Wiki Log

> Initialized: {date}

"""

ENTITIES_TEMPLATE = "{}"
RELATIONS_TEMPLATE = "{}"

CONFIG_TEMPLATE = json.dumps({
    "name": "Pharma Knowledge Base",
    "created": "",
    "entity_types": [
        "Drug", "Target", "Disease", "Gene", "Protein", "Pathway",
        "AdverseEvent", "ClinicalTrial", "Biomarker", "Dosage",
        "Contraindication", "Mechanism", "Other"
    ],
    "relation_types": [
        "inhibits", "activates", "treats", "causes", "associated_with",
        "metabolized_by", "contraindicated_with", "indicated_for",
        "resistant_to", "sensitive_to", "biomarker_for", "combined_with",
        "precedes", "interacts_with", "participates_in"
    ]
}, indent=2, ensure_ascii=False)


def scaffold(project_root: str) -> None:
    """Create raw/, wiki/, and graph/ directories with initial files."""
    today = datetime.date.today().isoformat()
    created = []

    dirs = {
        "raw": os.path.join(project_root, "raw"),
        "wiki": os.path.join(project_root, "wiki"),
        "graph": os.path.join(project_root, "graph"),
    }

    for name, d in dirs.items():
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, ".gitkeep"), "w").close()
            created.append(d)

    # wiki/index.md
    idx = os.path.join(project_root, "wiki", "index.md")
    if not os.path.exists(idx):
        with open(idx, "w", encoding="utf-8") as f:
            f.write(INDEX_TEMPLATE.format(date=today))
        created.append(idx)

    # wiki/log.md
    log = os.path.join(project_root, "wiki", "log.md")
    if not os.path.exists(log):
        with open(log, "w", encoding="utf-8") as f:
            f.write(LOG_TEMPLATE.format(date=today))
        created.append(log)

    # graph/entities.json
    ent = os.path.join(project_root, "graph", "entities.json")
    if not os.path.exists(ent):
        with open(ent, "w", encoding="utf-8") as f:
            f.write(ENTITIES_TEMPLATE)
        created.append(ent)

    # graph/relations.json
    rel = os.path.join(project_root, "graph", "relations.json")
    if not os.path.exists(rel):
        with open(rel, "w", encoding="utf-8") as f:
            f.write(RELATIONS_TEMPLATE)
        created.append(rel)

    # config.json
    cfg = os.path.join(project_root, "config.json")
    if not os.path.exists(cfg):
        config = json.loads(CONFIG_TEMPLATE)
        config["created"] = today
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        created.append(cfg)

    if created:
        print(f"✅ Scaffolded pharma-wiki at {project_root}")
        for p in created:
            print(f"   Created: {os.path.relpath(p, project_root)}")
    else:
        print(f"Pharma-wiki already initialized at {project_root}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <project-root>", file=sys.stderr)
        sys.exit(1)
    scaffold(sys.argv[1])
