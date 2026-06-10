---
name: pharma-wiki
description: "Build and query a pharmaceutical knowledge graph with entity extraction, normalization, and interactive visualization. Triggers: 'knowledge graph', '知识图谱', 'ingest document', 'add to knowledge base', 'query relations', 'pharma wiki', 'entity extraction'."
---

# Pharma Wiki — Knowledge Graph Skill

Build a persistent, compounding pharmaceutical knowledge base with structured entity/relation extraction, normalization, and interactive graph visualization.

## Architecture

Three layers under a project root:

- **raw/** — Immutable source documents (markdown)
- **wiki/** — Human-readable compiled articles + index + log
- **graph/** — Structured knowledge graph (JSON):
  - `entities.json` — All entities with aliases, types, descriptions
  - `relations.json` — All binary relations (triples)
  - `viz.html` — Auto-generated interactive D3.js visualization

### Entity Types (12 + Other)

Drug, Target, Disease, Gene, Protein, Pathway, AdverseEvent, ClinicalTrial, Biomarker, Dosage, Contraindication, Mechanism

### Relation Types (15)

inhibits, activates, treats, causes, associated_with, metabolized_by, contraindicated_with, indicated_for, resistant_to, sensitive_to, biomarker_for, combined_with, precedes, interacts_with, participates_in

---

## Operations

### 1. Init (scaffold)

```bash
python3 scripts/scaffold.py /path/to/project
```

Creates `raw/`, `wiki/`, `graph/` with initial files. Safe to re-run (won't overwrite).

### 2. Ingest (core pipeline)

Fetch → Extract → Normalize → Merge → Update graph.

```bash
# From stdin JSON
echo '{"input_text":"..."}' | python3 scripts/ingest.py /path/to/project

# From file
python3 scripts/ingest.py /path/to/project --file doc.md --topic drug-discovery

# From URL
python3 scripts/ingest.py /path/to/project --url https://... --topic clinical

# Mock mode (no LLM API key needed)
echo '{"input_text":"..."}' | python3 scripts/ingest.py /path/to/project --mock
```

**Pipeline steps:**
1. Save raw document to `raw/<topic>/YYYY-MM-DD-slug.md`
2. LLM extracts entities + relations (structured JSON with aliases)
3. Normalize: check aliases → merge with existing entities
4. Merge new entities/relations into `graph/entities.json` and `graph/relations.json`
5. Update `wiki/log.md`

**Entity normalization works by:**
- Exact name match (case-insensitive)
- Alias match across all entities
- Built-in known alias map (Gleevec → Imatinib, CML → Chronic myeloid leukemia, etc.)

### 3. Query

```bash
python3 scripts/query.py /path/to/project "imatinib 的靶点有哪些？"
python3 scripts/query.py /path/to/project "从 ABL1 到 CML 有什么路径？" --mock
```

**Query types detected automatically:**
- Entity lookup → all relations for mentioned entities
- Path query → BFS between two entities
- Compare → find shared relations
- General → LLM answers using graph as context

### 4. Visualize

```bash
python3 scripts/visualize.py /path/to/project
python3 scripts/visualize.py /path/to/project --output /tmp/my-graph.html
```

Generates `graph/viz.html` with:
- D3.js force-directed layout
- Nodes colored by entity type (Drug=red, Target=blue, Disease=green, etc.)
- Drag to reposition, scroll to zoom
- Hover → highlight neighborhood + tooltip
- Click → detail panel with all relations
- Search bar for filtering
- Legend click to toggle entity types

### 5. Lint

```bash
python3 scripts/lint.py /path/to/project
```

Checks:
1. Entity reference integrity (relation endpoints exist)
2. Alias conflicts (same alias on different entities)
3. Orphan entities (no relations)
4. Index consistency
5. Duplicate relations
6. Missing descriptions

---

## Data Format

### graph/entities.json

```json
{
  "E_imatinib": {
    "id": "E_imatinib",
    "name": "Imatinib",
    "aliases": ["Gleevec", "STI-571", "格列卫", "Glivec"],
    "type": "Drug",
    "description": "Tyrosine kinase inhibitor targeting BCR-ABL, KIT, PDGFRB",
    "sources": ["raw/general/2026-01-15-imatinib-review.md"],
    "first_seen": "2026-01-15",
    "last_updated": "2026-01-15"
  }
}
```

### graph/relations.json

```json
{
  "R_001": {
    "id": "R_001",
    "source": "E_imatinib",
    "target": "E_bcr_abl",
    "relation": "inhibits",
    "description": "Imatinib inhibits BCR-ABL tyrosine kinase activity",
    "sources": ["raw/general/2026-01-15-imatinib-review.md"]
  }
}
```

---

## Agent Workflow

When the user asks to add content to the knowledge base:

1. **Get source content** (URL, file, or pasted text)
2. **Run ingest**: `echo '{"input_text":"..."}' | python3 scripts/ingest.py <project> [--mock]`
3. **Run visualize** to update the graph view
4. **Report**: how many new entities, merged entities, new relations

When the user asks a question:

1. **Run query**: `python3 scripts/query.py <project> "<question>" [--mock]`
2. **Present answer** with citations from the graph

When the user asks for health check:

1. **Run lint**: `python3 scripts/lint.py <project>`
2. **Report** issues and suggest fixes

---

## Dependencies

- **Zero pip dependencies** — all scripts use Python stdlib only
- LLM calls use `urllib.request` (no `openai` library needed)
- D3.js loaded from CDN in visualization (no install needed)
- Requires `OPENAI_API_KEY` for real extraction; use `--mock` for testing

## File Reference

- `references/extraction-prompt.md` — LLM extraction prompts (system + user + few-shot)
- `references/entity-types.md` — Entity/relation type definitions and colors
- `references/raw-template.md` — Raw document template
- `references/article-template.md` — Wiki article template
- `references/index-template.md` — Index template
- `scripts/scaffold.py` — Initialize project structure
- `scripts/ingest.py` — Core pipeline: extract → normalize → merge
- `scripts/query.py` — Graph traversal + LLM Q&A
- `scripts/visualize.py` — D3.js interactive visualization generator
- `scripts/lint.py` — Health check
