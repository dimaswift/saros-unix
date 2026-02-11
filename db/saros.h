/*
 * saros.h — Eclipse lookup library (solar + lunar), PROGMEM/RAM compatible
 *
 * ── Usage ─────────────────────────────────────────────────────────────────
 *
 * The solar and lunar data headers share identical array names (e.g.
 * eclipse_times_modern[]) so they cannot both be included in the same
 * translation unit.  Compile two separate translation units:
 *
 *   solar_impl.c / solar_impl.cpp
 *   ─────────────────────────────
 *   #define SAROS_IMPL_SOLAR          // activates solar implementation
 *   // #define SAROS_USE_ALL          // uncomment to use full Saros 1-180 dataset
 *                                     // default is "modern" (Saros 110-173)
 *   // #define ECLIPSE_USE_PROGMEM    // uncomment on AVR/ESP32 to store in flash
 *   #include "solar/eclipse_times_modern.h"
 *   #include "solar/eclipse_info_modern.h"
 *   #include "solar/saros_modern.h"
 *   #include "saros.h"
 *
 *   lunar_impl.c / lunar_impl.cpp
 *   ─────────────────────────────
 *   #define SAROS_IMPL_LUNAR
 *   #include "lunar/eclipse_times_modern.h"
 *   #include "lunar/eclipse_info_modern.h"
 *   #include "lunar/saros_modern.h"
 *   #include "saros.h"
 *
 *   main.c / sketch.ino
 *   ───────────────────
 *   #include "saros.h"                // declarations only — no SAROS_IMPL_*
 *   // call find_next_solar_eclipse(), find_next_lunar_eclipse(), etc.
 *
 * ── Data slices ───────────────────────────────────────────────────────────
 *   "modern"  Saros 110–173  (default, ~4500 eclipses, lower flash usage)
 *   "all"     Saros   1–180  (full catalog, ~13000 eclipses)
 *
 *   To use "all" define SAROS_USE_ALL before including the data headers and
 *   this file, and change the included header names accordingly.
 *
 * ── PROGMEM (AVR / ESP32) ─────────────────────────────────────────────────
 *   Define ECLIPSE_USE_PROGMEM before including the data headers.
 *   The data headers define the ECLIPSE_READ_* macros accordingly.
 *
 * ── Caching ───────────────────────────────────────────────────────────────
 *   Each implementation (solar / lunar) keeps one cached result.
 *   On a subsequent call the cache is valid when the new timestamp still
 *   falls within the same inter-eclipse interval, avoiding a binary search.
 *   Call solar_invalidate_cache() / lunar_invalidate_cache() to force a
 *   fresh search (rarely needed).
 */

#ifndef SAROS_H
#define SAROS_H

#include <stdint.h>
#include <string.h>   /* memset, memcpy */

/* ── PROGMEM fallback (if data headers were not included first) ─────────── */
#ifndef ECLIPSE_READ_BYTE
#  define ECLIPSE_READ_BYTE(p)  (*(const uint8_t  *)(p))
#  define ECLIPSE_READ_WORD(p)  (*(const uint16_t *)(p))
#  define ECLIPSE_READ_DWORD(p) (*(const uint32_t *)(p))
#endif

/* ── Constants ──────────────────────────────────────────────────────────── */
#define SAROS_MAX_ECLIPSES  96u
#define SAROS_RECORD_SIZE  194u   /* uint8 count + uint8 pad + uint16[96] */
#define ECLIPSE_INFO_SIZE   10u

/* ── Types ──────────────────────────────────────────────────────────────── */

