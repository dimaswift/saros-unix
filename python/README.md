# saros-eclipse

Solar and lunar eclipse lookup from NASA's full Saros catalog.

Covers all 180 solar and 180 lunar Saros series — **13 206 solar** and
**12 223 lunar** eclipses spanning several millennia.  Data is read from
pre-built binary files bundled with the package; no network access or C
compilation is required.

## Installation

```bash
pip install saros-eclipse
```

Requires Python ≥ 3.11.

## Quick start

```python
from datetime import datetime, timezone
import saros

now = datetime.now(timezone.utc)

# Next solar eclipse, plus its Saros-series neighbours
result = saros.find_next_solar_eclipse(now)
if result.eclipse:
    e = result.eclipse
    print(f"Next solar: {e.time:%Y-%m-%d %H:%M} UTC")
    print(f"  type={e.type}  saros={e.saros_number}[{e.saros_pos}]")
    print(f"  lat={e.latitude:.1f}°  lon={e.longitude:.1f}°")
    if e.central_duration is not None:
        print(f"  central duration={e.central_duration}s")
    if result.saros_next:
        print(f"  next in series:  {result.saros_next.time:%Y-%m-%d}")

# Saros 145 window (the series that produced the Aug 2017 eclipse)
window = saros.find_solar_saros_window(now, 145)
if window.past:
    print(f"Saros 145 was last: {window.past.time:%Y-%m-%d}")
if window.future:
    print(f"Saros 145 next:     {window.future.time:%Y-%m-%d}")

# Nearest lunar eclipse
lunar = saros.find_closest_lunar_eclipse(now)
if lunar.eclipse:
    e = lunar.eclipse
    print(f"Closest lunar: {e.time:%Y-%m-%d}  type={e.type}  "
          f"saros={e.saros_number}")
    if e.total_duration is not None:
        print(f"  totality={e.total_duration}s ({e.total_duration//60} min)")
```

## API

All functions accept a timestamp as a `datetime` (aware or naive-UTC), or an
`int`/`float` Unix timestamp.

### Solar

```python
saros.find_next_solar_eclipse(ts)     -> EclipseResult[SolarEclipse]
saros.find_past_solar_eclipse(ts)     -> EclipseResult[SolarEclipse]
saros.find_closest_solar_eclipse(ts)  -> EclipseResult[SolarEclipse]
saros.find_solar_saros_window(ts, saros_number: int) -> SarosWindow[SolarEclipse]
```

### Lunar

```python
saros.find_next_lunar_eclipse(ts)     -> EclipseResult[LunarEclipse]
saros.find_past_lunar_eclipse(ts)     -> EclipseResult[LunarEclipse]
saros.find_closest_lunar_eclipse(ts)  -> EclipseResult[LunarEclipse]
saros.find_lunar_saros_window(ts, saros_number: int) -> SarosWindow[LunarEclipse]
```

### Return types

**`EclipseResult[T]`**

| Field | Type | Description |
|---|---|---|
| `eclipse` | `T \| None` | The matched eclipse, `None` if out of dataset range |
| `saros_prev` | `T \| None` | Previous eclipse in the same Saros series |
| `saros_next` | `T \| None` | Next eclipse in the same Saros series |

**`SarosWindow[T]`**

| Field | Type | Description |
|---|---|---|
| `saros_number` | `int` | The queried Saros series |
| `past` | `T \| None` | Most recent eclipse in the series before `ts` |
| `future` | `T \| None` | Next eclipse in the series at or after `ts` |

**`SolarEclipse`**

| Field | Type | Description |
|---|---|---|
| `time` | `datetime` | Greatest-eclipse moment (UTC) |
| `global_index` | `int` | Flat index in the dataset |
| `saros_number` | `int` | Saros series (1–180) |
| `saros_pos` | `int` | 0-based position within the series |
| `type` | `SolarEclipseType` | Eclipse type |
| `latitude` | `float` | Geographic latitude of greatest eclipse (°N) |
| `longitude` | `float` | Geographic longitude of greatest eclipse (°E) |
| `central_duration` | `int \| None` | Central-path duration in seconds; `None` if n/a |
| `sun_altitude` | `int` | Sun altitude above horizon at greatest eclipse (°) |

**`LunarEclipse`**

| Field | Type | Description |
|---|---|---|
| `time` | `datetime` | Greatest-eclipse moment (UTC) |
| `global_index` | `int` | Flat index in the dataset |
| `saros_number` | `int` | Saros series (1–180) |
| `saros_pos` | `int` | 0-based position within the series |
| `type` | `LunarEclipseType` | Eclipse type |
| `penumbral_duration` | `int \| None` | Penumbral phase duration in seconds |
| `partial_duration` | `int \| None` | Partial phase duration in seconds |
| `total_duration` | `int \| None` | Total phase duration in seconds |

### Eclipse types

**Solar** (`SolarEclipseType`): `A`, `Aplus` (`A+`), `Aminus` (`A-`), `Am`, `An`, `As`,
`H`, `H2`, `H3`, `Hm`, `P`, `Pb`, `Pe`, `T`, `Tplus` (`T+`), `Tminus` (`T-`), `Tm`, `Tn`, `Ts`

**Lunar** (`LunarEclipseType`): `N`, `Nb`, `Ne`, `Nx`, `P`, `Pb`, `Pe`,
`T`, `Tplus` (`T+`), `Tminus` (`T-`), `Tm`, `Tn`, `Ts`

`str(eclipse_type)` returns the canonical NASA code (e.g. `"T+"`, `"A-"`).

## Data source

Fred Espenak, NASA/GSFC (retired) —
[Solar Saros Series](https://eclipse.gsfc.nasa.gov/SEsaros/SEsaros.html) /
[Lunar Saros Series](https://eclipse.gsfc.nasa.gov/LEsaros/LEsaros.html)

## License

MIT
