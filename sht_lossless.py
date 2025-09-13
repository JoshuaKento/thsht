"""
Lossless SHT compiler for TH15 variants.

Commands:
  - dump  <input.sht> <output.json>
      Produce a JSON spec that embeds raw section bytes and trailer so that
      building from it reproduces the file byte-for-byte.

  - build <input.json> <output.sht>
      Build a .sht from a JSON spec. If the JSON contains raw_b64/raw_lists_b64
      and trailer_b64, the output will be identical to the original.

  - repack <input.sht> <output.sht>
      Dump then build in-memory, yielding an identical copy.
"""

from __future__ import annotations

import sys
import json
import base64
from pathlib import Path
from typing import Dict

import struct


def _read_header(data: bytes):
    if len(data) < 0x30:
        raise ValueError('Input too small for TH15 header')
    unknown1, level_count = struct.unpack_from('<HH', data, 0)
    header_floats = struct.unpack_from('<7f', data, 4)
    return unknown1, level_count, header_floats

def _sections(data: bytes):
    i1, i2, i3 = struct.unpack_from('<3I', data, 0x20)
    s0, s1, s2 = i1*16, i2*16, i3*16
    end2 = len(data) - 64
    return [(s0, s1), (s1, s2), (s2, end2)]

def _find_sec0_table(data: bytes, st: int, en: int, level_count: int):
    # Look for 10 ascending u32 with first 0, aligned
    for p in range(st, en - 4*level_count, 4):
        vals = [struct.unpack_from('<I', data, p+4*i)[0] for i in range(level_count)]
        if vals[0] != 0:
            continue
        if sorted(vals) != vals:
            continue
        if not all((v & 3) == 0 for v in vals):
            continue
        return p, vals
    return None

def dump_lossless_th15(data: bytes) -> dict:
    unknown1, level_count, header_floats = _read_header(data)
    secs = _sections(data)

    spec = {
        'format': 'TH15',
        'unknown1': unknown1,
        'level_count': level_count,
        'header_floats': list(header_floats),
        'sections': [],
        'trailer_b64': base64.b64encode(data[-64:]).decode('ascii'),
    }

    for si, (st, en) in enumerate(secs):
        entry = {'start': st, 'end': en, 'raw_b64': base64.b64encode(data[st:en]).decode('ascii')}
        if si == 0:
            maybe = _find_sec0_table(data, st, en, level_count)
            if maybe:
                p, offs = maybe
                base_abs = p + 4*level_count
                raw_lists = []
                for i in range(level_count):
                    a = base_abs + offs[i]
                    b = base_abs + (offs[i+1] if i+1<level_count else en)
                    raw_lists.append(base64.b64encode(data[a:b]).decode('ascii'))
                entry['raw_lists_b64'] = raw_lists
        spec['sections'].append(entry)
    return spec

