# saros-eclipse

Solar and lunar eclipse lookup from NASA's full Saros catalog.

Covers all 180 solar and 180 lunar Saros series — **13 206 solar** and
**12 223 lunar** eclipses spanning several millennia (~2872 BCE – 4017 CE).
Data is read from pre-built binary files bundled with the package; no network
access or native compilation needed.

## Installation

```bash
npm install saros-eclipse
```

Requires Node.js ≥ 18.

## Quick start

```ts
import {
  findNextSolarEclipse,
  findSolarSarosWindow,
  findClosestLunarEclipse,
  SolarEclipseType,
  solarEclipseTypeLabel,
} from 'saros-eclipse';

const result = findNextSolarEclipse(new Date());
if (result.eclipse) {
  const e = result.eclipse;
  console.log(`Next solar: ${e.date.toISOString()}`);
  console.log(`  type=${solarEclipseTypeLabel(e.type)}  saros=${e.sarosNumber}[${e.sarosPos}]`);
  console.log(`  lat=${e.latitude.toFixed(1)}°  lon=${e.longitude.toFixed(1)}°`);
  if (e.centralDuration !== null)
    console.log(`  central duration=${e.centralDuration}s`);
  if (result.sarosNext)
    console.log(`  next in series: ${result.sarosNext.date.toISOString().slice(0, 10)}`);
}

// Saros 145 window (the series that produced the Aug 2017 eclipse)
const window = findSolarSarosWindow(new Date(), 145);
if (window.past)   console.log(`Saros 145 was last: ${window.past.date.toISOString().slice(0,10)}`);
if (window.future) console.log(`Saros 145 next:     ${window.future.date.toISOString().slice(0,10)}`);

// Nearest lunar eclipse
const lunar = findClosestLunarEclipse(new Date());
if (lunar.eclipse) {
  const e = lunar.eclipse;
  console.log(`Closest lunar: ${e.date.toISOString().slice(0,10)}  type=${e.type}  saros=${e.sarosNumber}`);
  if (e.totalDuration !== null)
    console.log(`  totality=${e.totalDuration}s (${Math.round(e.totalDuration/60)} min)`);
}
```

## API

All functions accept a `Timestamp` — either a `Date` or a `number` (unix
seconds since epoch, may be fractional).

### Solar

```ts
findNextSolarEclipse(ts: Timestamp)                    => EclipseResult<SolarEclipse>
findPastSolarEclipse(ts: Timestamp)                    => EclipseResult<SolarEclipse>
findClosestSolarEclipse(ts: Timestamp)                 => EclipseResult<SolarEclipse>
findSolarSarosWindow(ts: Timestamp, sarosNumber: number) => SarosWindow<SolarEclipse>
```

### Lunar

```ts
findNextLunarEclipse(ts: Timestamp)                    => EclipseResult<LunarEclipse>
findPastLunarEclipse(ts: Timestamp)                    => EclipseResult<LunarEclipse>
findClosestLunarEclipse(ts: Timestamp)                 => EclipseResult<LunarEclipse>
findLunarSarosWindow(ts: Timestamp, sarosNumber: number) => SarosWindow<LunarEclipse>
```

### Return types

**`EclipseResult<T>`**

| Field | Type | Description |
|---|---|---|
| `eclipse` | `T \| null` | Matched eclipse; `null` if timestamp is outside dataset |
| `sarosPrev` | `T \| null` | Previous eclipse in the same Saros series |
| `sarosNext` | `T \| null` | Next eclipse in the same Saros series |

**`SarosWindow<T>`**

| Field | Type | Description |
|---|---|---|
| `sarosNumber` | `number` | The queried Saros series |
| `past` | `T \| null` | Most recent eclipse in the series before `ts` |
| `future` | `T \| null` | Next eclipse in the series at or after `ts` |

**`SolarEclipse`**

| Field | Type | Description |
|---|---|---|
| `unixTime` | `number` | Unix timestamp in seconds (may be negative) |
| `date` | `Date` | Greatest-eclipse moment (always valid across this dataset) |
| `globalIndex` | `number` | Flat index in the dataset |
| `sarosNumber` | `number` | Saros series (1–180) |
| `sarosPos` | `number` | 0-based position within the series |
| `type` | `SolarEclipseType` | Eclipse type enum |
| `latitude` | `number` | Geographic latitude of greatest eclipse (°N) |
| `longitude` | `number` | Geographic longitude of greatest eclipse (°E) |
| `centralDuration` | `number \| null` | Central-path duration in seconds; `null` if n/a |
| `sunAltitude` | `number` | Sun altitude above horizon at greatest eclipse (°) |

**`LunarEclipse`**

| Field | Type | Description |
|---|---|---|
| `unixTime` | `number` | Unix timestamp in seconds (may be negative) |
| `date` | `Date` | Greatest-eclipse moment |
| `globalIndex` | `number` | Flat index in the dataset |
| `sarosNumber` | `number` | Saros series (1–180) |
| `sarosPos` | `number` | 0-based position within the series |
| `type` | `LunarEclipseType` | Eclipse type enum |
| `penumbralDuration` | `number \| null` | Penumbral phase duration in seconds |
| `partialDuration` | `number \| null` | Partial phase duration in seconds |
| `totalDuration` | `number \| null` | Total phase duration in seconds |

### Eclipse types

Use `solarEclipseTypeLabel(type)` / `lunarEclipseTypeLabel(type)` to get the
canonical NASA code string (e.g. `"A+"`, `"T-"`).

**`SolarEclipseType`**: `A`, `Aplus` (`A+`), `Aminus` (`A-`), `Am`, `An`, `As`,
`H`, `H2`, `H3`, `Hm`, `P`, `Pb`, `Pe`, `T`, `Tplus` (`T+`), `Tminus` (`T-`),
`Tm`, `Tn`, `Ts`

**`LunarEclipseType`**: `N`, `Nb`, `Ne`, `Nx`, `P`, `Pb`, `Pe`,
`T`, `Tplus` (`T+`), `Tminus` (`T-`), `Tm`, `Tn`, `Ts`

## Data source

Fred Espenak, NASA/GSFC (retired) —
[Solar Saros Series](https://eclipse.gsfc.nasa.gov/SEsaros/SEsaros.html) /
[Lunar Saros Series](https://eclipse.gsfc.nasa.gov/LEsaros/LEsaros.html)

## License

MIT
