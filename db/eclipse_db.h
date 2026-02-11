#ifndef ECLIPSE_DB_H
#define ECLIPSE_DB_H

#include <stdint.h>

/*
 * Eclipse type enum — values match the uint8 encoding in eclipse_info.db
 * and the ECLIPSE_TYPE_NAMES[] array order.
 */
typedef enum {
    ECL_A    = 0,
    ECL_Aplus= 1,
    ECL_Am   = 2,
    ECL_An   = 3,
    ECL_As   = 4,
    ECL_H    = 5,
    ECL_H2   = 6,
    ECL_H3   = 7,
    ECL_Hm   = 8,
    ECL_P    = 9,
    ECL_Pb   = 10,
    ECL_Pe   = 11,
    ECL_T    = 12,
    ECL_Tplus= 13,
    ECL_Tm   = 14,
    ECL_Tn   = 15,
    ECL_Ts   = 16,
    ECL_TYPE_COUNT = 17
} eclipse_type_t;

extern const char *ECLIPSE_TYPE_NAMES[ECL_TYPE_COUNT];

/*
 * eclipse_info_t — 10 bytes, packed, no padding.
 *
 * latitude_deg10  : latitude  × 10 as signed int16  (e.g. 63.3° → 633)
 * longitude_deg10 : longitude × 10 as signed int16  (e.g. -137.6° → -1376)
 * central_duration: eclipse duration in seconds; 0xFFFF = not applicable
 * saros_number    : Saros series number (1–180)
 * saros_pos       : 0-based position within the Saros series (chronological)
 * ecl_type        : eclipse_type_t value (0–16)
 * sun_alt         : sun altitude in degrees at greatest eclipse (0–90)
 */
typedef struct __attribute__((packed)) {
    int16_t  latitude_deg10;
    int16_t  longitude_deg10;
    uint16_t central_duration;
    uint8_t  saros_number;
    uint8_t  saros_pos;
    uint8_t  ecl_type;
    uint8_t  sun_alt;
} eclipse_info_t;

/*
 * eclipse_ref_t — result of find_next_eclipse / find_past_eclipse.
 * found == 0 means no eclipse exists in that direction.
 */
typedef struct {
    int64_t  unix_time;
    uint16_t index;
    int      found;
} eclipse_ref_t;

/*
 * saros_series_t — result of get_saros_series.
 * indices[] holds global eclipse indices (into eclipse_times.db / eclipse_info.db).
 */
#define SAROS_MAX_ECLIPSES 86
typedef struct {
    uint16_t indices[SAROS_MAX_ECLIPSES];
    uint8_t  count;
} saros_series_t;

/*
 * Lifecycle
 * ---------
 * eclipse_db_open: opens all three database files.
 *   Returns 0 on success, -1 on error (check errno / perror).
 *   Loads eclipse_times.db entirely into memory for O(log n) binary search.
 *
 * eclipse_db_close: releases resources.
 */
int  eclipse_db_open(const char *times_path,
                     const char *info_path,
                     const char *saros_path);
void eclipse_db_close(void);

/*
 * Queries
 * -------
 * find_next_eclipse(ts) : smallest eclipse timestamp >= ts
 * find_past_eclipse(ts) : largest  eclipse timestamp <= ts
 * get_eclipse_info(idx) : read eclipse_info_t from eclipse_info.db by global index
 * get_saros_series(n)   : read all eclipse indices for Saros series n (1-based)
 */
eclipse_ref_t  find_next_eclipse(int64_t timestamp);
eclipse_ref_t  find_past_eclipse(int64_t timestamp);
eclipse_info_t get_eclipse_info(uint16_t index);
int64_t        get_eclipse_time(uint16_t index);   /* O(1) from in-memory array */
saros_series_t get_saros_series(uint8_t saros_number);

#endif /* ECLIPSE_DB_H */
