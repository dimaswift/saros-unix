// node_modules/tsup/assets/esm_shims.js
import path from "path";
import { fileURLToPath } from "url";
var getFilename = () => fileURLToPath(import.meta.url);
var getDirname = () => path.dirname(getFilename());
var __dirname = /* @__PURE__ */ getDirname();

// src/types.ts
var SolarEclipseType = /* @__PURE__ */ ((SolarEclipseType2) => {
  SolarEclipseType2[SolarEclipseType2["A"] = 0] = "A";
  SolarEclipseType2[SolarEclipseType2["Aplus"] = 1] = "Aplus";
  SolarEclipseType2[SolarEclipseType2["Aminus"] = 2] = "Aminus";
  SolarEclipseType2[SolarEclipseType2["Am"] = 3] = "Am";
  SolarEclipseType2[SolarEclipseType2["An"] = 4] = "An";
  SolarEclipseType2[SolarEclipseType2["As"] = 5] = "As";
  SolarEclipseType2[SolarEclipseType2["H"] = 6] = "H";
  SolarEclipseType2[SolarEclipseType2["H2"] = 7] = "H2";
  SolarEclipseType2[SolarEclipseType2["H3"] = 8] = "H3";
  SolarEclipseType2[SolarEclipseType2["Hm"] = 9] = "Hm";
  SolarEclipseType2[SolarEclipseType2["P"] = 10] = "P";
  SolarEclipseType2[SolarEclipseType2["Pb"] = 11] = "Pb";
  SolarEclipseType2[SolarEclipseType2["Pe"] = 12] = "Pe";
  SolarEclipseType2[SolarEclipseType2["T"] = 13] = "T";
  SolarEclipseType2[SolarEclipseType2["Tplus"] = 14] = "Tplus";
  SolarEclipseType2[SolarEclipseType2["Tminus"] = 15] = "Tminus";
  SolarEclipseType2[SolarEclipseType2["Tm"] = 16] = "Tm";
  SolarEclipseType2[SolarEclipseType2["Tn"] = 17] = "Tn";
  SolarEclipseType2[SolarEclipseType2["Ts"] = 18] = "Ts";
  return SolarEclipseType2;
})(SolarEclipseType || {});
var LunarEclipseType = /* @__PURE__ */ ((LunarEclipseType2) => {
  LunarEclipseType2[LunarEclipseType2["N"] = 0] = "N";
  LunarEclipseType2[LunarEclipseType2["Nb"] = 1] = "Nb";
  LunarEclipseType2[LunarEclipseType2["Ne"] = 2] = "Ne";
  LunarEclipseType2[LunarEclipseType2["Nx"] = 3] = "Nx";
  LunarEclipseType2[LunarEclipseType2["P"] = 4] = "P";
  LunarEclipseType2[LunarEclipseType2["Pb"] = 5] = "Pb";
  LunarEclipseType2[LunarEclipseType2["Pe"] = 6] = "Pe";
  LunarEclipseType2[LunarEclipseType2["T"] = 7] = "T";
  LunarEclipseType2[LunarEclipseType2["Tplus"] = 8] = "Tplus";
  LunarEclipseType2[LunarEclipseType2["Tminus"] = 9] = "Tminus";
  LunarEclipseType2[LunarEclipseType2["Tm"] = 10] = "Tm";
  LunarEclipseType2[LunarEclipseType2["Tn"] = 11] = "Tn";
  LunarEclipseType2[LunarEclipseType2["Ts"] = 12] = "Ts";
  return LunarEclipseType2;
})(LunarEclipseType || {});
var _SOLAR_LABELS = {
  [1 /* Aplus */]: "A+",
  [2 /* Aminus */]: "A-",
  [14 /* Tplus */]: "T+",
  [15 /* Tminus */]: "T-"
};
var _LUNAR_LABELS = {
  [8 /* Tplus */]: "T+",
  [9 /* Tminus */]: "T-"
};
function solarEclipseTypeLabel(type) {
  return _SOLAR_LABELS[type] ?? SolarEclipseType[type] ?? String(type);
}
function lunarEclipseTypeLabel(type) {
  return _LUNAR_LABELS[type] ?? LunarEclipseType[type] ?? String(type);
}

