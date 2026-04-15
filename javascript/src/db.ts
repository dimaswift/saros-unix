/**
 * Binary database reader for the saros-eclipse library.
 *
 * Reads the three .db files bundled in data/{solar,lunar}/ and exposes
 * findNext / findPast / sarosWindow queries backed by binary search.
 *
 * Binary layout (little-endian, matches saros.h / build_db.py):
 *   eclipse_times.db  — int64 per eclipse, 8 bytes, sorted ascending
 *   eclipse_info.db   — 10 bytes per eclipse
 *       solar: int16 lat10, int16 lon10, uint16 dur, uint8×4
 *       lunar: uint16×3 durations, uint8×4
 *   saros.db          — 194 bytes per series (Saros 1–180)
 *       uint8 count, uint8 pad, uint16[96] globalIndices
 */

import * as fs from "fs";
import * as path from "path";
import {
  EclipseResult,
  LunarEclipse,
  LunarEclipseType,
  SarosWindow,
  SolarEclipse,
  SolarEclipseType,
} from "./types.js";

// ── Layout constants (must match build_db.py / saros.h) ──────────────────────

const TIMES_SIZE    = 8;   // int64_t per eclipse
const INFO_SIZE     = 10;  // 10-byte packed record
const SAROS_SIZE    = 194; // uint8 count + uint8 pad + uint16[96]
const MAX_PER_SAROS = 96;
const NA_DURATION   = 0xffff; // sentinel for "not applicable"
const SOLAR_TYPE_COUNT = 19;
const LUNAR_TYPE_COUNT = 13;

type AnyEclipse = SolarEclipse | LunarEclipse;

// ── Timestamp helpers ─────────────────────────────────────────────────────────

/**
 * Read a little-endian int64 from a Buffer at offset.
 * Safe for values within Number.MAX_SAFE_INTEGER range (all Saros timestamps
 * span ≈ –1.5×10¹¹ to +9.5×10¹⁰ seconds, well within 2^53).
 */
function readInt64LE(buf: Buffer, offset: number): number {
  const lo = buf.readUInt32LE(offset);
  const hi = buf.readInt32LE(offset + 4);
  return hi * 4294967296 + lo;
}

/** Convert unix timestamp (seconds) to a Date. */
function toDate(unixTime: number): Date {
  return new Date(unixTime * 1000);
}

// ── Input normalisation ───────────────────────────────────────────────────────

/**
 * Normalise a timestamp input to a unix integer (seconds since epoch).
 * Accepts: `number` (unix seconds), `Date`, or an object with `.getTime()`
 * (ms since epoch).
 */
export function toUnix(ts: number | Date): number {
  if (ts instanceof Date) return Math.trunc(ts.getTime() / 1000);
  return Math.trunc(ts);
}

// ── Database reader ───────────────────────────────────────────────────────────

class EclipseDB {
  private readonly times: Buffer;
  private readonly info: Buffer;
  private readonly saros: Buffer;
  private readonly count: number;

  constructor(private readonly kind: "solar" | "lunar") {
    // __dirname is the compiled dist/ directory; data/ is at ../data/ relative to it.
    // tsup --shims injects __dirname into ESM output so this works for both formats.
    const dataDir = path.join(__dirname, "..", "data", kind);
    this.times = fs.readFileSync(path.join(dataDir, "eclipse_times.db"));
    this.info  = fs.readFileSync(path.join(dataDir, "eclipse_info.db"));
    this.saros = fs.readFileSync(path.join(dataDir, "saros.db"));
    this.count = this.times.length / TIMES_SIZE;
  }

  // ── Low-level accessors ──────────────────────────────────────────────────

  private readTime(idx: number): number {
    return readInt64LE(this.times, idx * TIMES_SIZE);
  }

  private makeSolarEntry(idx: number): SolarEclipse {
    const off = idx * INFO_SIZE;
    const lat10 = this.info.readInt16LE(off);
    const lon10 = this.info.readInt16LE(off + 2);
    const dur   = this.info.readUInt16LE(off + 4);
    const sarosNumber = this.info[off + 6];
    const sarosPos    = this.info[off + 7];
    const eclType     = this.info[off + 8];
    const sunAlt      = this.info[off + 9];
    const unixTime    = this.readTime(idx);
    return {
      unixTime,
      date: toDate(unixTime),
      globalIndex: idx,
      sarosNumber,
      sarosPos,
      type: eclType < SOLAR_TYPE_COUNT
        ? (eclType as SolarEclipseType)
        : SolarEclipseType.P,
      latitude:  lat10 / 10,
      longitude: lon10 / 10,
      centralDuration: dur === NA_DURATION ? null : dur,
      sunAltitude: sunAlt,
    };
  }

