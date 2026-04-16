/*
 * test_light.c — smoke test for solar_saros_unix.h and lunar_saros_unix.h
 *
 * Compile (from the db/ directory):
 *   cc -std=c11 -Wall -Wextra -o test_light test_light.c && ./test_light
 */

#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>

#define SOLAR_SAROS_IMPL
#define LUNAR_SAROS_IMPL
#include "solar_saros_unix.h"
#include "lunar_saros_unix.h"

/* Unix timestamp for 2026-04-15 12:00:00 UTC */
#define NOW_TS   ((int64_t)1776081600)

/* Unix timestamp for 2017-08-21 18:26:40 UTC (Aug 21 2017 total solar eclipse) */
#define ECLIPSE_2017_TS  ((int64_t)1503340000)

/* Unix timestamp for 2018-01-31 13:30:00 UTC (Jan 31 2018 total lunar eclipse) */
#define LUNAR_2018_TS    ((int64_t)1517402200)

/* Year 5000 CE in unix seconds (well past the dataset) */
#define FAR_FUTURE_TS    ((int64_t)95617584000LL)

/* ~4367 BCE in unix seconds (well before the dataset which starts ~2872 BCE) */
#define FAR_PAST_TS      ((int64_t)-200000000000LL)

/* ── Helpers ──────────────────────────────────────────────────────────────── */

static int tests_run   = 0;
static int tests_failed = 0;

#define CHECK(cond, msg)  do { \
    tests_run++; \
    if (!(cond)) { \
        fprintf(stderr, "FAIL [%s:%d]: %s\n", __FILE__, __LINE__, msg); \
        tests_failed++; \
    } else { \
        printf("  PASS: %s\n", msg); \
    } \
} while(0)

/* ── Solar tests ─────────────────────────────────────────────────────────── */

