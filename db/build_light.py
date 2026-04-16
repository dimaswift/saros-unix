#!/usr/bin/env python3
"""
build_light.py — Generate solar_saros_unix.h and lunar_saros_unix.h

Each header is a self-contained, single-header C library containing ONLY:
  - int64_t unix timestamp  (8 bytes, little-endian)
  - uint8_t saros_number    (1 byte)
  - uint8_t saros_pos       (1 byte)
Total: 10 bytes per eclipse record, sorted by unix_time ascending.

The full eclipse-type, geographic, and duration fields from the "fat" library
(saros.h) are deliberately omitted to keep flash usage minimal.

Run from any directory:
    python3 db/build_light.py           # both solar and lunar
    python3 db/build_light.py solar     # solar only
    python3 db/build_light.py lunar     # lunar only
"""

import os
import struct
import sys
import textwrap

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Offsets into eclipse_info.db (10-byte record) ────────────────────────────

INFO_SAROS_NUMBER_OFF = 6   # uint8_t
INFO_SAROS_POS_OFF    = 7   # uint8_t

# ── Helpers ───────────────────────────────────────────────────────────────────

def bytes_to_c_array(data: bytes, cols: int = 16) -> str:
    """Format bytes as a C hex initialiser, cols bytes per line."""
    lines = []
    for i in range(0, len(data), cols):
        chunk = data[i:i + cols]
        lines.append("    " + ", ".join(f"0x{b:02x}" for b in chunk))
    return ",\n".join(lines)


def build_light_blob(kind: str) -> bytes:
    """
    Read eclipse_times.db and eclipse_info.db for 'solar' or 'lunar'.
    Return a bytes object containing the interleaved 10-byte records:
        [int64_t unix_time (8 bytes LE)] [uint8_t saros_number] [uint8_t saros_pos]
    Records are already sorted by unix_time (the source .db files are sorted).
    """
    db_dir     = os.path.join(SCRIPT_DIR, kind)
    times_path = os.path.join(db_dir, "eclipse_times.db")
    info_path  = os.path.join(db_dir, "eclipse_info.db")

    with open(times_path, "rb") as f:
        times_data = f.read()
    with open(info_path, "rb") as f:
        info_data = f.read()

    count = len(times_data) // 8
    assert len(info_data) == count * 10, "times/info record count mismatch"

    blob = bytearray()
    for i in range(count):
        blob += times_data[i * 8 : i * 8 + 8]               # int64 timestamp
        blob += info_data[i * 10 + INFO_SAROS_NUMBER_OFF : i * 10 + INFO_SAROS_NUMBER_OFF + 2]
        # saros_number (byte 6) + saros_pos (byte 7)

    assert len(blob) == count * 10
    return bytes(blob), count


# ── Header template ───────────────────────────────────────────────────────────

_PROGMEM_BLOCK = """\
#ifdef {prefix}_PROGMEM
#  include <avr/pgmspace.h>
#  define _{p}_RD_BYTE(ptr)   pgm_read_byte(ptr)
#  define _{p}_RD_DWORD(ptr)  pgm_read_dword(ptr)
#  define _{p}_ATTR           PROGMEM
#else
#  define _{p}_RD_BYTE(ptr)   (*(const uint8_t  *)(ptr))
#  define _{p}_RD_DWORD(ptr)  (*(const uint32_t *)(ptr))
#  define _{p}_ATTR           /* nothing */
#endif"""

