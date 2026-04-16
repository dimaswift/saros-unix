"""
Binary database reader for the saros-eclipse library.

Reads the three .db files bundled in saros/data/{solar,lunar}/ and exposes
find_next / find_past / saros_window queries backed by binary search.

Binary layout (little-endian, matches saros.h / build_db.py):
  eclipse_times.db  — int64_t per eclipse, 8 bytes, sorted ascending
  eclipse_info.db   — 10 bytes per eclipse
      solar: <hhHBBBB  (lat10, lon10, dur_s, saros_num, saros_pos, ecl_type, sun_alt)
      lunar: <HHHBBBB  (pen_s, par_s, tot_s, saros_num, saros_pos, ecl_type, _pad)
  saros.db          — 194 bytes per series (Saros 1–180)
      <BB + uint16[96]  (count, _pad, global_indices[96])
"""

from __future__ import annotations

import struct
from datetime import datetime, timezone
from importlib.resources import files
from typing import Union

from ._types import (
    EclipseResult,
    LunarEclipse,
    LunarEclipseType,
    SarosWindow,
    SolarEclipse,
    SolarEclipseType,
)

# ── Binary format constants (must match build_db.py / saros.h) ───────────────

_TIMES_FMT   = struct.Struct("<q")          # int64_t, 8 bytes
_SOLAR_FMT   = struct.Struct("<hhHBBBB")    # 10 bytes
_LUNAR_FMT   = struct.Struct("<HHHBBBB")    # 10 bytes
_SAROS_FMT   = struct.Struct("<BB" + "H" * 96)  # 194 bytes

_TIMES_SIZE  = 8
_INFO_SIZE   = 10
_SAROS_SIZE  = 194
_MAX_PER_SAROS = 96
_NA_DURATION = 0xFFFF  # sentinel value for "not applicable" in packed records

_SOLAR_TYPE_COUNT = 19
_LUNAR_TYPE_COUNT = 13

AnyEclipse = Union[SolarEclipse, LunarEclipse]


# ── Input normalisation ───────────────────────────────────────────────────────

