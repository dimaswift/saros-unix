#!/usr/bin/env python3
"""
export_csv.py — Export eclipse data from binary .db files to CSV.

Reads db/solar/ and db/lunar/ eclipse_times.db + eclipse_info.db,
merges both streams sorted by date, and writes:

  saros_number, type, date, time

  type format : S [A+]   (solar)  /  L [T-]   (lunar)
  date format : DD.MM.YYYY
  time format : HH:MM:SS

Usage:
    python3 export_csv.py                          # all eclipses, stdout
    python3 export_csv.py 2000-01-01 2030-12-31    # date range
    python3 export_csv.py 2000-01-01 2030-12-31 eclipses.csv
    python3 export_csv.py --solar 2000-01-01 2030-12-31
    python3 export_csv.py --lunar 2000-01-01 2030-12-31
"""

import os
import sys
import struct
import csv
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR     = os.path.join(SCRIPT_DIR, "db")

# ── Binary layout (must match build_db.py) ───────────────────────────────────

TIMES_RECORD    = struct.Struct("<q")           # int64, 8 bytes
SOLAR_INFO_REC  = struct.Struct("<hhHBBBB")     # 10 bytes
LUNAR_INFO_REC  = struct.Struct("<HHHBBBB")     # 10 bytes

# Solar eclipse type codes (index matches ecl_type field in eclipse_info.db).
#   A   Annular                    — Moon's disk smaller than Sun, ring of sunlight visible
#   A+  Annular (long)             — long annular phase
#   A-  Annular (sub-central)      — path passes near edge of antumbra
#   Am  Annular (short)            — brief annular phase
#   An  Annular (non-central)      — annular but path misses Earth's centre
#   As  Annular (saros)            — first/last member of a Saros series, annular
#   H   Hybrid (annular-total)     — transitions between annular and total along the path
#   H2  Hybrid (variant 2)
#   H3  Hybrid (variant 3)
#   Hm  Hybrid (short)             — brief hybrid phase
#   P   Partial                    — Moon covers part of the solar disk only
#   Pb  Partial (beginning)        — first eclipse in a Saros series, partial
#   Pe  Partial (end)              — last eclipse in a Saros series, partial
#   T   Total                      — Moon fully covers the Sun
#   T+  Total (long)               — totality lasts more than ~5 minutes
#   T-  Total (sub-central)        — path passes near edge of umbra
#   Tm  Total (short)              — totality lasts less than ~1 minute
#   Tn  Total (non-central)        — total but path misses Earth's centre
#   Ts  Total (saros)              — first/last member of a Saros series, total
SOLAR_TYPE_NAMES = [
    "A", "A+", "A-", "Am", "An", "As",
    "H", "H2", "H3", "Hm",
    "P", "Pb", "Pe",
    "T", "T+", "T-", "Tm", "Tn", "Ts",
]

# Lunar eclipse type codes (index matches ecl_type field in eclipse_info.db).
#   N   Penumbral                  — Moon passes through Earth's penumbra only
#   Nb  Penumbral (beginning)      — first eclipse in a Saros series, penumbral
#   Ne  Penumbral (end)            — last eclipse in a Saros series, penumbral
#   Nx  Penumbral (non-central)    — penumbral, Moon misses the umbral shadow entirely
#   P   Partial                    — Moon partially enters the umbra
#   Pb  Partial (beginning)        — first eclipse in a Saros series, partial
#   Pe  Partial (end)              — last eclipse in a Saros series, partial
#   T   Total                      — Moon fully immersed in the umbra
#   T+  Total (long)               — totality lasts more than ~100 minutes
#   T-  Total (sub-central)        — Moon passes near the edge of the umbra during totality
#   Tm  Total (short)              — totality lasts less than ~20 minutes
#   Tn  Total (non-central)        — total but Moon misses the axis of the shadow
#   Ts  Total (saros)              — first/last member of a Saros series, total
LUNAR_TYPE_NAMES = [
    "N", "Nb", "Ne", "Nx",
    "P", "Pb", "Pe",
    "T", "T+", "T-", "Tm", "Tn", "Ts",
]

# ── Julian Day / calendar helpers ────────────────────────────────────────────

_JD_UNIX_EPOCH = 2440588  # JD of 1970-01-01

def _unix_to_gregorian(ts):
    """Return (year, month, day, hh, mm, ss) from a Unix timestamp (int)."""
    days = ts // 86400
    rem  = ts % 86400
    if rem < 0:
        days -= 1
        rem  += 86400
    hh = rem // 3600
    mm = (rem % 3600) // 60
    ss = rem % 60

    jd = days + _JD_UNIX_EPOCH
    a  = jd + 32044
    b  = (4 * a + 3) // 146097
    c  = a - (b * 146097) // 4
    d  = (4 * c + 3) // 1461
    e  = c - (1461 * d) // 4
    m  = (5 * e + 2) // 153
    day   = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year  = b * 100 + d - 4800 + m // 10
    return int(year), int(month), int(day), int(hh), int(mm), int(ss)

