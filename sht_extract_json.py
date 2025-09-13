"""
Extract OPTION POSITION and SHOT DETAILS to JSON for TH15 pl0x.sht files.

What it does
- Option positions: reads 40 floats at 0x40..0xDF (20 pairs), returns:
  - raw_pairs (20 [x,y] pairs)
  - grouped by levels: high L1..L4 and low L1..L4 (sizes 1,2,3,4)

- Shot details (88-byte records): starting at 0x108, split levels on 0xFFFFFFFF.
  Each record contains:
    - interval, delay
    - 6-float core (f6)
    - y_off, x_sp, size, ang, spd (derived from f6[1:6])
    - tail_raw (24 bytes at +28..+52) hex
    - extra_raw (36 bytes at +52..+88) hex

Usage
  python sht_extract_json.py               # processes all *.sht
  python sht_extract_json.py pl01.sht      # process only this file
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import List, Dict, Any


REC_SIZE = 88
START_ADDR = 0x108
SENTINEL = b"\xff\xff\xff\xff"


def extract_option_positions(data: bytes) -> Dict[str, Any]:
    start = 0x40
    end = 0xE0
    if len(data) < end:
        return {'raw_pairs': [], 'high': {}, 'low': {}}
    vals = [struct.unpack_from('<f', data, off)[0] for off in range(start, end, 4)]
    pairs = [(vals[i], vals[i+1]) for i in range(0, len(vals), 2)]  # 20 pairs

    def group_levels(ps: List[tuple[float, float]]):
        # Split 10 pairs into L1(1), L2(2), L3(3), L4(4)
        res = {}
        idx = 0
        for lvl, n in enumerate([1, 2, 3, 4], start=1):
            res[f'L{lvl}'] = ps[idx:idx+n]
            idx += n
        return res

    high_pairs = pairs[:10]
    low_pairs = pairs[10:]
    return {
        'raw_pairs': pairs,
        'high': group_levels(high_pairs),
        'low': group_levels(low_pairs),
    }


def parse_88_levels(data: bytes, start: int = START_ADDR) -> List[Dict[str, Any]]:
    levels: List[Dict[str, Any]] = []
    cur: List[Dict[str, Any]] = []
    p = start
    size = len(data)
    while p + REC_SIZE <= size:
        rec = data[p:p+REC_SIZE]
        iv, dl = struct.unpack_from('<HH', rec, 0)
        f6 = struct.unpack_from('<6f', rec, 4)
        tail = struct.unpack_from('<HBBHHIIII', rec, 28)
        tail_raw = rec[28:52]
        extra_raw = rec[52:88]
        cur.append({
            'addr': p,
            'interval': iv,
            'delay': dl,
            'f6': [float(x) for x in f6],
            'tail': list(tail),
            'option_num': int(tail[3]),
            'bullet_ai': int(tail[4]),
            'y_off': float(f6[1]),
            'x_sp': float(f6[2]),
            'size': float(f6[3]),
            'ang': float(f6[4]),
            'spd': float(f6[5]),
            'tail_raw': tail_raw.hex(),
            'extra_raw': extra_raw.hex(),
        })
        p += REC_SIZE
        # Level delimiter
        if p + 4 <= size and data[p:p+4] == SENTINEL:
            levels.append({'records': cur})
            cur = []
            p += 4
    if cur:
        levels.append({'records': cur})
    return levels


def extract_to_json(path: Path, pretty: bool = False, style: str = 'compact') -> Path:
    data = path.read_bytes()
    result = {
        'file': path.name,
        'option_positions': extract_option_positions(data),
        'shots_88': {
            'start': START_ADDR,
            'record_size': REC_SIZE,
            'levels': parse_88_levels(data),
        },
    }
    out = path.with_suffix('.json')

    # Rendering styles:
    # - compact: single-line JSON
    # - pretty: indent=2
    # - records: compact overall, but each records[] printed one per line
    if style == 'pretty' or pretty:
        txt = json.dumps(result, indent=2, ensure_ascii=False)
    elif style == 'records':
        # Manually render with per-record newlines
        # Compact pieces
        file_s = json.dumps(result['file'], ensure_ascii=False)
        opt_s = json.dumps(result['option_positions'], separators=(',', ':'), ensure_ascii=False)
        shots = result['shots_88']
        start_s = json.dumps(shots['start'])
        rsize_s = json.dumps(shots['record_size'])
        level_chunks = []
        for lvl in shots['levels']:
            recs = lvl.get('records', [])
            rec_lines = ",\n  ".join(json.dumps(r, separators=(',', ':'), ensure_ascii=False) for r in recs)
            recs_s = "[\n  " + rec_lines + "\n]" if rec_lines else "[]"
            level_chunks.append("{" + "\"records\":" + recs_s + "}")
        levels_s = "[\n " + ",\n ".join(level_chunks) + "\n]"
        txt = "{" + \
              f"\"file\":{file_s}," + \
              f"\"option_positions\":{opt_s}," + \
              f"\"shots_88\":{{\"start\":{start_s},\"record_size\":{rsize_s},\"levels\":{levels_s}}}" + \
              "}"
    else:
        txt = json.dumps(result, separators=(',', ':'), ensure_ascii=False)

    out.write_text(txt, encoding='utf-8')
    return out


def main(argv: List[str]) -> int:
    targets: List[Path]
    pretty = False
    style = 'compact'
    args = argv[1:]
    # Flags: --pretty for indented JSON; --style records for per-record newlines
    if args and args[0] in ('--pretty', '-p'):
        pretty = True
        args = args[1:]
    if args and args[0] in ('--style', '-s'):
        if len(args) >= 2:
            style = args[1]
            args = args[2:]
    if args:
        targets = [Path(a) for a in args]
    else:
        targets = sorted(Path('.').glob('*.sht'))
        if not targets:
            print('No .sht files found.')
            return 0
    for p in targets:
        out = extract_to_json(p, pretty=pretty, style=style)
        print(f'Wrote {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))

def cli() -> int:
    import sys as _sys
    return main(_sys.argv)