/** Solar eclipse type codes (match SOLAR_ECL_TYPE_MAP in build_db.py).
 *
 *  A   Annular                 Moon's disk smaller than Sun, ring of sunlight visible
 *  A+  Annular (long)          long annular phase
 *  A-  Annular (sub-central)   path passes near edge of antumbra
 *  Am  Annular (short)         brief annular phase
 *  An  Annular (non-central)   annular but path misses Earth's centre
 *  As  Annular (saros)         first/last member of a Saros series, annular
 *  H   Hybrid                  transitions between annular and total along the path
 *  H2  Hybrid (variant 2)
 *  H3  Hybrid (variant 3)
 *  Hm  Hybrid (short)          brief hybrid phase
 *  P   Partial                 Moon covers part of the solar disk only
 *  Pb  Partial (beginning)     first eclipse in a Saros series, partial
 *  Pe  Partial (end)           last eclipse in a Saros series, partial
 *  T   Total                   Moon fully covers the Sun
 *  T+  Total (long)            totality lasts more than ~5 minutes
 *  T-  Total (sub-central)     path passes near edge of umbra
 *  Tm  Total (short)           totality lasts less than ~1 minute
 *  Tn  Total (non-central)     total but path misses Earth's centre
 *  Ts  Total (saros)           first/last member of a Saros series, total
 */
typedef enum {
    SOLAR_ECL_A    = 0,  SOLAR_ECL_Aplus  = 1,  SOLAR_ECL_Aminus = 2,
    SOLAR_ECL_Am   = 3,  SOLAR_ECL_An     = 4,  SOLAR_ECL_As     = 5,
    SOLAR_ECL_H    = 6,  SOLAR_ECL_H2     = 7,  SOLAR_ECL_H3     = 8,  SOLAR_ECL_Hm = 9,
    SOLAR_ECL_P    = 10, SOLAR_ECL_Pb     = 11, SOLAR_ECL_Pe     = 12,
    SOLAR_ECL_T    = 13, SOLAR_ECL_Tplus  = 14, SOLAR_ECL_Tminus = 15,
    SOLAR_ECL_Tm   = 16, SOLAR_ECL_Tn     = 17, SOLAR_ECL_Ts     = 18,
    SOLAR_ECL_TYPE_COUNT = 19
} solar_eclipse_type_t;

/** Lunar eclipse type codes (match LUNAR_ECL_TYPE_MAP in build_db.py).
 *
 *  N   Penumbral               Moon passes through Earth's penumbra only
 *  Nb  Penumbral (beginning)   first eclipse in a Saros series, penumbral
 *  Ne  Penumbral (end)         last eclipse in a Saros series, penumbral
 *  Nx  Penumbral (non-central) Moon misses the umbral shadow entirely
 *  P   Partial                 Moon partially enters the umbra
 *  Pb  Partial (beginning)     first eclipse in a Saros series, partial
 *  Pe  Partial (end)           last eclipse in a Saros series, partial
 *  T   Total                   Moon fully immersed in the umbra
 *  T+  Total (long)            totality lasts more than ~100 minutes
 *  T-  Total (sub-central)     Moon passes near the edge of the umbra during totality
 *  Tm  Total (short)           totality lasts less than ~20 minutes
 *  Tn  Total (non-central)     Moon misses the axis of the shadow
 *  Ts  Total (saros)           first/last member of a Saros series, total
 */
typedef enum {
    LUNAR_ECL_N    = 0,  LUNAR_ECL_Nb = 1, LUNAR_ECL_Ne = 2, LUNAR_ECL_Nx = 3,
    LUNAR_ECL_P    = 4,  LUNAR_ECL_Pb = 5, LUNAR_ECL_Pe = 6,
    LUNAR_ECL_T    = 7,  LUNAR_ECL_Tplus = 8, LUNAR_ECL_Tminus = 9,
    LUNAR_ECL_Tm   = 10, LUNAR_ECL_Tn = 11, LUNAR_ECL_Ts = 12,
    LUNAR_ECL_TYPE_COUNT = 13
} lunar_eclipse_type_t;

