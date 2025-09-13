"""
Extract 88-byte candidate template chunks from pl01.sht.

Definition of a candidate chunk (pattern-based):
- Search for the 20-byte float sequence corresponding to:
    [-8.0, 48.0, 18.0, -1.5707963705062866, 24.0]
  in little-endian IEEE-754 representation.
- For each occurrence at offset P, the chunk start is S = P - 8
  (because those 5 floats begin at offset S+8 in the known 6-float core).
- Summarize the 88-byte window at [S .. S+88):
  * interval/delay (uint16/uint16) at S
  * 6-float core at S+4
  * tail fields at S+28 parsed as <H B B H H 4I
  * extra bytes [S+52 .. S+88) as hex

Output: pl01_88byte_templates.md with a readable table.
"""

from __future__ import annotations

import struct
from pathlib import Path


def main() -> int:
    path = Path('pl01.sht')
    data = path.read_bytes()

    # Build the 20-byte pattern for the 5 floats
    def f32(v: float) -> bytes:
        return struct.pack('<f', v)

    pattern = (
        f32(-8.0)
        + f32(48.0)
        + f32(18.0)
        + bytes.fromhex('db0fc9bf')  # -1.5707963705062866
        + f32(24.0)
    )

    # Find all pattern occurrences
    pos = []
    start = 0
    while True:
        i = data.find(pattern, start)
        if i == -1:
            break
        pos.append(i)
        start = i + 1

    # Compute chunk starts (start = pattern_pos - 8)
    starts = sorted({p - 8 for p in pos if p >= 8})

    rows = []
    for s in starts:
        if s < 0 or s + 88 > len(data):
            continue
        iv, dl = struct.unpack_from('<HH', data, s)
        f6 = struct.unpack_from('<6f', data, s + 4)
        tail = struct.unpack_from('<HBBHHIIII', data, s + 28)
        extra = data[s + 52 : s + 88]
        rows.append((s, iv, dl, f6, tail, extra))

    # Write report
    out = Path('pl01_88byte_templates.md')
    with out.open('w', encoding='utf-8') as o:
        o.write('# pl01.sht — 88-byte Template Chunks (pattern-based)\n')
        o.write(f'- Pattern hits: {len(pos)}\n')
        o.write(f'- Chunk starts: {len(rows)}\n')
        o.write('- Pattern floats (last 5 of f6): [-8.0, 48.0, 18.0, -1.570796, 24.0]\n\n')
        o.write('| # | Start | iv | dl | f6 (6 floats) | tail (H,B,B,H,H,4I) | extra [+52..+88) |\n')
        o.write('|---|-------|----|----|----------------|---------------------|------------------|\n')
        for i, (addr, iv, dl, f6, tail, extra) in enumerate(rows):
            f6s = ', '.join(f'{x:.6f}' for x in f6)
            tail_fmt = (
                f'{tail[0]},{tail[1]},{tail[2]},{tail[3]},{tail[4]},'
                f'0x{tail[5]:08x},0x{tail[6]:08x},0x{tail[7]:08x},0x{tail[8]:08x}'
            )
            o.write(
                f'| {i:02d} | 0x{addr:04X} | {iv} | {dl} | {f6s} | {tail_fmt} | {extra.hex()} |\n'
            )

    print(f'Wrote {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

def cli() -> int:
    return main()
