#!/usr/bin/env python3
"""
Build binary database files from the Saros eclipse JSONL data.

Outputs (written to the same db/ directory this script lives in):
  solar/
    eclipse_times.db  — sorted int64 timestamps, one per solar eclipse
    eclipse_info.db   — 10-byte packed records, one per solar eclipse (same order)
    saros.db          — 174-byte records, one per saros series (indexed by saros_number - 1)
    eclipse_times_<label>.h / eclipse_info_<label>.h / saros_<label>.h  (PROGMEM headers)

  lunar/
    eclipse_times.db  — sorted int64 timestamps, one per lunar eclipse
    eclipse_info.db   — 10-byte packed records, one per lunar eclipse (same order)
    saros.db          — 174-byte records, one per saros series (indexed by saros_number - 1)
    eclipse_times_<label>.h / eclipse_info_<label>.h / saros_<label>.h  (PROGMEM headers)

Lunar eclipse_info_t layout differs from solar:
  [0-1] int16   pen_duration_s   (penumbral duration in seconds, 0xFFFF = n/a)
  [2-3] int16   par_duration_s   (partial duration in seconds,   0xFFFF = n/a)
  [4-5] uint16  total_duration_s (total duration in seconds,     0xFFFF = n/a)
  [6]   uint8   saros_number
  [7]   uint8   saros_pos
  [8]   uint8   ecl_type  (lunar_eclipse_type_t enum)
  [9]   uint8   _pad

Run from any directory:
    python3 db/build_db.py           # build both solar and lunar
    python3 db/build_db.py solar     # build solar only
    python3 db/build_db.py lunar     # build lunar only
"""

import json
import os
import struct
import sys

# ── Type maps ────────────────────────────────────────────────────────────────

# Solar eclipse type -> uint8 (must match solar_eclipse_type_t enum in saros_lib.h)
SOLAR_ECL_TYPE_MAP = {
    "A":  0, "A+": 1, "A-": 2, "Am": 3, "An": 4, "As": 5,
    "H":  6, "H2": 7, "H3": 8, "Hm": 9,
    "P": 10, "Pb":11, "Pe":12,
    "T": 13, "T+":14, "T-":15, "Tm":16, "Tn":17, "Ts":18,
}

# Lunar eclipse type -> uint8
LUNAR_ECL_TYPE_MAP = {
    "N":  0, "Nb": 1, "Ne": 2, "Nx": 3,   # penumbral
    "P":  4, "Pb": 5, "Pe": 6,             # partial
    "T":  7, "T+": 8, "T-": 9, "Tm":10, "Tn":11, "Ts":12,  # total
}

# ── Layout constants ─────────────────────────────────────────────────────────

ECLIPSE_TIMES_RECORD = struct.Struct("<q")           # int64_t, 8 bytes

# Solar eclipse_info_t — 10 bytes
# [0-1] int16   latitude_deg10
# [2-3] int16   longitude_deg10
# [4-5] uint16  central_duration_s  (0xFFFF = n/a)
# [6]   uint8   saros_number
# [7]   uint8   saros_pos
# [8]   uint8   ecl_type  (solar_eclipse_type_t)
# [9]   uint8   sun_alt
SOLAR_INFO_RECORD = struct.Struct("<hhHBBBB")        # 10 bytes

# Lunar eclipse_info_t — 10 bytes
# [0-1] uint16  pen_duration_s   (0xFFFF = n/a)
# [2-3] uint16  par_duration_s   (0xFFFF = n/a)
# [4-5] uint16  total_duration_s (0xFFFF = n/a)
# [6]   uint8   saros_number
# [7]   uint8   saros_pos
# [8]   uint8   ecl_type  (lunar_eclipse_type_t)
# [9]   uint8   _pad
LUNAR_INFO_RECORD = struct.Struct("<HHHBBBB")        # 10 bytes

