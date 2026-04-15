import { describe, it, expect } from "vitest";
import {
  findNextLunarEclipse,
  findPastLunarEclipse,
  findClosestLunarEclipse,
  findLunarSarosWindow,
  LunarEclipseType,
  lunarEclipseTypeLabel,
} from "../src/index.js";

// ── Constants ─────────────────────────────────────────────────────────────────

const NOW    = new Date("2026-04-15T12:00:00Z");
const NOW_TS = Math.trunc(NOW.getTime() / 1000);

// Jan 31 2018 total lunar eclipse (Saros 124, "super blood moon")
const NEAR_2018 = new Date("2018-01-31T13:30:00Z");

const FAR_FUTURE_TS = 95_617_584_000;   // year 5000 CE
const FAR_PAST_TS   = -200_000_000_000; // before ~2872 BCE

// ── Return shape ──────────────────────────────────────────────────────────────

describe("findNextLunarEclipse return shape", () => {
  it("returns an EclipseResult object", () => {
    const r = findNextLunarEclipse(NOW);
    expect(r).toHaveProperty("eclipse");
    expect(r).toHaveProperty("sarosPrev");
    expect(r).toHaveProperty("sarosNext");
  });

  it("eclipse is a LunarEclipse object", () => {
    const r = findNextLunarEclipse(NOW);
    expect(r.eclipse).not.toBeNull();
    expect(r.eclipse).toHaveProperty("unixTime");
    expect(r.eclipse).toHaveProperty("date");
    expect(r.eclipse).toHaveProperty("sarosNumber");
    expect(r.eclipse).toHaveProperty("type");
    expect(r.eclipse).toHaveProperty("penumbralDuration");
    expect(r.eclipse).toHaveProperty("partialDuration");
    expect(r.eclipse).toHaveProperty("totalDuration");
  });
});

// ── Temporal logic ────────────────────────────────────────────────────────────

describe("temporal ordering", () => {
  it("next eclipse is in the future", () => {
    const r = findNextLunarEclipse(NOW);
    expect(r.eclipse!.unixTime).toBeGreaterThanOrEqual(NOW_TS);
  });

  it("past eclipse is in the past", () => {
    const r = findPastLunarEclipse(NOW);
    expect(r.eclipse!.unixTime).toBeLessThanOrEqual(NOW_TS);
  });

  it("past and next are different eclipses", () => {
    const nxt = findNextLunarEclipse(NOW);
    const pst = findPastLunarEclipse(NOW);
    expect(nxt.eclipse!.globalIndex).not.toBe(pst.eclipse!.globalIndex);
  });

  it("past comes before next", () => {
    const nxt = findNextLunarEclipse(NOW);
    const pst = findPastLunarEclipse(NOW);
    expect(pst.eclipse!.unixTime).toBeLessThan(nxt.eclipse!.unixTime);
  });
});

// ── Out-of-range ──────────────────────────────────────────────────────────────

describe("out-of-range timestamps", () => {
  it("far future returns null eclipse", () => {
    const r = findNextLunarEclipse(FAR_FUTURE_TS);
    expect(r.eclipse).toBeNull();
  });

  it("far past returns null eclipse", () => {
    const r = findPastLunarEclipse(FAR_PAST_TS);
    expect(r.eclipse).toBeNull();
  });
});

// ── Saros neighbours ──────────────────────────────────────────────────────────

describe("Saros neighbours", () => {
  it("neighbours belong to the same Saros series", () => {
    const r = findNextLunarEclipse(NOW);
    const sn = r.eclipse!.sarosNumber;
    if (r.sarosPrev) expect(r.sarosPrev.sarosNumber).toBe(sn);
    if (r.sarosNext) expect(r.sarosNext.sarosNumber).toBe(sn);
  });

  it("prev comes before, next comes after the eclipse", () => {
    const r = findNextLunarEclipse(NOW);
    if (r.sarosPrev) expect(r.sarosPrev.unixTime).toBeLessThan(r.eclipse!.unixTime);
    if (r.sarosNext) expect(r.sarosNext.unixTime).toBeGreaterThan(r.eclipse!.unixTime);
  });
});

// ── Known eclipse: Jan 31 2018 Saros 124 ─────────────────────────────────────

describe("known eclipse — Jan 31 2018 (Saros 124 Total)", () => {
  it("findClosest lands on 2018-01-31", () => {
    const r = findClosestLunarEclipse(NEAR_2018);
    expect(r.eclipse).not.toBeNull();
    const d = r.eclipse!.date;
    expect(d.getUTCFullYear()).toBe(2018);
    expect(d.getUTCMonth()).toBe(0); // 0-indexed January
  });

  it("type is a total variant", () => {
    const r = findClosestLunarEclipse(NEAR_2018);
    const totalTypes = [
      LunarEclipseType.T,
      LunarEclipseType.Tplus,
      LunarEclipseType.Tminus,
      LunarEclipseType.Tm,
    ];
    expect(totalTypes).toContain(r.eclipse!.type);
  });

  it("sarosNumber is 124", () => {
    const r = findClosestLunarEclipse(NEAR_2018);
    expect(r.eclipse!.sarosNumber).toBe(124);
  });
});

// ── LunarEclipse field validity ───────────────────────────────────────────────

