/**
 * Types for the saros-eclipse library.
 *
 * Enums match the C enums in saros.h. Interfaces expand the packed binary
 * records into convenient JavaScript objects.
 */
/**
 * Solar eclipse type codes. Numeric values match `solar_eclipse_type_t` in
 * saros.h / `SOLAR_ECL_TYPE_MAP` in build_db.py.
 *
 * Use {@link solarEclipseTypeLabel} to get the canonical NASA code string
 * (e.g. `"A+"`, `"T-"`).
 */
declare enum SolarEclipseType {
    /** Annular */
    A = 0,
    /** Annular (long) */
    Aplus = 1,
    /** Annular (sub-central) */
    Aminus = 2,
    /** Annular (short) */
    Am = 3,
    /** Annular (non-central) */
    An = 4,
    /** Annular (saros — first/last in series) */
    As = 5,
    /** Hybrid (annular-total) */
    H = 6,
    /** Hybrid variant 2 */
    H2 = 7,
    /** Hybrid variant 3 */
    H3 = 8,
    /** Hybrid (short) */
    Hm = 9,
    /** Partial */
    P = 10,
    /** Partial (beginning of series) */
    Pb = 11,
    /** Partial (end of series) */
    Pe = 12,
    /** Total */
    T = 13,
    /** Total (long, > ~5 min) */
    Tplus = 14,
    /** Total (sub-central) */
    Tminus = 15,
    /** Total (short, < ~1 min) */
    Tm = 16,
    /** Total (non-central) */
    Tn = 17,
    /** Total (saros — first/last in series) */
    Ts = 18
}
/**
 * Lunar eclipse type codes. Numeric values match `lunar_eclipse_type_t` in
 * saros.h / `LUNAR_ECL_TYPE_MAP` in build_db.py.
 */
declare enum LunarEclipseType {
    /** Penumbral */
    N = 0,
    /** Penumbral (beginning of series) */
    Nb = 1,
    /** Penumbral (end of series) */
    Ne = 2,
    /** Penumbral (non-central) */
    Nx = 3,
    /** Partial */
    P = 4,
    /** Partial (beginning of series) */
    Pb = 5,
    /** Partial (end of series) */
    Pe = 6,
    /** Total */
    T = 7,
    /** Total (long, > ~100 min) */
    Tplus = 8,
    /** Total (sub-central) */
    Tminus = 9,
    /** Total (short, < ~20 min) */
    Tm = 10,
    /** Total (non-central) */
    Tn = 11,
    /** Total (saros — first/last in series) */
    Ts = 12
}
/** Returns the canonical NASA code string for a solar eclipse type (e.g. `"A+"`, `"T-"`, `"T"`). */
declare function solarEclipseTypeLabel(type: SolarEclipseType): string;
/** Returns the canonical NASA code string for a lunar eclipse type (e.g. `"T+"`, `"T-"`, `"N"`). */
declare function lunarEclipseTypeLabel(type: LunarEclipseType): string;
/**
 * A decoded solar eclipse record.
 *
 * `unixTime` is the primary time field (seconds since Unix epoch, always
 * available). `date` is the same moment as a `Date` object; all eclipses in
 * this dataset (≈2872 BCE – 4017 CE) are within JavaScript's `Date` range.
 */
interface SolarEclipse {
    /** Unix timestamp in seconds (may be negative for ancient eclipses). */
    unixTime: number;
    /** Greatest-eclipse moment as a `Date`. */
    date: Date;
    /** Flat index in the binary database arrays. */
    globalIndex: number;
    /** Saros series number (1–180). */
    sarosNumber: number;
    /** 0-based position within the Saros series. */
    sarosPos: number;
    /** Eclipse type. */
    type: SolarEclipseType;
    /** Geographic latitude of greatest eclipse in degrees (+ = N). */
    latitude: number;
    /** Geographic longitude of greatest eclipse in degrees (+ = E). */
    longitude: number;
    /**
     * Central-path duration in seconds, or `null` for non-central / partial
     * eclipses where the value is not applicable.
     */
    centralDuration: number | null;
    /** Sun altitude above the horizon at greatest eclipse, in degrees. */
    sunAltitude: number;
}
/**
 * A decoded lunar eclipse record.
 *
 * `unixTime` is the primary time field. `date` is always populated for all
 * eclipses in this dataset.
 */
interface LunarEclipse {
    /** Unix timestamp in seconds (may be negative for ancient eclipses). */
    unixTime: number;
    /** Greatest-eclipse moment as a `Date`. */
    date: Date;
    /** Flat index in the binary database arrays. */
    globalIndex: number;
    /** Saros series number (1–180). */
    sarosNumber: number;
    /** 0-based position within the Saros series. */
    sarosPos: number;
    /** Eclipse type. */
    type: LunarEclipseType;
    /** Penumbral phase duration in seconds, or `null` if not applicable. */
    penumbralDuration: number | null;
    /** Partial phase duration in seconds, or `null` if not applicable. */
    partialDuration: number | null;
    /** Total phase duration in seconds, or `null` if not applicable. */
    totalDuration: number | null;
}
/**
 * Returned by `findNext*`, `findPast*`, and `findClosest*`.
 *
 * - `eclipse` — the matched eclipse, or `null` when the timestamp is outside
 *   the dataset range.
 * - `sarosPrev` — previous eclipse in the same Saros series (`null` if none).
 * - `sarosNext` — next eclipse in the same Saros series (`null` if none).
 */
