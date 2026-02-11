#!/usr/bin/env python3
"""
Build binary database files from the Saros eclipse JSONL data.

Outputs (written to the same db/ directory this script lives in):
  eclipse_times.db  — sorted int64 timestamps, one per eclipse
  eclipse_info.db   — 10-byte packed records, one per eclipse (same order)
  saros.db          — 174-byte records, one per saros series (indexed by saros_number - 1)

Run from any directory:
    python3 db/build_db.py
"""

import json
import os
import struct
import sys

# Eclipse type -> uint8 encoding (must match eclipse_db.h enum order)
ECL_TYPE_MAP = {
    "A":  0, "A+": 1, "Am": 2, "An": 3, "As": 4,
    "H":  5, "H2": 6, "H3": 7, "Hm": 8,
    "P":  9, "Pb":10, "Pe":11,
    "T": 12, "T+":13, "Tm":14, "Tn":15, "Ts":16,
}

# Layout constants
ECLIPSE_TIMES_RECORD  = struct.Struct("<q")          # int64_t
ECLIPSE_INFO_RECORD   = struct.Struct("<hhHBBBB")    # 10 bytes packed
#   int16  latitude_deg10
#   int16  longitude_deg10
#   uint16 central_duration  (seconds, 0xFFFF = null)
#   uint8  saros_number
#   uint8  saros_rel_num     (0-based position within saros)
#   uint8  ecl_type
#   uint8  sun_alt

MAX_ECLIPSES_PER_SAROS = 86
SAROS_ENTRY_RECORD = struct.Struct("<BB" + "H" * MAX_ECLIPSES_PER_SAROS)
#   uint8  count
#   uint8  _pad
#   uint16 indices[86]
# = 2 + 172 = 174 bytes

assert ECLIPSE_INFO_RECORD.size == 10, f"Expected 10, got {ECLIPSE_INFO_RECORD.size}"
assert SAROS_ENTRY_RECORD.size == 174, f"Expected 174, got {SAROS_ENTRY_RECORD.size}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.dirname(SCRIPT_DIR)  # parent of db/


def load_all_eclipses():
    """Load every eclipse from all saros JSONL files. Returns (saros_number, eclipse_dict) list."""
    entries = []
    for name in os.listdir(DATA_DIR):
        if not name.isdigit():
            continue
        saros_num = int(name)
        path = os.path.join(DATA_DIR, name, "eclipses.jsonl")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                e = json.loads(line)
                e["_saros_number"] = saros_num
                e["_saros_pos"] = i  # position within this saros (0-based, already sorted by ts)
                entries.append(e)
    return entries


def build(out_dir: str):
    print("Loading eclipse data...")
    eclipses = load_all_eclipses()
    eclipses.sort(key=lambda e: e["unix_timestamp"])
    total = len(eclipses)
    print(f"  {total} eclipses loaded and sorted")

    # Build a lookup: saros_number -> sorted list of global indices
    saros_index_map: dict[int, list[int]] = {}
    for global_idx, e in enumerate(eclipses):
        sn = e["_saros_number"]
        saros_index_map.setdefault(sn, []).append(global_idx)

    # --- eclipse_times.db ---
    times_path = os.path.join(out_dir, "eclipse_times.db")
    with open(times_path, "wb") as f:
        for e in eclipses:
            f.write(ECLIPSE_TIMES_RECORD.pack(e["unix_timestamp"]))
    print(f"  eclipse_times.db: {total * ECLIPSE_TIMES_RECORD.size:,} bytes")

    # --- eclipse_info.db ---
    info_path = os.path.join(out_dir, "eclipse_info.db")
    with open(info_path, "wb") as f:
        for e in eclipses:
            lat10  = round(e["latitude_deg"]  * 10)
            lon10  = round(e["longitude_deg"] * 10)
            dur_s  = e["central_duration"]
            if dur_s is not None:
                mins, secs = dur_s.rstrip("s").split("m")
                dur = int(mins) * 60 + int(secs)
            else:
                dur = 0xFFFF
            saros_num = e["_saros_number"]
            saros_pos = e["_saros_pos"]
            ecl_type  = ECL_TYPE_MAP[e["ecl_type"]]
            sun_alt   = e["sun_alt"] if e["sun_alt"] is not None else 0
            f.write(ECLIPSE_INFO_RECORD.pack(
                lat10, lon10, dur, saros_num, saros_pos, ecl_type, sun_alt
            ))
    print(f"  eclipse_info.db:  {total * ECLIPSE_INFO_RECORD.size:,} bytes")

    # --- saros.db ---
    saros_path = os.path.join(out_dir, "saros.db")
    with open(saros_path, "wb") as f:
        for sn in range(1, 181):
            indices = saros_index_map.get(sn, [])
            count   = len(indices)
            # Pad indices list to MAX_ECLIPSES_PER_SAROS with zeros
            padded  = indices + [0] * (MAX_ECLIPSES_PER_SAROS - count)
            f.write(SAROS_ENTRY_RECORD.pack(count, 0, *padded))
    print(f"  saros.db:         {180 * SAROS_ENTRY_RECORD.size:,} bytes")

    total_bytes = (total * ECLIPSE_TIMES_RECORD.size +
                   total * ECLIPSE_INFO_RECORD.size +
                   180   * SAROS_ENTRY_RECORD.size)
    print(f"  Total DB size:    {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")
    print("Done.")


# ── PROGMEM header generator ─────────────────────────────────────────────────

