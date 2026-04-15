"""
saros-eclipse — Solar and lunar eclipse lookup from NASA's Saros catalog.

Covers all 180 solar and 180 lunar Saros series (~25,000 eclipses total,
spanning several millennia).  Data is read from pre-built binary files
bundled with this package; no network access or compilation is needed.

Quick start::

    from datetime import datetime, timezone
    import saros

    now = datetime.now(timezone.utc)

    result = saros.find_next_solar_eclipse(now)
    if result.eclipse:
        e = result.eclipse
        print(f"Next solar eclipse: {e.time:%Y-%m-%d}  type={e.type}  "
              f"Saros {e.saros_number}[{e.saros_pos}]")

    window = saros.find_solar_saros_window(now, 145)
    if window.past:
        print(f"Saros 145 was last: {window.past.time:%Y-%m-%d}")
    if window.future:
        print(f"Saros 145 next:     {window.future.time:%Y-%m-%d}")

All public functions accept a timestamp as:

* A :class:`datetime.datetime` (aware preferred; naive treated as UTC)
* An ``int`` or ``float`` Unix timestamp (seconds since 1970-01-01)

Data slice
----------
This package uses the **full** (non-truncated) dataset: Saros 1–180,
13 206 solar and 12 223 lunar eclipses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Union

from ._db import _to_unix, lunar_db, solar_db
from ._types import (
    EclipseResult,
    LunarEclipse,
    LunarEclipseType,
    SarosWindow,
    SolarEclipse,
    SolarEclipseType,
)

__all__ = [
    # types
    "SolarEclipseType",
    "LunarEclipseType",
    "SolarEclipse",
    "LunarEclipse",
    "EclipseResult",
    "SarosWindow",
    # solar functions
    "find_next_solar_eclipse",
    "find_past_solar_eclipse",
    "find_closest_solar_eclipse",
    "find_solar_saros_window",
    # lunar functions
    "find_next_lunar_eclipse",
    "find_past_lunar_eclipse",
    "find_closest_lunar_eclipse",
    "find_lunar_saros_window",
]

__version__ = "0.1.0"

Timestamp = Union[int, float, datetime]

# ── Solar ─────────────────────────────────────────────────────────────────────


def find_next_solar_eclipse(ts: Timestamp) -> EclipseResult[SolarEclipse]:
    """Return the nearest solar eclipse at or after *ts*.

    The result also includes ``saros_prev`` and ``saros_next``: the preceding
    and following eclipses within the same Saros series.

    ``result.eclipse`` is ``None`` when *ts* is past the last eclipse in the
    dataset.
    """
    return solar_db().find_next(_to_unix(ts))


def find_past_solar_eclipse(ts: Timestamp) -> EclipseResult[SolarEclipse]:
    """Return the nearest solar eclipse at or before *ts*.

    ``result.eclipse`` is ``None`` when *ts* is before the first eclipse in
    the dataset.
    """
    return solar_db().find_past(_to_unix(ts))


def find_closest_solar_eclipse(ts: Timestamp) -> EclipseResult[SolarEclipse]:
    """Return the solar eclipse closest in time to *ts*.

    When the next and past eclipses are equidistant the future eclipse is
    returned (matches the behaviour of the inline helper in ``saros.h``).
    """
    unix = _to_unix(ts)
    nxt = solar_db().find_next(unix)
    pst = solar_db().find_past(unix)
    if nxt.eclipse is None:
        return pst
    if pst.eclipse is None:
        return nxt
    d_nxt = nxt.eclipse.unix_time - unix
    d_pst = unix - pst.eclipse.unix_time
    return pst if d_pst < d_nxt else nxt


def find_solar_saros_window(
    ts: Timestamp, saros_number: int
) -> SarosWindow[SolarEclipse]:
    """Return the past and future solar eclipses in a specific Saros series.

    Args:
        ts: Reference timestamp.
        saros_number: Saros series number (1–180).

    Returns:
        A :class:`SarosWindow` whose ``past`` field is the most recent
        eclipse in the series *before* *ts* (or ``None``) and whose
        ``future`` field is the next eclipse at or after *ts* (or ``None``).
    """
    return solar_db().saros_window(_to_unix(ts), saros_number)


# ── Lunar ─────────────────────────────────────────────────────────────────────


def find_next_lunar_eclipse(ts: Timestamp) -> EclipseResult[LunarEclipse]:
    """Return the nearest lunar eclipse at or after *ts*."""
    return lunar_db().find_next(_to_unix(ts))


def find_past_lunar_eclipse(ts: Timestamp) -> EclipseResult[LunarEclipse]:
    """Return the nearest lunar eclipse at or before *ts*."""
    return lunar_db().find_past(_to_unix(ts))


def find_closest_lunar_eclipse(ts: Timestamp) -> EclipseResult[LunarEclipse]:
    """Return the lunar eclipse closest in time to *ts*.

    When equidistant, the future eclipse is returned.
    """
    unix = _to_unix(ts)
    nxt = lunar_db().find_next(unix)
    pst = lunar_db().find_past(unix)
    if nxt.eclipse is None:
        return pst
    if pst.eclipse is None:
        return nxt
    d_nxt = nxt.eclipse.unix_time - unix
    d_pst = unix - pst.eclipse.unix_time
    return pst if d_pst < d_nxt else nxt


def find_lunar_saros_window(
    ts: Timestamp, saros_number: int
) -> SarosWindow[LunarEclipse]:
    """Return the past and future lunar eclipses in a specific Saros series.

    Args:
        ts: Reference timestamp.
        saros_number: Saros series number (1–180).
    """
    return lunar_db().saros_window(_to_unix(ts), saros_number)
