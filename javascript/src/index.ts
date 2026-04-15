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

export type {
  SolarEclipse,
  LunarEclipse,
  EclipseResult,
  SarosWindow,
} from "./types.js";

export {
  SolarEclipseType,
  LunarEclipseType,
  solarEclipseTypeLabel,
  lunarEclipseTypeLabel,
} from "./types.js";

import { lunarDB, solarDB, toUnix } from "./db.js";
import type {
  EclipseResult,
  LunarEclipse,
  SarosWindow,
  SolarEclipse,
} from "./types.js";

/** A value accepted as a timestamp by all public functions. */
export type Timestamp = number | Date;

// ── Solar ─────────────────────────────────────────────────────────────────────

/**
 * Returns the nearest solar eclipse at or after `ts`, plus its Saros-series
 * neighbours (`sarosPrev`, `sarosNext`).
 *
 * `result.eclipse` is `null` when `ts` is past the last eclipse in the dataset.
 */
export function findNextSolarEclipse(ts: Timestamp): EclipseResult<SolarEclipse> {
  return solarDB().findNext(toUnix(ts)) as EclipseResult<SolarEclipse>;
}

/**
 * Returns the nearest solar eclipse at or before `ts`, plus its Saros-series
 * neighbours.
 *
 * `result.eclipse` is `null` when `ts` is before the first eclipse in the dataset.
 */
export function findPastSolarEclipse(ts: Timestamp): EclipseResult<SolarEclipse> {
  return solarDB().findPast(toUnix(ts)) as EclipseResult<SolarEclipse>;
}

/**
 * Returns the solar eclipse closest in time to `ts`.
 * When the next and past eclipses are equidistant, the future eclipse is
 * returned (matches the C inline helper in `saros.h`).
 */
export function findClosestSolarEclipse(ts: Timestamp): EclipseResult<SolarEclipse> {
  const unix = toUnix(ts);
  const nxt  = solarDB().findNext(unix) as EclipseResult<SolarEclipse>;
  const pst  = solarDB().findPast(unix) as EclipseResult<SolarEclipse>;
  if (!nxt.eclipse) return pst;
  if (!pst.eclipse) return nxt;
  const dNxt = nxt.eclipse.unixTime - unix;
  const dPst = unix - pst.eclipse.unixTime;
  return dPst < dNxt ? pst : nxt;
}

/**
 * Returns the most recent past eclipse and the next future eclipse within a
 * specific solar Saros series, relative to `ts`.
 *
 * @param ts - Reference timestamp.
 * @param sarosNumber - Saros series number (1–180).
 */
export function findSolarSarosWindow(
  ts: Timestamp,
  sarosNumber: number,
): SarosWindow<SolarEclipse> {
  return solarDB().sarosWindow(toUnix(ts), sarosNumber) as SarosWindow<SolarEclipse>;
}

// ── Lunar ─────────────────────────────────────────────────────────────────────

/**
 * Returns the nearest lunar eclipse at or after `ts`, plus its Saros-series
 * neighbours.
 */
export function findNextLunarEclipse(ts: Timestamp): EclipseResult<LunarEclipse> {
  return lunarDB().findNext(toUnix(ts)) as EclipseResult<LunarEclipse>;
}

/**
 * Returns the nearest lunar eclipse at or before `ts`, plus its Saros-series
 * neighbours.
 */
export function findPastLunarEclipse(ts: Timestamp): EclipseResult<LunarEclipse> {
  return lunarDB().findPast(toUnix(ts)) as EclipseResult<LunarEclipse>;
}

/**
 * Returns the lunar eclipse closest in time to `ts`.
 * When equidistant, the future eclipse is returned.
 */
export function findClosestLunarEclipse(ts: Timestamp): EclipseResult<LunarEclipse> {
  const unix = toUnix(ts);
  const nxt  = lunarDB().findNext(unix) as EclipseResult<LunarEclipse>;
  const pst  = lunarDB().findPast(unix) as EclipseResult<LunarEclipse>;
  if (!nxt.eclipse) return pst;
  if (!pst.eclipse) return nxt;
  const dNxt = nxt.eclipse.unixTime - unix;
  const dPst = unix - pst.eclipse.unixTime;
  return dPst < dNxt ? pst : nxt;
}

/**
 * Returns the most recent past eclipse and the next future eclipse within a
 * specific lunar Saros series, relative to `ts`.
 *
 * @param ts - Reference timestamp.
 * @param sarosNumber - Saros series number (1–180).
 */
export function findLunarSarosWindow(
  ts: Timestamp,
  sarosNumber: number,
): SarosWindow<LunarEclipse> {
  return lunarDB().sarosWindow(toUnix(ts), sarosNumber) as SarosWindow<LunarEclipse>;
}