/** Decoded solar eclipse record (expanded from the 10-byte packed form). */
typedef struct {
    int16_t  latitude_deg10;   /**< latitude  × 10, e.g. 633 = 63.3°N */
    int16_t  longitude_deg10;  /**< longitude × 10, e.g. -1376 = 137.6°W */
    uint16_t central_duration; /**< central duration in seconds; 0xFFFF = n/a */
    uint8_t  saros_number;     /**< Saros series number (1–180) */
    uint8_t  saros_pos;        /**< 0-based position within the series */
    uint8_t  ecl_type;         /**< solar_eclipse_type_t value */
    uint8_t  sun_alt;          /**< sun altitude at greatest eclipse (degrees) */
} solar_eclipse_info_t;

/** Decoded lunar eclipse record (expanded from the 10-byte packed form). */
typedef struct {
    uint16_t pen_duration;     /**< penumbral phase duration in seconds; 0xFFFF = n/a */
    uint16_t par_duration;     /**< partial    phase duration in seconds; 0xFFFF = n/a */
    uint16_t total_duration;   /**< total      phase duration in seconds; 0xFFFF = n/a */
    uint8_t  saros_number;     /**< Saros series number (1–180) */
    uint8_t  saros_pos;        /**< 0-based position within the series */
    uint8_t  ecl_type;         /**< lunar_eclipse_type_t value */
    uint8_t  _pad;
} lunar_eclipse_info_t;

/**
 * eclipse_entry_t — one eclipse with timestamp, global index, and decoded info.
 * Check valid == 1 before using.
 */
typedef struct {
    int64_t  unix_time;        /**< seconds since Unix epoch (TD scale) */
    uint16_t global_index;     /**< flat index into eclipse_times / eclipse_info arrays */
    union {
        solar_eclipse_info_t solar;
        lunar_eclipse_info_t lunar;
    } info;
    uint8_t  valid;            /**< 1 = populated; 0 = no eclipse in this direction */
} eclipse_entry_t;

/**
 * eclipse_result_t — returned by find_next/past_solar/lunar_eclipse().
 *
 * eclipse    : the closest eclipse at-or-after (next) / at-or-before (past) ts
 * saros_prev : the previous eclipse in the same Saros series (valid=0 if none)
 * saros_next : the next    eclipse in the same Saros series (valid=0 if none)
 */
typedef struct {
    eclipse_entry_t eclipse;
    eclipse_entry_t saros_prev;
    eclipse_entry_t saros_next;
} eclipse_result_t;

/**
 * saros_window_t — returned by find_solar/lunar_saros_window().
 *
 * past   : most recent eclipse in the Saros series before timestamp (valid=0 if none)
 * future : next eclipse in the Saros series at-or-after timestamp   (valid=0 if none)
 */
typedef struct {
    eclipse_entry_t past;
    eclipse_entry_t future;
    uint8_t         saros_number;
} saros_window_t;

/* ── Public API ─────────────────────────────────────────────────────────── */

#ifdef __cplusplus
extern "C" {
#endif

/**
 * find_next_solar_eclipse(ts)
 *   Nearest solar eclipse at or after ts.
 *   Also returns the preceding and following eclipses in the same Saros series.
 *   result.eclipse.valid == 0 if ts is past the last eclipse in the dataset.
 */
eclipse_result_t find_next_solar_eclipse(int64_t timestamp);

/**
 * find_past_solar_eclipse(ts)
 *   Nearest solar eclipse at or before ts.
 *   Also returns the preceding and following eclipses in the same Saros series.
 *   result.eclipse.valid == 0 if ts is before the first eclipse in the dataset.
 */
eclipse_result_t find_past_solar_eclipse(int64_t timestamp);

/**
 * find_solar_saros_window(ts, saros_number)
 *   Returns the most recent past eclipse and the next future eclipse within
 *   the specified solar Saros series, relative to ts.
 */
saros_window_t find_solar_saros_window(int64_t timestamp, uint8_t saros_number);

/** Clear the solar lookup cache (rarely needed). */
void solar_invalidate_cache(void);

/** Same four functions for lunar eclipses. */
eclipse_result_t find_next_lunar_eclipse(int64_t timestamp);
eclipse_result_t find_past_lunar_eclipse(int64_t timestamp);
saros_window_t   find_lunar_saros_window(int64_t timestamp, uint8_t saros_number);
void             lunar_invalidate_cache(void);

#ifdef __cplusplus
}
#endif

