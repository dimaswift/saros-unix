#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "eclipse_db.h"

/* Format a unix timestamp as UTC string. Handles the full gmtime range only;
   prints raw int64 for dates outside it. */
static void fmt_time(int64_t ts, char *buf, size_t len)
{
    if (ts >= -62135596800LL && ts <= 253402300799LL) {
        time_t t = (time_t)ts;
        struct tm *tm = gmtime(&t);
        if (tm) { strftime(buf, len, "%Y-%m-%d %H:%M UTC", tm); return; }
    }
    snprintf(buf, len, "%lld (unix)", (long long)ts);
}

static void print_eclipse(uint16_t idx)
{
    int64_t        ts   = get_eclipse_time(idx);
    eclipse_info_t info = get_eclipse_info(idx);
    char           tbuf[40];
    fmt_time(ts, tbuf, sizeof(tbuf));

    float lat = info.latitude_deg10  / 10.0f;
    float lon = info.longitude_deg10 / 10.0f;

    printf("  [%5u]  %-26s  type=%-4s  saros=%3u  pos=%2u"
           "  lat=%+6.1f  lon=%+7.1f  alt=%2u°  dur=",
           idx, tbuf,
           ECLIPSE_TYPE_NAMES[info.ecl_type],
           info.saros_number, info.saros_pos,
           lat, lon, info.sun_alt);

    if (info.central_duration == 0xFFFF)
        printf("  n/a\n");
    else
        printf("%2um%02us\n",
               info.central_duration / 60,
               info.central_duration % 60);
}

int main(int argc, char *argv[])
{
    const char *dir = (argc > 1) ? argv[1] : ".";

    char times_path[512], info_path[512], saros_path[512];
    snprintf(times_path, sizeof(times_path), "%s/eclipse_times.db", dir);
    snprintf(info_path,  sizeof(info_path),  "%s/eclipse_info.db",  dir);
    snprintf(saros_path, sizeof(saros_path), "%s/saros.db",         dir);

    if (eclipse_db_open(times_path, info_path, saros_path) != 0) {
        fprintf(stderr, "Failed to open database in: %s\n", dir);
        return 1;
    }

    /* ── find_next / find_past around Unix epoch ─────────────────────── */
    puts("=== Next eclipse after 1970-01-01 00:00:00 UTC ===");
    eclipse_ref_t r = find_next_eclipse(0);
    if (r.found) print_eclipse(r.index); else puts("  (none)");

    puts("\n=== Last eclipse before 1970-01-01 00:00:00 UTC ===");
    r = find_past_eclipse(0);
    if (r.found) print_eclipse(r.index); else puts("  (none)");

    /* ── famous 2010-01-15 annular (Saros 141, longest of the century) ─ */
    puts("\n=== Next eclipse on/after 2010-01-15 00:00:00 UTC ===");
    r = find_next_eclipse(1263513600LL);
    if (r.found) print_eclipse(r.index); else puts("  (none)");

    /* ── next eclipse from right now (approx 2025) ───────────────────── */
    puts("\n=== Next eclipse after 2025-01-01 00:00:00 UTC ===");
    r = find_next_eclipse(1735689600LL);
    if (r.found) print_eclipse(r.index); else puts("  (none)");

    /* ── full Saros 141 listing ──────────────────────────────────────── */
    puts("\n=== Saros 141 — all eclipses ===");
    saros_series_t s = get_saros_series(141);
    printf("  count = %u\n", s.count);
    for (int i = 0; i < s.count; i++)
        print_eclipse(s.indices[i]);

    eclipse_db_close();
    return 0;
}
