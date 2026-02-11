#!/usr/bin/env python3
"""
check_sanity.py — Sanity-check fetched Saros eclipse data.

Checks performed:
  1. Coverage   : every series from 1–180 must have a JSONL file
  2. rel_num gaps: consecutive rel_nums within a series must differ by exactly 1
  3. Time gaps  : consecutive eclipse timestamps in series order (by rel_num)
                  must not exceed MAX_GAP_YEARS (default 27 years ≈ 1.5 Saros periods)

Usage:
    python3 check_sanity.py [solar|lunar|both]   (default: both)
    python3 check_sanity.py solar --max-gap 19
"""

import json
import glob
import os
import sys
import argparse

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

SAROS_PERIOD_YEARS = 18.031  # one Saros cycle ≈ 18 years 11 days
DEFAULT_MAX_GAP    = SAROS_PERIOD_YEARS * 1.5  # generous threshold


def check_series(kind: str, max_gap_years: float) -> int:
    """Check all JSONL files for `kind` (solar or lunar). Returns error count."""
    data_dir = os.path.join(ROOT_DIR, kind)
    errors = 0

    # Coverage check
    missing = []
    for sn in range(1, 181):
        path = os.path.join(data_dir, str(sn), "eclipses.jsonl")
        if not os.path.exists(path):
            missing.append(sn)
    if missing:
        print(f"[{kind}] MISSING data for {len(missing)} series: {missing}")
        errors += len(missing)
    else:
        print(f"[{kind}] Coverage: all 180 series present")

    max_gap_secs = max_gap_years * 365.25 * 86400
    rel_gap_errors = []
    time_gap_errors = []

    for path in sorted(glob.glob(os.path.join(data_dir, "*/eclipses.jsonl")),
                       key=lambda p: int(p.split(os.sep)[-2])):
        saros = int(path.split(os.sep)[-2])
        try:
            data = [json.loads(l) for l in open(path, encoding="utf-8")]
        except Exception as e:
            print(f"[{kind}] ERROR reading {path}: {e}")
            errors += 1
            continue

        if not data:
            print(f"[{kind}] Saros {saros:3d}: EMPTY file")
            errors += 1
            continue

        # Sort by rel_num — matches saros_pos ordering in saros_all.h
        by_rel = sorted(data, key=lambda e: e["rel_num"])

        # rel_num gap check
        for i in range(1, len(by_rel)):
            gap = by_rel[i]["rel_num"] - by_rel[i-1]["rel_num"]
            if gap != 1:
                rel_gap_errors.append((
                    saros, gap,
                    by_rel[i-1]["rel_num"], by_rel[i-1]["calendar_date"],
                    by_rel[i]["rel_num"],   by_rel[i]["calendar_date"],
                ))

        # Time gap check — walk in rel_num order
        for i in range(1, len(by_rel)):
            delta_s = by_rel[i]["unix_timestamp"] - by_rel[i-1]["unix_timestamp"]
            if delta_s > max_gap_secs:
                time_gap_errors.append((
                    saros,
                    delta_s / (365.25 * 86400),
                    by_rel[i-1]["calendar_date"],
                    by_rel[i]["calendar_date"],
                ))

    if rel_gap_errors:
        print(f"\n[{kind}] rel_num GAPS ({len(rel_gap_errors)}):")
        for saros, gap, r1, d1, r2, d2 in sorted(rel_gap_errors):
            print(f"  Saros {saros:3d}: rel {r1:+4d} ({d1}) → rel {r2:+4d} ({d2})  gap={gap}")
        errors += len(rel_gap_errors)
    else:
        print(f"[{kind}] rel_num gaps: none")

    if time_gap_errors:
        print(f"\n[{kind}] Time GAPS > {max_gap_years:.1f} years ({len(time_gap_errors)}):")
        for saros, yrs, d1, d2 in sorted(time_gap_errors, key=lambda x: -x[1]):
            print(f"  Saros {saros:3d}: {d1} → {d2}  ({yrs:.1f} years)")
        errors += len(time_gap_errors)
    else:
        print(f"[{kind}] Time gaps:    none exceeding {max_gap_years:.1f} years")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Sanity-check Saros eclipse data.")
    parser.add_argument("kind", nargs="?", default="both",
                        choices=["solar", "lunar", "both"],
                        help="Dataset to check (default: both)")
    parser.add_argument("--max-gap", type=float, default=DEFAULT_MAX_GAP,
                        metavar="YEARS",
                        help=f"Max allowed gap between eclipses in years "
                             f"(default: {DEFAULT_MAX_GAP:.1f})")
    args = parser.parse_args()

    kinds = ["solar", "lunar"] if args.kind == "both" else [args.kind]
    total_errors = 0

    for kind in kinds:
        print(f"\n{'─'*60}")
        print(f"  Checking {kind} data (max gap: {args.max_gap:.1f} years)")
        print(f"{'─'*60}")
        errs = check_series(kind, args.max_gap)
        total_errors += errs
        status = "OK" if errs == 0 else f"ERRORS: {errs}"
        print(f"[{kind}] Result: {status}")

    print(f"\n{'═'*60}")
    if total_errors == 0:
        print("  All checks passed.")
    else:
        print(f"  Total errors: {total_errors}")
    sys.exit(0 if total_errors == 0 else 1)


if __name__ == "__main__":
    main()