/* ── Closest-eclipse helpers (inline, use the functions above) ──────────── */

/**
 * find_closest_solar_eclipse(ts)
 *   Returns whichever of the next or past solar eclipse is nearer to ts.
 *   When equidistant, the future eclipse is returned.
 */
static inline eclipse_result_t find_closest_solar_eclipse(int64_t timestamp)
{
    eclipse_result_t nxt = find_next_solar_eclipse(timestamp);
    eclipse_result_t pst = find_past_solar_eclipse(timestamp);
    if (!nxt.eclipse.valid) return pst;
    if (!pst.eclipse.valid) return nxt;
    int64_t d_nxt = nxt.eclipse.unix_time - timestamp;
    int64_t d_pst = timestamp - pst.eclipse.unix_time;
    return (d_pst < d_nxt) ? pst : nxt;
}

/**
 * find_closest_lunar_eclipse(ts)
 *   Returns whichever of the next or past lunar eclipse is nearer to ts.
 *   When equidistant, the future eclipse is returned.
 */
static inline eclipse_result_t find_closest_lunar_eclipse(int64_t timestamp)
{
    eclipse_result_t nxt = find_next_lunar_eclipse(timestamp);
    eclipse_result_t pst = find_past_lunar_eclipse(timestamp);
    if (!nxt.eclipse.valid) return pst;
    if (!pst.eclipse.valid) return nxt;
    int64_t d_nxt = nxt.eclipse.unix_time - timestamp;
    int64_t d_pst = timestamp - pst.eclipse.unix_time;
    return (d_pst < d_nxt) ? pst : nxt;
}


/* ══════════════════════════════════════════════════════════════════════════ *
 * Implementation — compiled only when SAROS_IMPL_SOLAR or SAROS_IMPL_LUNAR  *
 * is defined (typically in the dedicated .c / .cpp translation unit).        *
 * ══════════════════════════════════════════════════════════════════════════ */
#if defined(SAROS_IMPL_SOLAR) || defined(SAROS_IMPL_LUNAR)

/* Determine which data-slice macros are available.
 * The data headers (eclipse_times_modern.h etc.) define:
 *   ECLIPSE_MODERN_COUNT / ECLIPSE_ALL_COUNT
 *   ECLIPSE_MODERN_SAROS_FIRST / ECLIPSE_ALL_SAROS_FIRST
 *   ECLIPSE_MODERN_SAROS_LAST  / ECLIPSE_ALL_SAROS_LAST
 * and declare the arrays:
 *   eclipse_times_modern[] / eclipse_times_all[]
 *   eclipse_info_modern[]  / eclipse_info_all[]
 *   saros_modern[]         / saros_all[]
 */
#ifdef SAROS_USE_ALL
#  define _SAROS_TIMES_ARR   eclipse_times_all
#  define _SAROS_INFO_ARR    eclipse_info_all
#  define _SAROS_SAROS_ARR   saros_all
#  define _SAROS_COUNT       ECLIPSE_ALL_COUNT
#  define _SAROS_FIRST       ((uint8_t)ECLIPSE_ALL_SAROS_FIRST)
#  define _SAROS_LAST        ((uint8_t)ECLIPSE_ALL_SAROS_LAST)
#else
#  define _SAROS_TIMES_ARR   eclipse_times_modern
#  define _SAROS_INFO_ARR    eclipse_info_modern
#  define _SAROS_SAROS_ARR   saros_modern
#  define _SAROS_COUNT       ECLIPSE_MODERN_COUNT
#  define _SAROS_FIRST       ((uint8_t)ECLIPSE_MODERN_SAROS_FIRST)
#  define _SAROS_LAST        ((uint8_t)ECLIPSE_MODERN_SAROS_LAST)
#endif