MAX_ECLIPSES_PER_SAROS = 96
SAROS_ENTRY_RECORD = struct.Struct("<BB" + "H" * MAX_ECLIPSES_PER_SAROS)
#   uint8  count
#   uint8  _pad
#   uint16 indices[96]
# = 2 + 192 = 194 bytes

assert SOLAR_INFO_RECORD.size == 10, f"Expected 10, got {SOLAR_INFO_RECORD.size}"
assert LUNAR_INFO_RECORD.size == 10, f"Expected 10, got {LUNAR_INFO_RECORD.size}"
assert SAROS_ENTRY_RECORD.size == 194, f"Expected 194, got {SAROS_ENTRY_RECORD.size}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)  # parent of db/


# ── Data loaders ─────────────────────────────────────────────────────────────

def load_eclipses(kind: str) -> list[dict]:
    """Load every eclipse from solar/ or lunar/ JSONL files."""
    data_dir = os.path.join(ROOT_DIR, kind)
    if not os.path.isdir(data_dir):
        print(f"  Warning: {data_dir} does not exist, skipping.", file=sys.stderr)
        return []
    entries = []
    for name in sorted(os.listdir(data_dir), key=lambda n: int(n) if n.isdigit() else -1):
        if not name.isdigit():
            continue
        saros_num = int(name)
        path = os.path.join(data_dir, name, "eclipses.jsonl")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                e = json.loads(line)
                e["_saros_number"] = saros_num
                e["_saros_pos"] = i
                entries.append(e)
    return entries


# ── Packers ──────────────────────────────────────────────────────────────────

def pack_solar_info(e: dict) -> bytes:
    lat10 = round(e["latitude_deg"] * 10)
    lon10 = round(e["longitude_deg"] * 10)
    dur_s = e["central_duration"]
    if dur_s is not None:
        mins, secs = dur_s.rstrip("s").split("m")
        dur = int(mins) * 60 + int(secs)
    else:
        dur = 0xFFFF
    ecl_type = SOLAR_ECL_TYPE_MAP[e["ecl_type"]]
    sun_alt  = e["sun_alt"] if e["sun_alt"] is not None else 0
    return SOLAR_INFO_RECORD.pack(
        lat10, lon10, dur, e["_saros_number"], e["_saros_pos"], ecl_type, sun_alt
    )


def _minutes_to_seconds(val: float | None) -> int:
    """Convert duration in fractional minutes to integer seconds, or 0xFFFF if None."""
    if val is None:
        return 0xFFFF
    return min(round(val * 60), 0xFFFE)


def pack_lunar_info(e: dict) -> bytes:
    pen   = _minutes_to_seconds(e.get("pen_duration_m"))
    par   = _minutes_to_seconds(e.get("par_duration_m"))
    total = _minutes_to_seconds(e.get("total_duration_m"))
    ecl_type = LUNAR_ECL_TYPE_MAP.get(e["ecl_type"], 0)
    return LUNAR_INFO_RECORD.pack(
        pen, par, total, e["_saros_number"], e["_saros_pos"], ecl_type, 0
    )


# ── Binary DB builder ────────────────────────────────────────────────────────

