/*
 * test_saros_lib.c — Exercise saros_lib.h solar and lunar APIs.
 *
 * Build (from db/):
 *   make test_saros_lib
 * or manually:
 *   cc -O2 -Wall -std=c11 -o test_saros_lib \
 *       test_saros_lib.c solar_impl.c lunar_impl.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#include "saros.h"

/* ── Formatting helpers ─────────────────────────────────────────────────── */

static const char *const SOLAR_TYPE_NAMES[] = {
    "A", "A+", "A-", "Am", "An", "As",
    "H", "H2", "H3", "Hm",
    "P", "Pb", "Pe",
    "T", "T+", "T-", "Tm", "Tn", "Ts"
};

static const char *const LUNAR_TYPE_NAMES[] = {
    "N", "Nb", "Ne", "Nx",
    "P", "Pb", "Pe",
    "T", "T+", "T-", "Tm", "Tn", "Ts"
};

/* Very rough Unix-timestamp → calendar date string (Gregorian, UTC, CE only). */
static void ts_to_date(int64_t ts, char *buf, size_t len)
{
    if (ts < 0) {
        /* BCE dates: just show raw timestamp */
        snprintf(buf, len, "<ts=%" PRId64 ">", ts);
        return;
    }
    /* days since epoch */
    int64_t days = ts / 86400;
    int64_t rem  = ts % 86400;
    int hh = (int)(rem / 3600);
    int mm = (int)((rem % 3600) / 60);
    int ss = (int)(rem % 60);

    /* Gregorian calendar from Julian Day Number */
    int64_t jd = days + 2440588;  /* JD of Unix epoch */
    int64_t a  = jd + 32044;
    int64_t b  = (4 * a + 3) / 146097;
    int64_t c  = a - (b * 146097) / 4;
    int64_t d  = (4 * c + 3) / 1461;
    int64_t e  = c - (1461 * d) / 4;
    int64_t m  = (5 * e + 2) / 153;
    int day    = (int)(e - (153 * m + 2) / 5 + 1);
    int month  = (int)(m + 3 - 12 * (m / 10));
    int year   = (int)(b * 100 + d - 4800 + m / 10);

    static const char *mons[] = {"","Jan","Feb","Mar","Apr","May","Jun",
                                 "Jul","Aug","Sep","Oct","Nov","Dec"};
    snprintf(buf, len, "%04d %s %02d  %02d:%02d:%02d UTC",
             year, mons[month], day, hh, mm, ss);
}

static void print_solar_entry(const char *label, const eclipse_entry_t *e)
{
    if (!e->valid) {
        printf("  %-16s  (none)\n", label);
        return;
    }
    char date[48];
    ts_to_date(e->unix_time, date, sizeof(date));
    const solar_eclipse_info_t *s = &e->info.solar;
    const char *type = (s->ecl_type < SOLAR_ECL_TYPE_COUNT)
                       ? SOLAR_TYPE_NAMES[s->ecl_type] : "?";
    printf("  %-16s  %s  type=%-3s  saros=%3u pos=%2u"
           "  lat=%+6.1f  lon=%+7.1f  sun_alt=%2u°",
           label, date,
           type, s->saros_number, s->saros_pos,
           s->latitude_deg10  / 10.0,
           s->longitude_deg10 / 10.0,
           s->sun_alt);
    if (s->central_duration != 0xFFFF)
        printf("  dur=%um%02us", s->central_duration / 60, s->central_duration % 60);
    printf("\n");
}

static void print_lunar_entry(const char *label, const eclipse_entry_t *e)
{
    if (!e->valid) {
        printf("  %-16s  (none)\n", label);
        return;
    }
    char date[48];
    ts_to_date(e->unix_time, date, sizeof(date));
    const lunar_eclipse_info_t *l = &e->info.lunar;
    const char *type = (l->ecl_type < LUNAR_ECL_TYPE_COUNT)
                       ? LUNAR_TYPE_NAMES[l->ecl_type] : "?";
    printf("  %-16s  %s  type=%-3s  saros=%3u pos=%2u",
           label, date,
           type, l->saros_number, l->saros_pos);
    if (l->pen_duration   != 0xFFFF)
        printf("  pen=%um%02us",   l->pen_duration   / 60, l->pen_duration   % 60);
    if (l->par_duration   != 0xFFFF)
        printf("  par=%um%02us",   l->par_duration   / 60, l->par_duration   % 60);
    if (l->total_duration != 0xFFFF)
        printf("  tot=%um%02us",   l->total_duration / 60, l->total_duration % 60);
    printf("\n");
}

static void print_solar_result(const char *title, const eclipse_result_t *r)
{
    printf("%s\n", title);
    print_solar_entry("eclipse",    &r->eclipse);
    print_solar_entry("saros_prev", &r->saros_prev);
    print_solar_entry("saros_next", &r->saros_next);
    printf("\n");
}