/* ── Low-level PROGMEM / RAM accessors ─────────────────────────────────── */

static inline int64_t _saros_read_time(const uint8_t *arr, uint32_t idx)
{
    const uint8_t *p = arr + idx * 8u;
    uint64_t lo = (uint64_t)ECLIPSE_READ_DWORD(p);
    uint64_t hi = (uint64_t)ECLIPSE_READ_DWORD(p + 4u);
    return (int64_t)(lo | (hi << 32));
}

static inline void _saros_read_info_raw(const uint8_t *arr, uint32_t idx,
                                        uint8_t out[ECLIPSE_INFO_SIZE])
{
    const uint8_t *p = arr + idx * ECLIPSE_INFO_SIZE;
    for (uint8_t i = 0; i < ECLIPSE_INFO_SIZE; i++)
        out[i] = ECLIPSE_READ_BYTE(p + i);
}

static void _saros_load_series(const uint8_t *saros_arr,
                               uint8_t  saros_num,
                               uint8_t  saros_first,
                               uint8_t *out_count,
                               uint16_t out_indices[SAROS_MAX_ECLIPSES])
{
    uint32_t offset = (uint32_t)(saros_num - saros_first) * SAROS_RECORD_SIZE;
    const uint8_t *p = saros_arr + offset;
    *out_count = ECLIPSE_READ_BYTE(p);
    for (uint8_t i = 0; i < SAROS_MAX_ECLIPSES; i++)
        out_indices[i] = ECLIPSE_READ_WORD(p + 2u + (uint32_t)i * 2u);
}

/* ── Decoders ───────────────────────────────────────────────────────────── */

static inline solar_eclipse_info_t _decode_solar(const uint8_t b[ECLIPSE_INFO_SIZE])
{
    solar_eclipse_info_t r;
    r.latitude_deg10   = (int16_t)((uint16_t)b[0] | ((uint16_t)b[1] << 8));
    r.longitude_deg10  = (int16_t)((uint16_t)b[2] | ((uint16_t)b[3] << 8));
    r.central_duration = (uint16_t)b[4] | ((uint16_t)b[5] << 8);
    r.saros_number     = b[6];
    r.saros_pos        = b[7];
    r.ecl_type         = b[8];
    r.sun_alt          = b[9];
    return r;
}

static inline lunar_eclipse_info_t _decode_lunar(const uint8_t b[ECLIPSE_INFO_SIZE])
{
    lunar_eclipse_info_t r;
    r.pen_duration   = (uint16_t)b[0] | ((uint16_t)b[1] << 8);
    r.par_duration   = (uint16_t)b[2] | ((uint16_t)b[3] << 8);
    r.total_duration = (uint16_t)b[4] | ((uint16_t)b[5] << 8);
    r.saros_number   = b[6];
    r.saros_pos      = b[7];
    r.ecl_type       = b[8];
    r._pad           = 0;
    return r;
}

/* ── eclipse_entry builder ─────────────────────────────────────────────── */

static eclipse_entry_t _make_entry(const uint8_t *times_arr,
                                   const uint8_t *info_arr,
                                   uint32_t global_idx,
                                   int is_lunar)
{
    eclipse_entry_t e;
    memset(&e, 0, sizeof(e));
    e.global_index = (uint16_t)global_idx;
    e.unix_time    = _saros_read_time(times_arr, global_idx);
    uint8_t b[ECLIPSE_INFO_SIZE];
    _saros_read_info_raw(info_arr, global_idx, b);
    if (is_lunar)
        e.info.lunar = _decode_lunar(b);
    else
        e.info.solar = _decode_solar(b);
    e.valid = 1;
    return e;
}

/* ── Binary search ──────────────────────────────────────────────────────── */

/* First index with value >= key; returns count if all values < key. */
static uint32_t _lower_bound(const uint8_t *times_arr, uint32_t count, int64_t key)
{
    uint32_t lo = 0, hi = count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2u;
        if (_saros_read_time(times_arr, mid) < key)
            lo = mid + 1u;
        else
            hi = mid;
    }
    return lo;
}