def build(kind: str, out_dir: str):
    print(f"Loading {kind} eclipse data...")
    eclipses = load_eclipses(kind)
    if not eclipses:
        print(f"  No data found for {kind}, skipping DB build.")
        return
    eclipses.sort(key=lambda e: e["unix_timestamp"])
    total = len(eclipses)
    print(f"  {total} eclipses loaded and sorted")

    os.makedirs(out_dir, exist_ok=True)

    pack_info = pack_solar_info if kind == "solar" else pack_lunar_info

    # Build saros index map
    saros_index_map: dict[int, list[int]] = {}
    for global_idx, e in enumerate(eclipses):
        saros_index_map.setdefault(e["_saros_number"], []).append(global_idx)

    # eclipse_times.db
    times_path = os.path.join(out_dir, "eclipse_times.db")
    with open(times_path, "wb") as f:
        for e in eclipses:
            f.write(ECLIPSE_TIMES_RECORD.pack(e["unix_timestamp"]))
    print(f"  eclipse_times.db: {total * ECLIPSE_TIMES_RECORD.size:,} bytes")

    # eclipse_info.db
    info_path = os.path.join(out_dir, "eclipse_info.db")
    with open(info_path, "wb") as f:
        for e in eclipses:
            f.write(pack_info(e))
    print(f"  eclipse_info.db:  {total * 10:,} bytes")

    # saros.db
    saros_path = os.path.join(out_dir, "saros.db")
    with open(saros_path, "wb") as f:
        for sn in range(1, 181):
            indices = saros_index_map.get(sn, [])
            count   = len(indices)
            padded  = indices + [0] * (MAX_ECLIPSES_PER_SAROS - count)
            f.write(SAROS_ENTRY_RECORD.pack(count, 0, *padded))
    print(f"  saros.db:         {180 * SAROS_ENTRY_RECORD.size:,} bytes")

    total_bytes = (total * ECLIPSE_TIMES_RECORD.size +
                   total * 10 +
                   180   * SAROS_ENTRY_RECORD.size)
    print(f"  Total DB size:    {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")
    print("Done.\n")


# ── PROGMEM header generator ─────────────────────────────────────────────────

def bytes_to_c_array(data: bytes, cols: int = 16) -> str:
    """Format a bytes object as a C hex initialiser, `cols` bytes per line."""
    lines = []
    for i in range(0, len(data), cols):
        chunk = data[i:i + cols]
        lines.append("    " + ", ".join(f"0x{b:02x}" for b in chunk))
    return ",\n".join(lines)


PROGMEM_MACROS = """\
#ifdef ECLIPSE_USE_PROGMEM
#  include <avr/pgmspace.h>
#  define ECLIPSE_READ_BYTE(p)   pgm_read_byte(p)
#  define ECLIPSE_READ_WORD(p)   pgm_read_word(p)
#  define ECLIPSE_READ_DWORD(p)  pgm_read_dword(p)
#  define ECLIPSE_ATTR           PROGMEM
#else
#  define ECLIPSE_READ_BYTE(p)   (*(const uint8_t  *)(p))
#  define ECLIPSE_READ_WORD(p)   (*(const uint16_t *)(p))
#  define ECLIPSE_READ_DWORD(p)  (*(const uint32_t *)(p))
#  define ECLIPSE_ATTR           /* nothing */
#endif"""


def _header_prologue(guard: str, description: str, size_bytes: int,
                     saros_start: int, saros_end: int, n_eclipses: int,
                     filename: str) -> str:
    return f"""\
/*
 * Auto-generated by build_db.py — DO NOT EDIT
 *
 * {description}
 * Saros range : {saros_start}–{saros_end}
 * Eclipses    : {n_eclipses}
 * Flash usage : {size_bytes:,} bytes ({size_bytes/1024:.1f} KB)
 *
 * Usage (AVR/ESP32):
 *   #define ECLIPSE_USE_PROGMEM
 *   #include "{filename}"
 *
 * Usage (hosted / RAM):
 *   #include "{filename}"
 */

#ifndef {guard}
#define {guard}

#include <stdint.h>

{PROGMEM_MACROS}

"""


def emit_times_header(eclipses: list[dict], label: str,
                      saros_start: int, saros_end: int, out_path: str):
    blob  = b"".join(ECLIPSE_TIMES_RECORD.pack(e["unix_timestamp"]) for e in eclipses)
    guard = f"ECLIPSE_TIMES_{label.upper()}_H"
    n     = len(eclipses)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_header_prologue(guard, "Sorted int64_t timestamps.",
                                 len(blob), saros_start, saros_end, n,
                                 os.path.basename(out_path)))
        f.write(f"#define ECLIPSE_{label.upper()}_COUNT       {n}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_FIRST {saros_start}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_LAST  {saros_end}u\n\n")
        f.write(f"/* eclipse_times_{label}[] — sorted int64_t timestamps, 8 bytes each.\n"
                f" * Size: {len(blob):,} bytes */\n")
        f.write(f"static const uint8_t eclipse_times_{label}[{len(blob)}u] ECLIPSE_ATTR = {{\n")
        f.write(bytes_to_c_array(blob))
        f.write(f"\n}};\n\n#endif /* {guard} */\n")
    print(f"  {os.path.basename(out_path):40s}  {len(blob):>8,} bytes  ({len(blob)/1024:.1f} KB)")


