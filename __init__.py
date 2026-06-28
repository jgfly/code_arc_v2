"""
code_arc_v2 - Python Code Architecture Visualizer (tree-layout edition)

Reads a Python project AND a reference "component structure" HTML (package/module
tree produced by the LLM prompt in README.md), merges the structure with AST-extracted
classes/functions/call-edges/inheritance, and generates an interactive tree-layout
HTML visualization (top-down tree with connector lines, collapse dots, expand-level
slider, no-overlap auto-reflow).
"""

import os

from .analyzer import CodeAnalyzer, PackageInfo
from .generator import HTMLGenerator
from .structure_reader import StructureGraph, read_structure


def visualize(project_path: str, structure_html_path: str,
               output_path: str = "code_arc_v2_output.html", title: str | None = None):
    """Analyze a Python project and generate an interactive module-graph visualization.

    Args:
        project_path: Path to the Python project root directory.
        structure_html_path: Path to the reference component-structure HTML
            (modules placed at (x, y) with LLM-curated call-flow edges; generated
            via the prompt in README.md).
        output_path: Path for the output HTML file.
        title: Optional title for the visualization. Defaults to project folder name.
    """
    if title is None:
        title = os.path.basename(os.path.abspath(project_path))

    analyzer = CodeAnalyzer(project_path)
    project_data = analyzer.analyze()

    structure: StructureGraph = read_structure(structure_html_path)

    generator = HTMLGenerator(project_data, structure, title)
    html_content = generator.generate()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[OK] Visualization generated: {output_path}")
    return output_path


__all__ = ["CodeAnalyzer", "HTMLGenerator", "PackageInfo", "StructureGraph",
           "read_structure", "visualize"]
