# saros-unix

A compact database of all 13,148 solar eclipses across Saros series 1–180, parsed from NASA's eclipse catalog and stored in two formats:

- **Binary files** for desktop / server use (seekable, ~262 KB total)
- **C headers with PROGMEM support** for embedded targets (AVR, ESP32, etc.)

---

## Repository layout

```
saros-unix/
  parse_saros.py        — fetch and parse one Saros series from NASA
  fetch_all.sh          — fetch all series 1–180

  {1..180}/
    eclipses.jsonl      — one eclipse per line, sorted by unix_timestamp
    saros.json          — series metadata (type counts, duration, etc.)

  db/
    build_db.py         — build binary files and generate C headers
    eclipse_db.h        — C API for disk-based database
    eclipse_db.c        — implementation
    eclipse_db_progmem.h — inline API for PROGMEM / RAM headers

    — generated binary files —
    eclipse_times.db    — sorted int64 timestamps (105 KB)
    eclipse_info.db     — packed eclipse records, 10 bytes each (131 KB)
    saros.db            — saros series index records (31 KB)

    — generated C headers (PROGMEM-ready) —
    eclipse_times_all.h     eclipse_times_modern.h
    eclipse_info_all.h      eclipse_info_modern.h
    saros_all.h             saros_modern.h
```

**Slices:**

| Slice | Saros range | Eclipses | Times | Info | Saros |
|-------|-------------|----------|-------|------|-------|
| `all` | 1–180 | 13,148 | 102.7 KB | 128.4 KB | 30.6 KB |
| `modern` | 110–173 | 4,593 | 35.9 KB | 44.9 KB | 10.9 KB |

---

## Fetching data

```bash
pip install requests beautifulsoup4

# Fetch one series
python3 parse_saros.py 141

# Fetch all series 1–180 (skips already-downloaded)
./fetch_all.sh
```

Each series is written to `{number}/eclipses.jsonl` and `{number}/saros.json`.

---

## Building the binary database and C headers

```bash
python3 db/build_db.py
```

This reads all `{1..180}/eclipses.jsonl` files and writes:
- `db/eclipse_times.db`, `db/eclipse_info.db`, `db/saros.db`
- `db/eclipse_times_{all,modern}.h`
- `db/eclipse_info_{all,modern}.h`
- `db/saros_{all,modern}.h`

---

## C API — disk-based (desktop / server)

Compile with `eclipse_db.c`:

```c
#include "eclipse_db.h"
```

### Lifecycle

```c
// Open all three database files. Returns 0 on success.
// Loads eclipse_times.db into RAM (105 KB) for O(log n) binary search.
int eclipse_db_open(const char *times_path,
                    const char *info_path,
                    const char *saros_path);

void eclipse_db_close(void);
```

### Queries

```c
// Smallest eclipse timestamp >= ts. .found == 0 if none exists.
eclipse_ref_t find_next_eclipse(int64_t timestamp);

// Largest eclipse timestamp <= ts. .found == 0 if none exists.
eclipse_ref_t find_past_eclipse(int64_t timestamp);

// Read eclipse metadata by global index. O(1) seek.
eclipse_info_t get_eclipse_info(uint16_t index);

// Read timestamp for global index from the in-memory array. O(1).
int64_t get_eclipse_time(uint16_t index);

// Read all eclipse indices for a Saros series. O(1) seek.
saros_series_t get_saros_series(uint8_t saros_number);
```

### Return types

```c
typedef struct {
    int64_t  unix_time;   // unix timestamp of the eclipse
    uint16_t index;       // global eclipse index
    int      found;       // 0 = no result
} eclipse_ref_t;

typedef struct {
    int16_t  latitude_deg10;    // latitude  × 10  (e.g. 633 = 63.3°N)
    int16_t  longitude_deg10;   // longitude × 10  (e.g. -1376 = 137.6°W)
    uint16_t central_duration;  // seconds; 0xFFFF = not applicable
    uint8_t  saros_number;      // 1–180
    uint8_t  saros_pos;         // 0-based position within this series
    uint8_t  ecl_type;          // eclipse_type_t enum (see eclipse_db.h)
    uint8_t  sun_alt;           // sun altitude at greatest eclipse (0–90°)
} eclipse_info_t;

typedef struct {
    uint16_t indices[86];  // global eclipse indices
    uint8_t  count;        // number of eclipses in the series
} saros_series_t;
```

### Example