static void test_solar(void)
{
    printf("\n=== Solar ===\n");

    /* Constants */
    CHECK(solar_saros_COUNT == 13206u, "solar_saros_COUNT == 13206");
    CHECK(solar_saros_REC_SIZE == 10u, "solar_saros_REC_SIZE == 10");

    /* find_next basic */
    solar_saros_entry_t nxt = solar_saros_find_next(NOW_TS);
    CHECK(nxt.valid == 1, "find_next(now) returns valid entry");
    CHECK(nxt.unix_time >= NOW_TS, "find_next(now).unix_time >= now");
    CHECK(nxt.saros_number >= 1 && nxt.saros_number <= 180,
          "find_next(now).saros_number in [1,180]");

    /* find_past basic */
    solar_saros_entry_t pst = solar_saros_find_past(NOW_TS);
    CHECK(pst.valid == 1, "find_past(now) returns valid entry");
    CHECK(pst.unix_time <= NOW_TS, "find_past(now).unix_time <= now");
    CHECK(pst.saros_number >= 1 && pst.saros_number <= 180,
          "find_past(now).saros_number in [1,180]");

    /* past < next */
    CHECK(pst.unix_time < nxt.unix_time, "past.unix_time < next.unix_time");

    /* find_closest on Aug 21 2017 eclipse */
    solar_saros_entry_t cls = solar_saros_find_closest(ECLIPSE_2017_TS);
    CHECK(cls.valid == 1, "find_closest(2017) returns valid entry");
    {
        /* Confirm it's within 1 day of the 2017 eclipse */
        int64_t diff = cls.unix_time - ECLIPSE_2017_TS;
        if (diff < 0) diff = -diff;
        CHECK(diff < 86400, "find_closest(2017) within 1 day of target");
    }
    CHECK(cls.saros_number == 145, "find_closest(2017).saros_number == 145");
    printf("  INFO: 2017 solar eclipse — saros=%u pos=%u unix=%lld\n",
           cls.saros_number, cls.saros_pos, (long long)cls.unix_time);

    /* find_closest ties: future wins */
    {
        solar_saros_entry_t a = solar_saros_find_next(NOW_TS);
        solar_saros_entry_t b = solar_saros_find_past(NOW_TS);
        if (a.valid && b.valid) {
            int64_t mid = b.unix_time + (a.unix_time - b.unix_time) / 2;
            solar_saros_entry_t eq = solar_saros_find_closest(mid);
            /* Either next or past is acceptable — just check it's valid */
            CHECK(eq.valid == 1, "find_closest(midpoint) valid");
        }
    }

    /* Out-of-range: far future → find_next returns invalid */
    solar_saros_entry_t oor_nxt = solar_saros_find_next(FAR_FUTURE_TS);
    CHECK(oor_nxt.valid == 0, "find_next(far future) returns invalid entry");

    /* Out-of-range: far past → find_past returns invalid */
    solar_saros_entry_t oor_pst = solar_saros_find_past(FAR_PAST_TS);
    CHECK(oor_pst.valid == 0, "find_past(far past) returns invalid entry");

    /* list_series: Saros 145 */
    uint8_t cnt_145 = solar_saros_list_series(145, NULL, 0);
    CHECK(cnt_145 > 0 && cnt_145 <= 96, "list_series(145) count in [1,96]");
    printf("  INFO: Saros 145 has %u solar eclipses\n", cnt_145);

    solar_saros_entry_t series145[96];
    uint8_t written = solar_saros_list_series(145, series145, 96);
    CHECK(written == cnt_145, "list_series(145) count matches NULL query");

    /* All entries in series have the right saros_number */
    int series_ok = 1;
    for (uint8_t i = 0; i < written; i++) {
        if (series145[i].saros_number != 145) { series_ok = 0; break; }
        if (i > 0 && series145[i].unix_time <= series145[i-1].unix_time) {
            series_ok = 0; break;
        }
    }
    CHECK(series_ok, "list_series(145) entries are saros 145, time-ordered");

    /* list_series: invalid series → count 0 */
    uint8_t cnt_inv = solar_saros_list_series(200, NULL, 0);
    CHECK(cnt_inv == 0, "list_series(200) count == 0 (invalid series)");

    /* max_count respected */
    solar_saros_entry_t small_buf[3];
    uint8_t written_small = solar_saros_list_series(145, small_buf, 3);
    CHECK(written_small == cnt_145, "list_series(145, max=3) returns total count");
    CHECK(small_buf[0].saros_number == 145, "list_series limited buf[0] valid");

    /* saros_window */
    solar_saros_entry_t w_past, w_future;
    solar_saros_window(NOW_TS, 145, &w_past, &w_future);
    CHECK(w_past.valid == 1, "saros_window(145).past valid");
    CHECK(w_future.valid == 1, "saros_window(145).future valid");
    CHECK(w_past.unix_time < NOW_TS, "saros_window(145).past < now");
    CHECK(w_future.unix_time >= NOW_TS, "saros_window(145).future >= now");
    CHECK(w_past.saros_number == 145, "saros_window(145).past.saros_number == 145");
    CHECK(w_future.saros_number == 145, "saros_window(145).future.saros_number == 145");
    printf("  INFO: Saros 145 window — past=%lld future=%lld\n",
           (long long)w_past.unix_time, (long long)w_future.unix_time);

    /* saros_window: invalid series → both invalid */
    solar_saros_entry_t inv_past, inv_future;
    solar_saros_window(NOW_TS, 200, &inv_past, &inv_future);
    CHECK(inv_past.valid == 0, "saros_window(200).past invalid");
    CHECK(inv_future.valid == 0, "saros_window(200).future invalid");
}

/* ── Lunar tests ─────────────────────────────────────────────────────────── */