  private makeLunarEntry(idx: number): LunarEclipse {
    const off = idx * INFO_SIZE;
    const pen = this.info.readUInt16LE(off);
    const par = this.info.readUInt16LE(off + 2);
    const tot = this.info.readUInt16LE(off + 4);
    const sarosNumber = this.info[off + 6];
    const sarosPos    = this.info[off + 7];
    const eclType     = this.info[off + 8];
    const unixTime    = this.readTime(idx);
    return {
      unixTime,
      date: toDate(unixTime),
      globalIndex: idx,
      sarosNumber,
      sarosPos,
      type: eclType < LUNAR_TYPE_COUNT
        ? (eclType as LunarEclipseType)
        : LunarEclipseType.P,
      penumbralDuration: pen === NA_DURATION ? null : pen,
      partialDuration:   par === NA_DURATION ? null : par,
      totalDuration:     tot === NA_DURATION ? null : tot,
    };
  }

  private makeEntry(idx: number): AnyEclipse {
    return this.kind === "solar"
      ? this.makeSolarEntry(idx)
      : this.makeLunarEntry(idx);
  }

  // ── Saros index ──────────────────────────────────────────────────────────

  private loadSarosSeries(sarosNumber: number): { count: number; indices: number[] } {
    if (sarosNumber < 1 || sarosNumber > 180) return { count: 0, indices: [] };
    const offset = (sarosNumber - 1) * SAROS_SIZE;
    const count  = this.saros[offset];
    const indices: number[] = [];
    for (let i = 0; i < count; i++) {
      indices.push(this.saros.readUInt16LE(offset + 2 + i * 2));
    }
    return { count, indices };
  }

  private sarosNeighbours(
    sarosNumber: number,
    sarosPos: number,
  ): { prev: AnyEclipse | null; next: AnyEclipse | null } {
    const { count, indices } = this.loadSarosSeries(sarosNumber);
    if (count === 0) return { prev: null, next: null };
    const prev = sarosPos > 0
      ? this.makeEntry(indices[sarosPos - 1])
      : null;
    const next = sarosPos + 1 < count
      ? this.makeEntry(indices[sarosPos + 1])
      : null;
    return { prev, next };
  }

  // ── Binary search ────────────────────────────────────────────────────────

  /** First index with time >= key; equals count if all times < key. */
  private lowerBound(key: number): number {
    let lo = 0, hi = this.count;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (this.readTime(mid) < key) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }

  /** First index with time > key; element at result-1 is last <= key. */
  private upperBound(key: number): number {
    let lo = 0, hi = this.count;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (this.readTime(mid) <= key) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }

  // ── Public query methods ─────────────────────────────────────────────────

  findNext(ts: number): EclipseResult<AnyEclipse> {
    const idx = this.lowerBound(ts);
    if (idx >= this.count) {
      return { eclipse: null, sarosPrev: null, sarosNext: null };
    }
    const entry = this.makeEntry(idx);
    const { prev, next } = this.sarosNeighbours(
      (entry as SolarEclipse).sarosNumber,
      (entry as SolarEclipse).sarosPos,
    );
    return { eclipse: entry, sarosPrev: prev, sarosNext: next };
  }

  findPast(ts: number): EclipseResult<AnyEclipse> {
    const idx = this.upperBound(ts);
    if (idx === 0) {
      return { eclipse: null, sarosPrev: null, sarosNext: null };
    }
    const entry = this.makeEntry(idx - 1);
    const { prev, next } = this.sarosNeighbours(
      (entry as SolarEclipse).sarosNumber,
      (entry as SolarEclipse).sarosPos,
    );
    return { eclipse: entry, sarosPrev: prev, sarosNext: next };
  }

  sarosWindow(ts: number, sarosNumber: number): SarosWindow<AnyEclipse> {
    const { count, indices } = this.loadSarosSeries(sarosNumber);
    if (count === 0) return { sarosNumber, past: null, future: null };

    // Binary search within the series-local index list.
    let lo = 0, hi = count;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (this.readTime(indices[mid]) < ts) lo = mid + 1;
      else hi = mid;
    }
    // lo = first position in indices[] with time >= ts

    const past   = lo > 0    ? this.makeEntry(indices[lo - 1]) : null;
    const future = lo < count ? this.makeEntry(indices[lo])     : null;
    return { sarosNumber, past, future };
  }
}

// ── Lazy singletons ───────────────────────────────────────────────────────────

let _solarDB: EclipseDB | undefined;
let _lunarDB: EclipseDB | undefined;

export function solarDB(): EclipseDB { return (_solarDB ??= new EclipseDB("solar")); }
export function lunarDB(): EclipseDB { return (_lunarDB ??= new EclipseDB("lunar")); }
