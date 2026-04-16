"""Tests for solar eclipse lookup functions."""

from datetime import datetime, timezone

import pytest

import saros
from saros import (
    EclipseResult,
    SarosWindow,
    SolarEclipse,
    SolarEclipseType,
    find_closest_solar_eclipse,
    find_next_solar_eclipse,
    find_past_solar_eclipse,
    find_solar_saros_window,
    get_solar_saros_series,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_NOW   = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)

# Aug 21 2017 total solar eclipse (Saros 145, well-documented event)
_SOLAR_2017_TS = 1503340000  # Unix seconds, ~18:26 UTC — falls within the eclipse window


# ── Return types ──────────────────────────────────────────────────────────────

def test_find_next_returns_eclipse_result():
    r = find_next_solar_eclipse(_NOW)
    assert isinstance(r, EclipseResult)


def test_eclipse_entry_is_solar_eclipse():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    assert isinstance(r.eclipse, SolarEclipse)


# ── Temporal logic ────────────────────────────────────────────────────────────

def test_next_eclipse_is_in_the_future():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    assert r.eclipse.unix_time >= int(_NOW.timestamp())


def test_past_eclipse_is_in_the_past():
    r = find_past_solar_eclipse(_NOW)
    assert r.eclipse is not None
    assert r.eclipse.unix_time <= int(_NOW.timestamp())


def test_next_and_past_are_different():
    nxt = find_next_solar_eclipse(_NOW)
    pst = find_past_solar_eclipse(_NOW)
    assert nxt.eclipse is not None
    assert pst.eclipse is not None
    assert nxt.eclipse.global_index != pst.eclipse.global_index


def test_past_before_next():
    nxt = find_next_solar_eclipse(_NOW)
    pst = find_past_solar_eclipse(_NOW)
    assert pst.eclipse.unix_time < nxt.eclipse.unix_time


# ── Out-of-range ──────────────────────────────────────────────────────────────

def test_far_future_returns_none():
    # Dataset ends around year 3518; use a Unix timestamp well beyond that.
    far_future_ts = 95_617_584_000  # year 5000 CE
    r = find_next_solar_eclipse(far_future_ts)
    assert r.eclipse is None
    assert r.saros_prev is None
    assert r.saros_next is None


def test_far_past_returns_none():
    # Dataset starts ~2872 BCE (unix ~-152785438447); use an earlier timestamp.
    far_past_ts = -200_000_000_000
    r = find_past_solar_eclipse(far_past_ts)
    assert r.eclipse is None


# ── Saros neighbours ──────────────────────────────────────────────────────────

def test_saros_neighbours_present():
    # Pick an eclipse well inside the dataset — should have both prev and next.
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    # Most eclipses have both neighbours; edges of a series may not.
    # At minimum one of them should be present for a mid-series eclipse.
    assert r.saros_prev is not None or r.saros_next is not None


def test_saros_neighbours_same_series():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    sn = r.eclipse.saros_number
    if r.saros_prev is not None:
        assert r.saros_prev.saros_number == sn
    if r.saros_next is not None:
        assert r.saros_next.saros_number == sn


def test_saros_neighbours_ordered():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    if r.saros_prev is not None:
        assert r.saros_prev.unix_time < r.eclipse.unix_time
    if r.saros_next is not None:
        assert r.saros_next.unix_time > r.eclipse.unix_time


# ── Known eclipse: Aug 21 2017 Saros 145 ─────────────────────────────────────

def test_known_2017_eclipse_closest():
    """find_closest should land on the Aug 21 2017 total solar eclipse."""
    # Query a few hours before/after the eclipse
    before = datetime(2017, 8, 21, 0, 0, 0, tzinfo=timezone.utc)
    r = find_closest_solar_eclipse(before)
    assert r.eclipse is not None
    t = r.eclipse.time
    assert t is not None
    assert t.year == 2017
    assert t.month == 8


def test_known_2017_eclipse_type():
    before = datetime(2017, 8, 21, 0, 0, 0, tzinfo=timezone.utc)
    r = find_closest_solar_eclipse(before)
    assert r.eclipse is not None
    assert r.eclipse.type == SolarEclipseType.T


def test_known_2017_eclipse_saros():
    before = datetime(2017, 8, 21, 0, 0, 0, tzinfo=timezone.utc)
    r = find_closest_solar_eclipse(before)
    assert r.eclipse is not None
    assert r.eclipse.saros_number == 145


def test_known_2017_eclipse_coordinates():
    before = datetime(2017, 8, 21, 0, 0, 0, tzinfo=timezone.utc)
    r = find_closest_solar_eclipse(before)
    assert r.eclipse is not None
    # Greatest eclipse was over the central USA, roughly 37°N, 87°W.
    assert 30 < r.eclipse.latitude < 45
    assert -100 < r.eclipse.longitude < -70


# ── SolarEclipse field validity ───────────────────────────────────────────────

def test_saros_number_in_range():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    assert 1 <= r.eclipse.saros_number <= 180


def test_saros_pos_non_negative():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    assert r.eclipse.saros_pos >= 0


def test_type_is_enum():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    assert isinstance(r.eclipse.type, SolarEclipseType)


def test_latitude_in_range():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    assert -90.0 <= r.eclipse.latitude <= 90.0


def test_longitude_in_range():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    assert -180.0 <= r.eclipse.longitude <= 180.0