interface EclipseResult<T> {
    eclipse: T | null;
    sarosPrev: T | null;
    sarosNext: T | null;
}
/**
 * Returned by `findSolarSarosWindow` and `findLunarSarosWindow`.
 *
 * - `sarosNumber` — the queried Saros series.
 * - `past` — most recent eclipse in the series *before* the query time.
 * - `future` — next eclipse in the series *at or after* the query time.
 */
interface SarosWindow<T> {
    sarosNumber: number;
    past: T | null;
    future: T | null;
}

/**
 * saros-eclipse — Solar and lunar eclipse lookup from NASA's Saros catalog.
 *
 * Covers all 180 solar and 180 lunar Saros series (~25 000 eclipses total,
 * spanning several millennia). Data is read from pre-built binary files
 * bundled with this package; no network access or native compilation needed.
 *
 * @example
 * ```ts
 * import {
 *   findNextSolarEclipse,
 *   findSolarSarosWindow,
 *   findClosestLunarEclipse,
 *   SolarEclipseType,
 *   solarEclipseTypeLabel,
 * } from 'saros-eclipse';
 *
 * const result = findNextSolarEclipse(new Date());
 * if (result.eclipse) {
 *   const e = result.eclipse;
 *   console.log(`Next solar: ${e.date.toISOString()}`);
 *   console.log(`  type=${solarEclipseTypeLabel(e.type)} saros=${e.sarosNumber}[${e.sarosPos}]`);
 *   console.log(`  lat=${e.latitude.toFixed(1)} lon=${e.longitude.toFixed(1)}`);
 *   if (e.centralDuration !== null) console.log(`  duration=${e.centralDuration}s`);
 * }
 *
 * const window = findSolarSarosWindow(new Date(), 145);
 * if (window.past)   console.log(`Saros 145 was last: ${window.past.date.toISOString()}`);
 * if (window.future) console.log(`Saros 145 next:     ${window.future.date.toISOString()}`);
 * ```
 *
 * @packageDocumentation
 */

/** A value accepted as a timestamp by all public functions. */
type Timestamp = number | Date;
/**
 * Returns the nearest solar eclipse at or after `ts`, plus its Saros-series
 * neighbours (`sarosPrev`, `sarosNext`).
 *
 * `result.eclipse` is `null` when `ts` is past the last eclipse in the dataset.
 */
declare function findNextSolarEclipse(ts: Timestamp): EclipseResult<SolarEclipse>;
/**
 * Returns the nearest solar eclipse at or before `ts`, plus its Saros-series
 * neighbours.
 *
 * `result.eclipse` is `null` when `ts` is before the first eclipse in the dataset.
 */
declare function findPastSolarEclipse(ts: Timestamp): EclipseResult<SolarEclipse>;
/**
 * Returns the solar eclipse closest in time to `ts`.
 * When the next and past eclipses are equidistant, the future eclipse is
 * returned (matches the C inline helper in `saros.h`).
 */
declare function findClosestSolarEclipse(ts: Timestamp): EclipseResult<SolarEclipse>;
/**
 * Returns the most recent past eclipse and the next future eclipse within a
 * specific solar Saros series, relative to `ts`.
 *
 * @param ts - Reference timestamp.
 * @param sarosNumber - Saros series number (1–180).
 */
declare function findSolarSarosWindow(ts: Timestamp, sarosNumber: number): SarosWindow<SolarEclipse>;
/**
 * Returns the nearest lunar eclipse at or after `ts`, plus its Saros-series
 * neighbours.
 */
declare function findNextLunarEclipse(ts: Timestamp): EclipseResult<LunarEclipse>;
/**
 * Returns the nearest lunar eclipse at or before `ts`, plus its Saros-series
 * neighbours.
 */
declare function findPastLunarEclipse(ts: Timestamp): EclipseResult<LunarEclipse>;
/**
 * Returns the lunar eclipse closest in time to `ts`.
 * When equidistant, the future eclipse is returned.
 */
declare function findClosestLunarEclipse(ts: Timestamp): EclipseResult<LunarEclipse>;
/**
 * Returns the most recent past eclipse and the next future eclipse within a
 * specific lunar Saros series, relative to `ts`.
 *
 * @param ts - Reference timestamp.
 * @param sarosNumber - Saros series number (1–180).
 */
declare function findLunarSarosWindow(ts: Timestamp, sarosNumber: number): SarosWindow<LunarEclipse>;

export { type EclipseResult, type LunarEclipse, LunarEclipseType, type SarosWindow, type SolarEclipse, SolarEclipseType, type Timestamp, findClosestLunarEclipse, findClosestSolarEclipse, findLunarSarosWindow, findNextLunarEclipse, findNextSolarEclipse, findPastLunarEclipse, findPastSolarEclipse, findSolarSarosWindow, lunarEclipseTypeLabel, solarEclipseTypeLabel };
