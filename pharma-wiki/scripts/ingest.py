#!/usr/bin/env python3
"""
pharma-wiki ingest: fetch → compile → extract → normalize → merge → update viz

Usage:
  # Real mode (needs OPENAI_API_KEY):
  echo '{"input_text":"..."}' | python3 scripts/ingest.py <project_root>

  # Mock mode (no API key needed, uses hardcoded extraction):
  echo '{"input_text":"..."}' | python3 scripts/ingest.py <project_root> --mock

  # From file:
  python3 scripts/ingest.py <project_root> --file /path/to/doc.md

  # From URL:
  python3 scripts/ingest.py <project_root> --url https://...
"""

import json
import sys
import os
import re
import hashlib
import datetime
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent

# ── Config ──────────────────────────────────────────────────────────────
DEFAULT_MODEL = os.environ.get("KG_EXTRACT_MODEL", "gpt-4o-mini")
DEFAULT_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

# ── Alias normalization map (built-in known aliases) ────────────────────
KNOWN_ALIASES = {
    # Drugs
    "imatinib": "Imatinib", "gleevec": "Imatinib", "sti-571": "Imatinib",
    "格列卫": "Imatinib", "glivec": "Imatinib", "imatinib mesylate": "Imatinib",
    "dasatinib": "Dasatinib", "sprycel": "Dasatinib", "bms-354825": "Dasatinib",
    "osimertinib": "Osimertinib", "tagrisso": "Osimertinib", "azd9291": "Osimertinib",
    # Targets
    "bcr-abl": "BCR-ABL", "bcr-abl fusion": "BCR-ABL",
    "c-kit": "KIT", "cd117": "KIT",
    "egfr": "EGFR", "erbb1": "EGFR", "her1": "EGFR",
    # Diseases
    "cml": "Chronic myeloid leukemia", "chronic myelogenous leukemia": "Chronic myeloid leukemia",
    "gist": "Gastrointestinal stromal tumor",
    "nsclc": "NSCLC", "non-small cell lung cancer": "NSCLC",
    # Proteins
    "cyp3a4": "CYP3A4", "cytochrome p450 3a4": "CYP3A4",
    # Biomarkers
    "t790m": "EGFR T790M",
    "c797s": "EGFR C797S",
}


def make_entity_id(name: str) -> str:
    """Create a stable entity ID from name."""
    slug = re.sub(r'[^a-zA-Z0-9]', '_', name.lower()).strip('_')
    slug = re.sub(r'_+', '_', slug)
    return f"E_{slug}"


def make_relation_id() -> str:
    """Create a unique relation ID."""
    import time
    return f"R_{int(time.time() * 1000)}_{os.urandom(3).hex()}"


# ── I/O helpers ─────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── LLM API ─────────────────────────────────────────────────────────────

def load_extraction_prompts():
    """Load system and user prompts from references/extraction-prompt.md."""
    prompt_file = SKILL_DIR / "references" / "extraction-prompt.md"
    if not prompt_file.exists():
        return None, None
    content = prompt_file.read_text(encoding="utf-8")

    # Extract system prompt
    m = re.search(r'## System Prompt\s*\n```\n(.*?)\n```', content, re.DOTALL)
    sys_prompt = m.group(1).strip() if m else None

    # Extract user prompt template
    m = re.search(r'## User Prompt Template\s*\n```\n(.*?)\n```', content, re.DOTALL)
    usr_template = m.group(1).strip() if m else None

    return sys_prompt, usr_template


def call_llm(messages: list, api_key: str = "", model: str = "") -> str:
    api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    model = model or DEFAULT_MODEL
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Use --mock for testing.")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 4000,
    }
    url = f"{DEFAULT_BASE_URL}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())
    return result["choices"][0]["message"]["content"]


def parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
        return {"entities": [], "relations": []}


# ── Mock extraction ─────────────────────────────────────────────────────

