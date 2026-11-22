"""Tests for external publication rendering and real visual QC."""
from __future__ import annotations

import numpy as np
import pytest

from comsol_agent.figure_render import FigureRenderError, render, require_arial, visual_qc


def synthetic_data():
    x = np.array([0.0, 0.1, 0.0, 0.1, 0.05])
    y = np.array([0.0, 0.0, 0.05, 0.05, 0.025])
    values = np.array([100.0, 0.0, 100.0, 0.0, 50.0])
    triangles = np.array([[0, 1, 4], [1, 3, 4], [3, 2, 4], [2, 0, 4]])
    return {
        "x": x, "y": y, "values": values, "triangles": triangles,
        "variable": "T", "unit": "degC", "length_unit": "m",
        "node_count": len(x), "element_count": len(triangles),
        "field_range": [0.0, 100.0], "data_file": "synthetic",
    }


def config(fmt="png", dpi=300):
    return {
        "format": fmt, "resolution_dpi": dpi, "width_mm": 85.0, "height_mm": 60.0,
        "font_size_pt": 7, "include_title": False, "title": "",
        "x_label": "x (m)", "y_label": "y (m)", "colorbar_label": "Temperature (degC)",
        "color_range": {"min": 0.0, "max": 100.0}, "renderer": "external", "unit": "degC",
    }


def test_arial_is_not_silently_substituted():
    assert "arial" in require_arial().lower()


def test_external_render_has_visible_text_and_colorbar(tmp_path):
    out = tmp_path / "figure.png"
    evidence = render(synthetic_data(), config(), out)
    qc = visual_qc(out, evidence, config())
    assert qc["passed"] is True, qc
    assert qc["checks"]["colorbar_gradient_visible"] is True
    assert qc["checks"]["axis_labels_present"] is True
    assert qc["checks"]["unit_labels_present"] is True
    assert qc["checks"]["no_text_clipped"] is True
    assert evidence["color_range"] == [0.0, 100.0]


def test_color_range_cannot_hide_extrema(tmp_path):
    bad = config()
    bad["color_range"] = {"min": 20.0, "max": 80.0}
    with pytest.raises(FigureRenderError, match="cannot hide real field extrema"):
        render(synthetic_data(), bad, tmp_path / "bad.png")