/* First index with value > key; element at result-1 is the last <= key. */
static uint32_t _upper_bound(const uint8_t *times_arr, uint32_t count, int64_t key)
{
    uint32_t lo = 0, hi = count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2u;
        if (_saros_read_time(times_arr, mid) <= key)
            lo = mid + 1u;
        else
            hi = mid;
    }
    return lo;
}

/* ── Saros-neighbour lookup ─────────────────────────────────────────────── */

/*
 * Given the focal eclipse's saros_number and saros_pos, load the series and
 * return the immediately preceding and following eclipses within it.
 */
static void _saros_neighbours(
    const uint8_t *times_arr,
    const uint8_t *info_arr,
    const uint8_t *saros_arr,
    uint8_t saros_first, uint8_t saros_last,
    uint8_t saros_num, uint8_t saros_pos,
    int is_lunar,
    eclipse_entry_t *out_prev,
    eclipse_entry_t *out_next)
{
    memset(out_prev, 0, sizeof(*out_prev));
    memset(out_next, 0, sizeof(*out_next));

    if (saros_num < saros_first || saros_num > saros_last)
        return;

    uint8_t  count = 0;
    uint16_t indices[SAROS_MAX_ECLIPSES];
    _saros_load_series(saros_arr, saros_num, saros_first, &count, indices);

    if (saros_pos > 0u) {
        *out_prev = _make_entry(times_arr, info_arr, indices[saros_pos - 1u], is_lunar);
    }
    if ((uint32_t)saros_pos + 1u < (uint32_t)count) {
        *out_next = _make_entry(times_arr, info_arr, indices[saros_pos + 1u], is_lunar);
    }
}

/* ── Cache type ─────────────────────────────────────────────────────────── */

/*
 * Stores the last eclipse_result_t and the timestamp interval [lo, hi)
 * (for "next" searches) or [lo, hi] (for "past" searches) within which
 * that result remains valid.
 */
typedef struct {
    eclipse_result_t result;
    int64_t          lo;       /* inclusive lower bound for cache hit */
    int64_t          hi;       /* inclusive upper bound for cache hit */
    uint8_t          valid;
    uint8_t          for_next; /* 1 = from a find_next call, 0 = find_past */
} _saros_cache_t;

/* ────────────────────────────────────────────────────────────────────────── *
 * SOLAR implementation                                                       *
 * ────────────────────────────────────────────────────────────────────────── */
#if defined(SAROS_IMPL_SOLAR)

static _saros_cache_t _solar_cache;  /* zero-initialised at startup */

void solar_invalidate_cache(void)
{
    memset(&_solar_cache, 0, sizeof(_solar_cache));
}

static eclipse_result_t _solar_build(uint32_t focal_idx)
{
    eclipse_result_t r;
    memset(&r, 0, sizeof(r));
    r.eclipse = _make_entry(_SAROS_TIMES_ARR, _SAROS_INFO_ARR, focal_idx, /*lunar=*/0);
    _saros_neighbours(
        _SAROS_TIMES_ARR, _SAROS_INFO_ARR, _SAROS_SAROS_ARR,
        _SAROS_FIRST, _SAROS_LAST,
        r.eclipse.info.solar.saros_number,
        r.eclipse.info.solar.saros_pos,
        /*lunar=*/0,
        &r.saros_prev, &r.saros_next);
    return r;
}

