# code_arc_v2 — Python Architecture Visualizer (semantic module graph)

`code_arc_v2` produces a self-contained, interactive HTML diagram of a Python project's
**architecture** as a **module-level call-flow graph**:

- A **module graph** is the always-on view: each module is a node placed by architectural role
  (entry point, engine, scheduler, …), with **call-direction arrows** between modules.
- Each module carries a **collapse dot** on its bottom edge; click it to reveal that module's
  classes/functions as a tidy row below the module (the "add detail" part). A class is one block
  (header + inline methods list, width 260–480).
- An **expand-level slider**: 0 = module graph only (default) → 1 = + classes/functions →
  2 = + class methods.
- Function-level call edges + inheritance (from the AST) are drawn among the visible blocks.
- Subsystem background boxes group related modules. Zoom/pan, click-to-view source, search, and a
  minimap (map + tree) are included.

This is genuinely different from v1 (`code_arc`): v1 mirrored the directory tree (as a fixed
grid). v2's structure is a **semantic architecture diagram** — the LLM analyzes the project and
lays modules out by role with the meaningful call flow, then the tool adds code detail on top.

---

## Why two inputs?

`code_arc_v2` takes **two files**:

1. **`<project_path>`** — the Python project. The bundled analyzer (AST) extracts classes,
   functions, call edges, and inheritance.
2. **`<structure_html>`** — a **reference component-structure HTML**: a module-level node graph
   where the LLM has placed each module at an explicit `(x, y)` and drawn the curated call-flow
   edges between them.

The tool merges them: the structure HTML supplies the module positions + the module call-flow
edges (the architecture); the analyzer fills in each module's classes/functions and supplies the
function-level call edges. **Classes/functions do not go in the structure HTML** — only modules
and the call-flow edges between them.

---

## Install / run

No dependencies beyond the Python 3.10+ standard library.

```bash
# from the parent of code_arc_v2/
python -m code_arc_v2 <project_path> <structure_html> [output.html]
```

Example (the bundled test project):

```bash
python -m code_arc_v2 /mnt/e/code/nano-vllm-test \
    code_arc_v2/examples/nano_vllm_test_structure.html \
    code_arc_v2/examples/nano_vllm_test_output.html
```

Open the output `.html` in any browser. Default view = the module call-flow graph; drag the
**Expand** slider right, or click a module's bottom dot, to reveal classes/functions.

### From Python

```python
from code_arc_v2 import visualize
visualize("/path/to/project", "/path/to/project_structure.html", "out.html")
```

---

## The structure HTML format

A normal `.html` file with two parts: a visual graph (for human/LLM review — not parsed) and a
**JSON island** the tool reads:

```html
<script type="application/json" id="code-arc-structure">
{ "version": 2, "project": "<project>",
  "modules": [ { "full_name": "...", "role": "...", "subsystem": "...",
                 "x": 120, "y": 40, "note": "..." }, ... ],
  "edges":   [ { "source": "...", "target": "..." }, ... ] }
</script>
```

**Module fields:**

| field        | required | meaning                                                                 |
|--------------|----------|-------------------------------------------------------------------------|
| `full_name`  | yes      | dotted Python path, relative to project root, `__init__` stripped       |
| `x`, `y`     | yes      | top-left position of the module node, in canvas pixels                  |
| `role`       | yes      | short role tag (entry / facade / scheduler / runner / layer / utility…) |
| `subsystem`  | no       | grouping tag → a light background box is drawn around its modules       |
| `note`       | no       | short role hint (tooltip)                                               |

**Edge fields:** `source`, `target` (module `full_name`s) — the **curated call-direction edges**
(the meaningful architecture flow, not every internal call).

**Critical rules:**
- `full_name` MUST equal the analyzer's dotted module path (relative to project root, `__init__`
  stripped). The tool matches each module to its AST-extracted classes/functions by `full_name`.
- Include ALL non-empty modules. Do NOT include classes/functions/methods — the tool adds them.
- **Positions are yours to design**: place modules by role/call-depth (entry near top, callees
  below, subsystems grouped). Leave vertical room below modules that will be expanded (the class/
  function row renders directly below the module when expanded).

See `examples/nano_vllm_test_structure.html` for a complete reference.

---

## Reusable prompt: generate a structure HTML for any project

Copy the prompt below into an LLM along with the project (paste the file tree + key files, or
point it at the repo). It emits a ready-to-use `*_structure.html`. Save the result and pass it to
`code_arc_v2`.

