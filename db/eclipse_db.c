#include "eclipse_db.h"

#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* ── Type name table ────────────────────────────────────────────────────── */

const char *ECLIPSE_TYPE_NAMES[ECL_TYPE_COUNT] = {
    "A", "A+", "Am", "An", "As",
    "H", "H2", "H3", "Hm",
    "P", "Pb", "Pe",
    "T", "T+", "Tm", "Tn", "Ts"
};

/* ── Internal state ─────────────────────────────────────────────────────── */

/* eclipse_times.db is fully loaded into RAM (105 KB) for binary search */
static int64_t  *g_times      = NULL;
static uint32_t  g_times_count = 0;

static int g_info_fd  = -1;
static int g_saros_fd = -1;

/* saros.db record layout (must match build_db.py) */
#define SAROS_RECORD_SIZE  174   /* 1 + 1 + 86*2 bytes */

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

int eclipse_db_open(const char *times_path,
                    const char *info_path,
                    const char *saros_path)
{
    /* ---- eclipse_times.db ---- */
    int times_fd = open(times_path, O_RDONLY);
    if (times_fd < 0) {
        perror(times_path);
        return -1;
    }

    off_t times_size = lseek(times_fd, 0, SEEK_END);
    if (times_size < 0) {
        perror("lseek times");
        close(times_fd);
        return -1;
    }
    lseek(times_fd, 0, SEEK_SET);

    if (times_size % (off_t)sizeof(int64_t) != 0) {
        fprintf(stderr, "eclipse_times.db: unexpected size %lld\n",
                (long long)times_size);
        close(times_fd);
        return -1;
    }

    g_times_count = (uint32_t)(times_size / (off_t)sizeof(int64_t));
    g_times = malloc((size_t)times_size);
    if (!g_times) {
        perror("malloc times");
        close(times_fd);
        return -1;
    }

    ssize_t n = read(times_fd, g_times, (size_t)times_size);
    close(times_fd);
    if (n != (ssize_t)times_size) {
        perror("read times");
        free(g_times);
        g_times = NULL;
        return -1;
    }

    /* ---- eclipse_info.db ---- */
    g_info_fd = open(info_path, O_RDONLY);
    if (g_info_fd < 0) {
        perror(info_path);
        free(g_times);
        g_times = NULL;
        return -1;
    }

    /* ---- saros.db ---- */
    g_saros_fd = open(saros_path, O_RDONLY);
    if (g_saros_fd < 0) {
        perror(saros_path);
        close(g_info_fd);
        g_info_fd = -1;
        free(g_times);
        g_times = NULL;
        return -1;
    }

    return 0;
}

void eclipse_db_close(void)
{
    free(g_times);
    g_times = NULL;
    g_times_count = 0;

    if (g_info_fd >= 0)  { close(g_info_fd);  g_info_fd  = -1; }
    if (g_saros_fd >= 0) { close(g_saros_fd); g_saros_fd = -1; }
}

/* ── Binary search helpers ───────────────────────────────────────────────── */

/*
 * lower_bound: returns index of first element >= key, or g_times_count if none.
 */
static uint32_t lower_bound(int64_t key)
{
    uint32_t lo = 0, hi = g_times_count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        if (g_times[mid] < key)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo;
}

/*
 * upper_bound: returns index of first element > key, or g_times_count if none.
 * The last element <= key is at upper_bound(key) - 1.
 */
static uint32_t upper_bound(int64_t key)
{
    uint32_t lo = 0, hi = g_times_count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        if (g_times[mid] <= key)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo;
}

/* ── Queries ─────────────────────────────────────────────────────────────── */

eclipse_ref_t find_next_eclipse(int64_t timestamp)
{
    eclipse_ref_t result = {0, 0, 0};
    uint32_t idx = lower_bound(timestamp);
    if (idx >= g_times_count)
        return result;  /* no future eclipse */
    result.unix_time = g_times[idx];
    result.index     = (uint16_t)idx;
    result.found     = 1;
    return result;
}

eclipse_ref_t find_past_eclipse(int64_t timestamp)
{
    eclipse_ref_t result = {0, 0, 0};
    uint32_t idx = upper_bound(timestamp);
    if (idx == 0)
        return result;  /* no past eclipse */
    idx--;
    result.unix_time = g_times[idx];
    result.index     = (uint16_t)idx;
    result.found     = 1;
    return result;
}

int64_t get_eclipse_time(uint16_t index)
{
    if (index >= g_times_count) return 0;
    return g_times[index];
}

eclipse_info_t get_eclipse_info(uint16_t index)
{
    eclipse_info_t info;
    memset(&info, 0, sizeof(info));

    off_t offset = (off_t)index * (off_t)sizeof(eclipse_info_t);
    if (lseek(g_info_fd, offset, SEEK_SET) < 0) {
        perror("lseek info");
        return info;
    }
    if (read(g_info_fd, &info, sizeof(info)) != (ssize_t)sizeof(info)) {
        perror("read info");
    }
    return info;
}

saros_series_t get_saros_series(uint8_t saros_number)
{
    saros_series_t result;
    memset(&result, 0, sizeof(result));

    if (saros_number < 1 || saros_number > 180)
        return result;

    /* Each record: uint8 count, uint8 pad, uint16 indices[86] = 174 bytes */
    off_t offset = (off_t)(saros_number - 1) * SAROS_RECORD_SIZE;
    if (lseek(g_saros_fd, offset, SEEK_SET) < 0) {
        perror("lseek saros");
        return result;
    }

    uint8_t  count;
    uint8_t  pad;
    uint16_t indices[SAROS_MAX_ECLIPSES];

    if (read(g_saros_fd, &count, 1) != 1) { perror("read saros count"); return result; }
    if (read(g_saros_fd, &pad,   1) != 1) { perror("read saros pad");   return result; }
    if (read(g_saros_fd, indices, sizeof(indices)) != (ssize_t)sizeof(indices)) {
        perror("read saros indices");
        return result;
    }

    result.count = count;
    memcpy(result.indices, indices, (size_t)count * sizeof(uint16_t));
    return result;
}