_HEADER_TEMPLATE = """\
/*
 * {filename} — Light {kind} eclipse lookup
 *              (Unix timestamp + Saros number/position only)
 *
 * Record layout  [10 bytes, little-endian]:
 *   bytes 0-7  int64_t  unix_time      — seconds since Unix epoch (may be negative)
 *   byte  8    uint8_t  saros_number   — Saros series (1–180)
 *   byte  9    uint8_t  saros_pos      — 0-based position within the series
 *
 * Data           {count:,} {kind} eclipses, Saros 1–180, sorted by unix_time
 *                Flash usage: {flash_kb:.1f} KB
 *
 * ── API ──────────────────────────────────────────────────────────────────────
 *
 * {prefix}_entry_t  {prefix}_find_next(int64_t ts)
 *   Nearest eclipse at or after ts.   .valid == 0 if past end of dataset.
 *
 * {prefix}_entry_t  {prefix}_find_past(int64_t ts)
 *   Nearest eclipse at or before ts.  .valid == 0 if before start of dataset.
 *
 * {prefix}_entry_t  {prefix}_find_closest(int64_t ts)
 *   Eclipse closest in time to ts.  Future wins when equidistant.
 *
 * uint8_t  {prefix}_list_series(uint8_t saros_number,
 *                               {prefix}_entry_t *out, uint8_t max_count)
 *   Fill out[] with all eclipses in the given Saros series (in time order).
 *   Pass out = NULL to get the count without writing any entries.
 *   Returns the total count of eclipses in the series (≤ 96).
 *
 * void  {prefix}_window(int64_t ts, uint8_t saros_number,
 *                        {prefix}_entry_t *past, {prefix}_entry_t *future)
 *   For the given Saros series:
 *     past   — most recent eclipse strictly before ts   (.valid == 0 if none)
 *     future — next eclipse at or after ts              (.valid == 0 if none)
 *
 * ── Usage ────────────────────────────────────────────────────────────────────
 *
 *   In exactly ONE translation unit (stb-style):
 *
 *     #define {impl_macro}
 *     // #define {PREFIX}_PROGMEM     // AVR / ESP32: store data in flash
 *     #include "{filename}"
 *
 *   In all other translation units (declarations only):
 *
 *     #include "{filename}"
 *
 *   Solar and lunar headers may be included together in the same translation
 *   unit — they use distinct prefixes and internal symbol names.
 *
 * ── Notes ────────────────────────────────────────────────────────────────────
 *
 *   • Timestamps are in the Terrestrial Dynamical (TD) time scale, matching
 *     the NASA source data.  For modern eclipses the offset from UTC is < 2 min.
 *   • find_closest / find_next / find_past perform O(log n) binary search.
 *   • list_series and window perform an O(n) linear scan (n ≈ {count:,}).
 *     For repeated series queries consider caching results.
 *   • Generated by db/build_light.py — do not edit manually.
 */

#ifndef {guard}
#define {guard}

#include <stdint.h>
#include <string.h>   /* memset */

/* ── PROGMEM / RAM accessors ─────────────────────────────────────────────── */

{progmem_block}

/* ── Constants ───────────────────────────────────────────────────────────── */

/** Total number of {kind} eclipses in the dataset (Saros 1–180). */
#define {prefix}_COUNT    {count}u
/** Packed record size in bytes (8-byte timestamp + saros_number + saros_pos). */
#define {prefix}_REC_SIZE 10u

/* ── Entry type ──────────────────────────────────────────────────────────── */

/**
 * A single {kind} eclipse with its Saros series identity.
 * Check .valid before using — it is 0 when no eclipse was found.
 */
typedef struct {{
    int64_t unix_time;      /**< Seconds since Unix epoch (may be negative). */
    uint8_t saros_number;   /**< Saros series number (1–180). */
    uint8_t saros_pos;      /**< 0-based position within the series. */
    uint8_t valid;          /**< 1 = populated; 0 = not found / out of range. */
}} {prefix}_entry_t;

/* ── Public API declarations ─────────────────────────────────────────────── */

{prefix}_entry_t {prefix}_find_next   (int64_t ts);
{prefix}_entry_t {prefix}_find_past   (int64_t ts);
{prefix}_entry_t {prefix}_find_closest(int64_t ts);

uint8_t {prefix}_list_series(uint8_t saros_number,
                              {prefix}_entry_t *out, uint8_t max_count);

void    {prefix}_window(int64_t ts, uint8_t saros_number,
                         {prefix}_entry_t *past, {prefix}_entry_t *future);

/* ══════════════════════════════════════════════════════════════════════════ *
 * Implementation — compiled only when {impl_macro} is defined.              *
 * Define it in exactly ONE translation unit before including this header.   *
 * ══════════════════════════════════════════════════════════════════════════ */
#ifdef {impl_macro}

/* ── Packed data array ───────────────────────────────────────────────────── */
/* {count:,} records × 10 bytes = {flash_bytes:,} bytes                       */
static const uint8_t _{sym}_data[{prefix}_COUNT * {prefix}_REC_SIZE] _{p}_ATTR = {{
{hex_data}
}};

/* ── Internal: read int64 timestamp at record index idx ─────────────────── */
static inline int64_t _{sym}_time(uint32_t idx)
{{
    const uint8_t *p = _{sym}_data + idx * {prefix}_REC_SIZE;
    uint64_t lo = (uint64_t)_{p}_RD_DWORD(p);
    uint64_t hi = (uint64_t)_{p}_RD_DWORD(p + 4u);
    return (int64_t)(lo | (hi << 32));
}}

/* ── Internal: build entry at record index idx ───────────────────────────── */
static {prefix}_entry_t _{sym}_make(uint32_t idx)
{{
    const uint8_t *p = _{sym}_data + idx * {prefix}_REC_SIZE;
    uint64_t lo = (uint64_t)_{p}_RD_DWORD(p);
    uint64_t hi = (uint64_t)_{p}_RD_DWORD(p + 4u);
    {prefix}_entry_t e;
    e.unix_time    = (int64_t)(lo | (hi << 32));
    e.saros_number = _{p}_RD_BYTE(p + 8u);
    e.saros_pos    = _{p}_RD_BYTE(p + 9u);
    e.valid        = 1;
    return e;
}}

/* ── Internal: lower_bound — first index with time >= key ─────────────────── */
static uint32_t _{sym}_lower(int64_t key)
{{
    uint32_t lo = 0, hi = {prefix}_COUNT;
    while (lo < hi) {{
        uint32_t mid = lo + (hi - lo) / 2u;
        if (_{sym}_time(mid) < key) lo = mid + 1u;
        else                         hi = mid;
    }}
    return lo;
}}

/* ── Internal: upper_bound — first index with time > key ─────────────────── */
static uint32_t _{sym}_upper(int64_t key)
{{
    uint32_t lo = 0, hi = {prefix}_COUNT;
    while (lo < hi) {{
        uint32_t mid = lo + (hi - lo) / 2u;
        if (_{sym}_time(mid) <= key) lo = mid + 1u;
        else                          hi = mid;
    }}
    return lo;
}}

/* ── Public function implementations ─────────────────────────────────────── */

{prefix}_entry_t {prefix}_find_next(int64_t ts)
{{
    {prefix}_entry_t empty; memset(&empty, 0, sizeof(empty));
    uint32_t idx = _{sym}_lower(ts);
    return (idx < {prefix}_COUNT) ? _{sym}_make(idx) : empty;
}}

{prefix}_entry_t {prefix}_find_past(int64_t ts)
{{
    {prefix}_entry_t empty; memset(&empty, 0, sizeof(empty));
    uint32_t idx = _{sym}_upper(ts);
    return (idx > 0u) ? _{sym}_make(idx - 1u) : empty;
}}

{prefix}_entry_t {prefix}_find_closest(int64_t ts)
{{
    {prefix}_entry_t nxt = {prefix}_find_next(ts);
    {prefix}_entry_t pst = {prefix}_find_past(ts);
    if (!nxt.valid) return pst;
    if (!pst.valid) return nxt;
    int64_t d_nxt = nxt.unix_time - ts;
    int64_t d_pst = ts - pst.unix_time;
    return (d_pst < d_nxt) ? pst : nxt;
}}

uint8_t {prefix}_list_series(uint8_t saros_number,
                              {prefix}_entry_t *out, uint8_t max_count)
{{
    uint8_t total = 0;
    for (uint32_t i = 0; i < {prefix}_COUNT; i++) {{
        if (_{p}_RD_BYTE(_{sym}_data + i * {prefix}_REC_SIZE + 8u) != saros_number)
            continue;
        if (out && total < max_count)
            out[total] = _{sym}_make(i);
        if (total < 255u) total++;
    }}
    return total;
}}

void {prefix}_window(int64_t ts, uint8_t saros_number,
                      {prefix}_entry_t *past, {prefix}_entry_t *future)
{{
    memset(past,   0, sizeof(*past));
    memset(future, 0, sizeof(*future));
    for (uint32_t i = 0; i < {prefix}_COUNT; i++) {{
        const uint8_t *p = _{sym}_data + i * {prefix}_REC_SIZE;
        if (_{p}_RD_BYTE(p + 8u) != saros_number) continue;
        int64_t t = _{sym}_time(i);
        if (t < ts) {{
            *past = _{sym}_make(i);   /* keep overwriting → last match = most recent past */
        }} else {{
            *future = _{sym}_make(i); /* first match at/after ts in series → earliest future */
            break;
        }}
    }}
}}

#endif /* {impl_macro} */
#endif /* {guard} */
"""


