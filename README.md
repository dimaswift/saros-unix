# saros-unix

Solar and lunar eclipse lookup library backed by NASA's Saros catalog.
Data covers all 180 solar and 180 lunar Saros series.
Designed for embedded targets (AVR, ESP32) via PROGMEM headers, and for
hosted (Linux / macOS) use with the same API.

---

## Repository layout

```
saros-unix/
  parse_solar_saros.py   — fetch and parse one solar Saros series from NASA
  parse_lunar_saros.py   — fetch and parse one lunar Saros series from NASA
  fetch_all.sh           — fetch all series (solar, lunar, or both)

  solar/{1..180}/eclipses.jsonl   — one solar eclipse per line
  lunar/{1..180}/eclipses.jsonl   — one lunar eclipse per line

  db/
    build_db.py          — build binary .db files and generate C headers

    saros.h              — C library (solar + lunar API, caching, PROGMEM)
    solar_impl.c         — solar implementation translation unit
    lunar_impl.c         — lunar implementation translation unit

    solar/               — generated solar headers and .db files
      eclipse_times_{all,modern}.h
      eclipse_info_{all,modern}.h
      saros_{all,modern}.h

    lunar/               — generated lunar headers and .db files
      eclipse_times_{all,modern}.h
      eclipse_info_{all,modern}.h
      saros_{all,modern}.h
```

**Data slices:**

| Slice | Saros range | Solar eclipses | Lunar eclipses |
|-------|-------------|---------------|----------------|
| `all` | 1–180 | 13,206 | 12,223 |
| `modern` | 110–173 | 4,612 | 4,279 |

---

## Fetching data

```bash
pip install requests beautifulsoup4

# Fetch all solar and lunar series (skips already-downloaded)
./fetch_all.sh

# Fetch only solar, or only lunar
./fetch_all.sh solar
./fetch_all.sh lunar

# Fetch a specific range
./fetch_all.sh solar 130 145
```

---

## Building the C headers

```bash
python3 db/build_db.py         # builds both solar and lunar
python3 db/build_db.py solar   # solar only
python3 db/build_db.py lunar   # lunar only
```

Outputs `eclipse_times_*.h`, `eclipse_info_*.h`, and `saros_*.h` into
`db/solar/` and `db/lunar/`.

---

## C library — saros.h

`db/saros.h` is a single-header library. It provides solar and lunar eclipse
lookup with binary search and a one-result cache.

### Two-translation-unit pattern

The solar and lunar data headers define arrays with the same names
(`eclipse_times_modern[]`, etc.) so they **cannot** both be in one TU.
Compile two separate files:

**solar_impl.c**
```c
#define SAROS_IMPL_SOLAR
// #define SAROS_USE_ALL          // full catalog (Saros 1-180); default is modern (110-173)
// #define ECLIPSE_USE_PROGMEM    // AVR/ESP32: store arrays in flash
#include "solar/eclipse_times_modern.h"
#include "solar/eclipse_info_modern.h"
#include "solar/saros_modern.h"
#include "saros.h"
```

**lunar_impl.c**
```c
#define SAROS_IMPL_LUNAR
#include "lunar/eclipse_times_modern.h"
#include "lunar/eclipse_info_modern.h"
#include "lunar/saros_modern.h"
#include "saros.h"
```

**main.c / sketch.ino**
```c
#include "saros.h"   // declarations only — no SAROS_IMPL_*
```

**Build:**
```bash
cc -O2 -std=c11 -o myapp main.c solar_impl.c lunar_impl.c
```

---

### API

```c
// ── Solar ─────────────────────────────────────────────────────────────────

// Nearest solar eclipse at or after ts.
// result.eclipse.valid == 0 if ts is past the last eclipse in the dataset.
// Also returns the preceding and following eclipses in the same Saros series.
eclipse_result_t find_next_solar_eclipse(int64_t timestamp);

// Nearest solar eclipse at or before ts.
eclipse_result_t find_past_solar_eclipse(int64_t timestamp);

// Past and future eclipses within a specific solar Saros series, relative to ts.
saros_window_t   find_solar_saros_window(int64_t timestamp, uint8_t saros_number);

// Solar eclipse closest to ts (inline helper — calls next + past internally).
eclipse_result_t find_closest_solar_eclipse(int64_t timestamp);

// Clear the solar lookup cache (rarely needed).
void solar_invalidate_cache(void);

// ── Lunar ─────────────────────────────────────────────────────────────────

eclipse_result_t find_next_lunar_eclipse(int64_t timestamp);
eclipse_result_t find_past_lunar_eclipse(int64_t timestamp);
eclipse_result_t find_closest_lunar_eclipse(int64_t timestamp);
saros_window_t   find_lunar_saros_window(int64_t timestamp, uint8_t saros_number);
void             lunar_invalidate_cache(void);
```

---

### Return types

```c
typedef struct {
    int64_t  unix_time;      // seconds since Unix epoch (TD scale)
    uint16_t global_index;   // flat index into eclipse_times / eclipse_info arrays
    union {
        solar_eclipse_info_t solar;
        lunar_eclipse_info_t lunar;
    } info;
    uint8_t  valid;          // 1 = populated; 0 = no eclipse in this direction
} eclipse_entry_t;

// Returned by find_next/past_*_eclipse()
typedef struct {
    eclipse_entry_t eclipse;     // the matched eclipse
    eclipse_entry_t saros_prev;  // previous eclipse in the same Saros series
    eclipse_entry_t saros_next;  // next eclipse in the same Saros series
} eclipse_result_t;

// Returned by find_*_saros_window()
typedef struct {
    eclipse_entry_t past;        // most recent eclipse in the series before ts
    eclipse_entry_t future;      // next eclipse in the series at or after ts
    uint8_t         saros_number;
} saros_window_t;
```

