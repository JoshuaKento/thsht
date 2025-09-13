# thsht

Tools for working with Touhou game series's `.sht` files.
This is a WIP project and currently only designed for `Th15`.
At the current stage, the code is a mostly AI made.

The current tool does: 
- Lossless dump/build (byte-identical roundtrips) with optional overlays
- Extract option positions and 88-byte shot records to JSON
- Parse and summarize 88-byte records by level
- Pattern-based extraction of candidate 88-byte chunks from `pl01.sht`

See `USAGE.md` for detailed examples and JSON formats.

## Installation

Python 3.8+ is required. No external dependencies (stdlib only).

Just download the repository and you can run the `.py` files directly.

## Quick Start

- Dump losslessly to JSON: `thsht-sht-lossless dump pl01.sht pl01.lossless.json`
- Build back from JSON: `thsht-sht-lossless build pl01.lossless.json pl01.new.sht`
- Repack identically: `thsht-sht-lossless repack pl01.sht pl01.copy.sht`
- Extract human-friendly JSON: `thsht-extract-json -p pl01.sht`
- Parse 88-byte levels: `thsht-parse-88-levels` (writes `*_88levels.txt`)
- pl01 pattern chunks: `thsht-extract-pl01-88-chunks` (writes markdown table)

## Command Line Tools

- `thsht-sht-lossless` — lossless dump/build for TH15 `.sht`
  - `dump` / `dumpx` / `dumpu`, `build`, `repack` (see `USAGE.md`)
- `thsht-extract-json` — extracts option positions and 88-byte records
- `thsht-parse-88-levels` — summarizes 88-byte records per level
- `thsht-extract-pl01-88-chunks` — pattern-based scan for `pl01.sht`

## Python API

- `thsht.sht_lossless` — `dump_lossless_th15(data)`, `pack_th15(spec)`, `apply_overlays_th15(out, overlays)`
- `thsht.sht_extract_json` — `extract_option_positions(data)`, `parse_88_levels(data)`

## Notes

- Only TH15 is supported by the packer. The extractor focuses on TH15 `pl0x.sht` layouts.
- Overlay precedence when building: `tail_raw` > `tail` > convenience fields (`option_num`, `bullet_ai`), and `f6` > individual float fields (`y_off`, `x_sp`, `size`, `ang`, `spd`). Details in `USAGE.md`.