MOCK_EXTRACTION = {
    "entities": [
        {"name": "Imatinib", "type": "Drug", "description": "Tyrosine kinase inhibitor targeting BCR-ABL, KIT, PDGFRB", "aliases": ["Gleevec", "STI-571", "格列卫", "Glivec"]},
        {"name": "BCR-ABL", "type": "Target", "description": "Fusion tyrosine kinase targeted by imatinib", "aliases": ["BCR-ABL fusion"]},
        {"name": "KIT", "type": "Target", "description": "Receptor tyrosine kinase targeted by imatinib", "aliases": ["c-KIT", "CD117"]},
        {"name": "PDGFRB", "type": "Target", "description": "Platelet-derived growth factor receptor beta", "aliases": ["PDGF receptor beta"]},
        {"name": "Chronic myeloid leukemia", "type": "Disease", "description": "Myeloproliferative neoplasm treated by imatinib", "aliases": ["CML", "chronic myelogenous leukemia"]},
        {"name": "Gastrointestinal stromal tumor", "type": "Disease", "description": "Mesenchymal tumor of GI tract", "aliases": ["GIST"]},
        {"name": "Edema", "type": "AdverseEvent", "description": "Common adverse event of imatinib", "aliases": ["swelling"]},
        {"name": "Nausea", "type": "AdverseEvent", "description": "Common adverse event of imatinib", "aliases": []},
        {"name": "Muscle cramps", "type": "AdverseEvent", "description": "Common adverse event of imatinib", "aliases": ["muscle spasms"]},
        {"name": "Dasatinib", "type": "Drug", "description": "Alternative TKI for imatinib-resistant CML", "aliases": ["Sprycel", "BMS-354825"]},
    ],
    "relations": [
        {"source": "Imatinib", "type": "inhibits", "target": "BCR-ABL", "description": "Imatinib inhibits BCR-ABL tyrosine kinase"},
        {"source": "Imatinib", "type": "inhibits", "target": "KIT", "description": "Imatinib inhibits KIT"},
        {"source": "Imatinib", "type": "inhibits", "target": "PDGFRB", "description": "Imatinib inhibits PDGFRB"},
        {"source": "Imatinib", "type": "treats", "target": "Chronic myeloid leukemia", "description": "Imatinib is indicated for CML"},
        {"source": "Imatinib", "type": "treats", "target": "Gastrointestinal stromal tumor", "description": "Imatinib is indicated for GIST"},
        {"source": "Imatinib", "type": "causes", "target": "Edema", "description": "Edema is a common adverse event"},
        {"source": "Imatinib", "type": "causes", "target": "Nausea", "description": "Nausea is a common adverse event"},
        {"source": "Imatinib", "type": "causes", "target": "Muscle cramps", "description": "Muscle cramps are common"},
        {"source": "Dasatinib", "type": "treats", "target": "Chronic myeloid leukemia", "description": "Dasatinib is alternative for imatinib-resistant CML"},
    ]
}


# ── Entity normalization ────────────────────────────────────────────────

def normalize_entity_name(name: str) -> str:
    """Try to normalize an entity name using known aliases."""
    key = name.lower().strip()
    return KNOWN_ALIASES.get(key, name)


def find_existing_entity(entities: dict, name: str, aliases: list) -> str | None:
    """Find if an entity already exists (by name or alias). Returns entity ID or None."""
    name_lower = name.lower().strip()
    # Check by name
    for eid, ent in entities.items():
        if ent["name"].lower() == name_lower:
            return eid
        if name_lower in [a.lower() for a in ent.get("aliases", [])]:
            return eid
    # Check aliases
    for alias in aliases:
        alias_lower = alias.lower().strip()
        for eid, ent in entities.items():
            if alias_lower in [a.lower() for a in ent.get("aliases", [])]:
                return eid
            if ent["name"].lower() == alias_lower:
                return eid
    # Check known aliases map
    normalized = normalize_entity_name(name)
    if normalized != name:
        for eid, ent in entities.items():
            if ent["name"] == normalized:
                return eid
    return None


# ── Core pipeline ───────────────────────────────────────────────────────

def extract(text: str, mock: bool = False) -> dict:
    """Extract entities and relations from text."""
    if mock:
        return MOCK_EXTRACTION

    sys_prompt, usr_template = load_extraction_prompts()
    if not sys_prompt or not usr_template:
        raise RuntimeError("Could not load extraction prompts from references/extraction-prompt.md")

    user_msg = usr_template.replace("{input_text}", text)
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg},
    ]
    response = call_llm(messages)
    return parse_llm_json(response)