eclipse_result_t find_next_solar_eclipse(int64_t timestamp)
{
    eclipse_result_t empty;
    memset(&empty, 0, sizeof(empty));

    /* Cache check: same interval → same "next" eclipse */
    if (_solar_cache.valid && _solar_cache.for_next &&
        timestamp >= _solar_cache.lo && timestamp <= _solar_cache.hi)
        return _solar_cache.result;

    uint32_t idx = _lower_bound(_SAROS_TIMES_ARR, _SAROS_COUNT, timestamp);
    if (idx >= _SAROS_COUNT)
        return empty;

    eclipse_result_t r = _solar_build(idx);

    /* Cache covers [previous_eclipse+1 .. this_eclipse] */
    _solar_cache.result   = r;
    _solar_cache.for_next = 1;
    _solar_cache.valid    = 1;
    _solar_cache.lo = (idx > 0u)
        ? _saros_read_time(_SAROS_TIMES_ARR, idx - 1u) + 1
        : INT64_MIN;
    _solar_cache.hi = r.eclipse.unix_time;

    return r;
}

eclipse_result_t find_past_solar_eclipse(int64_t timestamp)
{
    eclipse_result_t empty;
    memset(&empty, 0, sizeof(empty));

    /* Cache check: same interval → same "past" eclipse */
    if (_solar_cache.valid && !_solar_cache.for_next &&
        timestamp >= _solar_cache.lo && timestamp <= _solar_cache.hi)
        return _solar_cache.result;

    uint32_t idx = _upper_bound(_SAROS_TIMES_ARR, _SAROS_COUNT, timestamp);
    if (idx == 0u)
        return empty;
    idx--;

    eclipse_result_t r = _solar_build(idx);

    /* Cache covers [this_eclipse .. next_eclipse-1] */
    _solar_cache.result   = r;
    _solar_cache.for_next = 0;
    _solar_cache.valid    = 1;
    _solar_cache.lo = r.eclipse.unix_time;
    _solar_cache.hi = (idx + 1u < _SAROS_COUNT)
        ? _saros_read_time(_SAROS_TIMES_ARR, idx + 1u) - 1
        : INT64_MAX;

    return r;
}

saros_window_t find_solar_saros_window(int64_t timestamp, uint8_t saros_number)
{
    saros_window_t w;
    memset(&w, 0, sizeof(w));
    w.saros_number = saros_number;

    if (saros_number < _SAROS_FIRST || saros_number > _SAROS_LAST)
        return w;

    uint8_t  count = 0;
    uint16_t indices[SAROS_MAX_ECLIPSES];
    _saros_load_series(_SAROS_SAROS_ARR, saros_number, _SAROS_FIRST, &count, indices);

    if (count == 0u)
        return w;

    /* Binary-search within this series' eclipse list */
    uint8_t lo = 0, hi = count;
    while (lo < hi) {
        uint8_t mid = lo + (hi - lo) / 2u;
        int64_t t = _saros_read_time(_SAROS_TIMES_ARR, indices[mid]);
        if (t < timestamp)
            lo = mid + 1u;
        else
            hi = mid;
    }
    /* lo = first index in 'indices[]' whose eclipse time >= timestamp */

    if (lo < count)
        w.future = _make_entry(_SAROS_TIMES_ARR, _SAROS_INFO_ARR, indices[lo],      0);
    if (lo > 0u)
        w.past   = _make_entry(_SAROS_TIMES_ARR, _SAROS_INFO_ARR, indices[lo - 1u], 0);

    return w;
}

#endif /* SAROS_IMPL_SOLAR */

/* ────────────────────────────────────────────────────────────────────────── *
 * LUNAR implementation                                                       *
 * ────────────────────────────────────────────────────────────────────────── */
#if defined(SAROS_IMPL_LUNAR)

static _saros_cache_t _lunar_cache;  /* zero-initialised at startup */

void lunar_invalidate_cache(void)
{
    memset(&_lunar_cache, 0, sizeof(_lunar_cache));
}

static eclipse_result_t _lunar_build(uint32_t focal_idx)
{
    eclipse_result_t r;
    memset(&r, 0, sizeof(r));
    r.eclipse = _make_entry(_SAROS_TIMES_ARR, _SAROS_INFO_ARR, focal_idx, /*lunar=*/1);
    _saros_neighbours(
        _SAROS_TIMES_ARR, _SAROS_INFO_ARR, _SAROS_SAROS_ARR,
        _SAROS_FIRST, _SAROS_LAST,
        r.eclipse.info.lunar.saros_number,
        r.eclipse.info.lunar.saros_pos,
        /*lunar=*/1,
        &r.saros_prev, &r.saros_next);
    return r;
}