def _to_unix(ts: int | float | datetime) -> int:
    """Normalise a timestamp to a Unix integer (seconds since epoch)."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            # Treat naive datetimes as UTC, matching the most common expectation.
            ts = ts.replace(tzinfo=timezone.utc)
        return int(ts.timestamp())
    return int(ts)


# ── Database reader ───────────────────────────────────────────────────────────

class _EclipseDB:
    """Holds one kind (solar or lunar) of eclipse data loaded from .db files."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        pkg_data = files("saros") / "data" / kind

        self._times: bytes = (pkg_data / "eclipse_times.db").read_bytes()
        self._info:  bytes = (pkg_data / "eclipse_info.db").read_bytes()
        self._saros: bytes = (pkg_data / "saros.db").read_bytes()

        self._count = len(self._times) // _TIMES_SIZE

    # ── Low-level accessors ───────────────────────────────────────────────────

    def _read_time(self, idx: int) -> int:
        return _TIMES_FMT.unpack_from(self._times, idx * _TIMES_SIZE)[0]

    def _read_solar_info(self, idx: int) -> SolarEclipse:
        lat10, lon10, dur, saros_num, saros_pos, ecl_type, sun_alt = \
            _SOLAR_FMT.unpack_from(self._info, idx * _INFO_SIZE)
        return SolarEclipse(
            unix_time=self._read_time(idx),
            global_index=idx,
            saros_number=saros_num,
            saros_pos=saros_pos,
            type=SolarEclipseType(ecl_type) if ecl_type < _SOLAR_TYPE_COUNT
                 else SolarEclipseType.P,
            latitude=lat10 / 10.0,
            longitude=lon10 / 10.0,
            central_duration=None if dur == _NA_DURATION else dur,
            sun_altitude=sun_alt,
        )

    def _read_lunar_info(self, idx: int) -> LunarEclipse:
        pen, par, tot, saros_num, saros_pos, ecl_type, _pad = \
            _LUNAR_FMT.unpack_from(self._info, idx * _INFO_SIZE)
        return LunarEclipse(
            unix_time=self._read_time(idx),
            global_index=idx,
            saros_number=saros_num,
            saros_pos=saros_pos,
            type=LunarEclipseType(ecl_type) if ecl_type < _LUNAR_TYPE_COUNT
                 else LunarEclipseType.P,
            penumbral_duration=None if pen == _NA_DURATION else pen,
            partial_duration=None if par == _NA_DURATION else par,
            total_duration=None if tot == _NA_DURATION else tot,
        )

    def _make_entry(self, idx: int) -> AnyEclipse:
        if self._kind == "solar":
            return self._read_solar_info(idx)
        return self._read_lunar_info(idx)

    # ── Saros index ───────────────────────────────────────────────────────────

    def _load_saros_series(self, saros_number: int) -> tuple[int, list[int]]:
        """Return (count, [global_indices]) for the given Saros series (1–180)."""
        if not (1 <= saros_number <= 180):
            return 0, []
        offset = (saros_number - 1) * _SAROS_SIZE
        if offset + _SAROS_SIZE > len(self._saros):
            return 0, []
        fields = _SAROS_FMT.unpack_from(self._saros, offset)
        count = fields[0]
        indices = list(fields[2:2 + count])  # fields[1] is _pad; fields[2..] are uint16
        return count, indices

    def _saros_neighbours(
        self, saros_number: int, saros_pos: int
    ) -> tuple[AnyEclipse | None, AnyEclipse | None]:
        """Return (prev, next) eclipses within the same Saros series."""
        count, indices = self._load_saros_series(saros_number)
        if count == 0:
            return None, None
        prev_entry = self._make_entry(indices[saros_pos - 1]) if saros_pos > 0 else None
        next_entry = self._make_entry(indices[saros_pos + 1]) if saros_pos + 1 < count else None
        return prev_entry, next_entry

    # ── Binary search ─────────────────────────────────────────────────────────

    def _lower_bound(self, key: int) -> int:
        """First index whose timestamp >= key; equals self._count if all < key."""
        lo, hi = 0, self._count
        while lo < hi:
            mid = (lo + hi) // 2
            if self._read_time(mid) < key:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _upper_bound(self, key: int) -> int:
        """First index whose timestamp > key; element at result-1 is the last <= key."""
        lo, hi = 0, self._count
        while lo < hi:
            mid = (lo + hi) // 2
            if self._read_time(mid) <= key:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def list_series(self, saros_number: int) -> list[AnyEclipse]:
        """Return every eclipse in *saros_number* in ascending time order.

        Returns an empty list for invalid series numbers (outside 1–180) or
        series with no entries.
        """
        count, indices = self._load_saros_series(saros_number)
        return [self._make_entry(idx) for idx in indices[:count]]

    # ── Public query methods ──────────────────────────────────────────────────

    def find_next(self, ts: int) -> EclipseResult:
        """Nearest eclipse at or after *ts*, plus its Saros neighbours."""
        idx = self._lower_bound(ts)
        if idx >= self._count:
            return EclipseResult(eclipse=None, saros_prev=None, saros_next=None)
        entry = self._make_entry(idx)
        prev_e, next_e = self._saros_neighbours(entry.saros_number, entry.saros_pos)
        return EclipseResult(eclipse=entry, saros_prev=prev_e, saros_next=next_e)

    def find_past(self, ts: int) -> EclipseResult:
        """Nearest eclipse at or before *ts*, plus its Saros neighbours."""
        idx = self._upper_bound(ts)
        if idx == 0:
            return EclipseResult(eclipse=None, saros_prev=None, saros_next=None)
        entry = self._make_entry(idx - 1)
        prev_e, next_e = self._saros_neighbours(entry.saros_number, entry.saros_pos)
        return EclipseResult(eclipse=entry, saros_prev=prev_e, saros_next=next_e)

    def saros_window(self, ts: int, saros_number: int) -> SarosWindow:
        """Most recent past and next future eclipse in a specific Saros series."""
        count, indices = self._load_saros_series(saros_number)
        if count == 0:
            return SarosWindow(saros_number=saros_number, past=None, future=None)

        # Binary search within the series-local index list.
        lo, hi = 0, count
        while lo < hi:
            mid = (lo + hi) // 2
            if self._read_time(indices[mid]) < ts:
                lo = mid + 1
            else:
                hi = mid
        # lo = first position in indices[] with time >= ts

        past   = self._make_entry(indices[lo - 1]) if lo > 0     else None
        future = self._make_entry(indices[lo])     if lo < count  else None
        return SarosWindow(saros_number=saros_number, past=past, future=future)


# ── Lazy singletons ───────────────────────────────────────────────────────────

_solar_db: _EclipseDB | None = None
_lunar_db: _EclipseDB | None = None


def solar_db() -> _EclipseDB:
    global _solar_db
    if _solar_db is None:
        _solar_db = _EclipseDB("solar")
    return _solar_db


def lunar_db() -> _EclipseDB:
    global _lunar_db
    if _lunar_db is None:
        _lunar_db = _EclipseDB("lunar")
    return _lunar_db
