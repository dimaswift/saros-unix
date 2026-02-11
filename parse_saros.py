#!/usr/bin/env python3
"""
Parse NASA Saros eclipse series pages into JSONL + JSON output.

Usage:
    python parse_saros.py <saros_number>

Output:
    <saros_number>/
        eclipses.jsonl  - one JSON object per eclipse, sorted by unix_timestamp
        saros.json      - series-level metadata
"""

import sys
import os
import re
import json

import requests
from bs4 import BeautifulSoup


NASA_URL = "https://eclipse.gsfc.nasa.gov/SEsaros/SEsaros{:03d}.html"

# Regex for one eclipse data line in the <pre> block.
# Format: 08570 -33  1613 May 19  17:43:36    103  -4782   Pb   1.5171  0.0712  63.3N 137.6E   0  801  03m59s
ECLIPSE_RE = re.compile(
    r"^(\d{5}|-{5})\s+"         # seq_num (may be ----- for ancient eclipses)
    r"(-?\d+)\s+"               # rel_num
    r"(-?\d{1,5}\s+\w{3}\s+\d{1,2})\s+"  # calendar_date (YYYY Mon DD, year may be negative)
    r"(\d{2}:\d{2}:\d{2})\s+"  # td_of_greatest_eclipse
    r"(-?\d+)\s+"               # delta_t (seconds)
    r"(-?\d+)\s+"               # luna_num
    r"(\w+\+?)\s+"              # ecl_type (may include + suffix e.g. A+)
    r"(-?[\d.]+)\s+"            # gamma
    r"([\d.]+)\s+"              # magnitude
    r"([\d.]+[NS])\s+"          # latitude  e.g. 63.3N
    r"([\d.]+[EW])\s+"          # longitude e.g. 137.6E
    r"(-?\d+)"                  # sun_alt
    r"(?:\s+(-|\d+))?"          # central_width_km (optional, may be '-')
    r"(?:\s+(\d+m\d+s))?"       # central_duration (optional)
    r"\s*$"
)


def fetch_page(saros_num: int) -> str:
    url = NASA_URL.format(saros_num)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def coord_to_deg(value: str) -> float:
    """Convert '63.3N', '81.5W' etc. to signed float degrees."""
    num = float(value[:-1])
    if value[-1] in ("S", "W"):
        num = -num
    return num


_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Julian Day Number of the Unix epoch (1970-01-01)
_JD_UNIX_EPOCH = 2440588


