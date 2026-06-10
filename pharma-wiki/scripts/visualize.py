#!/usr/bin/env python3
"""
pharma-wiki visualize: generate interactive D3.js force-directed graph HTML

Usage:
  python3 scripts/visualize.py <project_root>
  python3 scripts/visualize.py <project_root> --output /path/to/viz.html
"""

import json
import sys
import html
from pathlib import Path

TYPE_COLORS = {
    "Drug": "#e74c3c", "Target": "#3498db", "Disease": "#2ecc71",
    "Gene": "#2980b9", "Protein": "#1abc9c", "Pathway": "#16a085",
    "AdverseEvent": "#e67e22", "ClinicalTrial": "#9b59b6",
    "Biomarker": "#f1c40f", "Dosage": "#95a5a6",
    "Contraindication": "#c0392b", "Mechanism": "#8e44ad",
    "Other": "#7f8c8d",
}

TYPE_LABELS = {
    "Drug": "药物", "Target": "靶点", "Disease": "疾病",
    "Gene": "基因", "Protein": "蛋白质", "Pathway": "通路",
    "AdverseEvent": "不良反应", "ClinicalTrial": "临床试验",
    "Biomarker": "生物标志物", "Dosage": "剂量",
    "Contraindication": "禁忌症", "Mechanism": "机制",
    "Other": "其他",
}

NODE_SIZES = {
    "Drug": 28, "Target": 22, "Disease": 22, "Gene": 18,
    "Protein": 16, "Pathway": 16, "AdverseEvent": 14,
    "ClinicalTrial": 14, "Biomarker": 14, "Dosage": 12,
    "Contraindication": 14, "Mechanism": 14, "Other": 12,
}


def load_json(path):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_type(t):
    if t in TYPE_COLORS:
        return t
    mapping = {
        "drug": "Drug", "target": "Target", "disease": "Disease",
        "gene": "Gene", "protein": "Protein", "pathway": "Pathway",
    }
    return mapping.get(t.lower(), "Other")


