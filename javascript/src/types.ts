/**
 * Types for the saros-eclipse library.
 *
 * Enums match the C enums in saros.h. Interfaces expand the packed binary
 * records into convenient JavaScript objects.
 */

// ── Eclipse type enums ────────────────────────────────────────────────────────

/**
 * Solar eclipse type codes. Numeric values match `solar_eclipse_type_t` in
 * saros.h / `SOLAR_ECL_TYPE_MAP` in build_db.py.
 *
 * Use {@link solarEclipseTypeLabel} to get the canonical NASA code string
 * (e.g. `"A+"`, `"T-"`).
 */
export enum SolarEclipseType {
  /** Annular */
  A      = 0,
  /** Annular (long) */
  Aplus  = 1,
  /** Annular (sub-central) */
  Aminus = 2,
  /** Annular (short) */
  Am     = 3,
  /** Annular (non-central) */
  An     = 4,
  /** Annular (saros — first/last in series) */
  As     = 5,
  /** Hybrid (annular-total) */
  H      = 6,
  /** Hybrid variant 2 */
  H2     = 7,
  /** Hybrid variant 3 */
  H3     = 8,
  /** Hybrid (short) */
  Hm     = 9,
  /** Partial */
  P      = 10,
  /** Partial (beginning of series) */
  Pb     = 11,
  /** Partial (end of series) */
  Pe     = 12,
  /** Total */
  T      = 13,
  /** Total (long, > ~5 min) */
  Tplus  = 14,
  /** Total (sub-central) */
  Tminus = 15,
  /** Total (short, < ~1 min) */
  Tm     = 16,
  /** Total (non-central) */
  Tn     = 17,
  /** Total (saros — first/last in series) */
  Ts     = 18,
}

/**
 * Lunar eclipse type codes. Numeric values match `lunar_eclipse_type_t` in
 * saros.h / `LUNAR_ECL_TYPE_MAP` in build_db.py.
 */
export enum LunarEclipseType {
  /** Penumbral */
  N      = 0,
  /** Penumbral (beginning of series) */
  Nb     = 1,
  /** Penumbral (end of series) */
  Ne     = 2,
  /** Penumbral (non-central) */
  Nx     = 3,
  /** Partial */
  P      = 4,
  /** Partial (beginning of series) */
  Pb     = 5,
  /** Partial (end of series) */
  Pe     = 6,
  /** Total */
  T      = 7,
  /** Total (long, > ~100 min) */
  Tplus  = 8,
  /** Total (sub-central) */
  Tminus = 9,
  /** Total (short, < ~20 min) */
  Tm     = 10,
  /** Total (non-central) */
  Tn     = 11,
  /** Total (saros — first/last in series) */
  Ts     = 12,
}

const _SOLAR_LABELS: Partial<Record<SolarEclipseType, string>> = {
  [SolarEclipseType.Aplus]:  "A+",
  [SolarEclipseType.Aminus]: "A-",
  [SolarEclipseType.Tplus]:  "T+",
  [SolarEclipseType.Tminus]: "T-",
};

const _LUNAR_LABELS: Partial<Record<LunarEclipseType, string>> = {
  [LunarEclipseType.Tplus]:  "T+",
  [LunarEclipseType.Tminus]: "T-",
};

/** Returns the canonical NASA code string for a solar eclipse type (e.g. `"A+"`, `"T-"`, `"T"`). */
export function solarEclipseTypeLabel(type: SolarEclipseType): string {
  return _SOLAR_LABELS[type] ?? SolarEclipseType[type] ?? String(type);
}

/** Returns the canonical NASA code string for a lunar eclipse type (e.g. `"T+"`, `"T-"`, `"N"`). */
export function lunarEclipseTypeLabel(type: LunarEclipseType): string {
  return _LUNAR_LABELS[type] ?? LunarEclipseType[type] ?? String(type);
}

// ── Eclipse data objects ──────────────────────────────────────────────────────

/**
 * A decoded solar eclipse record.
 *
 * `unixTime` is the primary time field (seconds since Unix epoch, always
 * available). `date` is the same moment as a `Date` object; all eclipses in
 * this dataset (≈2872 BCE – 4017 CE) are within JavaScript's `Date` range.
 */
export interface SolarEclipse {
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
export interface LunarEclipse {
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

// ── Result containers ─────────────────────────────────────────────────────────

/**
 * Returned by `findNext*`, `findPast*`, and `findClosest*`.
 *
 * - `eclipse` — the matched eclipse, or `null` when the timestamp is outside
 *   the dataset range.
 * - `sarosPrev` — previous eclipse in the same Saros series (`null` if none).
 * - `sarosNext` — next eclipse in the same Saros series (`null` if none).
 */
export interface EclipseResult<T> {
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
export interface SarosWindow<T> {
  sarosNumber: number;
  past: T | null;
  future: T | null;
}