def _julian_day(year: int, month: int, day: int) -> int:
    """Proleptic Gregorian Julian Day Number. Works for any year including BCE."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def to_unix_timestamp(calendar_date: str, td_time: str) -> int:
    """
    Convert NASA calendar date + TD time to Unix timestamp (integer seconds).
    calendar_date: '1613 May 19' or '-2872 Jun 04'  (negative = BCE)
    td_time:       '17:43:36'
    Uses Julian Day Numbers to support the full date range including BCE dates.
    """
    parts = calendar_date.split()
    year = int(parts[0])
    month = _MONTHS[parts[1]]
    day = int(parts[2])
    h, mn, s = (int(x) for x in td_time.split(":"))
    jd = _julian_day(year, month, day)
    day_seconds = h * 3600 + mn * 60 + s
    return (jd - _JD_UNIX_EPOCH) * 86400 + day_seconds


def parse_eclipses(html: str) -> list[dict]:
    """Parse all eclipse entries from the <pre> blocks on the page."""
    soup = BeautifulSoup(html, "html.parser")
    pres = soup.find_all("pre")

    eclipses = []
    seen_seq = set()

    for pre in pres:
        for line in pre.get_text().splitlines():
            m = ECLIPSE_RE.match(line)
            if not m:
                continue

            seq_raw = m.group(1)
            seq_num = int(seq_raw) if seq_raw != "-----" else None
            # Use (seq_num, rel_num) as dedup key since seq_num may be None
            dedup_key = (seq_num, int(m.group(2)))
            if dedup_key in seen_seq:
                continue  # skip duplicate table (page lists catalog twice)
            seen_seq.add(dedup_key)

            calendar_date = m.group(3)
            td_time = m.group(4)
            lat_raw = m.group(10)
            lon_raw = m.group(11)

            entry = {
                "seq_num": seq_num,  # None for ancient eclipses where catalog shows -----
                "rel_num": int(m.group(2)),
                "calendar_date": calendar_date,
                "td_of_greatest_eclipse": td_time,
                "delta_t": int(m.group(5)),
                "luna_num": int(m.group(6)),
                "ecl_type": m.group(7),
                "gamma": float(m.group(8)),
                "magnitude": float(m.group(9)),
                "latitude": lat_raw,
                "latitude_deg": coord_to_deg(lat_raw),
                "longitude": lon_raw,
                "longitude_deg": coord_to_deg(lon_raw),
                "sun_alt": int(m.group(12)),
                "central_width_km": int(m.group(13)) if m.group(13) and m.group(13) != "-" else None,
                "central_duration": m.group(14) if m.group(14) else None,
                "unix_timestamp": to_unix_timestamp(calendar_date, td_time),
            }
            eclipses.append(entry)

    return eclipses


def parse_series_metadata(html: str, saros_num: int, eclipses: list[dict]) -> dict:
    """Extract series-level metadata from the page."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ")

    # Duration in years
    duration_years = None
    m = re.search(r"Duration of Saros\s+\d+\s*=\s*([\d.]+)\s*Years", text, re.IGNORECASE)
    if m:
        duration_years = float(m.group(1))

    # Eclipse type counts from the type distribution table (first table on page)
    type_counts = {"partial": 0, "annular": 0, "total": 0, "hybrid": 0}
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        # Find the header row that contains "Eclipse Type"
        header_row_idx = None
        for idx, row in enumerate(rows):
            cells_text = " ".join(td.get_text(strip=True).lower() for td in row.find_all("td"))
            if "eclipse type" in cells_text:
                header_row_idx = idx
                break
        if header_row_idx is None:
            continue
        for row in rows[header_row_idx + 1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 3:
                continue
            type_name = cells[0].lower()
            try:
                count = int(cells[2])
            except ValueError:
                continue
            if "partial" in type_name:
                type_counts["partial"] = count
            elif "annular" in type_name:
                type_counts["annular"] = count
            elif "hybrid" in type_name or "a-t" in type_name:
                type_counts["hybrid"] = count
            elif "total" in type_name:
                type_counts["total"] = count
        break

    sorted_eclipses = sorted(eclipses, key=lambda e: e["unix_timestamp"])
    first = sorted_eclipses[0] if sorted_eclipses else None
    last = sorted_eclipses[-1] if sorted_eclipses else None

    return {
        "saros_number": saros_num,
        "total_eclipses": len(eclipses),
        "first_eclipse_date": first["calendar_date"] if first else None,
        "first_unix_timestamp": first["unix_timestamp"] if first else None,
        "last_eclipse_date": last["calendar_date"] if last else None,
        "last_unix_timestamp": last["unix_timestamp"] if last else None,
        "duration_years": duration_years,
        "eclipse_type_counts": type_counts,
    }


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <saros_number>", file=sys.stderr)
        sys.exit(1)

    try:
        saros_num = int(sys.argv[1])
    except ValueError:
        print(f"Error: saros_number must be an integer, got: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching Saros {saros_num} from NASA...")
    html = fetch_page(saros_num)

    print("Parsing eclipse data...")
    eclipses = parse_eclipses(html)
    if not eclipses:
        print("Error: no eclipse data found. Check the Saros number.", file=sys.stderr)
        sys.exit(1)
    eclipses.sort(key=lambda e: e["unix_timestamp"])
    print(f"  Found {len(eclipses)} eclipses")

    print("Parsing series metadata...")
    metadata = parse_series_metadata(html, saros_num, eclipses)

    out_dir = str(saros_num)
    os.makedirs(out_dir, exist_ok=True)

    jsonl_path = os.path.join(out_dir, "eclipses.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for entry in eclipses:
            f.write(json.dumps(entry) + "\n")
    print(f"Wrote {len(eclipses)} entries to {jsonl_path}")

    saros_json_path = os.path.join(out_dir, "saros.json")
    with open(saros_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Wrote series metadata to {saros_json_path}")


if __name__ == "__main__":
    main()