def pack_th15(spec: dict) -> bytes:
    unknown1 = int(spec.get('unknown1', 4))
    level_count = int(spec.get('level_count', 10))
    hf = [float(x) for x in spec.get('header_floats', [0,0,0,0,0,0,0])]
    if len(hf) != 7:
        hf = (hf + [0.0]*7)[:7]

    sections = spec.get('sections', [])
    if len(sections) != 3:
        raise ValueError('TH15 build expects exactly 3 sections in spec')

    # Assemble body after 0x40
    out = bytearray(b'\x00'*0x40)
    offsets = []
    for sec in sections:
        raw_b64 = sec.get('raw_b64')
        if not raw_b64:
            raise ValueError('Section missing raw_b64 for lossless build')
        b = base64.b64decode(raw_b64)
        # Align to 16
        if len(out) % 16:
            out += b'\x00' * (16 - (len(out) % 16))
        offsets.append(len(out))
        out += b

    # Trailer
    tb64 = spec.get('trailer_b64')
    if tb64:
        trailer = base64.b64decode(tb64)
        if len(trailer) != 64:
            raise ValueError('trailer_b64 must decode to 64 bytes')
    else:
        trailer = b'\x00'*60 + b'\xff\xff\xff\xff'
    out += trailer

    # Now fill header at start
    header = bytearray(b'\x00'*0x30)
    # unknown1, level_count
    import struct as _struct
    _struct.pack_into('<HH', header, 0, unknown1, level_count)
    _struct.pack_into('<7f', header, 4, *hf)
    idx = [off // 16 for off in offsets]
    _struct.pack_into('<3I', header, 0x20, *idx)

    out[0:0x30] = header

    # Apply overlays if any
    # Apply unified fields or legacy overlays
    overlays: Dict = {}
    if 'option_positions' in spec or 'shots_88' in spec or 'header' in spec:
        if 'option_positions' in spec:
            overlays['option_positions'] = spec['option_positions']
        if 'shots_88' in spec:
            overlays['shots_88'] = spec['shots_88']
    if spec.get('overlays'):
        overlays.update(spec['overlays'])
    if overlays:
        apply_overlays_th15(out, overlays)

    return bytes(out)

def apply_overlays_th15(out: bytearray, overlays: dict) -> None:
    import struct as _struct
    # Header overlay
    hdr = overlays.get('header') or {}
    if hdr:
        u1 = int(hdr.get('unknown1', _struct.unpack_from('<H', out, 0)[0]))
        lc = int(hdr.get('level_count', _struct.unpack_from('<H', out, 2)[0]))
        _struct.pack_into('<HH', out, 0, u1, lc)
        hf = hdr.get('header_floats')
        if hf and len(hf) == 7:
            _struct.pack_into('<7f', out, 4, *[float(x) for x in hf])

    # Option positions
    opt = overlays.get('option_positions')
    if opt:
        pairs = opt.get('raw_pairs')
        if not pairs:
            pairs = []
            for grp in (opt.get('high') or {}).values():
                pairs.extend(grp)
            for grp in (opt.get('low') or {}).values():
                pairs.extend(grp)
        if pairs and len(pairs) == 20:
            base = 0x40
            for i,(x,y) in enumerate(pairs):
                _struct.pack_into('<f', out, base + i*8, float(x))
                _struct.pack_into('<f', out, base + i*8 + 4, float(y))

    # 88-byte records overlay
    shots = overlays.get('shots_88')
    if shots and isinstance(shots.get('levels'), list):
        for lvl in shots['levels']:
            for r in (lvl.get('records') or []):
                addr = int(r.get('addr', -1))
                if addr < 0 or addr + 88 > len(out):
                    continue
                if 'interval' in r or 'delay' in r:
                    iv = int(r.get('interval', _struct.unpack_from('<H', out, addr)[0]))
                    dl = int(r.get('delay', _struct.unpack_from('<H', out, addr+2)[0]))
                    _struct.pack_into('<HH', out, addr, iv, dl)
                f6 = list(_struct.unpack_from('<6f', out, addr+4))
                if 'f6' in r and len(r['f6']) == 6:
                    f6 = [float(x) for x in r['f6']]
                if 'y_off' in r: f6[1] = float(r['y_off'])
                if 'x_sp' in r:  f6[2] = float(r['x_sp'])
                if 'size' in r:  f6[3] = float(r['size'])
                if 'ang' in r:   f6[4] = float(r['ang'])
                if 'spd' in r:   f6[5] = float(r['spd'])
                _struct.pack_into('<6f', out, addr+4, *f6)
                # Tail precedence: tail_raw > (tail list with optional field edits) > individual fields
                if 'tail_raw' in r:
                    b = bytes.fromhex(r['tail_raw'])
                    if len(b) == 24:
                        out[addr+28:addr+52] = b
                else:
                    t = list(_struct.unpack_from('<HBBHHIIII', out, addr+28))
                    if 'tail' in r and isinstance(r['tail'], (list, tuple)) and len(r['tail']) == 9:
                        t = [int(x) for x in r['tail']]
                    if 'option_num' in r:
                        t[3] = int(r['option_num'])
                    if 'bullet_ai' in r:
                        t[4] = int(r['bullet_ai'])
                    _struct.pack_into('<HBBHHIIII', out, addr+28, *t)
                if 'extra_raw' in r:
                    b = bytes.fromhex(r['extra_raw']);
                    if len(b) == 36:
                        out[addr+52:addr+88] = b

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    cmd = argv[1]

    if cmd == 'dump' and len(argv) == 4:
        inp, outp = Path(argv[2]), Path(argv[3])
        data = inp.read_bytes()
        spec = dump_lossless_th15(data)
        outp.write_text(json.dumps(spec, indent=2), encoding='utf-8')
        print(f'Wrote {outp}')
        return 0

    if cmd == 'build' and len(argv) == 4:
        inp, outp = Path(argv[2]), Path(argv[3])
        spec = json.loads(inp.read_text(encoding='utf-8'))
        if spec.get('format','TH15').upper() != 'TH15':
            print('Only TH15 build is supported.')
            return 2
        data = pack_th15(spec)
        outp.write_bytes(data)
        print(f'Wrote {outp} ({len(data)} bytes).')
        return 0

    if cmd == 'dumpx' and len(argv) == 4:
        # Dump lossless spec enriched with overlays (legacy; kept for compatibility)
        try:
            from .sht_extract_json import extract_option_positions, parse_88_levels, START_ADDR, REC_SIZE  # type: ignore
        except Exception:
            from sht_extract_json import extract_option_positions, parse_88_levels, START_ADDR, REC_SIZE  # type: ignore
        inp, outp = Path(argv[2]), Path(argv[3])
        data = inp.read_bytes()
        spec = dump_lossless_th15(data)
        # Single authoritative entries (no duplicates)
        shots_levels = parse_88_levels(data)
        for lvl in shots_levels:
            for rec in lvl.get('records', []):
                # Drop raw f6 and tail_raw, and any convenience duplicates
                rec.pop('f6', None)
                rec.pop('tail_raw', None)
                rec.pop('option_num', None)
                rec.pop('bullet_ai', None)
        spec['option_positions'] = extract_option_positions(data)
        spec['shots_88'] = {'start': START_ADDR, 'record_size': REC_SIZE, 'levels': shots_levels}
        outp.write_text(json.dumps(spec, indent=2), encoding='utf-8')
        print(f'Wrote {outp}')
        return 0

    if cmd == 'dumpu' and len(argv) == 4:
        # Dump unified single-entry JSON (no overlays block)
        try:
            from .sht_extract_json import extract_option_positions, parse_88_levels, START_ADDR, REC_SIZE  # type: ignore
        except Exception:
            from sht_extract_json import extract_option_positions, parse_88_levels, START_ADDR, REC_SIZE  # type: ignore
        inp, outp = Path(argv[2]), Path(argv[3])
        data = inp.read_bytes()
        spec = dump_lossless_th15(data)
        shots_levels = parse_88_levels(data)
        for lvl in shots_levels:
            for rec in lvl.get('records', []):
                rec.pop('f6', None)
                rec.pop('tail_raw', None)
                rec.pop('option_num', None)
                rec.pop('bullet_ai', None)
        spec['option_positions'] = extract_option_positions(data)
        spec['shots_88'] = {'start': START_ADDR, 'record_size': REC_SIZE, 'levels': shots_levels}
        outp.write_text(json.dumps(spec, indent=2), encoding='utf-8')
        print(f'Wrote {outp}')
        return 0

    if cmd == 'repack' and len(argv) == 4:
        inp, outp = Path(argv[2]), Path(argv[3])
        data = inp.read_bytes()
        spec = dump_lossless_th15(data)
        out = pack_th15(spec)
        outp.write_bytes(out)
        print(f'Repacked {inp} -> {outp} ({len(out)} bytes).')
        return 0

    print(__doc__.strip())
    return 2


def cli() -> int:
    import sys as _sys
    return main(_sys.argv)


if __name__ == '__main__':
    raise SystemExit(cli())