```text
You are a Python software architect. Produce a "component structure" HTML file that describes a
given Python project as a MODULE-LEVEL CALL-FLOW GRAPH (modules only — NO classes, functions, or
methods). A tool called code_arc_v2 will parse a JSON island from it and render the graph, then add
class/function detail under each module. Output ONLY the HTML file, nothing else.

STEPS
1. Read the project's directory tree and key files (entry scripts, __init__.py, engine/scheduler/
   runner modules) to understand the architecture and the real call flow.
2. Identify the modules that matter and assign each an architectural ROLE (entry, facade, engine,
   scheduler, runner, model, layer, loader, context, config, utility, …) and a SUBSYSTEM
   (entry, core, engine, models, layers, utils, …).
3. Determine the MEANINGFUL call-direction edges between modules (the architecture flow, e.g.
   example -> nanovllm.llm -> engine.llm_engine -> scheduler / model_runner -> models.qwen3 ->
   layers.*). Include only the important flow, not every incidental call.
4. Assign each module an (x, y) top-left position (canvas pixels) so the graph reads top-to-bottom
   by call depth: entry points near the top (small y), callees below (larger y), grouped by
   subsystem horizontally. LEAVE ~260px of vertical room below modules that will be expanded
   (the tool draws the module's classes/functions directly below it when expanded). Spread modules
   so their nodes (≈220px wide) and their call arrows do not overlap.
5. Include ALL non-empty modules (.py files with at least one class or function). Omit truly empty
   files unless they are notable entry points.

OUTPUT FORMAT (emit exactly this; fill in modules and edges). <body> has a small visual graph for
review, then a single JSON <script> island. The JSON MUST be valid (double quotes, no trailing
commas, no comments) — it is parsed with JSON.parse.

<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{PROJECT} — component structure</title>
<style>
body{font-family:'Segoe UI','Inter',sans-serif;background:#0d0e1a;color:#e0e0e0;padding:28px 36px;line-height:1.55}
h1{font-size:18px;color:#c8c8f0;margin-bottom:4px}
.sub{color:#666680;font-size:12px;margin-bottom:18px}
.node{display:inline-block;min-width:130px;padding:5px 10px;border-radius:8px;font-size:12px;font-family:'Cascadia Code','Fira Code',monospace;margin:4px;vertical-align:top}
.node .nm{font-weight:700}.node .rl{font-size:9px;text-transform:uppercase;opacity:.7;float:right}
.edge{color:#e8a040;font-size:11px}
code{font-family:'Cascadia Code','Fira Code',monospace;font-size:12px;color:#8ad0f0}
</style>
</head>
<body>
<h1>{PROJECT}</h1>
<div class="sub">Module-level call-flow graph. Machine-readable form is the
<code>#code-arc-structure</code> JSON island below; code_arc_v2 reads that and adds class/function detail.</div>
<!-- visual graph: <span class="node"><span class="nm">module</span><span class="rl">role</span></span>
     with <div class="edge">│ calls</div> connectors between layers -->
<script type="application/json" id="code-arc-structure">
{"version":2,"project":"{PROJECT}",
 "modules":[
   {"full_name":"entry_module","role":"entry","subsystem":"entry","x":120,"y":40,"note":"..."},
   {"full_name":"pkg.subpkg.module","role":"engine","subsystem":"engine","x":200,"y":220,"note":"..."}
 ],
 "edges":[
   {"source":"entry_module","target":"pkg.subpkg.module"},
   {"source":"pkg.subpkg.module","target":"pkg.other.module"}
 ]}
</script>
</body>
</html>

RULES
- full_name MUST match the analyzer dotted path (relative to project root, __init__ stripped).
  This is the single most important rule — the tool matches modules by full_name.
- Only modules. No class/function/method nodes.
- x,y are the module node's top-left in canvas pixels; design a top-to-bottom call-flow layout.
- The JSON island id MUST be exactly "code-arc-structure".
- Output the COMPLETE HTML file in one code block. No prose before/after.
```

### Worked example

`examples/nano_vllm_test_structure.html` is the output of this prompt for the `nano-vllm-test`
project — modules placed by role (entry → llm → engine → scheduler/model_runner → qwen3 → layers)
with the curated call-flow edges verified against the actual AST call edges.

---

## How the merge works (robustness)

- Each structure module is matched to an AST module by `full_name`; its classes/functions are
  attached (class + methods become one block).
- AST modules **not** in the structure are warned and placed in a dimmed "other" row below the graph.
- Structure modules with **no** matching AST module render header-only (dashed border).
- Module call-flow edges come from the structure HTML (LLM-curated). Function-level call edges +
  inheritance come from the AST and are drawn only when the relevant class/function blocks are
  visible; edges to hidden/collapsed blocks climb to the nearest visible ancestor.

---

## Files

| file                  | role                                                        |
|-----------------------|-------------------------------------------------------------|
| `analyzer.py`         | AST analyzer (reused from v1, unchanged)                   |
| `structure_reader.py` | parses the structure HTML's JSON island → StructureGraph   |
| `generator.py`        | merges structure + AST, emits the interactive graph HTML/JS |
| `__main__.py`         | CLI                                                          |
| `examples/`           | `nano_vllm_test_structure.html` (input) + sample output      |
