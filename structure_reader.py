"""
Reads a reference component-structure HTML produced by the README prompt.

The structure HTML is a **semantic module-level architecture diagram** (NOT a directory tree).
It embeds a JSON island in::

    <script type="application/json" id="code-arc-structure"> ... </script>

describing the project's modules placed by architectural role, plus the curated call-direction
edges between them. ``code_arc_v2`` renders modules at the LLM-given ``(x, y)`` positions and
draws the call arrows, then adds class/function detail under each module from the AST analyzer.

JSON schema::

    {"version": 2, "project": "<name>",
     "modules": [
        {"full_name": "example", "role": "entry", "subsystem": "entry",
         "x": 120, "y": 40, "note": "usage example"},
        ...
     ],
     "edges": [
        {"source": "example", "target": "nanovllm.llm"},
        ...
     ]}

- ``full_name`` MUST equal the analyzer's dotted module path (relative to project root,
  ``__init__`` stripped) so the tool can match each module to its AST-extracted classes/functions.
- ``x`` / ``y`` are the top-left of the module node in canvas pixels.
- ``edges`` are the LLM-curated call-flow edges (module -> module); only the meaningful
  architecture flow, not every internal call.
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ModuleSpec:
    full_name: str
    role: str = ""
    subsystem: str = ""
    x: float = 0.0
    y: float = 0.0
    note: str = ""


@dataclass
class EdgeSpec:
    source: str
    target: str
    label: str = ""


@dataclass
class StructureGraph:
    project: str
    modules: List[ModuleSpec] = field(default_factory=list)
    edges: List[EdgeSpec] = field(default_factory=list)


_SCRIPT_RE = re.compile(
    r'<script\b[^>]*\bid=["\']code-arc-structure["\'][^>]*>([\s\S]*?)</script>',
    re.IGNORECASE,
)


def read_structure(path: str) -> StructureGraph:
    """Parse a structure HTML file into a :class:`StructureGraph`."""
    with open(path, "r", encoding="utf-8") as f:
        html_text = f.read()

    m = _SCRIPT_RE.search(html_text)
    if not m:
        raise ValueError(
            'No <script id="code-arc-structure"> JSON island found. '
            "Generate the structure HTML with the prompt in README.md."
        )
    raw = json.loads(m.group(1))

    project = str(raw.get("project", "project"))
    modules = [_module(d) for d in raw.get("modules", []) or []]
    edges = [_edge(d) for d in raw.get("edges", []) or []]

    seen = set()
    deduped_modules = []
    for mod in modules:
        if mod.full_name in seen:
            continue
        seen.add(mod.full_name)
        deduped_modules.append(mod)
    return StructureGraph(project=project, modules=deduped_modules, edges=edges)


def _module(d: dict) -> ModuleSpec:
    if not isinstance(d, dict):
        raise ValueError(f"module must be an object, got {type(d).__name__}")
    full = str(d.get("full_name", d.get("name", "")))
    return ModuleSpec(
        full_name=full,
        role=str(d.get("role", "") or ""),
        subsystem=str(d.get("subsystem", "") or ""),
        x=float(d.get("x", 0) or 0),
        y=float(d.get("y", 0) or 0),
        note=str(d.get("note", "") or ""),
    )


def _edge(d: dict) -> EdgeSpec:
    if isinstance(d, str):
        return EdgeSpec(source=d, target="")
    if not isinstance(d, dict):
        raise ValueError(f"edge must be an object, got {type(d).__name__}")
    return EdgeSpec(
        source=str(d.get("source", "")),
        target=str(d.get("target", "")),
        label=str(d.get("label", "") or ""),
    )


def find_module(graph: StructureGraph, full_name: str) -> Optional[ModuleSpec]:
    for m in graph.modules:
        if m.full_name == full_name:
            return m
    return None
