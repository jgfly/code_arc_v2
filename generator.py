"""
HTML visualization generator for code_arc_v2 (semantic module-graph edition).

Inputs:
  * a StructureGraph (modules placed at LLM-given (x, y) + LLM-curated call-direction edges), and
  * AST-analyzed ProjectData (classes/functions/methods + function call edges + inheritance).

Render model:
  * The **module graph** is the always-on architecture view: modules drawn at their fixed (x, y),
    grouped by subsystem background boxes, connected by the LLM's call-direction arrows.
  * Each module carries a **collapse dot** on its bottom edge; click toggles a tidy row of its
    AST classes/functions directly below the module (the "add detail" part). A class is one block
    (header + inline methods list, width 260–480).
  * An **expand-level slider** sets depth: 0 = module graph only (default) → 1 = + classes/functions
    → 2 = + class methods. Per-module dots refine locally.
  * Function-level call edges (AST) + inheritance are drawn among visible class/function blocks.
  * Hierarchy via depth-graded color + font size; sub-trees laid out tidily (no overlap among a
    module's children); module positions are LLM-owned so the prompt asks for spacing.
"""

import html
import json
from typing import Iterator

from .analyzer import ModuleInfo, ProjectData
from .structure_reader import StructureGraph


class HTMLGenerator:
    def __init__(self, project_data: ProjectData, structure: StructureGraph,
                 title: str = "Code Arc v2"):
        self.data = project_data
        self.structure = structure
        self.title = title

    # ------------------------------------------------------------------ merge
    def _build_modules_json(self) -> str:
        ast_modules = {m.name: m for m in self.data.modules}
        used: set[str] = set()
        mods = []
        for spec in self.structure.modules:
            am = ast_modules.get(spec.full_name)
            children = self._content_children(am) if am else []
            if am:
                used.add(am.name)
            mods.append({
                "id": spec.full_name, "type": "module", "name": spec.full_name,
                "label": spec.full_name.split(".")[-1] or spec.full_name,
                "full_name": spec.full_name, "x": spec.x, "y": spec.y,
                "role": spec.role, "subsystem": spec.subsystem, "note": spec.note,
                "has_ast": bool(am),
                "n_cls": (len(am.classes) if am else 0),
                "n_fn": (len(am.functions) if am else 0),
                "children": children,
            })
        # AST modules not represented in the structure: place in an "other" row below the graph.
        max_y = max((m["y"] for m in mods), default=0) + 320
        ox = 40
        for m in self.data.modules:
            if m.name in used:
                continue
            print(f"[warn] AST module '{m.name}' not in structure HTML; placing in 'other' row.")
            mods.append({
                "id": m.name, "type": "module", "name": m.name,
                "label": m.name.split(".")[-1] or m.name, "full_name": m.name,
                "x": ox, "y": max_y, "role": "", "subsystem": "other", "note": "(not in structure)",
                "has_ast": True, "n_cls": len(m.classes), "n_fn": len(m.functions),
                "children": self._content_children(m),
            })
            ox += 280
        return json.dumps(mods, ensure_ascii=False)

    @staticmethod
    def _content_children(am: ModuleInfo) -> list:
        children = []
        for cls in am.classes:
            children.append({
                "id": cls.full_name, "type": "class", "name": cls.name,
                "label": cls.name, "full_name": cls.full_name,
                "bases": cls.bases, "init_params": cls.init_params,
                "methods": [
                    {"id": m.full_name, "type": "method", "name": m.name, "label": m.name,
                     "full_name": m.full_name,
                     "params": m.params, "return_type": m.return_type}
                    for m in cls.methods
                ],
                "children": [],
            })
        for fn in am.functions:
            children.append({
                "id": fn.full_name, "type": "function", "name": fn.name,
                "label": fn.name, "full_name": fn.full_name,
                "params": fn.params, "return_type": fn.return_type, "children": [],
            })
        return children

    def _module_edges_json(self) -> str:
        return json.dumps([{"source": e.source, "target": e.target, "label": e.label}
                           for e in self.structure.edges], ensure_ascii=False)

    def _edges_json(self) -> str:
        return json.dumps([{"source": s, "target": t, "type": "call"}
                           for s, t in self.data.call_edges], ensure_ascii=False)

    def _inheritance_json(self) -> str:
        return json.dumps([{"source": s, "target": t, "type": "inherit"}
                           for s, t in self.data.class_inheritance], ensure_ascii=False)

    def _source_json(self) -> str:
        sources = {}
        for m in self.data.modules:
            for c in m.classes:
                sources[c.full_name] = c.source_code
                for mt in c.methods:
                    sources[mt.full_name] = mt.source_code
            for f in m.functions:
                sources[f.full_name] = f.source_code
        return json.dumps(sources, ensure_ascii=False)

    # ------------------------------------------------------------------ html
    def generate(self) -> str:
        modules_json = self._build_modules_json()
        mod_edges_json = self._module_edges_json()
        edges_json = self._edges_json()
        inheritance_json = self._inheritance_json()
        source_json = self._source_json()
        return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n'
                '<meta charset="UTF-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                '<title>' + html.escape(self.title) + ' - Code Arc v2</title>\n'
                '<style>\n' + self._get_css() + '\n</style>\n</head>\n<body>\n'
                + self._get_html_body(modules_json, mod_edges_json, edges_json,
                                      inheritance_json, source_json)
                + '\n<script>\n' + self._get_javascript() + '\n</script>\n</body>\n</html>')

    def _get_css(self) -> str:
        return r"""*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:#0d0e1a;color:#e0e0e0;overflow:hidden;height:100vh;width:100vw}
#toolbar{position:fixed;top:0;left:0;right:0;height:50px;background:linear-gradient(180deg,#14152a,#10112a);border-bottom:1px solid #222340;display:flex;align-items:center;padding:0 18px;z-index:100;gap:10px}
#toolbar .logo{font-size:16px;font-weight:800;background:linear-gradient(135deg,#64b5f6,#9c7cff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:1px}
#toolbar .project-name{font-size:13px;color:#555570;border-left:1px solid #2a2b45;padding-left:12px;margin-left:4px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#search-box{margin-left:auto;padding:7px 14px;border-radius:8px;border:1px solid #222340;background:#181930;color:#e0e0e0;font-size:13px;width:220px;outline:none;transition:border-color .2s,width .3s}
#search-box:focus{border-color:#64b5f680;width:280px}
#search-box::placeholder{color:#444460}
.toolbar-btn{padding:5px 13px;border-radius:7px;border:1px solid #222340;background:#181930;color:#8888aa;font-size:12px;cursor:pointer;transition:all .2s;white-space:nowrap}
.toolbar-btn:hover{background:#222250;border-color:#444470;color:#bbb}
.toolbar-btn.active{background:#1a2a4a;border-color:#4488bb;color:#66aaee}
.toolbar-sep{width:1px;height:24px;background:#222340}
#expand-level{width:110px;vertical-align:middle;cursor:pointer;accent-color:#64b5f6}
#expand-level-label{font-size:11px;color:#5599cc;min-width:104px;display:inline-block;font-family:'Cascadia Code','Fira Code',monospace}
#edge-limit{width:52px;padding:4px 6px;border-radius:6px;border:1px solid #222340;background:#181930;color:#8888aa;font-size:12px;text-align:center;outline:none}
#edge-limit:focus{border-color:#4488bb;color:#bbb}
#canvas-container{position:fixed;top:50px;left:0;right:0;bottom:0;overflow:hidden;cursor:grab;background:radial-gradient(circle at 20% 30%,rgba(40,50,80,.15) 0%,transparent 50%),radial-gradient(circle at 80% 70%,rgba(60,30,70,.1) 0%,transparent 50%),#0d0e1a}
#canvas-container.grabbing{cursor:grabbing}
#canvas{position:absolute;transform-origin:0 0}
#bg-svg{position:absolute;top:0;left:0;overflow:visible;pointer-events:none;z-index:0}
#bg-svg .tree-conn{stroke:#3a3b5a;stroke-width:1.5;fill:none;opacity:.8}
#bg-svg .subsys-box{fill:#1a1c2e;fill-opacity:.45;stroke:#5a5c8a;stroke-width:2.4;stroke-dasharray:8,6}
#bg-svg .subsys-label{fill:#9a9cca;font-size:16px;font-weight:700;font-family:'Cascadia Code','Fira Code',monospace;letter-spacing:.4px}
#fg-svg{position:absolute;top:0;left:0;overflow:visible;pointer-events:none;z-index:5}
#fg-svg path.e{pointer-events:none}
#fg-svg path.e-hit{pointer-events:stroke;cursor:pointer}
#fg-svg path.flow{pointer-events:none}
#fg-svg path.flow-hit{pointer-events:stroke;cursor:pointer}
body:not(.edges-on-top) #fg-svg{z-index:0}
.node-block{position:absolute;border-radius:10px;overflow:visible;box-shadow:0 6px 20px rgba(0,0,0,.32);transition:box-shadow .25s}
.node-block:hover{box-shadow:0 8px 28px rgba(0,0,0,.42)}
.nhdr{padding:7px 12px;font-weight:700;letter-spacing:.3px;user-select:none;cursor:pointer;display:flex;align-items:center;gap:7px;border-radius:10px;transition:filter .18s}
.nhdr:hover{filter:brightness(1.16)}
.nhdr .ni{width:17px;height:17px;border-radius:4px;background:rgba(255,255,255,.14);display:flex;align-items:center;justify-content:center;font-size:10px;flex-shrink:0;font-weight:700}
.nhdr .nt{white-space:nowrap}
.nhdr .role{font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:.4px;padding:1px 5px;border-radius:4px;background:rgba(255,255,255,.12);margin-left:2px}
.nhdr .cnt{font-size:10px;font-weight:600;opacity:.75;margin-left:auto;padding-left:6px}
.module-block{border:1.5px solid #3e428055;background:linear-gradient(160deg,#181930,#151628)}
.module-block .nhdr{background:linear-gradient(135deg,#3e4280,#33366a);color:#d8d8f8;font-size:13px}
.module-block.no-ast{border-style:dashed;opacity:.7}
.module-block.no-ast .nhdr{background:linear-gradient(135deg,#3a3a52,#2e2e44)}
.class-block{border:1px solid #1e557566;border-radius:9px;background:linear-gradient(160deg,#13202e,#11253a);min-width:260px;max-width:480px}
.class-block .nhdr{background:linear-gradient(135deg,#1e6a8a,#1a5a78);color:#a0d8f0;font-size:12.5px;border-radius:9px 9px 0 0}
.class-block .bases{font-size:10.5px;color:#5a98b8;font-weight:400}
.class-init{padding:3px 12px 5px;font-size:10px;color:#5a90aa;font-family:'Cascadia Code','Fira Code','Consolas',monospace;border-bottom:1px solid #1e557520;word-break:break-all}
.class-methods{padding:4px 5px 6px}
.method-block{position:relative;display:block;background:linear-gradient(160deg,#1e1420,#201828);border:1px solid #6a2a6a55;border-radius:7px;margin:3px 1px;overflow:hidden;transition:border-color .2s,box-shadow .2s}
.method-block:hover{border-color:#9a3a9a;box-shadow:0 4px 14px rgba(106,42,106,.22)}
.method-header{display:flex;align-items:center;gap:6px;padding:4px 9px;font-size:11.5px;font-weight:600;color:#c888c8}
.method-header .ni{width:14px;height:14px;border-radius:3px;background:rgba(150,60,150,.18);display:flex;align-items:center;justify-content:center;font-size:8px;flex-shrink:0}
.method-header .nt{white-space:nowrap}
.method-block .bases{font-size:10px;color:#9a60a0;font-weight:400}
.method-block.search-hit{border-color:#ffd54f!important;box-shadow:0 0 0 2px #ffd54f60!important}
.method-sig{padding:1px 9px 4px 29px;font-size:10px;color:#7a507a;font-family:'Cascadia Code','Fira Code','Consolas',monospace;line-height:1.4;word-break:break-all}
.func-block{border:1px solid #2a6a2a66;border-radius:8px;background:linear-gradient(160deg,#102014,#0e2218);min-width:260px;max-width:480px}
.func-block .nhdr{background:linear-gradient(135deg,#2a6a3a,#226030);color:#90d890;font-size:12px;border-radius:8px}
.func-block .bases{font-size:10.5px;color:#5a9858;font-weight:400}
.func-sig{padding:2px 12px 5px 30px;font-size:10px;color:#508a50;font-family:'Cascadia Code','Fira Code','Consolas',monospace;word-break:break-all}
.child-card{position:absolute;border-radius:12px;background:#0e1020cc;border:1px solid #2a2c4a;box-shadow:0 8px 30px rgba(0,0,0,.5);z-index:40}
.collapse-dot{position:absolute;left:50%;bottom:-8px;transform:translateX(-50%);width:16px;height:16px;border-radius:50%;background:#181930;border:2px solid #4a4a80;color:#aab0d0;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:65;transition:background .15s,transform .15s,border-color .15s;user-select:none;line-height:1}
.collapse-dot:hover{background:#2a2a55;border-color:#64b5f6;transform:translateX(-50%) scale(1.18)}
.conn-dot{position:absolute;width:8px;height:8px;border-radius:50%;z-index:200;cursor:pointer;transition:transform .15s,box-shadow .15s;pointer-events:auto}
.conn-dot.call{background:#5b9bd5;border:1.5px solid #3a7ab5;box-shadow:0 0 4px rgba(91,155,213,.3)}
.conn-dot.inherit{background:#ff6b6b;border:1.5px solid #cc5555;box-shadow:0 0 4px rgba(255,107,107,.3)}
.conn-dot.flow{background:#e8a040;border:1.5px solid #c08030;box-shadow:0 0 4px rgba(232,160,64,.35)}
.conn-dot:hover{transform:scale(1.6);box-shadow:0 0 8px rgba(100,181,246,.5)!important}
.conn-dot::after{content:'';position:absolute;top:-6px;left:-6px;width:20px;height:20px;border-radius:50%}
.node-block.search-hit{box-shadow:0 0 0 3px #ffd54f,0 8px 28px rgba(255,213,79,.2)!important}
.block-hl{box-shadow:0 0 0 2px rgba(100,181,246,.55),0 0 18px rgba(100,181,246,.18)!important}
.nav-btn{position:absolute;top:3px;right:3px;width:16px;height:16px;border-radius:4px;background:#222340cc;border:1px solid #444470;color:#aab0d0;font-size:10px;display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:60;opacity:0;pointer-events:none;transition:opacity .15s,background .15s;line-height:1;user-select:none}
.nav-btn:hover{background:#2a2a55;color:#fff}
[data-id]:hover .nav-btn{opacity:1;pointer-events:auto}
#nav-menu{position:fixed;z-index:300;background:#12132af0;border:1px solid #333360;border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,.6);display:none;min-width:200px;max-width:340px;backdrop-filter:blur(8px);overflow:hidden}
#nav-menu.open{display:block}
#nav-menu .nm-hdr{padding:7px 10px;font-size:11px;color:#8888aa;border-bottom:1px solid #222340;font-family:'Cascadia Code','Fira Code',monospace;word-break:break-all}
#nav-menu .nm-list{max-height:300px;overflow-y:auto}
#nav-menu .nm-item{padding:6px 12px;font-size:12px;color:#c0c0e0;cursor:pointer;display:flex;align-items:center;gap:8px;font-family:'Cascadia Code','Fira Code',monospace;word-break:break-all}
#nav-menu .nm-item:hover{background:#222250;color:#fff}
#nav-menu .nm-dir{width:12px;flex-shrink:0;text-align:center;font-weight:700}
#nav-menu .nm-dir.out{color:#5b9bd5}
#nav-menu .nm-dir.in{color:#c8a050}
#nav-menu .nm-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
#nav-menu .nm-dot.call{background:#5b9bd5}
#nav-menu .nm-dot.inherit{background:#ff6b6b}
#nav-menu .nm-dot.flow{background:#e8a040}
#nav-menu .nm-empty{padding:12px;font-size:11px;color:#666;text-align:center}
#source-panel{position:fixed;top:50px;right:-760px;width:720px;bottom:0;background:#0e0f22;border-left:1px solid #222340;z-index:90;transition:right .35s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;box-shadow:-8px 0 32px rgba(0,0,0,.5)}
#source-panel.open{right:0}
#sp-resize{position:absolute;top:0;left:-4px;width:8px;bottom:0;cursor:ew-resize;z-index:2}
#sp-resize::before{content:'';position:absolute;top:50%;left:3px;width:2px;height:32px;margin-top:-16px;background:#44446080;border-radius:1px}
#sp-hdr{padding:12px 16px;background:#14152a;border-bottom:1px solid #222340;display:flex;align-items:center;justify-content:space-between;gap:12px}
#sp-title{font-size:12px;font-weight:600;color:#5599cc;font-family:'Cascadia Code','Fira Code','Consolas',monospace;word-break:break-all}
#sp-close{background:none;border:1px solid #222340;color:#666;font-size:13px;cursor:pointer;padding:3px 10px;border-radius:5px;transition:all .2s}
#sp-close:hover{background:#222340;color:#ddd}
#sp-code{flex:1;overflow:auto;padding:14px 16px;font-family:'Cascadia Code','Fira Code','Consolas',monospace;font-size:12px;line-height:1.7;white-space:pre;color:#a8a8c8;tab-size:4}
#sp-code .sk{color:#c586c0}#sp-code .sb{color:#4ec9b0}#sp-code .ss{color:#ce9178}#sp-code .sc{color:#6a9955;font-style:italic}#sp-code .sn{color:#b5cea8}#sp-code .sd{color:#dcdcaa}#sp-code .sl{color:#4fc1ff}#sp-code .so{color:#d4d4d4}#sp-code .sp{color:#808080}#sp-code .sf{color:#dcdcaa}#sp-code .st{color:#4ec9b0}
#minimap{position:fixed;bottom:16px;right:16px;width:200px;height:140px;background:#0e0f22e0;border:1px solid #222340;border-radius:10px;z-index:100;overflow:hidden;backdrop-filter:blur(8px);box-shadow:0 4px 20px rgba(0,0,0,.4);min-width:120px;min-height:80px}
#minimap canvas{width:100%;height:100%}
#mm-viewport{position:absolute;border:1.5px solid #64b5f680;border-radius:2px;pointer-events:none;background:rgba(100,181,246,.08)}
#mm-resize{position:absolute;top:0;left:0;width:16px;height:16px;cursor:nw-resize;z-index:2}
#mm-resize::before{content:'';position:absolute;top:4px;left:4px;width:8px;height:8px;border-left:2px solid #555570;border-top:2px solid #555570;opacity:.7}
#mm-toggle{position:absolute;top:0;right:0;width:20px;height:18px;cursor:pointer;z-index:3;display:flex;align-items:center;justify-content:center;color:#8888aa;font-size:12px;border-bottom-left-radius:6px;background:#18193080;transition:background .15s,color .15s;user-select:none}
#mm-toggle:hover{background:#222250;color:#fff}
#mm-tree{position:absolute;left:0;right:0;top:0;bottom:0;overflow:auto;padding:20px 6px 6px 0;display:none;font-family:'Cascadia Code','Fira Code',monospace;font-size:11px;line-height:1.5}
#minimap.mode-tree{cursor:default}
#minimap.mode-tree #mm-tree{display:block}
#minimap.mode-tree #mm-canvas,#minimap.mode-tree #mm-viewport{display:none}
.mm-tree-item{display:flex;align-items:center;gap:4px;padding:1px 6px 1px 0;cursor:pointer;color:#aab0d0;white-space:nowrap;border-radius:3px;user-select:none}
.mm-tree-item:hover{background:#222250;color:#fff}
.mm-tree-item .mm-ti-ico{flex-shrink:0;width:12px;text-align:center;font-size:9px}
.mm-tree-item .mm-ti-lbl{overflow:hidden;text-overflow:ellipsis}
.mm-tree-item.t-module{color:#9fb6e8}
.mm-tree-item.t-module .mm-ti-ico{color:#6a8fd8}
.mm-tree-item.t-class{color:#8ad0f0}
.mm-tree-item.t-class .mm-ti-ico{color:#3a98c0}
.mm-tree-item.t-function{color:#90d890}
.mm-tree-item.t-function .mm-ti-ico{color:#3aa050}
.mm-tree-item.t-method{color:#c888c8}
.mm-tree-item.t-method .mm-ti-ico{color:#a050a0}
#legend{position:fixed;bottom:16px;left:16px;background:#12132af0;border:1px solid #222340;border-radius:10px;padding:12px 16px;z-index:100;font-size:11px;backdrop-filter:blur(8px)}
#legend h3{font-size:10px;margin-bottom:8px;color:#555570;font-weight:600;text-transform:uppercase;letter-spacing:1px}
.legend-row{display:flex;align-items:center;gap:8px;margin:4px 0;color:#8888aa}
.legend-swatch{width:14px;height:10px;border-radius:2px;flex-shrink:0}
.legend-line{width:24px;height:2px;flex-shrink:0;border-radius:1px}
#stats{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:#12132af0;border:1px solid #222340;border-radius:8px;padding:6px 18px;font-size:11px;color:#555570;z-index:100;display:flex;gap:16px;backdrop-filter:blur(8px)}
.sv{color:#5599cc;font-weight:600}
#zoom{position:fixed;top:60px;right:16px;font-size:11px;color:#444460;z-index:100;font-family:'Cascadia Code','Fira Code',monospace}
#tip{position:fixed;background:#1a1b30f0;border:1px solid #333360;border-radius:7px;padding:7px 12px;font-size:11px;color:#b0b0d0;pointer-events:none;z-index:200;max-width:380px;display:none;box-shadow:0 4px 16px rgba(0,0,0,.5);font-family:'Cascadia Code','Fira Code','Consolas',monospace;backdrop-filter:blur(8px)}
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:#0e0f22}
::-webkit-scrollbar-thumb{background:#333360;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#4a4a80}"""

    def _get_html_body(self, modules_json: str, mod_edges_json: str, edges_json: str,
                       inheritance_json: str, source_json: str) -> str:
        return (
            '<div id="toolbar">\n'
            '    <span class="logo">Code Arc v2</span>\n'
            '    <span class="project-name">' + html.escape(self.title) + '</span>\n'
            '    <input type="text" id="search-box" placeholder="Search modules, classes, functions..." />\n'
            '    <div class="toolbar-sep"></div>\n'
            '    <span style="font-size:11px;color:#555570">Expand</span>\n'
            '    <input type="range" id="expand-level" min="0" max="2" value="0" />\n'
            '    <span id="expand-level-label">modules only</span>\n'
            '    <div class="toolbar-sep"></div>\n'
            '    <button class="toolbar-btn" id="btn-fit" title="Fit to screen (F)">Fit</button>\n'
            '    <button class="toolbar-btn active" id="btn-flow" title="Toggle module call-flow arrows">Flow</button>\n'
            '    <button class="toolbar-btn active" id="btn-edges" title="Toggle function edges">Edges</button>\n'
            '    <button class="toolbar-btn active" id="btn-calls" title="Toggle call edges">Calls</button>\n'
            '    <button class="toolbar-btn active" id="btn-inherit" title="Toggle inheritance edges">Inherit</button>\n'
            '    <button class="toolbar-btn active" id="btn-top" title="Edges on top layer">Edges Top</button>\n'
            '    <div class="toolbar-sep"></div>\n'
            '    <span style="font-size:11px;color:#555570">Max edges</span>\n'
            '    <input type="number" id="edge-limit" value="100" min="0" max="9999" title="Max function edges to display (0=all)" />\n'
            '</div>\n'
            '<div id="canvas-container">\n'
            '    <div id="canvas">\n'
            '        <svg id="bg-svg" xmlns="http://www.w3.org/2000/svg">\n'
            '            <defs></defs>\n'
            '            <g id="g-subsys"></g>\n'
            '            <g id="g-conn"></g>\n'
            '        </svg>\n'
            '        <svg id="fg-svg" xmlns="http://www.w3.org/2000/svg">\n'
            '            <defs></defs>\n'
            '        </svg>\n'
            '    </div>\n'
            '</div>\n'
            '<div id="source-panel">\n'
            '    <div id="sp-resize"></div>\n'
            '    <div id="sp-hdr"><span id="sp-title">Source</span><button id="sp-close">Close</button></div>\n'
            '    <pre id="sp-code"></pre>\n'
            '</div>\n'
            '<div id="minimap">\n'
            '    <div id="mm-resize"></div>\n'
            '    <canvas id="mm-canvas"></canvas>\n'
            '    <div id="mm-viewport"></div>\n'
            '    <div id="mm-toggle" title="Tree view">&#9776;</div>\n'
            '    <div id="mm-tree"></div>\n'
            '</div>\n'
            '<div id="legend">\n'
            '    <h3>Legend</h3>\n'
            '    <div class="legend-row"><div class="legend-swatch" style="background:linear-gradient(135deg,#3e4280,#33366a)"></div>Module</div>\n'
            '    <div class="legend-row"><div class="legend-swatch" style="background:linear-gradient(135deg,#1e6a8a,#1a5a78)"></div>Class</div>\n'
            '    <div class="legend-row"><div class="legend-swatch" style="background:linear-gradient(135deg,#2a6a3a,#226030)"></div>Function</div>\n'
            '    <div class="legend-row"><div class="legend-line" style="background:#e8a040"></div>Module call flow</div>\n'
            '    <div class="legend-row"><div class="legend-line" style="background:#3a3b5a"></div>Tree link</div>\n'
            '    <div class="legend-row"><div class="legend-line" style="background:#5b9bd5"></div>Call</div>\n'
            '    <div class="legend-row"><div class="legend-line" style="background:#ff6b6b;border-top:2px dashed #ff6b6b;height:0"></div>Inherit</div>\n'
            '</div>\n'
            '<div id="stats">\n'
            '    <span>Modules: <span class="sv" id="s-mod">0</span></span>\n'
            '    <span>Classes: <span class="sv" id="s-cls">0</span></span>\n'
            '    <span>Functions: <span class="sv" id="s-fn">0</span></span>\n'
            '    <span>Flow edges: <span class="sv" id="s-flow">0</span></span>\n'
            '    <span>Call edges: <span class="sv" id="s-edge">0</span></span>\n'
            '</div>\n'
            '<div id="zoom">100%</div>\n'
            '<div id="tip"></div>\n'
            '<div id="nav-menu"></div>\n'
            '<script id="d-modules" type="application/json">' + modules_json + '</script>\n'
            '<script id="d-flow" type="application/json">' + mod_edges_json + '</script>\n'
            '<script id="d-edges" type="application/json">' + edges_json + '</script>\n'
            '<script id="d-inherit" type="application/json">' + inheritance_json + '</script>\n'
            '<script id="d-source" type="application/json">' + source_json + '</script>\n'
        )

    def _get_javascript(self) -> str:
        return r"""(function(){
"use strict";
var SVGNS='http://www.w3.org/2000/svg';
var MODS=JSON.parse(document.getElementById('d-modules').textContent);
var FLOW=JSON.parse(document.getElementById('d-flow').textContent);
var ED=JSON.parse(document.getElementById('d-edges').textContent);
var ID=JSON.parse(document.getElementById('d-inherit').textContent);
var SD=JSON.parse(document.getElementById('d-source').textContent);

var HGAP=22, ROW_VGAP=16, SUB_VGAP=54, LAYER_VGAP=54, LAYER_Y_THR=90, MAX_ROW_W=1500;
var scale=1,panX=40,panY=40;
var dragging=false,dsx=0,dsy=0,psx=0,psy=0;
var showFlow=true,showEdges=true,showCalls=true,showInherit=true,edgesOnTop=true;
var searchTerm="",lockedId=null;

var ctnr=document.getElementById('canvas-container');
var cvs=document.getElementById('canvas');
var svg=document.getElementById('fg-svg');
var bgSvg=document.getElementById('bg-svg');
var tip=document.getElementById('tip');
var zoomEl=document.getElementById('zoom');
var EM={};
var nodeMap={},parentMap={};
(function(){MODS.forEach(function(m){nodeMap[m.id]=m;parentMap[m.id]=null;(m.children||[]).forEach(function(c){nodeMap[c.id]=c;parentMap[c.id]=m;if(c.type==='class'&&c.methods){c.methods.forEach(function(mt){nodeMap[mt.id]=mt;parentMap[mt.id]=c;});}});});})();

var connectedBlockIds=new Set();
(function(){function note(ep){var parts=ep.split('.');for(var i=parts.length;i>=1;i--)connectedBlockIds.add(parts.slice(0,i).join('.'));}ED.forEach(function(e){note(e.source);note(e.target);});ID.forEach(function(e){note(e.source);note(e.target);});FLOW.forEach(function(e){connectedBlockIds.add(e.source);connectedBlockIds.add(e.target);});})();

var nMod=MODS.length,nCls=0,nFn=0;
(function(){MODS.forEach(function(m){(m.children||[]).forEach(function(c){if(c.type==='class'){nCls++;}else if(c.type==='function'){nFn++;}});});})();
document.getElementById('s-mod').textContent=nMod;document.getElementById('s-cls').textContent=nCls;
document.getElementById('s-fn').textContent=nFn;document.getElementById('s-flow').textContent=FLOW.length;
document.getElementById('s-edge').textContent=ED.length+ID.length;

function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML;}

// ========== Build DOM ==========
function buildNode(node){
  var el=document.createElement('div');
  if(node.type==='module')el.className='node-block module-block'+(node.has_ast?'':' no-ast');
  else if(node.type==='class')el.className='node-block class-block';
  else el.className='node-block func-block';
  el.dataset.id=node.id;el.dataset.type=node.type;
  el.style.display=(node.type==='module')?'':'none';
  var hdr=document.createElement('div');hdr.className='nhdr';
  var icon=node.type==='module'?'▤':node.type==='class'?'C':'f';
  var h='<span class="ni">'+icon+'</span><span class="nt">'+esc(node.label)+'</span>';
  if(node.type==='class'&&node.bases&&node.bases.length)h+=' <span class="bases">→ '+esc(node.bases.join(', '))+'</span>';
  if(node.type==='function'&&node.return_type)h+=' <span class="bases">→ '+esc(node.return_type)+'</span>';
  if(node.type==='module'){if(node.role)h+='<span class="role">'+esc(node.role)+'</span>';var c=(node.n_cls||0)+(node.n_fn||0);if(c)h+='<span class="cnt">'+(node.n_cls||0)+'C '+(node.n_fn||0)+'F</span>';}
  hdr.innerHTML=h;hdr.title=node.full_name+(node.note?' — '+node.note:'');
  el.appendChild(hdr);
  if(node.type==='class'){
    if(node.init_params&&node.init_params.length){var ip=document.createElement('div');ip.className='class-init';ip.innerHTML='<span style="color:#3a7a9a;font-weight:600">init</span>('+node.init_params.map(esc).join(', ')+')';el.appendChild(ip);}
    if(node.methods&&node.methods.length){var ml=document.createElement('div');ml.className='class-methods';ml.style.display='none';node.methods.forEach(function(m){ml.appendChild(buildMethod(m));});el.appendChild(ml);}
  }else if(node.type==='function'){
    if(node.params&&node.params.length){var fs=document.createElement('div');fs.className='func-sig';fs.textContent='('+node.params.join(', ')+')';el.appendChild(fs);}
  }
  var hasToggle=(node.children&&node.children.length>0)||(node.type==='class'&&node.methods&&node.methods.length>0);
  if(hasToggle){var dot=document.createElement('div');dot.className='collapse-dot';dot.dataset.cid=node.id;dot.textContent='+';dot.title='Click to expand/collapse';el.appendChild(dot);}
  if(connectedBlockIds.has(node.id))addNavBtn(el,node.id);
  cvs.appendChild(el);EM[node.id]=el;
  (node.children||[]).forEach(buildNode);
}
function addNavBtn(el,id){var b=document.createElement('div');b.className='nav-btn';b.textContent='⇄';b.title='View connections';b.addEventListener('click',function(ev){ev.stopPropagation();openNavMenu(id,ev.clientX,ev.clientY);});el.appendChild(b);}
// A method is its own block (data-id + measured) inside the class's .class-methods list,
// so call arrows/dots targeting the method land on the method block when the class is open,
// and climb to the class when the class is collapsed (findPos ancestor walk).
function buildMethod(m){
  // A method is its own block (data-id + measured) that flows INSIDE the class's
  // .class-methods list using normal flow (position:relative, like v1), so it stays
  // inside the class block and never overlaps siblings. Call arrows/dots targeting a
  // method land on the method block when the class is open, and climb to the class
  // (findPos ancestor walk) when the class is collapsed.
  var el=document.createElement('div');el.className='method-block';el.dataset.id=m.id;el.dataset.type='method';el.title=m.full_name;
  var h='<span class="ni">m</span><span class="nt">'+esc(m.name)+'</span>';
  if(m.return_type)h+=' <span class="bases">→ '+esc(m.return_type)+'</span>';
  var hdr=document.createElement('div');hdr.className='method-header';hdr.innerHTML=h;el.appendChild(hdr);
  if(m.params&&m.params.length){var s=document.createElement('div');s.className='method-sig';s.textContent='('+m.params.join(', ')+')';el.appendChild(s);}
  hdr.addEventListener('click',function(ev){ev.stopPropagation();openSource(m);});
  if(connectedBlockIds.has(m.id))addNavBtn(el,m.id);
  return el;
}

// ========== Source map + highlighter ==========
var sourceMap={};
(function(){MODS.forEach(function(m){(m.children||[]).forEach(function(c){sourceMap[c.id]=c;if(c.type==='class'&&c.methods)c.methods.forEach(function(mt){sourceMap[mt.id]=mt;});});});})();

function openSource(node){var fn=node.full_name||node.id;document.getElementById('sp-title').textContent=fn;var code=SD[fn]||'(Source not available)';document.getElementById('sp-code').innerHTML=highlightPython(code);document.getElementById('source-panel').classList.add('open');}
var KW='await|break|continue|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|and|as|pass|raise|return|try|while|with|yield|async|def|class'.split('|');
var BI='print|len|range|enumerate|zip|map|filter|sorted|reversed|iter|next|id|hash|type|isinstance|issubclass|super|getattr|setattr|delattr|hasattr|callable|property|staticmethod|classmethod|abs|all|any|bin|bool|bytearray|bytes|chr|complex|dict|dir|divmod|eval|exec|float|format|frozenset|hex|input|int|list|max|min|object|oct|open|ord|pow|repr|round|set|slice|str|sum|tuple|vars|__import__|Exception|BaseException|ValueError|TypeError|KeyError|IndexError|AttributeError|RuntimeError|StopIteration|GeneratorExit|KeyboardInterrupt|OverflowError|ZeroDivisionError|FileNotFoundError|ImportError|ModuleNotFoundError|NameError|UnboundLocalError|OSError|IOError|EOFError|MemoryError|RecursionError|NotImplementedError|AssertionError|ArithmeticError|LookupError|Warning|UserWarning|DeprecationWarning|FutureWarning|RuntimeWarning|SyntaxWarning|ResourceWarning'.split('|');
var KW_SET=new Set(KW),BI_SET=new Set(BI);
var DQ3='"'+'""',SQ3="'"+"''";
var RE_TRI=new RegExp('(?:[rRbBfF]{0,2})(?:'+DQ3+'[\\s\\S]*?'+DQ3+'|'+SQ3+'[\\s\\S]*?'+SQ3+')','y');
var RE_STR=new RegExp('(?:[rRbBfF]{0,2})(?:"(?:[^"\\\\]|\\\\.)*"|\'(?:[^\'\\\\]|\\\\.)*\')','y');
var RE_CMT=/#.*/y;var RE_DECOR=/@[\w.]+/y;
var RE_NUM=/(?:0[xX][\da-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|(?:\d[.\d_]*)(?:[eE][+-]?\d+)?)(?:jJ)?/y;
var RE_IDENT=/[a-zA-Z_]\w*/y;var RE_OP=/(?::=|\*\*|\/\/|<<|>>|->|==|!=|<=|>=|[+\-*/%&|^~<>!=])/y;var RE_PUNCT=/[(){}\[\],;:.@]/y;
function highlightPython(code){var out=[],i=0,len=code.length,lastKW='';function escs(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}function span(cls,txt){out.push('<span class="',cls,'">',escs(txt),'</span>');}function plain(txt){out.push(escs(txt));}function tryRx(rx){rx.lastIndex=i;var m=rx.exec(code);if(m&&m.index===i)return m[0];return null;}while(i<len){var ch=code[i];if(ch===' '||ch==='\t'||ch==='\n'||ch==='\r'){var j=i+1;while(j<len&&' \t\n\r'.indexOf(code[j])>=0)j++;plain(code.substring(i,j));i=j;continue;}var m=tryRx(RE_TRI);if(m){span('ss',m);i+=m.length;lastKW='';continue;}m=tryRx(RE_STR);if(m){span('ss',m);i+=m.length;lastKW='';continue;}m=tryRx(RE_CMT);if(m){span('sc',m);i+=m.length;lastKW='';continue;}if(ch==='@'){var prev=code.substring(Math.max(0,i-30),i);if(/(?:^|[\n\r])\s*$/.test(prev)){m=tryRx(RE_DECOR);if(m){span('sd',m);i+=m.length;lastKW='';continue;}}}if((ch>='0'&&ch<='9')&&!(i>0&&/[a-zA-Z_]/.test(code[i-1]))){m=tryRx(RE_NUM);if(m){span('sn',m);i+=m.length;lastKW='';continue;}}if(/[a-zA-Z_]/.test(ch)){m=tryRx(RE_IDENT);if(m){if(KW_SET.has(m)){span('sk',m);lastKW=m;}else if(m==='self'||m==='cls'){span('sl',m);lastKW='';}else if(m==='True'||m==='False'||m==='None'||m==='__name__'||m==='__all__'||m==='__doc__'||m==='__init__'){span('sb',m);lastKW='';}else if(BI_SET.has(m)){span('sb',m);lastKW='';}else if(lastKW==='def'){span('sf',m);lastKW='';}else if(lastKW==='class'){span('st',m);lastKW='';}else{plain(m);lastKW='';}i+=m.length;continue;}}m=tryRx(RE_OP);if(m){span('so',m);i+=m.length;lastKW='';continue;}m=tryRx(RE_PUNCT);if(m){span('sp',m);i+=m.length;lastKW='';continue;}plain(ch);i++;lastKW='';}return out.join('');}

// ========== Collapse / expand model ==========
// expandLevel: 0 = module graph only; 1 = + classes/functions; 2 = + class methods
var expandLevel=0;
var modCollapsed={},classCollapsed={};
function moduleOpen(m){var o=modCollapsed[m.id];return o===undefined?(expandLevel>=1):o;}
function classOpen(c){if(!moduleOpen(parentMap[c.id]))return false;var o=classCollapsed[c.id];return o===undefined?(expandLevel>=2):o;}
function levelLabel(v){return v<=0?'modules only':v===1?'+ classes/funcs':'+ methods (full)';}
function setVisibility(){
  MODS.forEach(function(m){
    var el=EM[m.id];if(el)el.style.display='';
    var open=moduleOpen(m);
    (m.children||[]).forEach(function(c){
      var ce=EM[c.id];if(ce)ce.style.display=open?'':'none';
      if(c.type==='class'&&ce){var ml=ce.querySelector('.class-methods');if(ml)ml.style.display=(open&&classOpen(c))?'':'none';}
    });
  });
}
function updateDots(){
  for(var id in EM){var el=EM[id],dot=el.querySelector('.collapse-dot');if(!dot)continue;var node=nodeMap[id];if(!node)continue;
    if(node.type==='module'){dot.textContent=moduleOpen(node)?'−':'+';dot.style.display='';}
    else if(node.type==='class'){var par=parentMap[id];dot.textContent=classOpen(node)?'−':'+';dot.style.display=(par&&moduleOpen(par))?'':'none';}
  }
}
function toggleDot(id){var node=nodeMap[id];if(!node)return;if(node.type==='module'){var o=modCollapsed[id];modCollapsed[id]=(o===undefined?(expandLevel>=1):o)?false:true;}else if(node.type==='class'){var oc=classCollapsed[id];classCollapsed[id]=(oc===undefined?(expandLevel>=2):oc)?false:true;}refreshAll(false);}
function applySlider(v){expandLevel=v;modCollapsed={};classCollapsed={};document.getElementById('expand-level-label').textContent=levelLabel(v);refreshAll(false);}

// ========== Measure / layout ==========
var posCache=null,posDirty=true;
function measure(){
  if(!posDirty&&posCache)return posCache;
  var pos={},cr=cvs.getBoundingClientRect();
  var els=cvs.querySelectorAll('[data-id]');
  for(var i=0;i<els.length;i++){
    var el=els[i],id=el.dataset.id;
    if(!nodeMap[id]||!nodeMap[id].type)continue;
    if(el.style.display==='none')continue;
    var r=el.getBoundingClientRect();
    if(r.width===0&&r.height===0)continue;
    pos[id]={x:(r.left-cr.left)/scale,y:(r.top-cr.top)/scale,w:r.width/scale,h:r.height/scale,
      cx:(r.left-cr.left+r.width/2)/scale,cy:(r.top-cr.top+r.height/2)/scale};
  }
  posCache=pos;posDirty=false;return pos;
}
function invalidateMeasure(){posDirty=true;}
function applyLayout(){
  invalidateMeasure();
  // 1. Put modules at their base (x, y) so they take natural size, then measure.
  MODS.forEach(function(m){var el=EM[m.id];el.style.left=m.x+'px';el.style.top=m.y+'px';el.style.width='';});
  invalidateMeasure();
  var nat=measure();   // natural rects of modules + any visible children (at 0,0)
  // 2. For each module compute child-row layout + reserved slot width / full height.
  MODS.forEach(function(m){
    var n=nat[m.id]||{w:180,h:44};var mw=n.w,mh=n.h,sw=0,sh=0;
    var open=moduleOpen(m)&&m.children&&m.children.length>0;
    if(open){
      var rows=[],row=[],rowW=0;
      m.children.forEach(function(c){var w=(nat[c.id]?nat[c.id].w:200);if(row.length>0&&rowW+w+HGAP>MAX_ROW_W){rows.push(row);row=[];rowW=0;}row.push({id:c.id,w:w});rowW+=w+HGAP;});
      if(row.length)rows.push(row);
      rows.forEach(function(rw){var w=0;rw.forEach(function(it){w+=it.w;});w+=HGAP*(rw.length-1);if(w>sw)sw=w;});
      rows.forEach(function(rw){var h=0;rw.forEach(function(it){var ch=nat[it.id]?nat[it.id].h:60;if(ch>h)h=ch;});sh+=h+ROW_VGAP;});
      if(rows.length)sh-=ROW_VGAP;
      m._rows=rows;
    }else{m._rows=null;}
    m._mw=mw;m._mh=mh;m._sw=sw;m._sh=sh;
    m._slotW=Math.max(mw,sw);
    m._fullH=mh+(m._rows?SUB_VGAP+sh:0);
  });
  // 3. Cluster modules into layers by base y (preserves the LLM's vertical row structure).
  var sorted=MODS.slice().sort(function(a,b){return a.y-b.y;});
  var layers=[],cur=[sorted[0]],prevY=sorted[0].y;
  for(var i=1;i<sorted.length;i++){if(sorted[i].y-prevY>LAYER_Y_THR){layers.push(cur);cur=[];}cur.push(sorted[i]);prevY=sorted[i].y;}
  layers.push(cur);
  // 4. Assign each layer a dynamic top (the tallest expanded module pushes the rest down).
  var ly=0;
  layers.forEach(function(layer){var lh=0;layer.forEach(function(m){if(m._fullH>lh)lh=m._fullH;});layer._top=ly;layer._h=lh;ly+=lh+LAYER_VGAP;});
  // 5. Place modules in each layer, packed horizontally by base x (centered as a group).
  //    Each module centers in its slot; children center under the module -> fit within the slot.
  layers.forEach(function(layer){
    layer.sort(function(a,b){return a.x-b.x;});
    var totalW=0;layer.forEach(function(m){totalW+=m._slotW;});totalW+=HGAP*(layer.length-1);
    var cursor=-totalW/2;
    layer.forEach(function(m){
      var slotLeft=cursor;
      var mx=slotLeft+(m._slotW-m._mw)/2;
      var my=layer._top;
      var el=EM[m.id];el.style.left=mx+'px';el.style.top=my+'px';el.style.width=m._mw+'px';
      m._cx=mx+m._mw/2;
      if(m._rows){
        var topY=my+m._mh+SUB_VGAP;
        m._rows.forEach(function(rw){var rowW=0;rw.forEach(function(it){rowW+=it.w;});rowW+=HGAP*(rw.length-1);var lx=m._cx-rowW/2;var rowH=0;rw.forEach(function(it){var ce=EM[it.id];var ch=nat[it.id]?nat[it.id].h:60;if(ce){ce.style.left=lx+'px';ce.style.top=topY+'px';ce.style.width=it.w+'px';}lx+=it.w+HGAP;if(ch>rowH)rowH=ch;});topY+=rowH+ROW_VGAP;});
      }
      cursor+=m._slotW+HGAP;
    });
  });
  // 6. Size both SVG layers to the laid-out content.
  invalidateMeasure();
  var pos=measure();var maxX=0,maxY=0;
  for(var id in pos){var p=pos[id];if(p.x+p.w>maxX)maxX=p.x+p.w;if(p.y+p.h>maxY)maxY=p.y+p.h;}
  var W=Math.max(maxX+200,800),H=Math.max(maxY+200,600);
  bgSvg.setAttribute('width',W);bgSvg.setAttribute('height',H);
  svg.setAttribute('width',W);svg.setAttribute('height',H);
}
function drawSubsystems(){
  var g=document.getElementById('g-subsys');g.innerHTML='';
  var pos=measure();
  // Only consider placed modules; cluster into layers by measured top y (all modules in a
  // layer share the same y). Within a layer, wrap each CONTIGUOUS run of the same subsystem
  // in its own box -> boxes in different layers never overlap (different y), and boxes in the
  // same layer wrap disjoint module x-ranges (no overlap). A run needs >=2 modules so a box
  // is only drawn around an actual cluster, not a lone module.
  var vis=MODS.filter(function(m){return pos[m.id];}).slice().sort(function(a,b){var pa=pos[a.id],pb=pos[b.id];return pa.y-pb.y||pa.x-pb.x;});
  var layers=[],cur=[],curY=null;
  vis.forEach(function(m){var y=pos[m.id].y;if(curY===null){curY=y;cur.push(m);}else if(Math.abs(y-curY)<=1){cur.push(m);}else{layers.push(cur);cur=[m];curY=y;}});
  if(cur.length)layers.push(cur);
  layers.forEach(function(layer){
    var run=null,runs=[];
    layer.forEach(function(m){
      if(!m.subsystem){if(run){runs.push(run);run=null;}return;}
      if(run&&run.subsys===m.subsystem){run.items.push(m);}
      else{if(run)runs.push(run);run={subsys:m.subsystem,items:[m]};}
    });
    if(run)runs.push(run);
    runs.forEach(function(run){
      if(run.items.length<2)return;
      var x=Infinity,y=Infinity,xx=-Infinity,yy=-Infinity;
      run.items.forEach(function(m){
        var p=pos[m.id];x=Math.min(x,p.x);y=Math.min(y,p.y);xx=Math.max(xx,p.x+p.w);yy=Math.max(yy,p.y+p.h);
        (m.children||[]).forEach(function(c){var cp=pos[c.id],ce=EM[c.id];if(cp&&ce&&ce.style.display!=='none'){x=Math.min(x,cp.x);y=Math.min(y,cp.y);xx=Math.max(xx,cp.x+cp.w);yy=Math.max(yy,cp.y+cp.h);}});
      });
      var pad=8;var bx=x-pad,by=y-pad,bw=(xx-x)+pad*2,bh=(yy-y)+pad*2;
      var r=document.createElementNS(SVGNS,'rect');r.setAttribute('class','subsys-box');r.setAttribute('x',bx);r.setAttribute('y',by);r.setAttribute('width',bw);r.setAttribute('height',bh);r.setAttribute('rx',12);g.appendChild(r);
      var t=document.createElementNS(SVGNS,'text');t.setAttribute('class','subsys-label');t.setAttribute('x',bx+bw/2);t.setAttribute('y',by-6);t.setAttribute('text-anchor','middle');t.textContent=run.subsys;g.appendChild(t);
    });
  });
}
function nodeRect(id){var el=EM[id];if(!el||el.style.display==='none')return null;var r=el.getBoundingClientRect();var cr=cvs.getBoundingClientRect();return{x:(r.left-cr.left)/scale,y:(r.top-cr.top)/scale,w:r.width/scale,h:r.height/scale,cx:(r.left-cr.left+r.width/2)/scale,cy:(r.top-cr.top+r.height/2)/scale};}
function drawConnectors(){
  var g=document.getElementById('g-conn');g.innerHTML='';
  var pos=measure();
  MODS.forEach(function(m){
    if(!moduleOpen(m))return;
    var p=pos[m.id];if(!p)return;
    (m.children||[]).forEach(function(c){var cp=pos[c.id];if(!cp)return;
      var x1=p.cx,y1=p.y+p.h,x2=cp.cx,y2=cp.y,my=(y1+y2)/2;
      var d='M'+x1+','+y1+' V'+my+' H'+x2+' V'+y2;
      var path=document.createElementNS(SVGNS,'path');path.setAttribute('d',d);path.setAttribute('class','tree-conn');g.appendChild(path);
    });
  });
}

// ========== Module call-flow edges (LLM-curated) ==========
function drawFlow(){
  var old=svg.querySelectorAll('.flow,.flow-hit');for(var i=0;i<old.length;i++)old[i].remove();
  var oldD=cvs.querySelectorAll('.conn-dot.flow');for(var j=0;j<oldD.length;j++)oldD[j].remove();
  if(!showFlow)return;
  var defs=svg.querySelector('defs');
  function mk(id,fill){var m=document.createElementNS(SVGNS,'marker');m.setAttribute('id',id);m.setAttribute('viewBox','0 0 12 8');m.setAttribute('refX','11');m.setAttribute('refY','4');m.setAttribute('markerWidth','11');m.setAttribute('markerHeight','8');m.setAttribute('orient','auto');var p=document.createElementNS(SVGNS,'path');p.setAttribute('d','M0,0 L12,4 L0,8 Z');p.setAttribute('fill',fill);m.appendChild(p);defs.appendChild(m);}
  if(!document.getElementById('a-flow')){mk('a-flow','#e8a040');mk('a-flow-hl','#ffc060');}
  var pos=measure();
  FLOW.forEach(function(e){
    var sp=findPos(e.source,pos),tp=findPos(e.target,pos);if(!sp||!tp)return;
    var srcPt=rectEdgePoint(sp,tp.cx,tp.cy),tgtPt=rectEdgePoint(tp,sp.cx,sp.cy);
    var x1=srcPt.x,y1=srcPt.y,x2=tgtPt.x,y2=tgtPt.y;
    var mx=(x1+x2)/2,my=(y1+y2)/2;
    var d='M'+x1+','+y1+' Q'+mx+','+(my+ (y2>y1?40:-40))+' '+x2+','+y2;
    var hit=document.createElementNS(SVGNS,'path');hit.setAttribute('d',d);hit.classList.add('flow-hit');hit.setAttribute('stroke','transparent');hit.setAttribute('stroke-width','14');hit.setAttribute('fill','none');hit.dataset.source=e.source;hit.dataset.target=e.target;hit.dataset.edgeType='flow';svg.appendChild(hit);
    var path=document.createElementNS(SVGNS,'path');path.setAttribute('d',d);path.classList.add('flow');path.setAttribute('stroke','#e8a040b0');path.setAttribute('stroke-width','2');path.setAttribute('fill','none');path.setAttribute('marker-end','url(#a-flow)');path.dataset.source=e.source;path.dataset.target=e.target;path.dataset.edgeType='flow';svg.appendChild(path);
    createDot(x1,y1,e.target,e.source,'flow');createDot(x2,y2,e.source,e.target,'flow');
  });
}

// ========== Function call/inheritance edges (AST) ==========
var edgeDrawPending=false;
function scheduleDrawEdges(){if(edgeDrawPending)return;edgeDrawPending=true;requestAnimationFrame(function(){edgeDrawPending=false;drawEdges();});}
function drawEdges(){
  var defs=svg.querySelector('defs');
  var oldE=svg.querySelectorAll('.e,.e-hit');for(var ei=0;ei<oldE.length;ei++)oldE[ei].remove();
  var oldD=cvs.querySelectorAll('.conn-dot.call,.conn-dot.inherit,.conn-dot.temp');for(var di=0;di<oldD.length;di++)oldD[di].remove();
  if(!showEdges)return;
  function mk(id,refx,fill,stroke,sw){var m=document.createElementNS(SVGNS,'marker');m.setAttribute('id',id);m.setAttribute('viewBox','0 0 12 8');m.setAttribute('refX','11');m.setAttribute('refY','4');m.setAttribute('markerWidth','10');m.setAttribute('markerHeight','7');m.setAttribute('orient','auto');var p=document.createElementNS(SVGNS,'path');p.setAttribute('d','M0,0 L12,4 L0,8 Z');p.setAttribute('fill',fill);if(stroke){p.setAttribute('stroke',stroke);p.setAttribute('stroke-width',sw);}m.appendChild(p);defs.appendChild(m);}
  if(!document.getElementById('a-call')){mk('a-call','11','#5b9bd5',null,0);mk('a-call-hl','11','#7db8f0',null,0);mk('a-inh','11','#0d0e1a','#ff6b6b','1.5');mk('a-inh-hl','11','#1a0e1a','#ff9090','2');}
  var pos=measure(),vp=getViewport();
  var visibleIds=new Set();Object.keys(pos).forEach(function(id){var p=pos[id];if(p.x+p.w>vp.left&&p.x<vp.right&&p.y+p.h>vp.top&&p.y<vp.bottom)visibleIds.add(id);});
  function isBlockVisible(id){if(visibleIds.has(id))return true;var parts=id.split('.');for(var i=parts.length-1;i>0;i--){if(visibleIds.has(parts.slice(0,i).join('.')))return true;}return false;}
  var visible=[];
  if(showCalls)ED.forEach(function(e){if(isBlockVisible(e.source)||isBlockVisible(e.target)){var sp=findPos(e.source,pos),tp=findPos(e.target,pos);if(sp&&tp)visible.push({s:e.source,t:e.target,type:'call'});}});
  if(showInherit)ID.forEach(function(e){if(isBlockVisible(e.source)||isBlockVisible(e.target)){var sp=findPos(e.source,pos),tp=findPos(e.target,pos);if(sp&&tp)visible.push({s:e.source,t:e.target,type:'inherit'});}});
  if(maxEdges>0&&visible.length>maxEdges){for(var i=visible.length-1;i>0&&i>=visible.length-maxEdges;i--){var j=Math.floor(Math.random()*(i+1));var tmp=visible[i];visible[i]=visible[j];visible[j]=tmp;}visible=visible.slice(visible.length-maxEdges);}
  var BATCH=80,idx=0;function batch(){var end=Math.min(idx+BATCH,visible.length);for(;idx<end;idx++){var e=visible[idx];createEdgePath(e.s,e.t,e.type,pos);}if(idx<visible.length)requestAnimationFrame(batch);}
  if(visible.length>0)batch();
}
function rectEdgePoint(rect,tx,ty){var cx=rect.cx,cy=rect.cy,dx=tx-cx,dy=ty-cy;if(dx===0&&dy===0)return{x:cx,y:cy};var candidates=[];if(dy!==0){var t=(rect.y-cy)/dy;if(t>0){var ix=cx+dx*t;if(ix>=rect.x&&ix<=rect.x+rect.w)candidates.push({x:ix,y:rect.y,t:t});}}if(dy!==0){var t2=(rect.y+rect.h-cy)/dy;if(t2>0){var ix2=cx+dx*t2;if(ix2>=rect.x&&ix2<=rect.x+rect.w)candidates.push({x:ix2,y:rect.y+rect.h,t:t2});}}if(dx!==0){var t3=(rect.x-cx)/dx;if(t3>0){var iy=cy+dy*t3;if(iy>=rect.y&&iy<=rect.y+rect.h)candidates.push({x:rect.x,y:iy,t:t3});}}if(dx!==0){var t4=(rect.x+rect.w-cx)/dx;if(t4>0){var iy2=cy+dy*t4;if(iy2>=rect.y&&iy2<=rect.y+rect.h)candidates.push({x:rect.x+rect.w,y:iy2,t:t4});}}if(candidates.length===0)return{x:cx,y:cy};candidates.sort(function(a,b){return a.t-b.t;});return candidates[0];}
function findPos(id,pos){if(pos[id])return pos[id];var parts=id.split('.');for(var i=parts.length-1;i>0;i--){var c=parts.slice(0,i).join('.');if(pos[c])return pos[c];}return null;}
function createEdgePath(sourceId,targetId,type,pos){
  var sPos=findPos(sourceId,pos),tPos=findPos(targetId,pos);if(!sPos||!tPos)return;
  var srcPt=rectEdgePoint(sPos,tPos.cx,tPos.cy),tgtPt=rectEdgePoint(tPos,sPos.cx,sPos.cy);
  var x1=srcPt.x,y1=srcPt.y,x2=tgtPt.x,y2=tgtPt.y;var dx=x2-x1,dy=y2-y1,cx1,cy1,cx2,cy2;
  if(Math.abs(dy)>Math.abs(dx)*0.4){cx1=x1;cy1=y1+dy*0.35;cx2=x2;cy2=y2-dy*0.35;var offset=(Math.sin(x1*0.01+y1*0.01)*0.5+0.5)*30-15;cx1+=offset;cx2+=offset;}
  else{cx1=x1+dx*0.35;cy1=y1;cx2=x1+dx*0.65;cy2=y2;var offy=(Math.sin(x1*0.01+y1*0.01)*0.5+0.5)*30-15;cy1+=offy;cy2+=offy;}
  var d='M'+x1+','+y1+' C'+cx1+','+cy1+' '+cx2+','+cy2+' '+x2+','+y2;
  var hit=document.createElementNS(SVGNS,'path');hit.setAttribute('d',d);hit.classList.add('e-hit');hit.setAttribute('stroke','transparent');hit.setAttribute('stroke-width','14');hit.setAttribute('fill','none');hit.dataset.source=sourceId;hit.dataset.target=targetId;hit.dataset.edgeType=type;svg.appendChild(hit);
  var path=document.createElementNS(SVGNS,'path');path.setAttribute('d',d);path.classList.add('e');var isCall=type==='call';path.setAttribute('stroke',isCall?'#5b9bd540':'#ff6b6b40');path.setAttribute('stroke-width','1.5');path.setAttribute('fill','none');path.setAttribute('marker-end',isCall?'url(#a-call)':'url(#a-inh)');if(!isCall)path.setAttribute('stroke-dasharray','8,5');path.dataset.source=sourceId;path.dataset.target=targetId;path.dataset.edgeType=type;svg.appendChild(path);
  createDot(x1,y1,targetId,sourceId,type);createDot(x2,y2,sourceId,targetId,type);
}
function createDot(x,y,navId,fromId,type){
  var dot=document.createElement('div');dot.className='conn-dot '+type;dot.style.left=(x-4)+'px';dot.style.top=(y-4)+'px';dot.dataset.navId=navId;dot.dataset.fromId=fromId;
  var navShort=navId.split('.').slice(-2).join('.');dot.title='→ '+navShort;
  dot.addEventListener('pointerenter',function(ev){showTip(ev,'→ '+navShort);hlBlocks(navId);});
  dot.addEventListener('pointerleave',function(){hideTip();clearBlockHL();});cvs.appendChild(dot);
}
function highlightEdge(el,on){var et=el.dataset.edgeType;if(et==='flow'){if(on){el.setAttribute('stroke-width','3');el.setAttribute('stroke','#ffc060');el.setAttribute('marker-end','url(#a-flow-hl)');el.parentNode.appendChild(el);}else{el.setAttribute('stroke-width','2');el.setAttribute('stroke','#e8a040b0');el.setAttribute('marker-end','url(#a-flow)');}return;}var isCall=et==='call';if(on){el.setAttribute('stroke-width','2.5');el.setAttribute('stroke',isCall?'#7db8f0':'#ff9090');el.setAttribute('marker-end',isCall?'url(#a-call-hl)':'url(#a-inh-hl)');var hit=el.previousElementSibling;if(hit&&hit.classList.contains('e-hit')){hit.parentNode.appendChild(hit);}el.parentNode.appendChild(el);}else{el.setAttribute('stroke-width','1.5');el.setAttribute('stroke',isCall?'#5b9bd540':'#ff6b6b40');el.setAttribute('marker-end',isCall?'url(#a-call)':'url(#a-inh)');if(!isCall)el.setAttribute('stroke-dasharray','8,5');}}
function isLockedConnected(el){if(!lockedId)return false;var s=el.dataset.source,t=el.dataset.target;return s===lockedId||t===lockedId||s.startsWith(lockedId+'.')||t.startsWith(lockedId+'.');}
function hlBlocks(){for(var i=0;i<arguments.length;i++){var id=arguments[i];var el=EM[id];if(!el){var parts=id.split('.');for(var j=parts.length-1;j>0;j--){var c=parts.slice(0,j).join('.');if(EM[c]){el=EM[c];break;}}}if(el)el.classList.add('block-hl');}}
function clearBlockHL(){for(var id in EM)EM[id].classList.remove('block-hl');}
function resolveEdge(el){if(el.classList.contains('e-hit')||el.classList.contains('flow-hit')){var next=el.nextElementSibling;if(next&&(next.classList.contains('e')||next.classList.contains('flow')))return next;}if(el.classList.contains('e')||el.classList.contains('flow'))return el;return null;}
function findEdgeFromTarget(ev){var hit=ev.target.closest('.e-hit,.flow-hit');if(hit)return resolveEdge(hit);var e=ev.target.closest('.e,.flow');return e||null;}
svg.addEventListener('pointerenter',function(ev){var p=findEdgeFromTarget(ev);if(!p)return;highlightEdge(p,true);var sn=p.dataset.source.split('.').slice(-2).join('.');var tn=p.dataset.target.split('.').slice(-2).join('.');showTip(ev,sn+' → '+tn);hlBlocks(p.dataset.source,p.dataset.target);},true);
svg.addEventListener('pointermove',function(ev){if(findEdgeFromTarget(ev)){tip.style.left=(ev.clientX+14)+'px';tip.style.top=(ev.clientY+14)+'px';}},true);
svg.addEventListener('pointerleave',function(ev){var p=findEdgeFromTarget(ev);if(!p)return;if(!isLockedConnected(p))highlightEdge(p,false);hideTip();clearBlockHL();},true);
function highlightEdgesFor(id,on){
  if(on){
    var paths=svg.querySelectorAll('.e,.flow');var existingKeys={};
    for(var i=0;i<paths.length;i++){var p=paths[i],s=p.dataset.source,t=p.dataset.target;existingKeys[s+'|'+t+'|'+p.dataset.edgeType]=true;var connected=s===id||t===id||s.startsWith(id+'.')||t.startsWith(id+'.');if(connected){highlightEdge(p,true);var hit=p.previousElementSibling;if(hit&&(hit.classList.contains('e-hit')||hit.classList.contains('flow-hit')))hit.parentNode.appendChild(hit);p.parentNode.appendChild(p);}}
    var pos=measure();
    function addTemp(s,t,type){var key=s+'|'+t+'|'+type;if(existingKeys[key])return;var connected=s===id||t===id||s.startsWith(id+'.')||t.startsWith(id+'.');if(!connected)return;if(!findPos(s,pos)||!findPos(t,pos))return;var svgBefore=svg.children.length,dotBefore=cvs.querySelectorAll('.conn-dot').length;createEdgePath(s,t,type,pos);for(var k=svgBefore;k<svg.children.length;k++){var ch=svg.children[k];if(ch.classList&&(ch.classList.contains('e')||ch.classList.contains('e-hit'))){ch.classList.add('e-temp');ch.dataset.tempFor=id;}}var dots=cvs.querySelectorAll('.conn-dot');for(var k2=dotBefore;k2<dots.length;k2++){dots[k2].classList.add('temp');dots[k2].dataset.tempFor=id;}var np=svg.lastElementChild;if(np&&np.classList.contains('e'))highlightEdge(np,true);existingKeys[key]=true;}
    if(showCalls)ED.forEach(function(e){addTemp(e.source,e.target,'call');});
    if(showInherit)ID.forEach(function(e){addTemp(e.source,e.target,'inherit');});
  }else{
    var temps=svg.querySelectorAll('.e-temp');for(var i2=0;i2<temps.length;i2++){if(temps[i2].dataset.tempFor===id)temps[i2].remove();}
    var tempDots=cvs.querySelectorAll('.conn-dot.temp');for(var i3=0;i3<tempDots.length;i3++){if(tempDots[i3].dataset.tempFor===id)tempDots[i3].remove();}
    var paths2=svg.querySelectorAll('.e');for(var i4=0;i4<paths2.length;i4++){var p2=paths2[i4],s2=p2.dataset.source,t2=p2.dataset.target;var connected2=s2===id||t2===id||s2.startsWith(id+'.')||t2.startsWith(id+'.');if(connected2)highlightEdge(p2,false);}
  }
}
function clearAllEdgeHL(){var temps=svg.querySelectorAll('.e-temp');for(var i=0;i<temps.length;i++)temps[i].remove();var tempDots=cvs.querySelectorAll('.conn-dot.temp');for(var i=0;i<tempDots.length;i++)tempDots[i].remove();var paths=svg.querySelectorAll('.e,.flow');for(var i=0;i<paths.length;i++)highlightEdge(paths[i],false);}

// ========== Per-block connection list ==========
function getConnections(blockId){
  var map={};function add(other,dir,type){if(!map[other])map[other]={dirs:{},types:{}};map[other].dirs[dir]=1;map[other].types[type]=1;}
  function handle(s,t,type){var sHere=s===blockId||s.startsWith(blockId+'.'),tHere=t===blockId||t.startsWith(blockId+'.');if(sHere&&tHere)return;if(sHere)add(t,'out',type);else if(tHere)add(s,'in',type);}
  ED.forEach(function(e){handle(e.source,e.target,'call');});ID.forEach(function(e){handle(e.source,e.target,'inherit');});FLOW.forEach(function(e){handle(e.source,e.target,'flow');});
  return Object.keys(map).sort().map(function(k){return {other:k,dirs:map[k].dirs,types:map[k].types};});
}
var navMenu=document.getElementById('nav-menu');
function closeNavMenu(){navMenu.classList.remove('open');navMenu.innerHTML='';}
function openNavMenu(id,x,y){
  var conns=getConnections(id);navMenu.innerHTML='';
  var h=document.createElement('div');h.className='nm-hdr';h.textContent=id+'  ('+conns.length+')';navMenu.appendChild(h);
  var list=document.createElement('div');list.className='nm-list';
  if(conns.length===0){var em=document.createElement('div');em.className='nm-empty';em.textContent='No connections';list.appendChild(em);}
  conns.forEach(function(c){var it=document.createElement('div');it.className='nm-item';var both=c.dirs.out&&c.dirs.in;var dir=document.createElement('span');dir.className='nm-dir '+(c.dirs.out?'out':'in');dir.textContent=both?'⇄':(c.dirs.out?'→':'←');it.appendChild(dir);if(c.types.call){var d1=document.createElement('span');d1.className='nm-dot call';it.appendChild(d1);}if(c.types.inherit){var d2=document.createElement('span');d2.className='nm-dot inherit';it.appendChild(d2);}if(c.types.flow){var d3=document.createElement('span');d3.className='nm-dot flow';it.appendChild(d3);}var lab=document.createElement('span');lab.textContent=c.other.split('.').slice(-2).join('.');lab.title=c.other;it.appendChild(lab);it.addEventListener('click',function(ev){ev.stopPropagation();navigateToBlock(c.other);closeNavMenu();});list.appendChild(it);});
  navMenu.appendChild(list);navMenu.style.left='0px';navMenu.style.top='0px';navMenu.classList.add('open');
  var mw=navMenu.offsetWidth,mh=navMenu.offsetHeight;var nx=Math.max(8,Math.min(x,window.innerWidth-mw-8));var ny=Math.max(8,Math.min(y,window.innerHeight-mh-8));navMenu.style.left=nx+'px';navMenu.style.top=ny+'px';
}
document.addEventListener('mousedown',function(e){if(navMenu.classList.contains('open')&&!navMenu.contains(e.target))closeNavMenu();});

// ========== Navigation ==========
// Open the full ancestor path of `id` so the clicked block becomes visible and can be centered,
// without collapsing anything. The convention is: modCollapsed[id]/classCollapsed[id] === true
// means OPEN (override), false means COLLAPSED (override), undefined means follow expandLevel.
// So to force-open we set true. The clicked block itself is opened too (module or its parent
// class for a method).
function expandPathTo(id){
  var node=nodeMap[id];if(!node)return;
  if(node.type==='module')modCollapsed[node.id]=true;
  else if(node.type==='class')classCollapsed[node.id]=true;
  var p=parentMap[id];
  while(p){
    if(p.type==='module')modCollapsed[p.id]=true;
    else if(p.type==='class')classCollapsed[p.id]=true;
    p=parentMap[p.id];
  }
}
function navigateToBlock(id){if(nodeMap[id])expandPathTo(id);refreshAll(false);requestAnimationFrame(function(){centerOn(id);});}
function centerOn(id){var pos=measure(),p=pos[id];function hidden(x){return !x||(x.w===0&&x.h===0);}if(hidden(p)){var parts=id.split('.');for(var i=parts.length-1;i>0;i--){var c=parts.slice(0,i).join('.');if(!hidden(pos[c])){p=pos[c];break;}}}if(hidden(p))return;var cr=ctnr.getBoundingClientRect();panX=cr.width/2-p.cx*scale;panY=cr.height/2-p.cy*scale;updateTx();scheduleDrawEdges();updateMinimap();}

// ========== Zoom / pan / fit ==========
function getViewport(){var cr=ctnr.getBoundingClientRect();return{left:-panX/scale-200,top:-panY/scale-200,right:(cr.width-panX)/scale+200,bottom:(cr.height-panY)/scale+200};}
function updateTx(){cvs.style.transform='translate('+panX+'px,'+panY+'px) scale('+scale+')';zoomEl.textContent=Math.round(scale*100)+'%';}
ctnr.addEventListener('mousedown',function(e){if(e.target.closest('[data-id]')||e.target.closest('.e')||e.target.closest('.e-hit')||e.target.closest('.flow')||e.target.closest('.flow-hit')||e.target.closest('.collapse-dot')||e.target.closest('.conn-dot')||e.target.closest('.nav-btn'))return;closeNavMenu();dragging=true;dsx=e.clientX;dsy=e.clientY;psx=panX;psy=panY;ctnr.classList.add('grabbing');});
window.addEventListener('mousemove',function(e){if(!dragging)return;panX=psx+(e.clientX-dsx);panY=psy+(e.clientY-dsy);updateTx();scheduleDrawEdges();updateMinimap();});
window.addEventListener('mouseup',function(){dragging=false;ctnr.classList.remove('grabbing');});
ctnr.addEventListener('wheel',function(e){e.preventDefault();var d=e.deltaY>0?0.92:1.08;var ns=Math.max(0.12,Math.min(3,scale*d));var r=ctnr.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;panX=mx-(mx-panX)*(ns/scale);panY=my-(my-panY)*(ns/scale);scale=ns;updateTx();invalidateMeasure();scheduleDrawEdges();updateMinimap();},{passive:false});
function fitToScreen(){invalidateMeasure();var cr=ctnr.getBoundingClientRect(),pos=measure();var minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;Object.keys(pos).forEach(function(id){var p=pos[id];minX=Math.min(minX,p.x);minY=Math.min(minY,p.y);maxX=Math.max(maxX,p.x+p.w);maxY=Math.max(maxY,p.y+p.h);});if(minX===Infinity)return;var cw=maxX-minX+100,ch=maxY-minY+100;scale=Math.min(cr.width/cw,cr.height/ch,1.0);scale=Math.max(0.12,scale);panX=(cr.width-cw*scale)/2-minX*scale+50*scale;panY=(cr.height-ch*scale)/2-minY*scale+50*scale;updateTx();updateMinimap();}

// ========== Source panel wiring ==========
document.getElementById('sp-close').addEventListener('click',function(){var sp=document.getElementById('source-panel');sp.classList.remove('open');sp.style.width='';});
var spEl=document.getElementById('source-panel');var spResize=document.getElementById('sp-resize');var spResizing=false,spRSx=0,spRSw=0;
spResize.addEventListener('mousedown',function(e){e.preventDefault();e.stopPropagation();spResizing=true;spRSx=e.clientX;spRSw=spEl.offsetWidth;spEl.style.transition='none';});
window.addEventListener('mousemove',function(e){if(!spResizing)return;var dx=spRSx-e.clientX;var nw=Math.max(280,Math.min(window.innerWidth*0.7,spRSw+dx));spEl.style.width=nw+'px';});
window.addEventListener('mouseup',function(){if(spResizing){spResizing=false;spEl.style.transition='';}});

// ========== Canvas click / hover ==========
cvs.addEventListener('click',function(e){
  var dot=e.target.closest('.collapse-dot');if(dot){e.stopPropagation();toggleDot(dot.dataset.cid);return;}
  var cd=e.target.closest('.conn-dot');if(cd){e.stopPropagation();navigateToBlock(cd.dataset.navId);return;}
  var block=e.target.closest('[data-id]');if(block){var id=block.dataset.id;if(lockedId&&lockedId!==id){clearAllEdgeHL();clearBlockHL();}lockedId=id;highlightEdgesFor(id,true);hlBlocks(id);var item=sourceMap[id];if(item){openSource(item);}else{document.getElementById('sp-title').textContent=id;var code=SD[id];if(code!=null){document.getElementById('sp-code').innerHTML=highlightPython(code);document.getElementById('source-panel').classList.add('open');}}e.stopPropagation();return;}
  if(lockedId){lockedId=null;clearAllEdgeHL();clearBlockHL();}
});
cvs.addEventListener('mouseover',function(e){var block=e.target.closest('[data-id]');if(!block)return;var id=block.dataset.id;highlightEdgesFor(id,true);hlBlocks(id);});
cvs.addEventListener('mouseout',function(e){var block=e.target.closest('[data-id]');if(!block)return;var id=block.dataset.id;if(id===lockedId)return;highlightEdgesFor(id,false);clearBlockHL();if(lockedId){highlightEdgesFor(lockedId,true);hlBlocks(lockedId);}});

// ========== Toolbar wiring ==========
document.getElementById('btn-fit').addEventListener('click',fitToScreen);
document.getElementById('btn-flow').addEventListener('click',function(){showFlow=!showFlow;this.classList.toggle('active',showFlow);refreshAll(false);});
document.getElementById('btn-edges').addEventListener('click',function(){showEdges=!showEdges;this.classList.toggle('active',showEdges);if(!showEdges){document.getElementById('btn-calls').classList.remove('active');document.getElementById('btn-inherit').classList.remove('active');}else{if(showCalls)document.getElementById('btn-calls').classList.add('active');if(showInherit)document.getElementById('btn-inherit').classList.add('active');}scheduleDrawEdges();});
document.getElementById('btn-calls').addEventListener('click',function(){if(!showEdges){showEdges=true;document.getElementById('btn-edges').classList.add('active');}showCalls=!showCalls;this.classList.toggle('active',showCalls);scheduleDrawEdges();});
document.getElementById('btn-inherit').addEventListener('click',function(){if(!showEdges){showEdges=true;document.getElementById('btn-edges').classList.add('active');}showInherit=!showInherit;this.classList.toggle('active',showInherit);scheduleDrawEdges();});
document.getElementById('btn-top').addEventListener('click',function(){edgesOnTop=!edgesOnTop;this.classList.toggle('active',edgesOnTop);document.body.classList.toggle('edges-on-top',edgesOnTop);});
var edgeLimitInput=document.getElementById('edge-limit');var maxEdges=parseInt(edgeLimitInput.value)||100;
edgeLimitInput.addEventListener('change',function(){maxEdges=parseInt(this.value)||0;scheduleDrawEdges();});
var slider=document.getElementById('expand-level');slider.value=expandLevel;
slider.addEventListener('input',function(){applySlider(parseInt(this.value));});
document.getElementById('expand-level-label').textContent=levelLabel(expandLevel);

// ========== Search ==========
var searchTimer;
document.getElementById('search-box').addEventListener('input',function(e){clearTimeout(searchTimer);searchTimer=setTimeout(function(){searchTerm=e.target.value.toLowerCase().trim();clearSearch();if(!searchTerm)return;var first=null;for(var id in EM){var n=nodeMap[id];var hay=((n?n.full_name:id)+' '+(EM[id].textContent||'')).toLowerCase();if(hay.indexOf(searchTerm)>=0){EM[id].classList.add('search-hit');if(!first)first=id;}}if(first)navigateToBlock(first);},200);});
function clearSearch(){for(var id in EM)EM[id].classList.remove('search-hit');}

// ========== Minimap ==========
var mmEl=document.getElementById('minimap');var mmCanvas=document.getElementById('mm-canvas');var mmVp=document.getElementById('mm-viewport');var mmCtx=mmCanvas.getContext('2d');
function getMmSize(){var r=mmEl.getBoundingClientRect();return{w:r.width,h:r.height};}
function typeColor(t){if(t==='module')return'#3e4280a0';if(t==='class')return'#1e6a8aa0';return'#2a6a3aa0';}
function updateMinimap(){var mmSz=getMmSize(),mmW=mmSz.w,mmH=mmSz.h;var dpr=window.devicePixelRatio||1;mmCanvas.width=mmW*dpr;mmCanvas.height=mmH*dpr;mmCtx.setTransform(dpr,0,0,dpr,0,0);var pos=measure();var ids=Object.keys(pos);if(ids.length===0)return;var minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;ids.forEach(function(id){var p=pos[id];minX=Math.min(minX,p.x);minY=Math.min(minY,p.y);maxX=Math.max(maxX,p.x+p.w);maxY=Math.max(maxY,p.y+p.h);});var contentW=maxX-minX+40,contentH=maxY-minY+40;var mmScale=Math.min(mmW/contentW,mmH/contentH);var offX=(mmW-contentW*mmScale)/2-minX*mmScale;var offY=(mmH-contentH*mmScale)/2-minY*mmScale;mmCtx.fillStyle='#0d0e1a';mmCtx.fillRect(0,0,mmW,mmH);ids.forEach(function(id){var p=pos[id];var el=EM[id];var t=el?el.dataset.type:'module';mmCtx.fillStyle=typeColor(t);mmCtx.fillRect(p.x*mmScale+offX,p.y*mmScale+offY,Math.max(p.w*mmScale,1),Math.max(p.h*mmScale,1));});var cr=ctnr.getBoundingClientRect();var vpLeft=(-panX/scale)*mmScale+offX;var vpTop=(-panY/scale)*mmScale+offY;var vpW=(cr.width/scale)*mmScale;var vpH=(cr.height/scale)*mmScale;mmVp.style.left=Math.max(0,vpLeft)+'px';mmVp.style.top=Math.max(0,vpTop)+'px';mmVp.style.width=Math.min(mmW,vpW)+'px';mmVp.style.height=Math.min(mmH,vpH)+'px';mmEl._map={scale:mmScale,offX:offX,offY:offY};}
mmEl.addEventListener('click',function(e){if(mmResizing||mmMode==='tree')return;var map=mmEl._map;if(!map)return;var rect=mmEl.getBoundingClientRect();var mx=e.clientX-rect.left,my=e.clientY-rect.top;if(mx<12||my<12||mx>rect.width-12||my>rect.height-12)return;var cx=(mx-map.offX)/map.scale;var cy=(my-map.offY)/map.scale;var cr=ctnr.getBoundingClientRect();panX=cr.width/2-cx*scale;panY=cr.height/2-cy*scale;updateTx();scheduleDrawEdges();updateMinimap();});
var mmResize=document.getElementById('mm-resize');var mmResizing=false,mmRSx=0,mmRSy=0,mmRSw=0,mmRSh=0,mmRSright=0,mmRSbottom=0;
mmResize.addEventListener('mousedown',function(e){e.preventDefault();e.stopPropagation();mmResizing=true;var r=mmEl.getBoundingClientRect();mmRSx=e.clientX;mmRSy=e.clientY;mmRSw=r.width;mmRSh=r.height;mmRSright=r.right;mmRSbottom=r.bottom;});
window.addEventListener('mousemove',function(e){if(!mmResizing)return;var dx=e.clientX-mmRSx,dy=e.clientY-mmRSy;var nw=Math.max(120,mmRSw-dx),nh=Math.max(80,mmRSh-dy);mmEl.style.width=nw+'px';mmEl.style.height=nh+'px';mmEl.style.right=(window.innerWidth-mmRSright)+'px';mmEl.style.bottom=(window.innerHeight-mmRSbottom)+'px';updateMinimap();});
window.addEventListener('mouseup',function(){mmResizing=false;});
new ResizeObserver(function(){updateMinimap();}).observe(mmEl);
var mmMode='map';var mmToggle=document.getElementById('mm-toggle');var mmTree=document.getElementById('mm-tree');
function buildMmTree(){mmTree.innerHTML='';function add(node,depth){var t=node.type||'module';var it=document.createElement('div');it.className='mm-tree-item t-'+t;it.style.paddingLeft=(6+depth*12)+'px';var ico=document.createElement('span');ico.className='mm-ti-ico';ico.textContent=t==='module'?'▤':t==='class'?'C':t==='method'?'m':'f';var lab=document.createElement('span');lab.className='mm-ti-lbl';lab.textContent=node.label||node.name;lab.title=node.full_name;it.appendChild(ico);it.appendChild(lab);it.addEventListener('click',function(e){e.stopPropagation();navigateToBlock(node.id);});mmTree.appendChild(it);(node.children||[]).forEach(function(c){add(c,depth+1);});if(t==='class'&&node.methods){node.methods.forEach(function(m){add(m,depth+1);});}}MODS.forEach(function(m){add(m,0);});}
mmToggle.addEventListener('click',function(e){e.stopPropagation();mmMode=mmMode==='map'?'tree':'map';mmEl.classList.toggle('mode-tree',mmMode==='tree');if(mmMode==='tree'){mmToggle.textContent='▤';mmToggle.title='Map view';buildMmTree();}else{mmToggle.textContent='☰';mmToggle.title='Tree view';updateMinimap();}});
mmEl.addEventListener('wheel',function(e){if(mmMode==='tree')return;e.preventDefault();var d=e.deltaY>0?0.92:1.08;var ns=Math.max(0.12,Math.min(3,scale*d));var cr=ctnr.getBoundingClientRect(),cx=cr.width/2,cy=cr.height/2;panX=cx-(cx-panX)*(ns/scale);panY=cy-(cy-panY)*(ns/scale);scale=ns;updateTx();invalidateMeasure();scheduleDrawEdges();updateMinimap();},{passive:false});

// ========== Refresh orchestration ==========
var refreshPending=false;
function refreshAll(fit){if(refreshPending){if(fit)pendingFit=true;return;}refreshPending=true;var doFit=fit;requestAnimationFrame(function(){refreshPending=false;setVisibility();updateDots();applyLayout();drawSubsystems();drawConnectors();drawFlow();drawEdges();updateMinimap();if(doFit)fitToScreen();});}
var pendingFit=false;

// ========== Keyboard ==========
document.addEventListener('keydown',function(e){if(e.target.id==='search-box'||e.target.id==='edge-limit'){if(e.key==='Escape')e.target.blur();return;}if(e.key==='f'||e.key==='F')fitToScreen();else if(e.key==='Escape'){closeNavMenu();document.getElementById('source-panel').classList.remove('open');clearSearch();document.getElementById('search-box').value='';searchTerm='';lockedId=null;clearAllEdgeHL();clearBlockHL();}else if(e.key==='/'||(e.ctrlKey&&e.key==='f')){e.preventDefault();document.getElementById('search-box').focus();}});
function showTip(e,text){tip.textContent=text;tip.style.display='block';tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';}
function hideTip(){tip.style.display='none';}

// ========== Go ==========
function buildAll(){MODS.forEach(buildNode);refreshAll(true);}
buildAll();
document.body.classList.toggle('edges-on-top',edgesOnTop);
})();"""


def _walk_dicts(node: dict) -> Iterator[dict]:
    yield node
    for ch in node.get("children", []) or []:
        yield from _walk_dicts(ch)
