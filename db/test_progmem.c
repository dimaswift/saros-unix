/*
 * test_progmem.c — hosted test for eclipse_db_progmem.h
 *
 * No ECLIPSE_USE_PROGMEM defined → PROGMEM macros are no-ops, data lives in RAM.
 * This mirrors what the embedded target does, just without flash placement.
 */

#include <stdio.h>
#include <time.h>

/* Modern slice: include only what we need */
#include "eclipse_times_modern.h"
#include "eclipse_info_modern.h"
#include "saros_modern.h"
#include "eclipse_db_progmem.h"

/* Eclipse type names (matches enum order in eclipse_db.h) */
static const char *TYPE_NAMES[] = {
    "A", "A+", "Am", "An", "As",
    "H", "H2", "H3", "Hm",
    "P", "Pb", "Pe",
    "T", "T+", "Tm", "Tn", "Ts"
};

static void fmt_time(int64_t ts, char *buf, int len)
{
    if (ts >= -62135596800LL && ts <= 253402300799LL) {
        time_t t = (time_t)ts;
        struct tm *tm = gmtime(&t);
        if (tm) { strftime(buf, (size_t)len, "%Y-%m-%d %H:%M UTC", tm); return; }
    }
    snprintf(buf, (size_t)len, "%lld (unix)", (long long)ts);
}

static void print_eclipse(uint16_t idx)
{
    int64_t           ts   = pgm_get_eclipse_time(eclipse_times_modern, idx);
    pgm_eclipse_info_t info = pgm_get_eclipse_info(eclipse_info_modern, idx);
    char tbuf[40];
    fmt_time(ts, tbuf, sizeof(tbuf));

    float lat = info.latitude_deg10  / 10.0f;
    float lon = info.longitude_deg10 / 10.0f;

    printf("  [%5u]  %-26s  type=%-4s  saros=%3u  pos=%2u"
           "  lat=%+6.1f  lon=%+7.1f  alt=%2u  dur=",
           idx, tbuf,
           TYPE_NAMES[info.ecl_type],
           info.saros_number, info.saros_pos,
           lat, lon, info.sun_alt);

    if (info.central_duration == 0xFFFF)
        printf("  n/a\n");
    else
        printf("%2um%02us\n",
               info.central_duration / 60,
               info.central_duration % 60);
}

int main(void)
{
    printf("=== PROGMEM modern slice: saros %u-%u, %u eclipses ===\n\n",
           ECLIPSE_MODERN_SAROS_FIRST, ECLIPSE_MODERN_SAROS_LAST,
           ECLIPSE_MODERN_COUNT);

    /* Next eclipse after 1970-01-01 (within the modern slice) */
    puts("--- find_next_eclipse(0) ---");
    pgm_eclipse_ref_t r = pgm_find_next_eclipse(
            eclipse_times_modern, ECLIPSE_MODERN_COUNT, 0LL);
    if (r.found) print_eclipse(r.index); else puts("  (none)");

    /* Last eclipse before 1970-01-01 */
    puts("\n--- find_past_eclipse(0) ---");
    r = pgm_find_past_eclipse(eclipse_times_modern, ECLIPSE_MODERN_COUNT, 0LL);
    if (r.found) print_eclipse(r.index); else puts("  (none)");

    /* 2010-01-15 annular */
    puts("\n--- find_next_eclipse(2010-01-15) ---");
    r = pgm_find_next_eclipse(eclipse_times_modern, ECLIPSE_MODERN_COUNT, 1263513600LL);
    if (r.found) print_eclipse(r.index); else puts("  (none)");

    /* Next after 2025-01-01 */
    puts("\n--- find_next_eclipse(2025-01-01) ---");
    r = pgm_find_next_eclipse(eclipse_times_modern, ECLIPSE_MODERN_COUNT, 1735689600LL);
    if (r.found) print_eclipse(r.index); else puts("  (none)");

    /* Saros 141 via modern slice */
    puts("\n--- get_saros_series(141) via modern slice ---");
    pgm_saros_series_t s = pgm_get_saros_series(
            saros_modern, ECLIPSE_MODERN_SAROS_FIRST, 141);
    printf("  count = %u\n", s.count);
    for (int i = 0; i < s.count; i++)
        print_eclipse(s.indices[i]);

    return 0;
}