def pack_eclipse_info_bytes(e: dict) -> bytes:
    """Pack one eclipse into the 10-byte eclipse_info_t layout."""
    lat10 = round(e["latitude_deg"]  * 10)
    lon10 = round(e["longitude_deg"] * 10)
    dur_s = e["central_duration"]
    if dur_s is not None:
        mins, secs = dur_s.rstrip("s").split("m")
        dur = int(mins) * 60 + int(secs)
    else:
        dur = 0xFFFF
    saros_num = e["_saros_number"]
    saros_pos = e["_saros_pos"]
    ecl_type  = ECL_TYPE_MAP[e["ecl_type"]]
    sun_alt   = e["sun_alt"] if e["sun_alt"] is not None else 0
    return ECLIPSE_INFO_RECORD.pack(lat10, lon10, dur, saros_num, saros_pos, ecl_type, sun_alt)


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
    """eclipse_times_<label>.h — sorted int64 timestamps only."""
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
        f.write(f"/* eclipse_times_{label}[]\n"
                f" * Sorted int64_t timestamps, 8 bytes each.\n"
                f" * Array index == local eclipse index for this slice.\n"
                f" * Size: {len(blob):,} bytes\n */\n")
        f.write(f"static const uint8_t eclipse_times_{label}[{len(blob)}u] ECLIPSE_ATTR = {{\n")
        f.write(bytes_to_c_array(blob))
        f.write(f"\n}};\n\n#endif /* {guard} */\n")

    print(f"  {os.path.basename(out_path):40s}  {len(blob):>8,} bytes  ({len(blob)/1024:.1f} KB)")


def emit_info_header(eclipses: list[dict], label: str,
                     saros_start: int, saros_end: int, out_path: str):
    """eclipse_info_<label>.h — packed eclipse_info_t records only."""
    blob  = b"".join(pack_eclipse_info_bytes(e) for e in eclipses)
    guard = f"ECLIPSE_INFO_{label.upper()}_H"
    n     = len(eclipses)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_header_prologue(guard, "Packed eclipse_info_t records (10 bytes each).",
                                 len(blob), saros_start, saros_end, n,
                                 os.path.basename(out_path)))
        f.write(f"#define ECLIPSE_{label.upper()}_COUNT       {n}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_FIRST {saros_start}u\n")
        f.write(f"#define ECLIPSE_{label.upper()}_SAROS_LAST  {saros_end}u\n\n")
        f.write(f"/* eclipse_info_{label}[]\n"
                f" * Packed eclipse_info_t records, 10 bytes each (same order as times array).\n"
                f" * Layout per record (little-endian):\n"
                f" *   [0-1] int16   latitude_deg10\n"
                f" *   [2-3] int16   longitude_deg10\n"
                f" *   [4-5] uint16  central_duration_s  (0xFFFF = n/a)\n"
                f" *   [6]   uint8   saros_number\n"
                f" *   [7]   uint8   saros_pos\n"
                f" *   [8]   uint8   ecl_type  (eclipse_type_t enum)\n"
                f" *   [9]   uint8   sun_alt\n"
                f" * Size: {len(blob):,} bytes\n */\n")
        f.write(f"static const uint8_t eclipse_info_{label}[{len(blob)}u] ECLIPSE_ATTR = {{\n")
        f.write(bytes_to_c_array(blob))
        f.write(f"\n}};\n\n#endif /* {guard} */\n")

    print(f"  {os.path.basename(out_path):40s}  {len(blob):>8,} bytes  ({len(blob)/1024:.1f} KB)")


def emit_saros_header(eclipses: list[dict], label: str,
                      saros_start: int, saros_end: int, out_path: str):
    """saros_<label>.h — fixed-size saros series records only."""
    # Local index map
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
        f.write(f"/* saros_{label}[]\n"
                f" * Fixed 174-byte records, indexed by (saros_number - {saros_start}).\n"
                f" * Layout per record:\n"
                f" *   [0]      uint8   count  (eclipses in this series)\n"
                f" *   [1]      uint8   _pad\n"
                f" *   [2-3]   uint16  indices[0]   local eclipse index\n"
                f" *   ...\n"
                f" *   [172-173] uint16 indices[85]\n"
                f" * Size: {len(blob):,} bytes\n */\n")
        f.write(f"static const uint8_t saros_{label}[{len(blob)}u] ECLIPSE_ATTR = {{\n")
        f.write(bytes_to_c_array(blob))
        f.write(f"\n}};\n\n#endif /* {guard} */\n")

    print(f"  {os.path.basename(out_path):40s}  {len(blob):>8,} bytes  ({len(blob)/1024:.1f} KB)")


def build_headers(out_dir: str):
    print("Loading eclipse data for headers...")
    all_eclipses = load_all_eclipses()
    all_eclipses.sort(key=lambda e: e["unix_timestamp"])
    print(f"  {len(all_eclipses)} eclipses loaded\n")

    slices = [
        ("all",    1,   180, all_eclipses),
        ("modern", 110, 173, [e for e in all_eclipses
                              if 110 <= e["_saros_number"] <= 173]),
    ]

    for label, s_start, s_end, eclipses in slices:
        print(f"  — {label} (saros {s_start}–{s_end}, {len(eclipses)} eclipses)")
        emit_times_header(eclipses, label, s_start, s_end,
                          os.path.join(out_dir, f"eclipse_times_{label}.h"))
        emit_info_header(eclipses, label, s_start, s_end,
                         os.path.join(out_dir, f"eclipse_info_{label}.h"))
        emit_saros_header(eclipses, label, s_start, s_end,
                          os.path.join(out_dir, f"saros_{label}.h"))
        print()

    print("Done.")


if __name__ == "__main__":
    out_dir = SCRIPT_DIR
    build(out_dir)
    print()
    build_headers(out_dir)
