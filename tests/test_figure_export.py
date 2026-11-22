"""Focused tests for figure export configuration and metadata QC."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from comsol_agent import executor as executor_module
from comsol_agent.figure_export import (
    FigureExportError, expected_pixels, qc_image, resolve_config, sha256_file,
    SUPPORTED_FORMATS, UNSUPPORTED_FORMATS,
)

def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def make_png(path: Path, width: int, height: int, dpi: int) -> Path:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ppm = round(dpi / 0.0254)
    phys = struct.pack(">IIB", ppm, ppm, 1)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"pHYs", phys) + _chunk(b"IEND", b""))
    return path


def make_tiff(path: Path, width: int, height: int, dpi: int) -> Path:
    header = b"II" + struct.pack("<HI", 42, 8)
    entries = [
        (256, 3, 1, width), (257, 3, 1, height), (259, 3, 1, 1),
        (282, 5, 1, 86), (283, 5, 1, 94), (296, 3, 1, 2),
    ]
    ifd = struct.pack("<H", len(entries))
    for tag, typ, count, value in entries:
        ifd += struct.pack("<HHI", tag, typ, count) + (struct.pack("<H", value) + b"\x00\x00" if typ == 3 else struct.pack("<I", value))
    ifd += struct.pack("<I", 0)
    assert len(ifd) == 78
    data = header + ifd + struct.pack("<II", dpi, 1) + struct.pack("<II", dpi, 1)
    path.write_bytes(data)
    return path



def test_default_publication_preset():
    cfg = resolve_config({"tag": "fig", "filename": "fig.tif", "format": "tiff", "purpose": "publication"})
    assert cfg["size_preset"] == "single_column"
    assert cfg["width_mm"] == 85.0 and cfg["height_mm"] == 60.0
    assert cfg["resolution_dpi"] == 600
    assert cfg["font_family"] == "Arial" and cfg["font_size_pt"] == 7
    assert cfg["include_title"] is False


def test_format_suffix_and_unsupported_formats():
    with pytest.raises(FigureExportError, match="matching extension"):
        resolve_config({"tag": "f", "filename": "f.png", "format": "tiff", "purpose": "publication"})
    for fmt in UNSUPPORTED_FORMATS:
        with pytest.raises(FigureExportError, match="not supported"):
            resolve_config({"tag": "f", "filename": f"f.{fmt}", "format": fmt})
    assert SUPPORTED_FORMATS == {"png", "tiff"}


def test_invalid_dpi_and_canvas():
    with pytest.raises(FigureExportError, match="resolution_dpi"):
        resolve_config({"tag": "f", "filename": "f.png", "format": "png", "resolution_dpi": 0})
    with pytest.raises(FigureExportError, match="width_mm"):
        resolve_config({"tag": "f", "filename": "f.png", "format": "png", "width_mm": 0})
    with pytest.raises(FigureExportError, match="custom"):
        resolve_config({"tag": "f", "filename": "f.png", "format": "png", "size_preset": "custom"})
    with pytest.raises(FigureExportError, match=">= 300"):
        resolve_config({"tag": "f", "filename": "f.png", "format": "png", "purpose": "preview", "resolution_dpi": 150})


def test_pixels_physical_size_consistency():
    cfg = resolve_config({
        "tag": "f", "filename": "f.png", "format": "png", "purpose": "preview",
        "width_mm": 100, "height_mm": 50, "resolution_dpi": 300,
    })
    assert expected_pixels(cfg) == (1181, 591)


def test_png_metadata_and_qc(tmp_path):
    cfg = resolve_config({
        "tag": "f", "filename": "f.png", "format": "png", "purpose": "preview",
        "width_mm": 100, "height_mm": 50, "resolution_dpi": 300,
    })
    qc = qc_image(make_png(tmp_path / "f.png", 1181, 591, 300), cfg)
    assert qc["passed"] is True
    assert qc["metadata"]["dpi"] == [300, 300]
    assert qc["metadata"]["width_px"] == 1181
    assert len(qc["sha256"]) == 64
    assert qc["manual_review_required"]


def test_tiff_compression_and_dpi(tmp_path):
    cfg = resolve_config({
        "tag": "f", "filename": "f.tif", "format": "tiff", "purpose": "publication",
        "size_preset": "custom", "width_mm": 100, "height_mm": 50, "resolution_dpi": 600,
    })
    qc = qc_image(make_tiff(tmp_path / "f.tif", 2362, 1181, 600), cfg)
    assert qc["passed"] is True
    assert qc["metadata"]["dpi"] == [600, 600]
    assert qc["metadata"]["compression"] == 1


def test_hash_helper(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_partial_failure_keeps_successful_exports(tmp_path, monkeypatch):
    class ExportNode:
        def set(self, key, value):
            setattr(self, key, value)

        def run(self):
            Path(self.pngfilename).write_bytes(b"\x89PNG\r\n\x1a\n")

    class ExportList:
        def create(self, tag, kind):
            return ExportNode()

    class Result:
        def export(self):
            return ExportList()

    class Java:
        def result(self):
            return Result()

    class Model:
        java = Java()

    class PlotGroup:
        def tag(self):
            return "g"

    ex = executor_module.ProfileExecutor(
        client=type("C", (), {"version": "6.4"})(),
        manifest={"metadata": {"task_id": "t"}, "outputs": {"export_images": True}},
        output_dir=tmp_path,
    )
    ex.profile = {"profile_id": "p", "image_exports": [
        {"tag": "ok", "filename": "ok.png", "format": "png", "purpose": "preview", "plotgroup": "plot_group:g"},
        {"tag": "bad", "filename": "bad.png", "format": "png", "purpose": "preview",
         "size_preset": "custom", "plotgroup": "plot_group:g"},
    ]}
    ex.nodes = {"plot_group:g": PlotGroup()}
    ex.model = Model()
    monkeypatch.setattr(executor_module, "qc_image", lambda path, cfg: {
        "passed": True, "errors": [], "sha256": "0" * 64,
    })
    out = ex.run_image_exports()
    assert out["status"] == "PARTIAL"
    assert [e["status"] for e in out["results"]] == ["PASS", "FAIL"]
    assert Path(out["report_path"]).is_file()
    assert Path(out["results"][0]["path"]).is_file()
