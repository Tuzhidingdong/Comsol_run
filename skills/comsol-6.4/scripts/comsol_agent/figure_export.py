"""Scientific figure export presets, validation and metadata QC.

The presets implement the reusable conventions ported from Data_analysis
(deterministic output, 300 dpi preview, explicit physical canvas, traceable
report and SHA-256). No physics model, variable or journal size is hardcoded.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

SUPPORTED_FORMATS = {"png", "tiff"}
UNSUPPORTED_FORMATS = {
    "pdf": "COMSOL 6.4 client API rejected export type 'PDF' in this installation",
    "svg": "COMSOL 6.4 client API rejected export type 'SVG' in this installation",
    "eps": "Image export exposes epsfilename but imagetype allowlist has no 'eps'",
}
SIZE_PRESETS = {
    "single_column": {"width_mm": 85.0, "height_mm": 60.0},
    "double_column": {"width_mm": 170.0, "height_mm": 110.0},
}
DEFAULT_FONT_FAMILY = "Arial"
DEFAULT_FONT_SIZE_PT = 7
DEFAULT_TEXT_COLOR = "black"
DEFAULT_BACKGROUND = "white"


class FigureExportError(ValueError):
    pass


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_config(item: dict[str, Any]) -> dict[str, Any]:
    """Validate and fill defaults for one image export declaration."""
    if not isinstance(item, dict):
        raise FigureExportError("image export configuration must be an object")
    fmt = str(item.get("format") or item.get("api_type") or "png").lower()
    if fmt in UNSUPPORTED_FORMATS:
        raise FigureExportError(f"format {fmt!r} is not supported: {UNSUPPORTED_FORMATS[fmt]}")
    if fmt not in SUPPORTED_FORMATS:
        raise FigureExportError(
            f"unsupported image format {fmt!r}; supported: {sorted(SUPPORTED_FORMATS)}"
        )
    preset = str(item.get("size_preset") or "single_column")
    if preset not in SIZE_PRESETS and preset != "custom":
        raise FigureExportError(f"unknown size_preset {preset!r}")
    base = SIZE_PRESETS.get(preset, {"width_mm": 0.0, "height_mm": 0.0})
    width = float(item.get("width_mm", base["width_mm"]))
    height = float(item.get("height_mm", base["height_mm"]))
    if preset == "custom" and (width <= 0 or height <= 0):
        raise FigureExportError("custom size_preset requires positive width_mm and height_mm")
    if width <= 0 or height <= 0 or not math.isfinite(width) or not math.isfinite(height):
        raise FigureExportError("canvas width_mm and height_mm must be finite positive numbers")
    renderer = str(item.get("renderer") or "external")
    if renderer not in {"external", "native"}:
        raise FigureExportError("renderer must be 'external' or 'native'")
    purpose = str(item.get("purpose") or "preview")
    if purpose not in {"preview", "publication"}:
        raise FigureExportError("purpose must be 'preview' or 'publication'")
    default_dpi = 300 if purpose == "preview" else 600
    dpi = int(item.get("resolution_dpi", default_dpi))
    if dpi <= 0 or not math.isfinite(dpi):
        raise FigureExportError("resolution_dpi must be a positive integer")
    if purpose == "preview" and fmt == "png" and dpi < 300:
        raise FigureExportError("PNG preview requires resolution_dpi >= 300")
    if purpose == "publication" and fmt == "tiff" and dpi < 600:
        raise FigureExportError("TIFF publication export requires resolution_dpi >= 600")
    filename = str(item.get("filename") or f"{item.get('tag', 'figure')}.{fmt}")
    if Path(filename).name != filename or Path(filename).suffix.lower().lstrip(".") not in {fmt, "tif" if fmt == "tiff" else fmt}:
        raise FigureExportError("filename must be a simple name with a matching extension")
    tag = str(item.get("tag") or Path(filename).stem)
    if not tag or Path(tag).name != tag:
        raise FigureExportError("tag must be a simple name")
    return {
        "tag": tag, "filename": filename, "format": fmt, "purpose": purpose,
        "size_preset": preset, "width_mm": width, "height_mm": height,
        "resolution_dpi": dpi,
        "font_family": str(item.get("font_family", DEFAULT_FONT_FAMILY)),
        "font_size_pt": float(item.get("font_size_pt", DEFAULT_FONT_SIZE_PT)),
        "text_color": str(item.get("text_color", DEFAULT_TEXT_COLOR)),
        "background": str(item.get("background", DEFAULT_BACKGROUND)),
        "include_title": bool(item.get("include_title", False)),
        "renderer": renderer,
        "component": str(item.get("component") or "comp1"),
        "mesh": str(item.get("mesh") or "mesh1"),
        "variable": str(item.get("variable") or "T"),
        "unit": str(item.get("unit") or "degC"),
        "x_label": item.get("x_label"),
        "y_label": item.get("y_label"),
        "colorbar_label": item.get("colorbar_label"),
        "title": str(item.get("title") or ""),
        "plotgroup": item.get("plotgroup"),
        "colorbar": item.get("colorbar"),
        "color_range": item.get("color_range"),
        "legacy_properties": item.get("properties") or {},
    }


def expected_pixels(config: dict[str, Any]) -> tuple[int, int]:
    dpi = config["resolution_dpi"]
    return (
        int(round(config["width_mm"] / 25.4 * dpi)),
        int(round(config["height_mm"] / 25.4 * dpi)),
    )


def _png_metadata(data: bytes) -> dict[str, Any]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise FigureExportError("PNG signature mismatch")
    pos, width, height, dpi = 8, None, None, None
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
        elif ctype == b"pHYs":
            px, py, unit = struct.unpack(">IIB", payload[:9])
            if unit == 1:
                dpi = [round(px * 0.0254), round(py * 0.0254)]
        pos += 12 + length
        if ctype == b"IEND":
            break
    return {"format": "png", "width_px": width, "height_px": height, "dpi": dpi}


def _tiff_metadata(data: bytes) -> dict[str, Any]:
    endian = "<" if data[:2] == b"II" else ">"
    if struct.unpack(endian + "H", data[2:4])[0] != 42:
        raise FigureExportError("TIFF signature mismatch")
    ifd = struct.unpack(endian + "I", data[4:8])[0]
    count = struct.unpack(endian + "H", data[ifd:ifd + 2])[0]
    tags: dict[int, Any] = {}
    for i in range(count):
        off = ifd + 2 + i * 12
        tag, typ, n = struct.unpack(endian + "HHI", data[off:off + 8])
        if tag not in (256, 257, 258, 259, 282, 283, 296):
            continue
        raw = data[off + 8:off + 12]
        if typ == 3 and n == 1:
            value = struct.unpack(endian + "H", raw[:2])[0]
        elif typ == 4 and n == 1:
            value = struct.unpack(endian + "I", raw)[0]
        elif typ == 5 and n == 1:
            ptr = struct.unpack(endian + "I", raw)[0]
            num, den = struct.unpack(endian + "II", data[ptr:ptr + 8])
            value = round(num / den, 3) if den else None
        else:
            continue
        tags[tag] = value
    unit = tags.get(296)
    dpi = None
    if unit == 2 and tags.get(282) and tags.get(283):
        dpi = [int(round(tags[282])), int(round(tags[283]))]
    return {
        "format": "tiff", "width_px": tags.get(256), "height_px": tags.get(257),
        "compression": tags.get(259), "dpi": dpi, "resolution_unit": unit,
    }


def inspect_image(path: str | Path) -> dict[str, Any]:
    data = Path(path).read_bytes()
    if not data:
        raise FigureExportError("exported image is empty")
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return _png_metadata(data)
    if data[:2] in (b"II", b"MM"):
        return _tiff_metadata(data)
    raise FigureExportError("file signature is not PNG or TIFF")


def qc_image(path: str | Path, config: dict[str, Any]) -> dict[str, Any]:
    meta = inspect_image(path)
    exp_w, exp_h = expected_pixels(config)
    errors: list[str] = []
    if (abs((meta.get("width_px") or 0) - exp_w) > 1
            or abs((meta.get("height_px") or 0) - exp_h) > 1):
        errors.append(
            f"pixel size {meta.get('width_px')}x{meta.get('height_px')} differs from expected {exp_w}x{exp_h} by more than 1 px"
        )
    if meta.get("dpi") != [config["resolution_dpi"], config["resolution_dpi"]]:
        errors.append(f"actual DPI {meta.get('dpi')} != configured {config['resolution_dpi']}")
    if config["format"] == "tiff" and meta.get("compression") != 1:
        errors.append(f"TIFF compression {meta.get('compression')} is not lossless (1)")
    physical_w = (meta.get("width_px") or 0) / (meta.get("dpi") or [1, 1])[0] * 25.4 if meta.get("dpi") else 0
    physical_h = (meta.get("height_px") or 0) / (meta.get("dpi") or [1, 1])[1] * 25.4 if meta.get("dpi") else 0
    if abs(physical_w - config["width_mm"]) > 0.5 or abs(physical_h - config["height_mm"]) > 0.5:
        errors.append(
            f"physical size {physical_w:.2f}x{physical_h:.2f} mm != configured "
            f"{config['width_mm']}x{config['height_mm']} mm"
        )
    manual_review = [
        "Font family replacement cannot be fully proven from image bytes; visual check required.",
        "Scientific colour perception (avoid misleading scales) and manuscript-level readability "
        "require human review.",
    ]
    return {
        "passed": not errors, "errors": errors, "metadata": meta,
        "expected_pixels": {"width": exp_w, "height": exp_h},
        "actual_physical_mm": {"width": round(physical_w, 3), "height": round(physical_h, 3)},
        "sha256": sha256_file(path), "manual_review_required": manual_review,
    }