def generate_header(kind: str, out_path: str):
    """Generate a light single-header for 'solar' or 'lunar'."""
    print(f"  Loading {kind} data...")
    blob, count = build_light_blob(kind)
    flash_bytes = len(blob)
    flash_kb    = flash_bytes / 1024.0

    if kind == "solar":
        prefix      = "solar_saros"
        sym         = "ss"           # internal symbol prefix (short → less text)
        p           = "SS"           # PROGMEM macro prefix
        impl_macro  = "SOLAR_SAROS_IMPL"
        guard       = "SOLAR_SAROS_UNIX_H"
    else:
        prefix      = "lunar_saros"
        sym         = "ls"
        p           = "LS"
        impl_macro  = "LUNAR_SAROS_IMPL"
        guard       = "LUNAR_SAROS_UNIX_H"

    filename = os.path.basename(out_path)

    progmem_block = _PROGMEM_BLOCK.format(prefix=prefix.upper(), p=p)

    print(f"  Formatting {count:,} records ({flash_bytes:,} bytes) as hex array...")
    hex_data = bytes_to_c_array(blob, cols=10)   # 10 bytes per line = 1 record per line

    content = _HEADER_TEMPLATE.format(
        filename    = filename,
        kind        = kind,
        count       = count,
        flash_bytes = flash_bytes,
        flash_kb    = flash_kb,
        prefix      = prefix,
        PREFIX      = prefix.upper(),
        sym         = sym,
        p           = p,
        impl_macro  = impl_macro,
        guard       = guard,
        progmem_block = progmem_block,
        hex_data    = hex_data,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    file_kb = os.path.getsize(out_path) / 1024.0
    print(f"  {filename:35s}  {count:>6,} eclipses  "
          f"{flash_bytes:>8,} B binary  {file_kb:>7.1f} KB text")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    kinds = sys.argv[1:] if len(sys.argv) > 1 else ["solar", "lunar"]
    valid = {"solar", "lunar"}
    for k in kinds:
        if k not in valid:
            print(f"Usage: {sys.argv[0]} [solar] [lunar]", file=sys.stderr)
            sys.exit(1)

    print("Building light single-header libraries...")
    for kind in kinds:
        out_path = os.path.join(SCRIPT_DIR, f"{kind}_saros_unix.h")
        generate_header(kind, out_path)
    print("Done.")
