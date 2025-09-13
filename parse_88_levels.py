"""
Parse 88-byte bullet records, grouping by 0xFFFFFFFF level delimiters.

Assumptions (per user-provided spec):
- Bullet record size = 88 bytes.
- Each level ends with a 32-bit sentinel 0xFFFFFFFF.
- Start scanning at 0x108 (first observed record) and proceed sequentially,
  ignoring prior section boundaries.

Output: <name>_88levels.txt with counts and key fields per level.
"""

import struct
from pathlib import Path
from typing import List, Tuple


REC_SIZE = 88
SENTINEL = b"\xff\xff\xff\xff"
START = 0x108


def parse_levels(data: bytes, start: int = START, max_levels: int = 16) -> List[List[bytes]]:
    levels: List[List[bytes]] = []
    cur: List[bytes] = []
    p = start
    size = len(data)
    while p + REC_SIZE <= size:
        cur.append(data[p : p + REC_SIZE])
        p += REC_SIZE
        # Check for 4-byte sentinel
        if p + 4 <= size and data[p : p + 4] == SENTINEL:
            levels.append(cur)
            cur = []
            p += 4
            if len(levels) >= max_levels:
                break
        # Safety stop if we encounter a long run of zeros
        if p >= size:
            break
    if cur:
        levels.append(cur)
    return levels


def unpack_record(rec: bytes):
    # interval, delay, 6 floats, then tail and extra
    iv, dl = struct.unpack_from("<HH", rec, 0)
    f6 = struct.unpack_from("<6f", rec, 4)
    tail = struct.unpack_from("<HBBHHIIII", rec, 28)
    extra = rec[52:88]
    return iv, dl, f6, tail, extra


def main() -> int:
    # Process all .sht files in current directory
    sht_files = sorted(Path('.').glob('*.sht'))
    if not sht_files:
        print('No .sht files found.')
        return 0
    for pth in sht_files:
        fn = str(pth)
        data = pth.read_bytes()
        levels = parse_levels(data)
        out = Path(fn.replace('.sht','_88levels.txt'))
        with out.open('w', encoding='utf-8') as o:
            o.write(f"File: {fn}\n")
            o.write(f"Start: 0x{START:X}, record_size={REC_SIZE}, sentinel=0xFFFFFFFF\n")
            o.write(f"Levels detected: {len(levels)}\n\n")
            for li, lvl in enumerate(levels):
                o.write(f"Level {li}: {len(lvl)} records\n")
                for ri, rec in enumerate(lvl):  # show all records per level
                    iv, dl, f6, tail, extra = unpack_record(rec)
                    y_off, x_sp, size_param, ang, spd = f6[1], f6[2], f6[3], f6[4], f6[5]
                    o.write(
                        f"  [{ri:02d}] iv={iv} dl={dl} y_off={y_off:.3f} x_sp={x_sp:.3f} size={size_param:.3f} ang={ang:.6f} spd={spd:.3f} tail={tail} extra={extra.hex()}\n"
                    )
                o.write("\n")
        print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

def cli() -> int:
    return main()