def _gregorian_to_unix(year, month, day):
    """Midnight UTC Unix timestamp for a Gregorian date."""
    a = (14 - month) // 12
    y = year + 4800 - a
    mo = month + 12 * a - 3
    jd = day + (153 * mo + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    return (jd - _JD_UNIX_EPOCH) * 86400

def _parse_date(s):
    """Parse YYYY-MM-DD into a Unix timestamp at midnight UTC."""
    parts = s.split("-")
    if len(parts) != 3:
        raise ValueError(f"Expected YYYY-MM-DD, got: {s!r}")
    return _gregorian_to_unix(int(parts[0]), int(parts[1]), int(parts[2]))

# ── DB readers ───────────────────────────────────────────────────────────────

def _load_times(path):
    """Read eclipse_times.db → list of int64 timestamps."""
    size = os.path.getsize(path)
    count = size // 8
    with open(path, "rb") as f:
        data = f.read()
    return [TIMES_RECORD.unpack_from(data, i * 8)[0] for i in range(count)]

def _load_info_solar(path, count):
    """Read eclipse_info.db (solar layout) → list of dicts."""
    records = []
    with open(path, "rb") as f:
        for _ in range(count):
            raw = f.read(10)
            _lat, _lon, _dur, saros_number, _pos, ecl_type, _alt = \
                SOLAR_INFO_REC.unpack(raw)
            type_name = SOLAR_TYPE_NAMES[ecl_type] \
                if ecl_type < len(SOLAR_TYPE_NAMES) else str(ecl_type)
            records.append({"saros_number": saros_number, "type_name": type_name})
    return records

def _load_info_lunar(path, count):
    """Read eclipse_info.db (lunar layout) → list of dicts."""
    records = []
    with open(path, "rb") as f:
        for _ in range(count):
            raw = f.read(10)
            _pen, _par, _tot, saros_number, _pos, ecl_type, _pad = \
                LUNAR_INFO_REC.unpack(raw)
            type_name = LUNAR_TYPE_NAMES[ecl_type] \
                if ecl_type < len(LUNAR_TYPE_NAMES) else str(ecl_type)
            records.append({"saros_number": saros_number, "type_name": type_name})
    return records

def load_kind(kind):
    """Load all eclipses for 'solar' or 'lunar'. Returns list of row dicts."""
    d = os.path.join(DB_DIR, kind)
    times_path = os.path.join(d, "eclipse_times.db")
    info_path  = os.path.join(d, "eclipse_info.db")
    if not os.path.exists(times_path) or not os.path.exists(info_path):
        print(f"Warning: {kind} db files not found in {d}", file=sys.stderr)
        return []

    times = _load_times(times_path)
    if kind == "solar":
        infos = _load_info_solar(info_path, len(times))
        prefix = "S"
    else:
        infos = _load_info_lunar(info_path, len(times))
        prefix = "L"

    rows = []
    for ts, info in zip(times, infos):
        rows.append({
            "ts":           ts,
            "saros_number": info["saros_number"],
            "type":         f"{prefix} [{info['type_name']}]",
        })
    return rows

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Export eclipse data from binary .db files to CSV.")
    parser.add_argument("start", nargs="?", metavar="YYYY-MM-DD",
                        help="Start date (inclusive). Omit for all data.")
    parser.add_argument("end",   nargs="?", metavar="YYYY-MM-DD",
                        help="End date (inclusive). Omit for all data.")
    parser.add_argument("output", nargs="?", metavar="FILE",
                        help="Output CSV file. Omit to write to stdout.")
    parser.add_argument("--solar",  action="store_true", help="Solar eclipses only.")
    parser.add_argument("--lunar",  action="store_true", help="Lunar eclipses only.")
    args = parser.parse_args()

    kinds = []
    if args.solar:
        kinds = ["solar"]
    elif args.lunar:
        kinds = ["lunar"]
    else:
        kinds = ["solar", "lunar"]

    ts_start = _parse_date(args.start) if args.start else None
    ts_end   = _parse_date(args.end)   if args.end   else None
    # end is inclusive: advance to end of that day
    if ts_end is not None:
        ts_end += 86399

    rows = []
    for kind in kinds:
        rows.extend(load_kind(kind))

    rows.sort(key=lambda r: r["ts"])

    if ts_start is not None:
        rows = [r for r in rows if r["ts"] >= ts_start]
    if ts_end is not None:
        rows = [r for r in rows if r["ts"] <= ts_end]

    out = open(args.output, "w", newline="", encoding="utf-8") \
          if args.output else sys.stdout

    writer = csv.writer(out)
    writer.writerow(["saros_number", "type", "date", "time"])
    for r in rows:
        year, month, day, hh, mm, ss = _unix_to_gregorian(r["ts"])
        date_str = f"{day:02d}.{month:02d}.{year:04d}"
        time_str = f"{hh:02d}:{mm:02d}:{ss:02d}"
        writer.writerow([r["saros_number"], r["type"], date_str, time_str])

    if args.output:
        out.close()
        print(f"Wrote {len(rows)} eclipses to {args.output}", file=sys.stderr)
    else:
        sys.stderr.write(f"{len(rows)} eclipses\n")

if __name__ == "__main__":
    main()