describe("LunarEclipse field validity", () => {
  it("sarosNumber is 1–180", () => {
    const e = findNextLunarEclipse(NOW).eclipse!;
    expect(e.sarosNumber).toBeGreaterThanOrEqual(1);
    expect(e.sarosNumber).toBeLessThanOrEqual(180);
  });

  it("sarosPos is >= 0", () => {
    const e = findNextLunarEclipse(NOW).eclipse!;
    expect(e.sarosPos).toBeGreaterThanOrEqual(0);
  });

  it("type is a valid LunarEclipseType", () => {
    const e = findNextLunarEclipse(NOW).eclipse!;
    expect(Object.values(LunarEclipseType)).toContain(e.type);
  });

  it("duration fields are null or > 0", () => {
    const e = findNextLunarEclipse(NOW).eclipse!;
    for (const d of [e.penumbralDuration, e.partialDuration, e.totalDuration]) {
      if (d !== null) expect(d).toBeGreaterThan(0);
    }
  });

  it("date is a valid Date", () => {
    const e = findNextLunarEclipse(NOW).eclipse!;
    expect(e.date).toBeInstanceOf(Date);
    expect(isNaN(e.date.getTime())).toBe(false);
  });

  it("date matches unixTime", () => {
    const e = findNextLunarEclipse(NOW).eclipse!;
    expect(Math.trunc(e.date.getTime() / 1000)).toBe(e.unixTime);
  });

  it("total eclipse has a non-null totalDuration", () => {
    let ts = NOW_TS;
    let found = false;
    for (let i = 0; i < 200; i++) {
      const r = findNextLunarEclipse(ts);
      if (!r.eclipse) break;
      if (r.eclipse.type === LunarEclipseType.T) {
        expect(r.eclipse.totalDuration).not.toBeNull();
        expect(r.eclipse.totalDuration!).toBeGreaterThan(0);
        found = true;
        break;
      }
      ts = r.eclipse.unixTime + 1;
    }
    expect(found).toBe(true);
  });
});

// ── Saros window ──────────────────────────────────────────────────────────────

describe("findLunarSarosWindow", () => {
  it("returns correct sarosNumber", () => {
    const w = findLunarSarosWindow(NOW, 124);
    expect(w.sarosNumber).toBe(124);
  });

  it("Saros 124 has at least one entry", () => {
    const w = findLunarSarosWindow(NOW, 124);
    expect(w.past !== null || w.future !== null).toBe(true);
  });

  it("past comes before future", () => {
    const w = findLunarSarosWindow(NOW, 124);
    if (w.past && w.future) {
      expect(w.past.unixTime).toBeLessThan(w.future.unixTime);
    }
  });

  it("past is in the past", () => {
    const w = findLunarSarosWindow(NOW, 124);
    if (w.past) expect(w.past.unixTime).toBeLessThan(NOW_TS);
  });

  it("future is in the future", () => {
    const w = findLunarSarosWindow(NOW, 124);
    if (w.future) expect(w.future.unixTime).toBeGreaterThanOrEqual(NOW_TS);
  });

  it("invalid series returns nulls", () => {
    const w = findLunarSarosWindow(NOW, 999);
    expect(w.past).toBeNull();
    expect(w.future).toBeNull();
  });
});

// ── Input type variants ───────────────────────────────────────────────────────

describe("input type flexibility", () => {
  it("accepts a Date object", () => {
    expect(findNextLunarEclipse(new Date()).eclipse).not.toBeNull();
  });

  it("accepts a unix timestamp number", () => {
    expect(findNextLunarEclipse(NOW_TS).eclipse).not.toBeNull();
  });

  it("accepts a float unix timestamp", () => {
    expect(findNextLunarEclipse(NOW_TS + 0.9).eclipse).not.toBeNull();
  });
});

// ── Eclipse type labels ───────────────────────────────────────────────────────

describe("lunarEclipseTypeLabel", () => {
  it("returns 'T+' for Tplus", () => {
    expect(lunarEclipseTypeLabel(LunarEclipseType.Tplus)).toBe("T+");
  });

  it("returns 'T-' for Tminus", () => {
    expect(lunarEclipseTypeLabel(LunarEclipseType.Tminus)).toBe("T-");
  });

  it("returns 'T' for T", () => {
    expect(lunarEclipseTypeLabel(LunarEclipseType.T)).toBe("T");
  });

  it("returns 'N' for N", () => {
    expect(lunarEclipseTypeLabel(LunarEclipseType.N)).toBe("N");
  });
});

// ── findClosest ───────────────────────────────────────────────────────────────

describe("findClosestLunarEclipse", () => {
  it("returns the nearer eclipse", () => {
    const nxt = findNextLunarEclipse(NOW).eclipse!;
    const pst = findPastLunarEclipse(NOW).eclipse!;
    const cls = findClosestLunarEclipse(NOW).eclipse!;
    const dNxt = Math.abs(nxt.unixTime - NOW_TS);
    const dPst = Math.abs(pst.unixTime - NOW_TS);
    const dCls = Math.abs(cls.unixTime - NOW_TS);
    expect(dCls).toBeLessThanOrEqual(Math.min(dNxt, dPst));
  });
});