def normalize_and_merge(entities_store: dict, relations_store: dict,
                        new_entities: list, new_relations: list,
                        source: str) -> tuple[dict, dict, list]:
    """Normalize and merge new extractions into existing stores. Returns (entities, relations, log)."""
    today = datetime.date.today().isoformat()
    merge_log = []

    # Build name → eid map for quick lookup
    name_to_eid = {}
    for eid, ent in entities_store.items():
        name_to_eid[ent["name"].lower()] = eid
        for alias in ent.get("aliases", []):
            name_to_eid[alias.lower()] = eid

    # Process entities
    name_to_new_eid = {}  # maps extracted name → eid (existing or new)
    for raw_ent in new_entities:
        name = raw_ent.get("name", "").strip()
        if not name:
            continue
        etype = raw_ent.get("type", "Other")
        desc = raw_ent.get("description", "")
        aliases = raw_ent.get("aliases", [])

        # Check if entity exists
        existing_eid = find_existing_entity(entities_store, name, aliases)

        if existing_eid:
            # Merge: add new aliases, update description if longer, add source
            ent = entities_store[existing_eid]
            new_aliases = [a for a in aliases if a.lower() not in
                          [x.lower() for x in ent.get("aliases", [])] and
                          a.lower() != ent["name"].lower()]
            ent["aliases"].extend(new_aliases)
            if desc and (not ent.get("description") or len(desc) > len(ent.get("description", ""))):
                ent["description"] = desc
            if source not in ent.get("sources", []):
                ent.setdefault("sources", []).append(source)
            ent["last_updated"] = today
            name_to_new_eid[name] = existing_eid
            for a in aliases:
                name_to_new_eid[a] = existing_eid
            merge_log.append(f"  Merged entity: {name} → {existing_eid}")
        else:
            # New entity
            eid = make_entity_id(name)
            # Ensure unique ID
            while eid in entities_store:
                eid = make_entity_id(name + "_" + os.urandom(2).hex())
            entities_store[eid] = {
                "id": eid,
                "name": name,
                "aliases": [a for a in aliases if a.lower() != name.lower()],
                "type": etype,
                "description": desc,
                "sources": [source],
                "first_seen": today,
                "last_updated": today,
            }
            name_to_new_eid[name] = eid
            for a in aliases:
                name_to_new_eid[a] = eid
            merge_log.append(f"  New entity: {name} ({etype}) → {eid}")

    # Process relations
    for raw_rel in new_relations:
        src_name = raw_rel.get("source", "").strip()
        tgt_name = raw_rel.get("target", "").strip()
        rel_type = raw_rel.get("type", raw_rel.get("relation", "associated_with"))
        desc = raw_rel.get("description", "")

        # Resolve to entity IDs
        src_eid = name_to_new_eid.get(src_name)
        tgt_eid = name_to_new_eid.get(tgt_name)

        if not src_eid:
            src_eid = find_existing_entity(entities_store, src_name, [])
        if not tgt_eid:
            tgt_eid = find_existing_entity(entities_store, tgt_name, [])

        if not src_eid or not tgt_eid:
            merge_log.append(f"  Skipped relation (missing entity): {src_name} → {tgt_name}")
            continue

        # Check for duplicate relation
        is_dup = False
        for rid, rel in relations_store.items():
            if (rel["source"] == src_eid and rel["target"] == tgt_eid and
                    rel["relation"] == rel_type):
                is_dup = True
                # Update if new source
                if source not in rel.get("sources", []):
                    rel.setdefault("sources", []).append(source)
                break

        if not is_dup:
            rid = make_relation_id()
            relations_store[rid] = {
                "id": rid,
                "source": src_eid,
                "target": tgt_eid,
                "relation": rel_type,
                "description": desc,
                "sources": [source],
            }
            merge_log.append(f"  New relation: {src_name} —{rel_type}→ {tgt_name}")

    return entities_store, relations_store, merge_log


# ── Main ────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest a document into pharma-wiki")
    parser.add_argument("project_root", help="Project root directory")
    parser.add_argument("--mock", action="store_true", help="Use mock extraction (no LLM)")
    parser.add_argument("--file", help="Input file path")
    parser.add_argument("--url", help="Input URL")
    parser.add_argument("--topic", default="general", help="Topic subdirectory (default: general)")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    if not project_root.exists():
        print(f"Error: {project_root} does not exist. Run scaffold first.", file=sys.stderr)
        sys.exit(1)

    # Get input text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.url:
        req = urllib.request.Request(args.url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    else:
        # Read JSON from stdin
        stdin_data = json.loads(sys.stdin.read())
        text = stdin_data.get("input_text", "")

    if not text.strip():
        print("Error: No input text provided.", file=sys.stderr)
        sys.exit(1)

    today = datetime.date.today().isoformat()

    # Step 1: Save raw
    topic_dir = project_root / "raw" / args.topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r'[^a-zA-Z0-9]', '-', text[:60].split('\n')[0]).strip('-')[:50] or "doc"
    raw_path = topic_dir / f"{today}-{slug}.md"
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(f"---\nCollected: {today}\nTopic: {args.topic}\n---\n\n{text}")
    print(f"📄 Raw saved: {raw_path.relative_to(project_root)}")

    # Step 2: Extract
    print("🔍 Extracting entities and relations...")
    extraction = extract(text, mock=args.mock)
    raw_entities = extraction.get("entities", [])
    raw_relations = extraction.get("relations", [])
    print(f"   Found {len(raw_entities)} entities, {len(raw_relations)} relations")

    # Step 3: Load existing graph
    entities_path = project_root / "graph" / "entities.json"
    relations_path = project_root / "graph" / "relations.json"
    entities_store = load_json(str(entities_path))
    relations_store = load_json(str(relations_path))

    # Step 4: Normalize and merge
    print("🔗 Normalizing and merging...")
    source_ref = f"raw/{args.topic}/{raw_path.name}"
    entities_store, relations_store, merge_log = normalize_and_merge(
        entities_store, relations_store, raw_entities, raw_relations, source_ref
    )
    for line in merge_log:
        print(line)

    # Step 5: Save graph
    save_json(str(entities_path), entities_store)
    save_json(str(relations_path), relations_store)
    print(f"💾 Graph updated: {len(entities_store)} entities, {len(relations_store)} relations")

    # Step 6: Update wiki log
    log_path = project_root / "wiki" / "log.md"
    log_entry = f"\n## [{today}] ingest | {slug}\n- Entities: +{len([e for e in merge_log if 'New entity' in e])}, merged: {len([e for e in merge_log if 'Merged entity' in e])}\n- Relations: +{len([e for e in merge_log if 'New relation' in e])}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_entry)

    # Summary
    print(f"\n✅ Ingest complete!")
    print(f"   Total entities: {len(entities_store)}")
    print(f"   Total relations: {len(relations_store)}")
    print(f"   Source: {source_ref}")


if __name__ == "__main__":
    main()
