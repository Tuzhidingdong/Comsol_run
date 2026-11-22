# Scientific figure output standard (COMSOL 6.4 Skill)

This reference defines the **reusable** output rules that the COMSOL Skill must apply whenever it exports a figure. It is derived from the Data_analysis project's engineering conventions, not from any single physics model. Every formal figure export must load and follow this document.

## 1. Source conventions (Data_analysis, read-only reference)

- `src/data_analysis/eis.py:332-420` `plot_eis()` uses Matplotlib `Agg`, explicit canvas sizes (`figsize=(5.2, 4.2)` for Nyquist, `(5.2, 6.0)` for Bode), `constrained_layout=True`, `dpi=300`, explicit axis labels with units, linewidth 1, markersize 3, `set_aspect("equal")` for Nyquist, and a per-operation report with source hash, output hashes and warnings.
- `AGENTS.md` requires deterministic scripts, byte-for-byte source preservation, derived artifacts with parent hashes, and never reporting a partial result as complete.
- `.agents/skills/scientific-data-analysis/SKILL.md` requires plotting and table export to carry exact input IDs and analysis parameters.
- `pyproject.toml` places plotting dependencies in the optional `eis` extra; no global installation is implied.

The 5.2×4.2 / 5.2×6.0 inch values are EIS example sizes and **must not** be hardcoded for COMSOL figures.

## 2. Verified COMSOL 6.4 export capabilities (local runtime evidence)

Evidence: `runs/acceptance/figure_export_validation/export_api_reflection.json`, `export_formats.json`, `export_formats2.json`, `metadata_probe.json`.

| Capability | Result |
|---|---|
| Image export node | `result().export().create(tag, "Image")` created successfully; properties include `size`, `unit`, `width`, `height`, `resolution`, `imagetype`, `pngfilename`, `tifffilename`, `fontsize`, `legend2d`, `title2d`, `background`, `customcolor`, `antialias`. |
| `imagetype` allowlist | `bmp`, `jpeg`, `png`, `tiff`, `gif`, `gltf`. TIFF is **native**; no re-labelled PNG is used. |
| Physical canvas | `size="manualprint"`, `unit="mm"`, `width`, `height` (float), `resolution` (float DPI). 100×50 mm at 300 dpi → 1181×591 px; at 600 dpi → 2362×1181 px. |
| DPI metadata | PNG `pHYs` = 300×300; TIFF `XResolution`/`YResolution` = 600/600 with `ResolutionUnit=2` (inch). Confirmed by binary parsing, not by extension. |
| TIFF compression | Tag 259 = 1 (uncompressed / lossless). |
| PDF / SVG / EPS | `result().export().create(tag, "PDF"|"SVG"|"EPS")` rejected with `FlException: operation cannot be created in this context`. **Vector export is NOT_SUPPORTED** by this COMSOL 6.4 client API. `epsfilename` exists in Image properties but `imagetype` has no `eps`. |
| Font family | No `fontfamily` property found on export node or plot group; `fontsize` is available. Arial cannot be enforced through the verified API. The configured value is recorded and a manual font check is required. |
| Colour bar | `legend2d` on export; `unit`, `legendtitle`, `legendunit`, `colortable`, `rangedatamin/max` on the Surface feature. Configuration is applied and recorded, but headless export in this installation did **not** render a visible colour bar; colour-bar visibility is a manual-review item, not an automatic QC pass. |

## 3. Output presets

| Purpose | Format | DPI | Default size |
|---|---|---|---|
| `preview` | PNG | 300 | `single_column` = 85×60 mm |
| `publication` | TIFF | 600 | `single_column` = 85×60 mm; may be overridden |

`double_column` = 170×110 mm. `size_preset="custom"` requires explicit `width_mm` / `height_mm`. Journal-specific sizes are configuration, never Skill defaults.

Never convert a 300 dpi PNG into a TIFF and rewrite metadata to 600 dpi. A higher-DPI TIFF must be exported natively by COMSOL.

## 4. Declaration example (generic; no model-specific values in the Skill)

```json
"image_exports": [
  {
    "tag": "field_preview", "filename": "field_preview.png",
    "format": "png", "purpose": "preview", "size_preset": "single_column",
    "resolution_dpi": 300, "font_family": "Arial", "font_size_pt": 7,
    "text_color": "black", "background": "white", "include_title": false,
    "plotgroup": "plot_group:<tag>",
    "colorbar": {"unit": "<quantity unit>", "legendtitle": "<quantity name>"}
  }
]
```

All outputs are written under `results/images/preview/` and `results/images/publication/`. A single `figure_export_report.json` records configuration, COMSOL properties, pixel/physical sizes, DPI, compression, SHA-256 and QC results.

## 5. Scientific plotting rules

- Continuous fields: state quantity name, unit, range and colour table explicitly; do not hide real extrema for aesthetics.
- Compare cases with a shared colour range unless scientifically justified.
- Diverging fields with a physical centre use a diverging, centred colour scale; monotonic positive fields use a perceptually uniform sequential scale; rainbow is not the default.
- Line plots: explicit units, linewidth, marker size; maintain aspect where meaningful.
- No automatic in-figure title; captions belong in the manuscript.
- Multi-panel figures share font size, line width, colour range and alignment.

## 6. QC and honesty

Automatic QC verifies signature, decode, pixel size, DPI, physical size consistency, TIFF lossless compression and SHA-256. It **cannot** verify font family replacement or text/colour-bar overlap from file bytes; these are reported as `manual_review_required`. A failed image does not discard successful siblings: report status is `PARTIAL`. Unsupported formats fail explicitly, never silently.
