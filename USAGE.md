# thsht — Usage Guide (Standalone)

This guide covers the command line tools and JSON formats produced/consumed by the `thsht` package for Touhou 15 (`TH15`) `.sht` files.

Contents
- Lossless workflow (`thsht-sht-lossless` / `python -m thsht.sht_lossless`)
- Human-friendly extraction (`thsht-extract-json` / `python -m thsht.sht_extract_json`)
- 88-byte levels summary (`thsht-parse-88-levels` / `python -m thsht.parse_88_levels`)
- JSON schemas and editing tips

---

## Installing vs. Running In-Place

You can either install the package to get console scripts, or run modules directly without installing.

- Installed (console scripts):
  - `pip install .` (or `pip install -e .` for dev)
  - Use: `thsht-sht-lossless`, `thsht-extract-json`, `thsht-parse-88-levels`

- In-place (no install):
  - Use: `python -m thsht.sht_lossless`, `python -m thsht.sht_extract_json`, `python -m thsht.parse_88_levels`

Python 3.8+ is required. No external dependencies (stdlib only).

---

## Lossless Workflow (`thsht-sht-lossless`)

Commands
- `dump <input.sht> <output.json>`: Emit a lossless spec. Rebuilding from it reproduces the file byte-for-byte.
- `dumpx <input.sht> <output.json>`: Like `dump`, enriched with unified overlay sections (option positions and shot records). Duplicate fields are removed to avoid conflicts.
- `dumpu <input.sht> <output.json>`: Unified JSON style (no separate `overlays` block).
- `build <input.json> <output.sht>`: Build a `.sht` from a spec. If raw blobs are present, result is byte-identical to the original.
- `repack <input.sht> <output.sht>`: Dump then build in memory, producing an identical copy.

Examples (installed)
- `thsht-sht-lossless dump pl01.sht pl01.lossless.json`
- `thsht-sht-lossless dumpu pl01.sht pl01.losslessu.json`
- `thsht-sht-lossless build pl01.losslessu.json pl01.new.sht`

Examples (in-place)
- `python -m thsht.sht_lossless dump pl01.sht pl01.lossless.json`
- `python -m thsht.sht_lossless build pl01.lossless.json pl01.new.sht`

Notes
- The lossless spec contains three raw sections and a 64-byte trailer, plus header fields. During `build`, header indices are recomputed automatically based on 16-byte alignment.
- When overlays are present (header, option positions, shots), they are applied on top of the reconstructed bytes.

---

## Human-Friendly Extraction (`thsht-extract-json`)

Produces JSON with:
- `option_positions`: 20 XY float pairs (10 high, 10 low), both raw and grouped into levels L1..L4.
- `shots_88`: 88-byte shot records grouped into levels, split by sentinel `0xFFFFFFFF`.

Usage (installed)
- `thsht-extract-json [-p|--pretty] [--style records] [files...]`

Usage (in-place)
- `python -m thsht.sht_extract_json [-p|--pretty] [--style records] [files...]`

Styles
- `compact` (default): single-line JSON
- `pretty`: multi-line, `indent=2`
- `records`: compact overall, but each record listed on its own line

---

## 88-byte Levels Summary (`thsht-parse-88-levels`)

Scans `.sht` for 88-byte records starting at `0x108`, splits levels at `0xFFFFFFFF`, and writes `<name>_88levels.txt` with per-level counts and key fields.

Usage (installed)
- `thsht-parse-88-levels`

Usage (in-place)
- `python -m thsht.parse_88_levels`

---

## JSON Formats and Editing

### Lossless spec (relevant fields)

Top-level
- `format`: must be `"TH15"` for building
- `unknown1`: uint16 (header field)
- `level_count`: uint16 (header field)
- `header_floats`: 7 floats (header payload)
- `sections`: array of 3 entries, each with:
  - `start`, `end`: original offsets (informational)
  - `raw_b64`: base64 of raw section bytes (required for lossless build)
  - `raw_lists_b64` (optional, section 0 only): array of base64 blobs for sub-lists; informational
- `trailer_b64`: base64 of the last 64 bytes of the file

Overlays (optional)
- Placed under either `overlays` or unified at the top level by `dumpu`/`dumpx`.
- `header`: `{ unknown1, level_count, header_floats }`
- `option_positions`:
  - `raw_pairs`: 20 `[x, y]` float pairs
  - or grouped as `high: { L1..L4 }`, `low: { L1..L4 }` (the builder flattens to 20 pairs)
- `shots_88`:
  - `start`: starting address (usually `0x108`)
  - `record_size`: `88`
  - `levels`: list of `{ records: [...] }`

Each record can include the following (builder precedence shown):
- Address/size
  - `addr`: absolute address where this 88-byte record lives
- Timing
  - `interval` (uint16), `delay` (uint16)
- Core floats (6 values at `+4`):
  - Option A: `f6: [f0,f1,f2,f3,f4,f5]`
  - Option B: individual fields (override corresponding `f6` entries):
    - `y_off` (f1), `x_sp` (f2), `size` (f3), `ang` (f4), `spd` (f5)
- Tail (24 bytes at `+28`):
  - Option A (strongest): `tail_raw`: 24 bytes as hex string
  - Option B: `tail`: 9-element array parsed as `<H, B, B, H, H, I, I, I, I>`
    - Convenience overrides (apply to `tail[3]` and `tail[4]` if provided):
      - `option_num` → `tail[3]`
      - `bullet_ai` → `tail[4]`
- Extra (36 bytes at `+52`):
  - `extra_raw`: 36 bytes as hex string

Precedence summary
- For floats: `f6` > individual float fields (`y_off`, `x_sp`, `size`, `ang`, `spd`)
- For tail: `tail_raw` > `tail` > convenience fields (`option_num`, `bullet_ai`)

### Example record edit

Editing a record in a unified lossless JSON (snippet):

```json
{
  "shots_88": {
    "start": 264,
    "record_size": 88,
    "levels": [
      {
        "records": [
          {
            "addr": 1200,
            "interval": 30,
            "delay": 0,
            "y_off": -8.0,
            "x_sp": 48.0,
            "size": 18.0,
            "ang": -1.5707963,
            "spd": 24.0,
            "tail": [0, 0, 0, 258, 3, 65535, 1, 1, 0]
          }
        ]
      }
    ]
  }
}
```

The `tail` array is parsed as `<H, B, B, H, H, I, I, I, I>`. Only `tail[3]` (option number) and `tail[4]` (bullet AI) have convenience keys (`option_num`, `bullet_ai`). If you need full control of all 24 tail bytes, provide `tail_raw` instead of `tail`.

### Byte-identical builds

- If the lossless spec includes all three `raw_b64` section blobs and `trailer_b64`, `build` reproduces the original file exactly (aside from any overlays you intentionally apply).
- Header indices are recomputed according to actual section offsets (16-byte alignment), matching original layout when using original raw blobs.

---

## Tips & Troubleshooting

- Windows paths: quote them if they contain spaces, e.g., `"TH15\\arch\\pl01.sht"`.
- If you run modules directly (without installing), use `python -m thsht.sht_lossless ...` and similar.
- Only TH15 is supported by the packer. Extraction helpers were written against TH15 `pl0x.sht` layouts.