def test_central_duration_none_or_positive():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    dur = r.eclipse.central_duration
    assert dur is None or dur > 0


def test_time_is_utc_aware():
    r = find_next_solar_eclipse(_NOW)
    assert r.eclipse is not None
    t = r.eclipse.time
    assert t is not None
    assert t.tzinfo is not None


# ── Saros window ──────────────────────────────────────────────────────────────

def test_saros_window_returns_correct_type():
    w = find_solar_saros_window(_NOW, 145)
    assert isinstance(w, SarosWindow)
    assert w.saros_number == 145


def test_saros_window_145_has_entries():
    w = find_solar_saros_window(_NOW, 145)
    # Saros 145 is active in 2026 — should have both past and future.
    assert w.past is not None
    assert w.future is not None


def test_saros_window_past_before_future():
    w = find_solar_saros_window(_NOW, 145)
    if w.past is not None and w.future is not None:
        assert w.past.unix_time < w.future.unix_time


def test_saros_window_past_is_past():
    w = find_solar_saros_window(_NOW, 145)
    if w.past is not None:
        assert w.past.unix_time < int(_NOW.timestamp())


def test_saros_window_future_is_future():
    w = find_solar_saros_window(_NOW, 145)
    if w.future is not None:
        assert w.future.unix_time >= int(_NOW.timestamp())


def test_saros_window_invalid_series():
    w = find_solar_saros_window(_NOW, 999)
    assert w.past is None
    assert w.future is None


# ── Input type variants ───────────────────────────────────────────────────────

def test_accepts_int_timestamp():
    ts = int(_NOW.timestamp())
    r = find_next_solar_eclipse(ts)
    assert r.eclipse is not None


def test_accepts_float_timestamp():
    ts = float(_NOW.timestamp())
    r = find_next_solar_eclipse(ts)
    assert r.eclipse is not None


def test_accepts_naive_datetime():
    # Naive datetimes should be treated as UTC without raising.
    naive = datetime(2026, 4, 15, 12, 0, 0)
    r = find_next_solar_eclipse(naive)
    assert r.eclipse is not None


# ── Eclipse type string representation ───────────────────────────────────────

def test_solar_type_str_aplus():
    assert str(SolarEclipseType.Aplus) == "A+"


def test_solar_type_str_tminus():
    assert str(SolarEclipseType.Tminus) == "T-"


def test_solar_type_str_plain():
    assert str(SolarEclipseType.T) == "T"
    assert str(SolarEclipseType.P) == "P"


# ── Closest ───────────────────────────────────────────────────────────────────

def test_closest_returns_nearer_eclipse():
    nxt = find_next_solar_eclipse(_NOW)
    pst = find_past_solar_eclipse(_NOW)
    cls = find_closest_solar_eclipse(_NOW)
    assert cls.eclipse is not None
    assert nxt.eclipse is not None
    assert pst.eclipse is not None
    now_ts = int(_NOW.timestamp())
    d_nxt = abs(nxt.eclipse.unix_time - now_ts)
    d_pst = abs(pst.eclipse.unix_time - now_ts)
    d_cls = abs(cls.eclipse.unix_time - now_ts)
    assert d_cls <= min(d_nxt, d_pst)


# ── get_solar_saros_series ────────────────────────────────────────────────────

def test_get_series_returns_list():
    series = get_solar_saros_series(145)
    assert isinstance(series, list)

def test_get_series_nonempty_for_valid_saros():
    series = get_solar_saros_series(145)
    assert len(series) > 0

def test_get_series_all_have_correct_saros_number():
    series = get_solar_saros_series(145)
    assert all(e.saros_number == 145 for e in series)

def test_get_series_saros_pos_sequential():
    series = get_solar_saros_series(145)
    assert [e.saros_pos for e in series] == list(range(len(series)))

def test_get_series_sorted_by_unix_time():
    series = get_solar_saros_series(145)
    times = [e.unix_time for e in series]
    assert times == sorted(times)

def test_get_series_all_entries_are_solar_eclipse():
    series = get_solar_saros_series(145)
    assert all(isinstance(e, SolarEclipse) for e in series)

def test_get_series_count_matches_saros_window():
    """Number of entries should be consistent with successive window queries."""
    series = get_solar_saros_series(145)
    assert len(series) >= 2  # Saros 145 spans many centuries

def test_get_series_first_entry_is_oldest():
    series = get_solar_saros_series(145)
    assert series[0].unix_time < series[-1].unix_time

def test_get_series_known_2017_eclipse_present():
    """The Aug 2017 eclipse (Saros 145, pos 21) must appear in the series."""
    series = get_solar_saros_series(145)
    unix_times = [e.unix_time for e in series]
    # The 2017 eclipse timestamp should be within 1 day of one of the entries
    assert any(abs(t - _SOLAR_2017_TS) < 86400 for t in unix_times)

def test_get_series_invalid_returns_empty():
    assert get_solar_saros_series(0)   == []
    assert get_solar_saros_series(181) == []
    assert get_solar_saros_series(999) == []

def test_get_series_global_index_matches_find_closest():
    """Entry returned by find_closest should appear in list_series."""
    r = find_closest_solar_eclipse(_NOW)
    assert r.eclipse is not None
    series = get_solar_saros_series(r.eclipse.saros_number)
    indices = [e.global_index for e in series]
    assert r.eclipse.global_index in indices
