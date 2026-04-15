"""
Types for the saros-eclipse library.

Enums mirror the C enums in saros.h; dataclasses expand the packed binary
records into convenient Python objects.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Generic, TypeVar

__all__ = [
    "SolarEclipseType",
    "LunarEclipseType",
    "SolarEclipse",
    "LunarEclipse",
    "EclipseResult",
    "SarosWindow",
]


class SolarEclipseType(enum.Enum):
    """Solar eclipse type codes (matches ``solar_eclipse_type_t`` in saros.h).

    The string representation of each member is the canonical NASA code
    (e.g. ``"A+"``, ``"T-"``).
    """

    A      = 0   # Annular
    Aplus  = 1   # Annular (long)
    Aminus = 2   # Annular (sub-central)
    Am     = 3   # Annular (short)
    An     = 4   # Annular (non-central)
    As     = 5   # Annular (saros — first/last in series)
    H      = 6   # Hybrid (annular-total)
    H2     = 7   # Hybrid variant 2
    H3     = 8   # Hybrid variant 3
    Hm     = 9   # Hybrid (short)
    P      = 10  # Partial
    Pb     = 11  # Partial (beginning of series)
    Pe     = 12  # Partial (end of series)
    T      = 13  # Total
    Tplus  = 14  # Total (long, > ~5 min)
    Tminus = 15  # Total (sub-central)
    Tm     = 16  # Total (short, < ~1 min)
    Tn     = 17  # Total (non-central)
    Ts     = 18  # Total (saros — first/last in series)

    def __str__(self) -> str:
        _LABELS = {
            "Aplus": "A+", "Aminus": "A-",
            "Tplus": "T+", "Tminus": "T-",
        }
        return _LABELS.get(self.name, self.name)


class LunarEclipseType(enum.Enum):
    """Lunar eclipse type codes (matches ``lunar_eclipse_type_t`` in saros.h)."""

    N      = 0   # Penumbral
    Nb     = 1   # Penumbral (beginning of series)
    Ne     = 2   # Penumbral (end of series)
    Nx     = 3   # Penumbral (non-central)
    P      = 4   # Partial
    Pb     = 5   # Partial (beginning of series)
    Pe     = 6   # Partial (end of series)
    T      = 7   # Total
    Tplus  = 8   # Total (long, > ~100 min)
    Tminus = 9   # Total (sub-central)
    Tm     = 10  # Total (short, < ~20 min)
    Tn     = 11  # Total (non-central)
    Ts     = 12  # Total (saros — first/last in series)

    def __str__(self) -> str:
        _LABELS = {"Tplus": "T+", "Tminus": "T-"}
        return _LABELS.get(self.name, self.name)


@dataclass(frozen=True)
class SolarEclipse:
    """A decoded solar eclipse record.

    The primary time field is ``unix_time`` (seconds since the Unix epoch,
    possibly negative for ancient eclipses).  The ``time`` property converts
    it to a ``datetime`` for eclipses within Python's representable range
    (year 1–9999); it returns ``None`` for eclipses outside that range.

    Attributes:
        unix_time: Greatest-eclipse moment as a Unix timestamp (int).
        global_index: Flat index in the binary database arrays.
        saros_number: Saros series number (1–180).
        saros_pos: 0-based position within the Saros series.
        type: Eclipse type.
        latitude: Geographic latitude of greatest eclipse (degrees, + = N).
        longitude: Geographic longitude of greatest eclipse (degrees, + = E).
        central_duration: Central-line duration in seconds, or ``None`` for
            non-central/partial eclipses where the value is not applicable.
        sun_altitude: Sun altitude above the horizon at greatest eclipse (degrees).
    """

    unix_time: int
    global_index: int
    saros_number: int
    saros_pos: int
    type: SolarEclipseType
    latitude: float
    longitude: float
    central_duration: int | None
    sun_altitude: int

    @property
    def time(self) -> "datetime | None":
        """Greatest-eclipse moment in UTC, or ``None`` for ancient eclipses.

        Returns ``None`` when the eclipse pre-dates year 1 CE or post-dates
        year 9999 CE (Python's ``datetime`` range).  Use ``unix_time`` to
        handle the full dataset.
        """
        return _unix_to_datetime(self.unix_time)

    def __repr__(self) -> str:
        dur = f"{self.central_duration}s" if self.central_duration is not None else "n/a"
        dt = self.time
        ts = dt.strftime("%Y-%m-%d %H:%M") if dt is not None else str(self.unix_time)
        return (
            f"SolarEclipse({ts} UTC, "
            f"type={self.type}, saros={self.saros_number}[{self.saros_pos}], "
            f"lat={self.latitude:.1f}, lon={self.longitude:.1f}, dur={dur})"
        )


@dataclass(frozen=True)
class LunarEclipse:
    """A decoded lunar eclipse record.

    The primary time field is ``unix_time`` (seconds since the Unix epoch,
    possibly negative for ancient eclipses).  The ``time`` property converts
    it to a ``datetime`` for eclipses within Python's representable range.

    Attributes:
        unix_time: Greatest-eclipse moment as a Unix timestamp (int).
        global_index: Flat index in the binary database arrays.
        saros_number: Saros series number (1–180).
        saros_pos: 0-based position within the Saros series.
        type: Eclipse type.
        penumbral_duration: Penumbral phase duration in seconds, or ``None``.
        partial_duration: Partial phase duration in seconds, or ``None``.
        total_duration: Total phase duration in seconds, or ``None``.
    """

    unix_time: int
    global_index: int
    saros_number: int
    saros_pos: int
    type: LunarEclipseType
    penumbral_duration: int | None
    partial_duration: int | None
    total_duration: int | None

    @property
    def time(self) -> "datetime | None":
        """Greatest-eclipse moment in UTC, or ``None`` for ancient eclipses."""
        return _unix_to_datetime(self.unix_time)

    def __repr__(self) -> str:
        dt = self.time
        ts = dt.strftime("%Y-%m-%d %H:%M") if dt is not None else str(self.unix_time)
        return (
            f"LunarEclipse({ts} UTC, "
            f"type={self.type}, saros={self.saros_number}[{self.saros_pos}])"
        )


T = TypeVar("T", SolarEclipse, LunarEclipse)


@dataclass(frozen=True)
class EclipseResult(Generic[T]):
    """Result of ``find_next_*`` / ``find_past_*`` / ``find_closest_*``.

    Attributes:
        eclipse: The matched eclipse, or ``None`` if the timestamp is outside
            the dataset range.
        saros_prev: The previous eclipse in the same Saros series, or ``None``
            if the matched eclipse is the first in its series.
        saros_next: The next eclipse in the same Saros series, or ``None`` if
            the matched eclipse is the last in its series.
    """

    eclipse: T | None
    saros_prev: T | None
    saros_next: T | None


@dataclass(frozen=True)
class SarosWindow(Generic[T]):
    """Result of ``find_solar_saros_window`` / ``find_lunar_saros_window``.

    Attributes:
        saros_number: The queried Saros series number.
        past: The most recent eclipse in the series *before* the query time,
            or ``None`` if the query is before the series starts.
        future: The next eclipse in the series *at or after* the query time,
            or ``None`` if the query is after the series ends.
    """

    saros_number: int
    past: T | None
    future: T | None


def _unix_to_datetime(ts: int) -> "datetime | None":
    """Convert a Unix timestamp to a UTC datetime, or None if out of range.

    Python's datetime supports years 1–9999.  The Saros dataset spans ~2872 BCE
    to ~3500 CE; eclipses before year 1 CE will return None.
    """
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None