// src/db.ts
import * as fs from "fs";
import * as path2 from "path";
var TIMES_SIZE = 8;
var INFO_SIZE = 10;
var SAROS_SIZE = 194;
var NA_DURATION = 65535;
var SOLAR_TYPE_COUNT = 19;
var LUNAR_TYPE_COUNT = 13;
function readInt64LE(buf, offset) {
  const lo = buf.readUInt32LE(offset);
  const hi = buf.readInt32LE(offset + 4);
  return hi * 4294967296 + lo;
}
function toDate(unixTime) {
  return new Date(unixTime * 1e3);
}
function toUnix(ts) {
  if (ts instanceof Date) return Math.trunc(ts.getTime() / 1e3);
  return Math.trunc(ts);
}
var EclipseDB = class {
  constructor(kind) {
    this.kind = kind;
    const dataDir = path2.join(__dirname, "..", "data", kind);
    this.times = fs.readFileSync(path2.join(dataDir, "eclipse_times.db"));
    this.info = fs.readFileSync(path2.join(dataDir, "eclipse_info.db"));
    this.saros = fs.readFileSync(path2.join(dataDir, "saros.db"));
    this.count = this.times.length / TIMES_SIZE;
  }
  // ── Low-level accessors ──────────────────────────────────────────────────
  readTime(idx) {
    return readInt64LE(this.times, idx * TIMES_SIZE);
  }
  makeSolarEntry(idx) {
    const off = idx * INFO_SIZE;
    const lat10 = this.info.readInt16LE(off);
    const lon10 = this.info.readInt16LE(off + 2);
    const dur = this.info.readUInt16LE(off + 4);
    const sarosNumber = this.info[off + 6];
    const sarosPos = this.info[off + 7];
    const eclType = this.info[off + 8];
    const sunAlt = this.info[off + 9];
    const unixTime = this.readTime(idx);
    return {
      unixTime,
      date: toDate(unixTime),
      globalIndex: idx,
      sarosNumber,
      sarosPos,
      type: eclType < SOLAR_TYPE_COUNT ? eclType : 10 /* P */,
      latitude: lat10 / 10,
      longitude: lon10 / 10,
      centralDuration: dur === NA_DURATION ? null : dur,
      sunAltitude: sunAlt
    };
  }
  makeLunarEntry(idx) {
    const off = idx * INFO_SIZE;
    const pen = this.info.readUInt16LE(off);
    const par = this.info.readUInt16LE(off + 2);
    const tot = this.info.readUInt16LE(off + 4);
    const sarosNumber = this.info[off + 6];
    const sarosPos = this.info[off + 7];
    const eclType = this.info[off + 8];
    const unixTime = this.readTime(idx);
    return {
      unixTime,
      date: toDate(unixTime),
      globalIndex: idx,
      sarosNumber,
      sarosPos,
      type: eclType < LUNAR_TYPE_COUNT ? eclType : 4 /* P */,
      penumbralDuration: pen === NA_DURATION ? null : pen,
      partialDuration: par === NA_DURATION ? null : par,
      totalDuration: tot === NA_DURATION ? null : tot
    };
  }
  makeEntry(idx) {
    return this.kind === "solar" ? this.makeSolarEntry(idx) : this.makeLunarEntry(idx);
  }
  // ── Saros index ──────────────────────────────────────────────────────────
  loadSarosSeries(sarosNumber) {
    if (sarosNumber < 1 || sarosNumber > 180) return { count: 0, indices: [] };
    const offset = (sarosNumber - 1) * SAROS_SIZE;
    const count = this.saros[offset];
    const indices = [];
    for (let i = 0; i < count; i++) {
      indices.push(this.saros.readUInt16LE(offset + 2 + i * 2));
    }
    return { count, indices };
  }
  sarosNeighbours(sarosNumber, sarosPos) {
    const { count, indices } = this.loadSarosSeries(sarosNumber);
    if (count === 0) return { prev: null, next: null };
    const prev = sarosPos > 0 ? this.makeEntry(indices[sarosPos - 1]) : null;
    const next = sarosPos + 1 < count ? this.makeEntry(indices[sarosPos + 1]) : null;
    return { prev, next };
  }
  // ── Binary search ────────────────────────────────────────────────────────
  /** First index with time >= key; equals count if all times < key. */
  lowerBound(key) {
    let lo = 0, hi = this.count;
    while (lo < hi) {
      const mid = lo + hi >>> 1;
      if (this.readTime(mid) < key) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }
  /** First index with time > key; element at result-1 is last <= key. */
  upperBound(key) {
    let lo = 0, hi = this.count;
    while (lo < hi) {
      const mid = lo + hi >>> 1;
      if (this.readTime(mid) <= key) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }
  // ── Public query methods ─────────────────────────────────────────────────
  findNext(ts) {
    const idx = this.lowerBound(ts);
    if (idx >= this.count) {
      return { eclipse: null, sarosPrev: null, sarosNext: null };
    }
    const entry = this.makeEntry(idx);
    const { prev, next } = this.sarosNeighbours(
      entry.sarosNumber,
      entry.sarosPos
    );
    return { eclipse: entry, sarosPrev: prev, sarosNext: next };
  }
  findPast(ts) {
    const idx = this.upperBound(ts);
    if (idx === 0) {
      return { eclipse: null, sarosPrev: null, sarosNext: null };
    }
    const entry = this.makeEntry(idx - 1);
    const { prev, next } = this.sarosNeighbours(
      entry.sarosNumber,
      entry.sarosPos
    );
    return { eclipse: entry, sarosPrev: prev, sarosNext: next };
  }
  sarosWindow(ts, sarosNumber) {
    const { count, indices } = this.loadSarosSeries(sarosNumber);
    if (count === 0) return { sarosNumber, past: null, future: null };
    let lo = 0, hi = count;
    while (lo < hi) {
      const mid = lo + hi >>> 1;
      if (this.readTime(indices[mid]) < ts) lo = mid + 1;
      else hi = mid;
    }
    const past = lo > 0 ? this.makeEntry(indices[lo - 1]) : null;
    const future = lo < count ? this.makeEntry(indices[lo]) : null;
    return { sarosNumber, past, future };
  }
};
var _solarDB;
var _lunarDB;
function solarDB() {
  return _solarDB ??= new EclipseDB("solar");
}
function lunarDB() {
  return _lunarDB ??= new EclipseDB("lunar");
}

// src/index.ts
function findNextSolarEclipse(ts) {
  return solarDB().findNext(toUnix(ts));
}
function findPastSolarEclipse(ts) {
  return solarDB().findPast(toUnix(ts));
}
function findClosestSolarEclipse(ts) {
  const unix = toUnix(ts);
  const nxt = solarDB().findNext(unix);
  const pst = solarDB().findPast(unix);
  if (!nxt.eclipse) return pst;
  if (!pst.eclipse) return nxt;
  const dNxt = nxt.eclipse.unixTime - unix;
  const dPst = unix - pst.eclipse.unixTime;
  return dPst < dNxt ? pst : nxt;
}
function findSolarSarosWindow(ts, sarosNumber) {
  return solarDB().sarosWindow(toUnix(ts), sarosNumber);
}
function findNextLunarEclipse(ts) {
  return lunarDB().findNext(toUnix(ts));
}
function findPastLunarEclipse(ts) {
  return lunarDB().findPast(toUnix(ts));
}
function findClosestLunarEclipse(ts) {
  const unix = toUnix(ts);
  const nxt = lunarDB().findNext(unix);
  const pst = lunarDB().findPast(unix);
  if (!nxt.eclipse) return pst;
  if (!pst.eclipse) return nxt;
  const dNxt = nxt.eclipse.unixTime - unix;
  const dPst = unix - pst.eclipse.unixTime;
  return dPst < dNxt ? pst : nxt;
}
function findLunarSarosWindow(ts, sarosNumber) {
  return lunarDB().sarosWindow(toUnix(ts), sarosNumber);
}
export {
  LunarEclipseType,
  SolarEclipseType,
  findClosestLunarEclipse,
  findClosestSolarEclipse,
  findLunarSarosWindow,
  findNextLunarEclipse,
  findNextSolarEclipse,
  findPastLunarEclipse,
  findPastSolarEclipse,
  findSolarSarosWindow,
  lunarEclipseTypeLabel,
  solarEclipseTypeLabel
};
