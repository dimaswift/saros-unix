"""Tests for lunar eclipse lookup functions."""

from datetime import datetime, timezone

import pytest

import saros
from saros import (
    EclipseResult,
    LunarEclipse,
    LunarEclipseType,
    SarosWindow,
    find_closest_lunar_eclipse,
    find_lunar_saros_window,
    find_next_lunar_eclipse,
    find_past_lunar_eclipse,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_NOW = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)

# Jan 31 2018 total lunar eclipse (Saros 124, well-documented "super blood moon")
_LUNAR_2018 = datetime(2018, 1, 31, 13, 30, 0, tzinfo=timezone.utc)


# ── Return types ──────────────────────────────────────────────────────────────

def test_find_next_returns_eclipse_result():
    r = find_next_lunar_eclipse(_NOW)
    assert isinstance(r, EclipseResult)


def test_eclipse_entry_is_lunar_eclipse():
    r = find_next_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    assert isinstance(r.eclipse, LunarEclipse)


# ── Temporal logic ────────────────────────────────────────────────────────────

def test_next_eclipse_is_in_the_future():
    r = find_next_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    assert r.eclipse.unix_time >= int(_NOW.timestamp())


def test_past_eclipse_is_in_the_past():
    r = find_past_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    assert r.eclipse.unix_time <= int(_NOW.timestamp())


def test_next_and_past_are_different():
    nxt = find_next_lunar_eclipse(_NOW)
    pst = find_past_lunar_eclipse(_NOW)
    assert nxt.eclipse is not None
    assert pst.eclipse is not None
    assert nxt.eclipse.global_index != pst.eclipse.global_index


def test_past_before_next():
    nxt = find_next_lunar_eclipse(_NOW)
    pst = find_past_lunar_eclipse(_NOW)
    assert pst.eclipse.unix_time < nxt.eclipse.unix_time


# ── Out-of-range ──────────────────────────────────────────────────────────────

def test_far_future_returns_none():
    # Dataset ends around year 3518; use a Unix timestamp well beyond that.
    far_future_ts = 95_617_584_000  # year 5000 CE
    r = find_next_lunar_eclipse(far_future_ts)
    assert r.eclipse is None


def test_far_past_returns_none():
    # Dataset starts ~2872 BCE (unix ~-152785438447); use an earlier timestamp.
    far_past_ts = -200_000_000_000
    r = find_past_lunar_eclipse(far_past_ts)
    assert r.eclipse is None


# ── Saros neighbours ──────────────────────────────────────────────────────────

def test_saros_neighbours_same_series():
    r = find_next_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    sn = r.eclipse.saros_number
    if r.saros_prev is not None:
        assert r.saros_prev.saros_number == sn
    if r.saros_next is not None:
        assert r.saros_next.saros_number == sn


def test_saros_neighbours_ordered():
    r = find_next_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    if r.saros_prev is not None:
        assert r.saros_prev.unix_time < r.eclipse.unix_time
    if r.saros_next is not None:
        assert r.saros_next.unix_time > r.eclipse.unix_time


# ── Known eclipse: Jan 31 2018 total lunar (Saros 124) ───────────────────────

def test_known_2018_eclipse_closest():
    r = find_closest_lunar_eclipse(_LUNAR_2018)
    assert r.eclipse is not None
    t = r.eclipse.time
    assert t is not None
    assert t.year == 2018
    assert t.month == 1


def test_known_2018_eclipse_type():
    r = find_closest_lunar_eclipse(_LUNAR_2018)
    assert r.eclipse is not None
    assert r.eclipse.type in (LunarEclipseType.T, LunarEclipseType.Tplus,
                               LunarEclipseType.Tminus, LunarEclipseType.Tm)


def test_known_2018_eclipse_saros():
    r = find_closest_lunar_eclipse(_LUNAR_2018)
    assert r.eclipse is not None
    assert r.eclipse.saros_number == 124


# ── LunarEclipse field validity ───────────────────────────────────────────────

def test_saros_number_in_range():
    r = find_next_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    assert 1 <= r.eclipse.saros_number <= 180


def test_saros_pos_non_negative():
    r = find_next_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    assert r.eclipse.saros_pos >= 0


def test_type_is_enum():
    r = find_next_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    assert isinstance(r.eclipse.type, LunarEclipseType)