static void print_lunar_result(const char *title, const eclipse_result_t *r)
{
    printf("%s\n", title);
    print_lunar_entry("eclipse",    &r->eclipse);
    print_lunar_entry("saros_prev", &r->saros_prev);
    print_lunar_entry("saros_next", &r->saros_next);
    printf("\n");
}

static void print_solar_window(const char *title, const saros_window_t *w)
{
    printf("%s  (saros %u)\n", title, w->saros_number);
    print_solar_entry("past",   &w->past);
    print_solar_entry("future", &w->future);
    printf("\n");
}

static void print_lunar_window(const char *title, const saros_window_t *w)
{
    printf("%s  (saros %u)\n", title, w->saros_number);
    print_lunar_entry("past",   &w->past);
    print_lunar_entry("future", &w->future);
    printf("\n");
}

/* ── Tests ──────────────────────────────────────────────────────────────── */

int main(void)
{
    /* Some reference timestamps */
    /* 2024-04-08 18:17:21 UTC — Great North American total solar eclipse */
    const int64_t ts_2024_solar = 1712600241LL;

    /* 2025-03-14 06:58:44 UTC — Total lunar eclipse */
    const int64_t ts_2025_lunar = 1741935524LL;

    /* 2010-01-15 07:06:00 UTC — longest annular solar eclipse of 21st century */
    const int64_t ts_2010_solar = 1263539160LL;

    /* 1970-01-01 00:00:00 UTC — Unix epoch */
    const int64_t ts_epoch = 0LL;

    printf("═══════════════════════════════════════════════════════════════\n");
    printf("  saros_lib.h — test_saros_lib\n");
    printf("═══════════════════════════════════════════════════════════════\n\n");

    /* ── Solar: find_next ───────────────────────────────────────────────── */
    {
        eclipse_result_t r = find_next_solar_eclipse(ts_2024_solar);
        print_solar_result("find_next_solar_eclipse(2024-04-08):", &r);
    }

    /* ── Solar: find_past ───────────────────────────────────────────────── */
    {
        eclipse_result_t r = find_past_solar_eclipse(ts_2024_solar);
        print_solar_result("find_past_solar_eclipse(2024-04-08):", &r);
    }

    /* ── Solar: 2010 annular ────────────────────────────────────────────── */
    {
        eclipse_result_t r = find_next_solar_eclipse(ts_2010_solar);
        print_solar_result("find_next_solar_eclipse(2010-01-15):", &r);
    }

    /* ── Solar: epoch ───────────────────────────────────────────────────── */
    {
        eclipse_result_t r = find_next_solar_eclipse(ts_epoch);
        print_solar_result("find_next_solar_eclipse(1970-01-01):", &r);
        eclipse_result_t p = find_past_solar_eclipse(ts_epoch);
        print_solar_result("find_past_solar_eclipse(1970-01-01):", &p);
    }

    /* ── Solar: saros window ────────────────────────────────────────────── */
    {
        /* Saros 145 — the series that produced the 1999 total solar eclipse */
        saros_window_t w = find_solar_saros_window(ts_2024_solar, 145);
        print_solar_window("find_solar_saros_window(2024-04-08, saros=145):", &w);

        /* Saros 136 — series of the 2009 total solar eclipse */
        saros_window_t w2 = find_solar_saros_window(ts_2010_solar, 136);
        print_solar_window("find_solar_saros_window(2010-01-15, saros=136):", &w2);
    }

    printf("═══════════════════════════════════════════════════════════════\n\n");

    /* ── Lunar: find_next ───────────────────────────────────────────────── */
    {
        eclipse_result_t r = find_next_lunar_eclipse(ts_2025_lunar);
        print_lunar_result("find_next_lunar_eclipse(2025-03-14):", &r);
    }

    /* ── Lunar: find_past ───────────────────────────────────────────────── */
    {
        eclipse_result_t r = find_past_lunar_eclipse(ts_2025_lunar);
        print_lunar_result("find_past_lunar_eclipse(2025-03-14):", &r);
    }

    /* ── Lunar: epoch ───────────────────────────────────────────────────── */
    {
        eclipse_result_t r = find_next_lunar_eclipse(ts_epoch);
        print_lunar_result("find_next_lunar_eclipse(1970-01-01):", &r);
    }

    /* ── Lunar: saros window ────────────────────────────────────────────── */
    {
        /* Saros 132 — series of the 2025-03-14 total lunar eclipse */
        saros_window_t w = find_lunar_saros_window(ts_2025_lunar, 132);
        print_lunar_window("find_lunar_saros_window(2025-03-14, saros=132):", &w);

        saros_window_t w2 = find_lunar_saros_window(ts_epoch, 110);
        print_lunar_window("find_lunar_saros_window(1970-01-01, saros=110):", &w2);
    }

    return 0;
}