**Solar eclipse info:**
```c
typedef struct {
    int16_t  latitude_deg10;    // latitude  × 10 (e.g. 633 = 63.3°N)
    int16_t  longitude_deg10;   // longitude × 10 (e.g. -1376 = 137.6°W)
    uint16_t central_duration;  // central duration in seconds; 0xFFFF = n/a
    uint8_t  saros_number;      // 1–180
    uint8_t  saros_pos;         // 0-based position within the series
    uint8_t  ecl_type;          // solar_eclipse_type_t
    uint8_t  sun_alt;           // sun altitude at greatest eclipse (degrees)
} solar_eclipse_info_t;
```

**Lunar eclipse info:**
```c
typedef struct {
    uint16_t pen_duration;      // penumbral phase duration in seconds; 0xFFFF = n/a
    uint16_t par_duration;      // partial    phase duration in seconds; 0xFFFF = n/a
    uint16_t total_duration;    // total      phase duration in seconds; 0xFFFF = n/a
    uint8_t  saros_number;
    uint8_t  saros_pos;
    uint8_t  ecl_type;          // lunar_eclipse_type_t
} lunar_eclipse_info_t;
```

---

### Eclipse type codes

**Solar** (`solar_eclipse_type_t`):

| Value | Code | Description |
|-------|------|-------------|
| 0 | `A`  | Annular |
| 1 | `A+` | Annular (long) |
| 2 | `A-` | Annular (sub-central) |
| 3 | `Am` | Annular (short) |
| 4 | `An` | Annular (non-central) |
| 5 | `As` | Annular (saros) |
| 6 | `H`  | Hybrid (annular-total) |
| 7 | `H2` | Hybrid |
| 8 | `H3` | Hybrid |
| 9 | `Hm` | Hybrid (short) |
| 10 | `P`  | Partial |
| 11 | `Pb` | Partial (beginning of saros) |
| 12 | `Pe` | Partial (end of saros) |
| 13 | `T`  | Total |
| 14 | `T+` | Total (long) |
| 15 | `T-` | Total (sub-central) |
| 16 | `Tm` | Total (short) |
| 17 | `Tn` | Total (non-central) |
| 18 | `Ts` | Total (saros) |

**Lunar** (`lunar_eclipse_type_t`):

| Value | Code | Description |
|-------|------|-------------|
| 0 | `N`  | Penumbral |
| 1 | `Nb` | Penumbral (beginning of saros) |
| 2 | `Ne` | Penumbral (end of saros) |
| 3 | `Nx` | Penumbral (non-central) |
| 4 | `P`  | Partial |
| 5 | `Pb` | Partial (beginning of saros) |
| 6 | `Pe` | Partial (end of saros) |
| 7 | `T`  | Total |
| 8 | `T+` | Total (long) |
| 9 | `T-` | Total (sub-central) |
| 10 | `Tm` | Total (short) |
| 11 | `Tn` | Total (non-central) |
| 12 | `Ts` | Total (saros) |

---

### Caching

Each implementation (solar / lunar) keeps one cached `eclipse_result_t`.
A subsequent call hits the cache when the new timestamp falls within the same
inter-eclipse interval, avoiding a binary search.  No explicit management is
needed; call `solar_invalidate_cache()` / `lunar_invalidate_cache()` only if
the dataset is hot-swapped at runtime.

---

### PROGMEM (AVR / ESP32)

Define `ECLIPSE_USE_PROGMEM` before including the data headers.  The headers
will place arrays in flash with `PROGMEM` and define the `ECLIPSE_READ_*`
macros to use `pgm_read_byte` / `pgm_read_word` / `pgm_read_dword`.  The
`saros.h` implementation uses only these macros, so no other changes are
needed.

---

### Example

```c
#include <time.h>
#include "saros.h"

int main(void)
{
    int64_t now = (int64_t)time(NULL);

    // Next solar eclipse and its Saros neighbours
    eclipse_result_t r = find_next_solar_eclipse(now);
    if (r.eclipse.valid) {
        solar_eclipse_info_t *s = &r.eclipse.info.solar;
        printf("Next solar: unix=%lld  saros=%u  pos=%u  type=%u\n",
               (long long)r.eclipse.unix_time,
               s->saros_number, s->saros_pos, s->ecl_type);
    }

    // Saros 145 window around now
    saros_window_t w = find_solar_saros_window(now, 145);
    if (w.past.valid)
        printf("Saros 145 past:   unix=%lld\n", (long long)w.past.unix_time);
    if (w.future.valid)
        printf("Saros 145 future: unix=%lld\n", (long long)w.future.unix_time);

    // Next lunar eclipse
    eclipse_result_t lr = find_next_lunar_eclipse(now);
    if (lr.eclipse.valid) {
        lunar_eclipse_info_t *l = &lr.eclipse.info.lunar;
        printf("Next lunar: unix=%lld  saros=%u  type=%u\n",
               (long long)lr.eclipse.unix_time,
               l->saros_number, l->ecl_type);
    }

    return 0;
}
```

Build and run the included test:
```bash
make -C db
./db/test_saros_lib
```

---

## Data source

[NASA Eclipse Web Site — Solar Saros Series](https://eclipse.gsfc.nasa.gov/SEsaros/SEsaros.html)
[NASA Eclipse Web Site — Lunar Saros Series](https://eclipse.gsfc.nasa.gov/LEsaros/LEsaros.html)
Fred Espenak, NASA/GSFC (retired)
