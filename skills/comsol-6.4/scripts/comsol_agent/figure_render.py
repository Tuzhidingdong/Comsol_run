"""Deterministic publication renderer driven by real COMSOL solution data.

The headless COMSOL 6.4 Image export did not render a visible colour bar,
tick labels or axis text. This renderer reads the solved field and the actual
finite-element mesh from COMSOL and draws the same data with Matplotlib Agg.
No screenshot, decorative overlay, arbitrary resampling or new solve is used.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.tri import Triangulation
from PIL import Image


class FigureRenderError(RuntimeError):
    pass


def require_arial() -> str:
    """Return the Arial font path, failing instead of silent substitution."""
    try:
        path = font_manager.findfont("Arial", fallback_to_default=False)
    except Exception as exc:
        raise FigureRenderError(f"Arial font is unavailable: {exc}") from exc
    if "arial" not in Path(path).name.lower():
        raise FigureRenderError(f"Arial font was substituted by {path!r}")
    return path


def extract_field_data(model: Any, output_dir: Path, *, component: str = "comp1",
                       mesh_tag: str = "mesh1", variable: str = "T",
                       unit: str = "degC", tag: str = "field_export") -> dict[str, Any]:
    """Export real x/y/T nodes and mesh triangles from an already solved model."""
    java = model.java
    try:
        mesh = java.component(component).mesh(mesh_tag)
    except Exception as exc:
        raise FigureRenderError(f"Mesh {component}/{mesh_tag} is not available: {exc}") from exc
    try:
        vertices = np.asarray([[float(v) for v in row] for row in mesh.getVertex()], dtype=float)
        # COMSOL returns three rows (one per triangle vertex) with one column
        # per element; transpose to the (n_elements, 3) convention.
        triangles = np.array([[int(i) for i in row] for row in mesh.getElem("tri")], dtype=int).T
    except Exception as exc:
        raise FigureRenderError(f"Cannot read mesh vertices/triangles: {exc}") from exc
    if vertices.shape[0] != 2 or triangles.ndim != 2 or triangles.shape[1] != 3 or not len(triangles):
        raise FigureRenderError("A 2-D triangular mesh with connectivity is required")

    data_dir = (Path(output_dir) / "_field_data").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    data_file = (data_dir / "xyT.txt").resolve()
    if data_file.exists():
        raise FigureRenderError(f"Refusing to overwrite field export: {data_file}")
    node = java.result().export().create(tag, "Data")
    node.set("expr", ["x", "y", variable])
    node.set("unit", ["m", "m", unit])
    node.set("filename", str(data_file))
    node.run()
    if not data_file.is_file():
        raise FigureRenderError("COMSOL Data export produced no field file")

    length_unit = "m"
    rows: list[list[float]] = []
    for line in data_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("% Length unit:"):
            length_unit = line.split(":", 1)[1].strip()
        elif line.startswith("%"):
            continue
        else:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    rows.append([float(p) for p in parts[-3:]])
                except ValueError:
                    continue
    exported = np.asarray(rows, dtype=float)
    if exported.ndim != 2 or exported.shape[1] != 3 or len(exported) < 3:
        raise FigureRenderError("COMSOL field export has no usable x/y/T rows")
    value_map = {(round(x, 10), round(y, 10)): t for x, y, t in exported}
    field = []
    for x, y in zip(vertices[0], vertices[1]):
        key = (round(x, 10), round(y, 10))
        if key not in value_map:
            raise FigureRenderError(f"Mesh vertex {key} is missing from the COMSOL field export")
        field.append(value_map[key])
    field_array = np.asarray(field, dtype=float)
    if not np.all(np.isfinite(field_array)):
        raise FigureRenderError("COMSOL field export contains non-finite values")
    return {
        "x": np.asarray(vertices[0]), "y": np.asarray(vertices[1]),
        "values": field_array, "triangles": triangles,
        "variable": variable, "unit": unit, "length_unit": length_unit,
        "node_count": len(field_array), "element_count": len(triangles),
        "data_file": str(data_file), "field_range": [float(field_array.min()), float(field_array.max())],
    }


def _text_boxes(fig: matplotlib.figure.Figure) -> list[dict[str, Any]]:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = []
    for text in fig.findobj(matplotlib.text.Text):
        if not text.get_visible() or not text.get_text().strip():
            continue
        bbox = text.get_window_extent(renderer=renderer)
        boxes.append({
            "text": text.get_text(),
            "x0": float(bbox.x0), "y0": float(bbox.y0),
            "x1": float(bbox.x1), "y1": float(bbox.y1),
        })
    return boxes


def render(data: dict[str, Any], config: dict[str, Any], path: Path) -> dict[str, Any]:
    """Render one PNG/TIFF from COMSOL field data; return visual evidence."""
    arial = require_arial()
    plt.rcParams.update({
        "font.family": "Arial", "font.sans-serif": ["Arial"],
        "font.size": float(config["font_size_pt"]),
        "text.color": "black", "axes.labelcolor": "black",
        "xtick.color": "black", "ytick.color": "black",
        "axes.titlesize": float(config["font_size_pt"]),
    })
    fig, ax = plt.subplots(figsize=(config["width_mm"] / 25.4, config["height_mm"] / 25.4),
                           constrained_layout=True)
    # Keep text bounding boxes in the same pixel coordinate system as the file.
    fig.set_dpi(float(config["resolution_dpi"]))
    triangulation = Triangulation(data["x"], data["y"], data["triangles"])
    cmap = plt.get_cmap("viridis")
    color_range = config.get("color_range") or {}
    vmin = float(color_range.get("min", data["field_range"][0]))
    vmax = float(color_range.get("max", data["field_range"][1]))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
        raise FigureRenderError("Invalid color_range in figure configuration")
    if vmin > data["field_range"][0] or vmax < data["field_range"][1]:
        raise FigureRenderError("color_range cannot hide real field extrema")
    mesh = ax.tripcolor(triangulation, data["values"], cmap=cmap, shading="gouraud",
                        vmin=vmin, vmax=vmax)
    ax.set_xlabel(config["x_label"])
    ax.set_ylabel(config["y_label"])
    ax.set_xlim(float(data["x"].min()), float(data["x"].max()))
    ax.set_ylim(float(data["y"].min()), float(data["y"].max()))
    ax.locator_params(axis="x", nbins=5)
    ax.locator_params(axis="y", nbins=4)
    ax.set_aspect("equal", adjustable="box")
    colorbar = fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.06)
    colorbar.set_label(config["colorbar_label"])
    colorbar.ax.tick_params(labelsize=float(config["font_size_pt"]))
    if config["include_title"]:
        ax.set_title(config["title"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FigureRenderError(f"Refusing to overwrite existing image: {path}")
    fig.savefig(path, dpi=int(config["resolution_dpi"]), format="png" if config["format"] == "png" else "tiff",
                bbox_inches=None, pil_kwargs={} if config["format"] == "tiff" else None)
    boxes = _text_boxes(fig)
    plt.close(fig)
    return {
        "path": str(path), "renderer": "matplotlib_agg_external",
        "font_path": arial, "font_size_pt": config["font_size_pt"],
        "colormap": "viridis", "shading": "gouraud",
        "field_range": data["field_range"], "color_range": [vmin, vmax],
        "text_boxes": boxes,
        "canvas_px": [fig.get_size_inches()[0] * config["resolution_dpi"],
                      fig.get_size_inches()[1] * config["resolution_dpi"]],
        "mesh_nodes": data["node_count"], "mesh_elements": data["element_count"],
    }


def visual_qc(image_path: Path, evidence: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Check rendered pixels and text geometry, not just file metadata."""
    with Image.open(image_path) as im:
        image = im.convert("RGB")
    w, h = image.size
    arr = np.asarray(image)
    boxes = evidence["text_boxes"]
    dark_boxes = 0
    dark_by_text: list[tuple[str, int]] = []
    clipped = []
    for box in boxes:
        x0, y0, x1, y1 = (int(round(box[k])) for k in ("x0", "y0", "x1", "y1"))
        if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
            clipped.append(box["text"])
            continue
        # Matplotlib bbox y is measured from the bottom; PIL from the top.
        crop = arr[h - y1:h - y0, x0:x1]
        count = int((crop.max(axis=2) < 100).sum()) if crop.size else 0
        dark_by_text.append((box["text"], count))
        if count > 0:
            dark_boxes += 1
    # Colour bar: find a narrow region with many distinct colours along a column.
    colorbar_strip = []
    for x in range(int(w * 0.75), w, max(1, w // 200)):
        column = arr[:, x, :]
        if len(np.unique(column[::max(1, h // 200)], axis=0)) >= 20:
            colorbar_strip.append(x)
    critical = [config["x_label"], config["y_label"], config["colorbar_label"]]
    critical_rendered = all(
        any(text == wanted and count > 0 for text, count in dark_by_text) for wanted in critical
    )
    tick_count = sum(1 for text, count in dark_by_text if count > 0 and text not in critical)
    checks = {
        "critical_labels_rendered": critical_rendered,
        "tick_labels_rendered": tick_count >= 6,
        "no_text_clipped": not clipped,
        "colorbar_gradient_visible": bool(colorbar_strip),
        "field_colors_present": len(np.unique(arr[::max(1, h // 100), ::max(1, w // 100)], axis=0)) > 20,
        "axis_labels_present": any("x" in b["text"] for b in boxes) and any("y" in b["text"] for b in boxes),
        "unit_labels_present": any(config["unit"] in b["text"] for b in boxes),
    }
    return {
        "passed": all(checks.values()), "checks": checks,
        "text_box_count": len(boxes), "dark_text_boxes": dark_boxes,
        "critical_labels": critical, "dark_tick_labels": tick_count,
        "clipped_text": clipped, "colorbar_columns": colorbar_strip[:10],
        "image_size_px": [w, h], "manual_review": [
            "Human should confirm scientific colormap choice and tick readability in the final manuscript."
        ],
    }