def test_durations_are_none_or_positive():
    r = find_next_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    e = r.eclipse
    for dur in (e.penumbral_duration, e.partial_duration, e.total_duration):
        assert dur is None or dur > 0


def test_total_eclipse_has_total_duration():
    """A total lunar eclipse should have a non-None total_duration."""
    # Search forward up to 200 eclipses to find a total one.
    ts = int(_NOW.timestamp())
    found = False
    for _ in range(200):
        r = find_next_lunar_eclipse(ts)
        if r.eclipse is None:
            break
        if r.eclipse.type == LunarEclipseType.T:
            assert r.eclipse.total_duration is not None
            assert r.eclipse.total_duration > 0
            found = True
            break
        ts = r.eclipse.unix_time + 1
    assert found, "No total lunar eclipse found in next 200 eclipses"


def test_penumbral_eclipse_has_no_total_duration():
    """A purely penumbral eclipse should have total_duration == None."""
    ts = int(_NOW.timestamp())
    found = False
    for _ in range(200):
        r = find_next_lunar_eclipse(ts)
        if r.eclipse is None:
            break
        if r.eclipse.type == LunarEclipseType.N:
            assert r.eclipse.total_duration is None
            found = True
            break
        ts = r.eclipse.unix_time + 1
    # Penumbral eclipses may or may not appear in the next 200; skip if not found.
    if not found:
        pytest.skip("No penumbral lunar eclipse found in next 200 eclipses")


def test_time_is_utc_aware():
    r = find_next_lunar_eclipse(_NOW)
    assert r.eclipse is not None
    t = r.eclipse.time
    assert t is not None
    assert t.tzinfo is not None


# ── Saros window ──────────────────────────────────────────────────────────────

def test_saros_window_returns_correct_type():
    w = find_lunar_saros_window(_NOW, 124)
    assert isinstance(w, SarosWindow)
    assert w.saros_number == 124


def test_saros_window_124_has_entries():
    w = find_lunar_saros_window(_NOW, 124)
    # Saros 124 is an active series — should have both past and future.
    assert w.past is not None or w.future is not None


def test_saros_window_past_before_future():
    w = find_lunar_saros_window(_NOW, 124)
    if w.past is not None and w.future is not None:
        assert w.past.unix_time < w.future.unix_time


def test_saros_window_past_is_past():
    w = find_lunar_saros_window(_NOW, 124)
    if w.past is not None:
        assert w.past.unix_time < int(_NOW.timestamp())


def test_saros_window_future_is_future():
    w = find_lunar_saros_window(_NOW, 124)
    if w.future is not None:
        assert w.future.unix_time >= int(_NOW.timestamp())


def test_saros_window_invalid_series():
    w = find_lunar_saros_window(_NOW, 999)
    assert w.past is None
    assert w.future is None


# ── Input type variants ───────────────────────────────────────────────────────

def test_accepts_int_timestamp():
    ts = int(_NOW.timestamp())
    r = find_next_lunar_eclipse(ts)
    assert r.eclipse is not None


def test_accepts_float_timestamp():
    ts = float(_NOW.timestamp())
    r = find_next_lunar_eclipse(ts)
    assert r.eclipse is not None


def test_accepts_naive_datetime():
    naive = datetime(2026, 4, 15, 12, 0, 0)
    r = find_next_lunar_eclipse(naive)
    assert r.eclipse is not None


# ── Eclipse type string representation ───────────────────────────────────────

def test_lunar_type_str_tplus():
    assert str(LunarEclipseType.Tplus) == "T+"


def test_lunar_type_str_tminus():
    assert str(LunarEclipseType.Tminus) == "T-"


def test_lunar_type_str_plain():
    assert str(LunarEclipseType.T) == "T"
    assert str(LunarEclipseType.N) == "N"


# ── Closest ───────────────────────────────────────────────────────────────────

def test_closest_returns_nearer_eclipse():
    nxt = find_next_lunar_eclipse(_NOW)
    pst = find_past_lunar_eclipse(_NOW)
    cls = find_closest_lunar_eclipse(_NOW)
    assert cls.eclipse is not None
    assert nxt.eclipse is not None
    assert pst.eclipse is not None
    now_ts = int(_NOW.timestamp())
    d_nxt = abs(nxt.eclipse.unix_time - now_ts)
    d_pst = abs(pst.eclipse.unix_time - now_ts)
    d_cls = abs(cls.eclipse.unix_time - now_ts)
    assert d_cls <= min(d_nxt, d_pst)