def emit_solar_info_header(eclipses: list[dict], label: str,
                           saros_start: int, saros_end: int, out_path: str):
    blob  = b"".join(pack_solar_info(e) for e in eclipses)
    guard = f"ECLIPSE_INFO_{label.upper()}_H"
    n     = len(eclipses)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_header_prologue(guard, "Packed solar eclipse_info_t records (10 bytes each).",
                                 len(blob), saros_start, saros_end, n,
                                 os.path.basename(out_path)))
        f.write(f"#define ECLIPSE_{label.upper()}_COUNT       {n}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_FIRST {saros_start}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_LAST  {saros_end}u\n\n")
        f.write(f"/* eclipse_info_{label}[] — 10 bytes each (same order as times array).\n"
                f" * Layout per record (little-endian):\n"
                f" *   [0-1] int16   latitude_deg10\n"
                f" *   [2-3] int16   longitude_deg10\n"
                f" *   [4-5] uint16  central_duration_s  (0xFFFF = n/a)\n"
                f" *   [6]   uint8   saros_number\n"
                f" *   [7]   uint8   saros_pos\n"
                f" *   [8]   uint8   ecl_type  (solar_eclipse_type_t enum)\n"
                f" *   [9]   uint8   sun_alt\n"
                f" * Size: {len(blob):,} bytes */\n")
        f.write(f"static const uint8_t eclipse_info_{label}[{len(blob)}u] ECLIPSE_ATTR = {{\n")
        f.write(bytes_to_c_array(blob))
        f.write(f"\n}};\n\n#endif /* {guard} */\n")
    print(f"  {os.path.basename(out_path):40s}  {len(blob):>8,} bytes  ({len(blob)/1024:.1f} KB)")


def emit_lunar_info_header(eclipses: list[dict], label: str,
                           saros_start: int, saros_end: int, out_path: str):
    blob  = b"".join(pack_lunar_info(e) for e in eclipses)
    guard = f"ECLIPSE_INFO_{label.upper()}_H"
    n     = len(eclipses)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_header_prologue(guard, "Packed lunar eclipse_info_t records (10 bytes each).",
                                 len(blob), saros_start, saros_end, n,
                                 os.path.basename(out_path)))
        f.write(f"#define ECLIPSE_{label.upper()}_COUNT       {n}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_FIRST {saros_start}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_LAST  {saros_end}u\n\n")
        f.write(f"/* eclipse_info_{label}[] — 10 bytes each (same order as times array).\n"
                f" * Layout per record (little-endian):\n"
                f" *   [0-1] uint16  pen_duration_s   (0xFFFF = n/a)\n"
                f" *   [2-3] uint16  par_duration_s   (0xFFFF = n/a)\n"
                f" *   [4-5] uint16  total_duration_s (0xFFFF = n/a)\n"
                f" *   [6]   uint8   saros_number\n"
                f" *   [7]   uint8   saros_pos\n"
                f" *   [8]   uint8   ecl_type  (lunar_eclipse_type_t enum)\n"
                f" *   [9]   uint8   _pad\n"
                f" * Size: {len(blob):,} bytes */\n")
        f.write(f"static const uint8_t eclipse_info_{label}[{len(blob)}u] ECLIPSE_ATTR = {{\n")
        f.write(bytes_to_c_array(blob))
        f.write(f"\n}};\n\n#endif /* {guard} */\n")
    print(f"  {os.path.basename(out_path):40s}  {len(blob):>8,} bytes  ({len(blob)/1024:.1f} KB)")