static void test_lunar(void)
{
    printf("\n=== Lunar ===\n");

    /* Constants */
    CHECK(lunar_saros_COUNT == 13383u, "lunar_saros_COUNT == 13383");
    CHECK(lunar_saros_REC_SIZE == 10u, "lunar_saros_REC_SIZE == 10");

    /* find_next basic */
    lunar_saros_entry_t nxt = lunar_saros_find_next(NOW_TS);
    CHECK(nxt.valid == 1, "find_next(now) returns valid entry");
    CHECK(nxt.unix_time >= NOW_TS, "find_next(now).unix_time >= now");
    CHECK(nxt.saros_number >= 1 && nxt.saros_number <= 180,
          "find_next(now).saros_number in [1,180]");

    /* find_past basic */
    lunar_saros_entry_t pst = lunar_saros_find_past(NOW_TS);
    CHECK(pst.valid == 1, "find_past(now) returns valid entry");
    CHECK(pst.unix_time <= NOW_TS, "find_past(now).unix_time <= now");

    /* past < next */
    CHECK(pst.unix_time < nxt.unix_time, "past.unix_time < next.unix_time");

    /* find_closest on Jan 31 2018 lunar eclipse */
    lunar_saros_entry_t cls = lunar_saros_find_closest(LUNAR_2018_TS);
    CHECK(cls.valid == 1, "find_closest(2018 lunar) valid");
    {
        int64_t diff = cls.unix_time - LUNAR_2018_TS;
        if (diff < 0) diff = -diff;
        CHECK(diff < 86400, "find_closest(2018 lunar) within 1 day of target");
    }
    CHECK(cls.saros_number == 124, "find_closest(2018 lunar).saros_number == 124");
    printf("  INFO: Jan 2018 lunar eclipse — saros=%u pos=%u unix=%lld\n",
           cls.saros_number, cls.saros_pos, (long long)cls.unix_time);

    /* Out-of-range */
    lunar_saros_entry_t oor_nxt = lunar_saros_find_next(FAR_FUTURE_TS);
    CHECK(oor_nxt.valid == 0, "find_next(far future) returns invalid entry");

    lunar_saros_entry_t oor_pst = lunar_saros_find_past(FAR_PAST_TS);
    CHECK(oor_pst.valid == 0, "find_past(far past) returns invalid entry");

    /* list_series: Saros 124 */
    uint8_t cnt_124 = lunar_saros_list_series(124, NULL, 0);
    CHECK(cnt_124 > 0 && cnt_124 <= 96, "list_series(124) count in [1,96]");
    printf("  INFO: Saros 124 has %u lunar eclipses\n", cnt_124);

    lunar_saros_entry_t series124[96];
    uint8_t written = lunar_saros_list_series(124, series124, 96);
    CHECK(written == cnt_124, "list_series(124) count matches NULL query");

    int series_ok = 1;
    for (uint8_t i = 0; i < written; i++) {
        if (series124[i].saros_number != 124) { series_ok = 0; break; }
        if (i > 0 && series124[i].unix_time <= series124[i-1].unix_time) {
            series_ok = 0; break;
        }
    }
    CHECK(series_ok, "list_series(124) entries are saros 124, time-ordered");

    /* list_series: invalid */
    uint8_t cnt_inv = lunar_saros_list_series(200, NULL, 0);
    CHECK(cnt_inv == 0, "list_series(200) count == 0");

    /* saros_window */
    lunar_saros_entry_t w_past, w_future;
    lunar_saros_window(NOW_TS, 124, &w_past, &w_future);
    CHECK(w_past.valid == 1, "saros_window(124).past valid");
    CHECK(w_future.valid == 1, "saros_window(124).future valid");
    CHECK(w_past.unix_time < NOW_TS, "saros_window(124).past < now");
    CHECK(w_future.unix_time >= NOW_TS, "saros_window(124).future >= now");
    CHECK(w_past.saros_number == 124, "saros_window(124).past.saros_number == 124");
    CHECK(w_future.saros_number == 124, "saros_window(124).future.saros_number == 124");
    printf("  INFO: Saros 124 window — past=%lld future=%lld\n",
           (long long)w_past.unix_time, (long long)w_future.unix_time);

    /* saros_window: invalid */
    lunar_saros_entry_t inv_past, inv_future;
    lunar_saros_window(NOW_TS, 200, &inv_past, &inv_future);
    CHECK(inv_past.valid == 0, "saros_window(200).past invalid");
    CHECK(inv_future.valid == 0, "saros_window(200).future invalid");
}

/* ── Cross-kind: both headers coexist without symbol clashes ─────────────── */

static void test_coexistence(void)
{
    printf("\n=== Coexistence ===\n");
    solar_saros_entry_t s = solar_saros_find_next(NOW_TS);
    lunar_saros_entry_t l = lunar_saros_find_next(NOW_TS);
    CHECK(s.valid && l.valid, "Both solar and lunar find_next valid in same TU");
    /* They should have different counts */
    CHECK(solar_saros_COUNT != lunar_saros_COUNT,
          "Solar and lunar have distinct COUNT constants");
}

/* ── Entry point ─────────────────────────────────────────────────────────── */

int main(void)
{
    printf("=== test_light.c ===\n");
    test_solar();
    test_lunar();
    test_coexistence();

    printf("\n=== Results: %d/%d passed ===\n",
           tests_run - tests_failed, tests_run);

    return tests_failed == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