def generate_html(entities: dict, relations: dict) -> str:
    """Generate interactive D3.js visualization HTML."""

    # Build nodes
    nodes = []
    node_ids = set()
    for eid, ent in entities.items():
        etype = normalize_type(ent.get("type", "Other"))
        name = ent.get("name", eid)
        label = name if len(name) <= 30 else name[:27] + "..."
        aliases = ent.get("aliases", [])
        desc = ent.get("description", "")
        sources = ent.get("sources", [])
        nodes.append({
            "id": eid,
            "label": label,
            "fullName": name,
            "type": etype,
            "color": TYPE_COLORS.get(etype, "#95a5a6"),
            "size": NODE_SIZES.get(etype, 12),
            "aliases": aliases,
            "description": desc,
            "sources": sources,
        })
        node_ids.add(eid)

    # Build links
    links = []
    for rid, rel in relations.items():
        src = rel.get("source", "")
        tgt = rel.get("target", "")
        if src in node_ids and tgt in node_ids:
            links.append({
                "source": src,
                "target": tgt,
                "relation": rel.get("relation", ""),
                "description": rel.get("description", ""),
            })

    # Type stats for legend
    type_counts = {}
    for n in nodes:
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1

    legend_items = []
    for etype in sorted(type_counts.keys()):
        color = TYPE_COLORS.get(etype, "#95a5a6")
        label = TYPE_LABELS.get(etype, etype)
        count = type_counts[etype]
        legend_items.append(
            f'<span class="legend-item">'
            f'<span style="background:{color}" class="legend-dot"></span>'
            f'{label} ({count})</span>'
        )
    legend_html = "".join(legend_items)

    nodes_json = json.dumps(nodes, ensure_ascii=False)
    links_json = json.dumps(links, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>医药知识图谱</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f23; color: #e0e0e0; overflow: hidden; }}
#header {{ padding: 12px 20px; background: #1a1a2e; border-bottom: 1px solid #2a2a4a; display: flex; justify-content: space-between; align-items: center; }}
#header h1 {{ font-size: 18px; color: #e74c3c; }}
#stats {{ font-size: 13px; color: #888; }}
#toolbar {{ padding: 8px 20px; background: #151528; border-bottom: 1px solid #2a2a4a; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }}
#legend {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; }}
.legend-item {{ display: inline-flex; align-items: center; gap: 4px; cursor: pointer; opacity: 0.8; }}
.legend-item:hover {{ opacity: 1; }}
.legend-item.dimmed {{ opacity: 0.3; }}
.legend-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
#search {{ background: #1a1a2e; border: 1px solid #3a3a5a; color: #e0e0e0; padding: 4px 10px; border-radius: 4px; font-size: 12px; width: 200px; }}
#search::placeholder {{ color: #666; }}
#graph {{ width: 100vw; height: calc(100vh - 90px); cursor: grab; }}
#graph:active {{ cursor: grabbing; }}
svg {{ width: 100%; height: 100%; }}
.node {{ cursor: pointer; }}
.node circle {{ stroke: #fff; stroke-width: 2px; transition: r 0.2s; }}
.node:hover circle {{ stroke: #ffd700; stroke-width: 3px; }}
.node text {{ fill: #ccc; font-size: 10px; pointer-events: none; text-anchor: middle; }}
.node.dimmed circle {{ opacity: 0.15; }}
.node.dimmed text {{ opacity: 0.15; }}
.link {{ stroke-opacity: 0.5; }}
.link.dimmed {{ stroke-opacity: 0.05; }}
.link-label {{ fill: #666; font-size: 8px; pointer-events: none; }}
#tooltip {{ position: absolute; background: #1a1a2e; border: 1px solid #3a3a5a; border-radius: 6px; padding: 10px 14px; font-size: 12px; max-width: 320px; pointer-events: none; opacity: 0; transition: opacity 0.2s; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
#tooltip.visible {{ opacity: 1; }}
#tooltip h3 {{ color: #e74c3c; margin-bottom: 4px; font-size: 14px; }}
#tooltip .type {{ color: #888; font-size: 11px; }}
#tooltip .aliases {{ color: #aaa; font-size: 11px; margin-top: 4px; }}
#tooltip .desc {{ margin-top: 6px; line-height: 1.4; }}
#detail-panel {{ position: absolute; top: 90px; right: 10px; width: 280px; background: #1a1a2e; border: 1px solid #3a3a5a; border-radius: 8px; padding: 14px; font-size: 12px; display: none; max-height: calc(100vh - 110px); overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
#detail-panel.visible {{ display: block; }}
#detail-panel h3 {{ color: #e74c3c; margin-bottom: 6px; }}
#detail-panel .close {{ position: absolute; top: 8px; right: 10px; cursor: pointer; color: #666; font-size: 16px; }}
#detail-panel .close:hover {{ color: #e74c3c; }}
#detail-panel .section {{ margin-top: 8px; }}
#detail-panel .section-title {{ color: #888; font-weight: bold; margin-bottom: 2px; }}
#detail-panel .rel-item {{ padding: 2px 0; color: #ccc; }}
</style>
</head>
<body>
<div id="header">
  <h1>💊 医药知识图谱</h1>
  <span id="stats">节点: {len(nodes)} | 边: {len(links)}</span>
</div>
<div id="toolbar">
  <div id="legend">{legend_html}</div>
  <input type="text" id="search" placeholder="搜索实体..." autocomplete="off">
</div>
<div id="graph"></div>
<div id="tooltip"></div>
<div id="detail-panel">
  <span class="close" onclick="hideDetail()">&times;</span>
  <div id="detail-content"></div>
</div>
<script>
const nodesData = {nodes_json};
const linksData = {links_json};

// Build lookup maps
const entityMap = {{}};
nodesData.forEach(n => entityMap[n.id] = n);

// Adjacency for highlighting
const adjacency = {{}};
linksData.forEach(l => {{
  adjacency[l.source] = adjacency[l.source] || [];
  adjacency[l.source].push(l.target);
  adjacency[l.target] = adjacency[l.target] || [];
  adjacency[l.target].push(l.source);
}});

const width = window.innerWidth;
const height = window.innerHeight - 90;

const svg = d3.select("#graph").append("svg")
  .attr("width", width).attr("height", height);

// Zoom
const g = svg.append("g");
svg.call(d3.zoom().scaleExtent([0.1, 5]).on("zoom", e => g.attr("transform", e.transform)));

// Arrow markers
svg.append("defs").append("marker")
  .attr("id", "arrow").attr("viewBox", "0 -5 10 10")
  .attr("refX", 30).attr("refY", 0)
  .attr("markerWidth", 6).attr("markerHeight", 6)
  .attr("orient", "auto")
  .append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", "#555");

const simulation = d3.forceSimulation(nodesData)
  .force("link", d3.forceLink(linksData).id(d => d.id).distance(120))
  .force("charge", d3.forceManyBody().strength(-400))
  .force("center", d3.forceCenter(width / 2, height / 2))
  .force("collision", d3.forceCollide().radius(d => d.size + 10));

const linkGroup = g.append("g");
const link = linkGroup.selectAll("line")
  .data(linksData).join("line")
  .attr("class", "link")
  .attr("stroke", "#444")
  .attr("stroke-width", 1.5)
  .attr("marker-end", "url(#arrow)");

const linkLabel = g.append("g").selectAll("text")
  .data(linksData).join("text")
  .attr("class", "link-label")
  .text(d => d.relation)
  .attr("text-anchor", "middle");

const nodeGroup = g.append("g");
const node = nodeGroup.selectAll("g")
  .data(nodesData).join("g")
  .attr("class", "node")
  .call(d3.drag()
    .on("start", (e, d) => {{ if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
    .on("drag", (e, d) => {{ d.fx = e.x; d.fy = e.y; }})
    .on("end", (e, d) => {{ if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }})
  );

node.append("circle")
  .attr("r", d => d.size)
  .attr("fill", d => d.color);

node.append("text")
  .attr("dy", d => d.size + 14)
  .text(d => d.label);

// Hover → highlight neighborhood
node.on("mouseenter", function(e, d) {{
  const connected = new Set(adjacency[d.id] || []);
  connected.add(d.id);
  node.classed("dimmed", n => !connected.has(n.id));
  link.classed("dimmed", l => l.source.id !== d.id && l.target.id !== d.id);
  // Tooltip
  const tt = d3.select("#tooltip");
  let html = '<h3>' + d.fullName + '</h3>';
  html += '<div class="type">' + d.type + '</div>';
  if (d.aliases && d.aliases.length) html += '<div class="aliases">别名: ' + d.aliases.join(', ') + '</div>';
  if (d.description) html += '<div class="desc">' + d.description + '</div>';
  tt.html(html).classed("visible", true)
    .style("left", (e.pageX + 15) + "px").style("top", (e.pageY + 15) + "px");
}}).on("mouseleave", function() {{
  node.classed("dimmed", false);
  link.classed("dimmed", false);
  d3.select("#tooltip").classed("visible", false);
}});

// Click → detail panel
node.on("click", function(e, d) {{
  e.stopPropagation();
  showDetail(d);
}});

function showDetail(d) {{
  const panel = d3.select("#detail-panel");
  const content = d3.select("#detail-content");
  let html = '<h3>' + d.fullName + '</h3>';
  html += '<div class="type" style="color:' + d.color + '">' + d.type + '</div>';
  if (d.aliases && d.aliases.length) html += '<div style="margin-top:4px;color:#aaa">别名: ' + d.aliases.join(', ') + '</div>';
  if (d.description) html += '<div class="section"><div class="section-title">描述</div><div>' + d.description + '</div></div>';

  // Relations
  const rels = linksData.filter(l => l.source.id === d.id || l.target === d.id || l.source === d.id || l.target.id === d.id);
  if (rels.length) {{
    html += '<div class="section"><div class="section-title">关系 (' + rels.length + ')</div>';
    rels.forEach(r => {{
      const srcName = (typeof r.source === 'object' ? r.source.fullName : entityMap[r.source]?.fullName) || r.source;
      const tgtName = (typeof r.target === 'object' ? r.target.fullName : entityMap[r.target]?.fullName) || r.target;
      html += '<div class="rel-item">' + srcName + ' →[' + r.relation + ']→ ' + tgtName + '</div>';
      if (r.description) html += '<div style="color:#888;font-size:10px;margin-left:8px">' + r.description + '</div>';
    }});
    html += '</div>';
  }}

  if (d.sources && d.sources.length) {{
    html += '<div class="section"><div class="section-title">来源</div>';
    d.sources.forEach(s => html += '<div style="color:#888;font-size:10px">' + s + '</div>');
    html += '</div>';
  }}

  content.html(html);
  panel.classed("visible", true);
}}

function hideDetail() {{
  d3.select("#detail-panel").classed("visible", false);
}}

svg.on("click", hideDetail);

simulation.on("tick", () => {{
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  linkLabel.attr("x", d => (d.source.x + d.target.x) / 2)
    .attr("y", d => (d.source.y + d.target.y) / 2);
  node.attr("transform", d => 'translate(' + d.x + ',' + d.y + ')');
}});

// Search
d3.select("#search").on("input", function() {{
  const query = this.value.toLowerCase().trim();
  if (!query) {{
    node.classed("dimmed", false);
    link.classed("dimmed", false);
    return;
  }}
  const matched = new Set();
  nodesData.forEach(n => {{
    if (n.fullName.toLowerCase().includes(query) ||
        (n.aliases || []).some(a => a.toLowerCase().includes(query))) {{
      matched.add(n.id);
      (adjacency[n.id] || []).forEach(id => matched.add(id));
    }}
  }});
  node.classed("dimmed", n => !matched.has(n.id));
  link.classed("dimmed", l => !matched.has(l.source.id) || !matched.has(l.target.id));
}});

// Legend click → toggle type
d3.selectAll(".legend-item").on("click", function() {{
  const dot = d3.select(this).select(".legend-dot");
  const color = dot.style("background");
  const isDimmed = d3.select(this).classed("dimmed");
  d3.select(this).classed("dimmed", !isDimmed);
  // Get type by matching color
  const visibleTypes = new Set();
  d3.selectAll(".legend-item:not(.dimmed)").each(function() {{
    const bg = d3.select(this).select(".legend-dot").style("background");
    // Match type by color
    for (const [t, c] of Object.entries({json.dumps(TYPE_COLORS)})) {{
      if (bg === c || bg === t) visibleTypes.add(t);
    }}
  }});
  node.classed("dimmed", n => !visibleTypes.has(n.type));
  link.classed("dimmed", l => !visibleTypes.has(l.source.type) || !visibleTypes.has(l.target.type));
}});
</script>
</body>
</html>"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate visualization HTML")
    parser.add_argument("project_root", help="Project root directory")
    parser.add_argument("--output", help="Output HTML path (default: graph/viz.html)")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    entities = load_json(str(project_root / "graph" / "entities.json"))
    relations = load_json(str(project_root / "graph" / "relations.json"))

    if not entities:
        print("Error: No entities found. Run ingest first.", file=sys.stderr)
        sys.exit(1)

    html_content = generate_html(entities, relations)

    output_path = Path(args.output) if args.output else project_root / "graph" / "viz.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")

    print(f"✅ Visualization: {output_path}")
    print(f"   Nodes: {len(entities)}, Edges: {len(relations)}")
    print(f"   Open in browser to interact (drag, zoom, click, search)")


if __name__ == "__main__":
    main()