def emit_saros_header(eclipses: list[dict], label: str,
                      saros_start: int, saros_end: int, out_path: str):
    saros_local_map: dict[int, list[int]] = {}
    for local_idx, e in enumerate(eclipses):
        saros_local_map.setdefault(e["_saros_number"], []).append(local_idx)

    blob = b""
    for sn in range(saros_start, saros_end + 1):
        indices = saros_local_map.get(sn, [])
        count   = len(indices)
        padded  = indices + [0] * (MAX_ECLIPSES_PER_SAROS - count)
        blob   += SAROS_ENTRY_RECORD.pack(count, 0, *padded)

    num_saros = saros_end - saros_start + 1
    guard     = f"SAROS_{label.upper()}_H"
    n         = len(eclipses)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_header_prologue(guard, "Saros series index records (174 bytes each).",
                                 len(blob), saros_start, saros_end, n,
                                 os.path.basename(out_path)))
        f.write(f"#define ECLIPSE_{label.upper()}_COUNT       {n}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_FIRST {saros_start}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_LAST  {saros_end}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_COUNT {num_saros}u\n\n")
        f.write(f"/* saros_{label}[] — 174-byte records, indexed by (saros_number - {saros_start}).\n"
                f" * Layout: [0] uint8 count, [1] uint8 _pad, [2..173] uint16 indices[86]\n"
                f" * Size: {len(blob):,} bytes */\n")
        f.write(f"static const uint8_t saros_{label}[{len(blob)}u] ECLIPSE_ATTR = {{\n")
        f.write(bytes_to_c_array(blob))
        f.write(f"\n}};\n\n#endif /* {guard} */\n")
    print(f"  {os.path.basename(out_path):40s}  {len(blob):>8,} bytes  ({len(blob)/1024:.1f} KB)")


def build_headers(kind: str, out_dir: str):
    print(f"Loading {kind} eclipse data for headers...")
    all_eclipses = load_eclipses(kind)
    if not all_eclipses:
        print(f"  No data found for {kind}, skipping header build.")
        return
    all_eclipses.sort(key=lambda e: e["unix_timestamp"])
    print(f"  {len(all_eclipses)} eclipses loaded\n")

    os.makedirs(out_dir, exist_ok=True)

    emit_info = emit_solar_info_header if kind == "solar" else emit_lunar_info_header

    slices = [
        ("all",    1,   180, all_eclipses),
        ("modern", 110, 173, [e for e in all_eclipses
                               if 110 <= e["_saros_number"] <= 173]),
    ]

    for label, s_start, s_end, eclipses in slices:
        print(f"  — {label} (saros {s_start}–{s_end}, {len(eclipses)} eclipses)")
        emit_times_header(eclipses, label, s_start, s_end,
                          os.path.join(out_dir, f"eclipse_times_{label}.h"))
        emit_info(eclipses, label, s_start, s_end,
                  os.path.join(out_dir, f"eclipse_info_{label}.h"))
        emit_saros_header(eclipses, label, s_start, s_end,
                          os.path.join(out_dir, f"saros_{label}.h"))
        print()

    print("Done.\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    kinds = sys.argv[1:] if len(sys.argv) > 1 else ["solar", "lunar"]
    valid = {"solar", "lunar"}
    for k in kinds:
        if k not in valid:
            print(f"Usage: {sys.argv[0]} [solar] [lunar]", file=sys.stderr)
            sys.exit(1)

    for kind in kinds:
        out_dir = os.path.join(SCRIPT_DIR, kind)
        print(f"{'='*60}")
        print(f"  Building {kind.upper()} databases -> db/{kind}/")
        print(f"{'='*60}")
        build(kind, out_dir)
        build_headers(kind, out_dir)