eclipse_result_t find_next_lunar_eclipse(int64_t timestamp)
{
    eclipse_result_t empty;
    memset(&empty, 0, sizeof(empty));

    if (_lunar_cache.valid && _lunar_cache.for_next &&
        timestamp >= _lunar_cache.lo && timestamp <= _lunar_cache.hi)
        return _lunar_cache.result;

    uint32_t idx = _lower_bound(_SAROS_TIMES_ARR, _SAROS_COUNT, timestamp);
    if (idx >= _SAROS_COUNT)
        return empty;

    eclipse_result_t r = _lunar_build(idx);

    _lunar_cache.result   = r;
    _lunar_cache.for_next = 1;
    _lunar_cache.valid    = 1;
    _lunar_cache.lo = (idx > 0u)
        ? _saros_read_time(_SAROS_TIMES_ARR, idx - 1u) + 1
        : INT64_MIN;
    _lunar_cache.hi = r.eclipse.unix_time;

    return r;
}

eclipse_result_t find_past_lunar_eclipse(int64_t timestamp)
{
    eclipse_result_t empty;
    memset(&empty, 0, sizeof(empty));

    if (_lunar_cache.valid && !_lunar_cache.for_next &&
        timestamp >= _lunar_cache.lo && timestamp <= _lunar_cache.hi)
        return _lunar_cache.result;

    uint32_t idx = _upper_bound(_SAROS_TIMES_ARR, _SAROS_COUNT, timestamp);
    if (idx == 0u)
        return empty;
    idx--;

    eclipse_result_t r = _lunar_build(idx);

    _lunar_cache.result   = r;
    _lunar_cache.for_next = 0;
    _lunar_cache.valid    = 1;
    _lunar_cache.lo = r.eclipse.unix_time;
    _lunar_cache.hi = (idx + 1u < _SAROS_COUNT)
        ? _saros_read_time(_SAROS_TIMES_ARR, idx + 1u) - 1
        : INT64_MAX;

    return r;
}

saros_window_t find_lunar_saros_window(int64_t timestamp, uint8_t saros_number)
{
    saros_window_t w;
    memset(&w, 0, sizeof(w));
    w.saros_number = saros_number;

    if (saros_number < _SAROS_FIRST || saros_number > _SAROS_LAST)
        return w;

    uint8_t  count = 0;
    uint16_t indices[SAROS_MAX_ECLIPSES];
    _saros_load_series(_SAROS_SAROS_ARR, saros_number, _SAROS_FIRST, &count, indices);

    if (count == 0u)
        return w;

    uint8_t lo = 0, hi = count;
    while (lo < hi) {
        uint8_t mid = lo + (hi - lo) / 2u;
        int64_t t = _saros_read_time(_SAROS_TIMES_ARR, indices[mid]);
        if (t < timestamp)
            lo = mid + 1u;
        else
            hi = mid;
    }

    if (lo < count)
        w.future = _make_entry(_SAROS_TIMES_ARR, _SAROS_INFO_ARR, indices[lo],      1);
    if (lo > 0u)
        w.past   = _make_entry(_SAROS_TIMES_ARR, _SAROS_INFO_ARR, indices[lo - 1u], 1);

    return w;
}

#endif /* SAROS_IMPL_LUNAR */

/* Clean up internal macros */
#undef _SAROS_TIMES_ARR
#undef _SAROS_INFO_ARR
#undef _SAROS_SAROS_ARR
#undef _SAROS_COUNT
#undef _SAROS_FIRST
#undef _SAROS_LAST

#endif /* SAROS_IMPL_SOLAR || SAROS_IMPL_LUNAR */

#endif /* SAROS_H */