```c
if (eclipse_db_open("db/eclipse_times.db",
                    "db/eclipse_info.db",
                    "db/saros.db") != 0) { /* handle error */ }

// Next eclipse from now
eclipse_ref_t r = find_next_eclipse(time(NULL));
if (r.found) {
    eclipse_info_t info = get_eclipse_info(r.index);
    printf("Next eclipse: unix=%lld  type=%s  saros=%u\n",
           (long long)r.unix_time,
           ECLIPSE_TYPE_NAMES[info.ecl_type],
           info.saros_number);
}

// All eclipses in Saros 141
saros_series_t s = get_saros_series(141);
for (int i = 0; i < s.count; i++) {
    int64_t ts = get_eclipse_time(s.indices[i]);
}

eclipse_db_close();
```

### Build

```bash
make -C db test_db
db/test_db db/
```

---

## C API — PROGMEM headers (embedded / AVR / ESP32)

All data is baked into C headers as `static const uint8_t[]` arrays.
Include only the headers you need — each array is in its own file.

| Header | Contents | modern | all |
|--------|----------|--------|-----|
| `eclipse_times_*.h` | Sorted int64 timestamps | 35.9 KB | 102.7 KB |
| `eclipse_info_*.h` | Packed eclipse_info_t records | 44.9 KB | 128.4 KB |
| `saros_*.h` | Saros series index records | 10.9 KB | 30.6 KB |

### Usage on AVR / ESP32

```c
#define ECLIPSE_USE_PROGMEM          // activates PROGMEM placement + pgm_read_*
#include "eclipse_times_modern.h"
#include "eclipse_info_modern.h"
#include "saros_modern.h"            // optional — only if you need series lookup
#include "eclipse_db_progmem.h"
```

### Usage on hosted (Linux / macOS, for testing)

```c
// No #define — data lives in RAM, same API
#include "eclipse_times_modern.h"
#include "eclipse_info_modern.h"
#include "eclipse_db_progmem.h"
```

### Queries

All functions are `static inline` and take the array pointer + count explicitly, so they work with any slice.

```c
// Next eclipse >= timestamp
pgm_eclipse_ref_t pgm_find_next_eclipse(
    const uint8_t *times_base, uint16_t count, int64_t timestamp);

// Last eclipse <= timestamp
pgm_eclipse_ref_t pgm_find_past_eclipse(
    const uint8_t *times_base, uint16_t count, int64_t timestamp);

// Read timestamp by local index. O(1).
int64_t pgm_get_eclipse_time(const uint8_t *times_base, uint16_t index);

// Read eclipse_info_t by local index. O(1).
pgm_eclipse_info_t pgm_get_eclipse_info(const uint8_t *info_base, uint16_t index);

// Read all indices for a saros series.
pgm_saros_series_t pgm_get_saros_series(
    const uint8_t *saros_base, uint8_t saros_range_start, uint8_t saros_number);
```

### Example (modern slice, times + info only)

```c
#define ECLIPSE_USE_PROGMEM
#include "eclipse_times_modern.h"
#include "eclipse_info_modern.h"
#include "eclipse_db_progmem.h"

// Find next eclipse after a unix timestamp
pgm_eclipse_ref_t r = pgm_find_next_eclipse(
    eclipse_times_modern, ECLIPSE_MODERN_COUNT, now_unix);

if (r.found) {
    pgm_eclipse_info_t info = pgm_get_eclipse_info(eclipse_info_modern, r.index);
    // info.saros_number, info.ecl_type, info.central_duration, etc.
}
```

### Example (saros series lookup, modern slice)

```c
#include "eclipse_times_modern.h"
#include "saros_modern.h"
#include "eclipse_db_progmem.h"

pgm_saros_series_t s = pgm_get_saros_series(
    saros_modern, ECLIPSE_MODERN_SAROS_FIRST, 141);

for (int i = 0; i < s.count; i++) {
    int64_t ts = pgm_get_eclipse_time(eclipse_times_modern, s.indices[i]);
}
```

### Build (hosted test)

```bash
make -C db test_progmem
db/test_progmem
```

---

## Eclipse type enum

| Value | Name | Description |
|-------|------|-------------|
| 0 | `A` | Annular |
| 1 | `A+` | Annular (long) |
| 2 | `Am` | Annular (short) |
| 3 | `An` | Annular (non-central) |
| 4 | `As` | Annular (saros) |
| 5 | `H` | Hybrid (annular-total) |
| 6 | `H2` | Hybrid |
| 7 | `H3` | Hybrid |
| 8 | `Hm` | Hybrid (short) |
| 9 | `P` | Partial |
| 10 | `Pb` | Partial (beginning of saros) |
| 11 | `Pe` | Partial (end of saros) |
| 12 | `T` | Total |
| 13 | `T+` | Total (long) |
| 14 | `Tm` | Total (short) |
| 15 | `Tn` | Total (non-central) |
| 16 | `Ts` | Total (saros) |

---

## Data source

[NASA Eclipse Web Site — Saros Series](https://eclipse.gsfc.nasa.gov/SEsaros/SEsaros.html)
Fred Espenak, NASA/GSFC (retired)
