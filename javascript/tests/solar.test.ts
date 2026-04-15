import { describe, it, expect } from "vitest";
import {
  findNextSolarEclipse,
  findPastSolarEclipse,
  findClosestSolarEclipse,
  findSolarSarosWindow,
  SolarEclipseType,
  solarEclipseTypeLabel,
} from "../src/index.js";

// ── Constants ─────────────────────────────────────────────────────────────────

const NOW = new Date("2026-04-15T12:00:00Z");
const NOW_TS = Math.trunc(NOW.getTime() / 1000);

// Aug 21 2017 total solar eclipse (Saros 145, well-documented event)
const BEFORE_2017 = new Date("2017-08-21T00:00:00Z");

// Far outside dataset range
const FAR_FUTURE_TS = 95_617_584_000;   // year 5000 CE (dataset ends ~4017 CE)
const FAR_PAST_TS   = -200_000_000_000; // before ~2872 BCE dataset start

// ── Return shape ──────────────────────────────────────────────────────────────

describe("findNextSolarEclipse return shape", () => {
  it("returns an EclipseResult object", () => {
    const r = findNextSolarEclipse(NOW);
    expect(r).toHaveProperty("eclipse");
    expect(r).toHaveProperty("sarosPrev");
    expect(r).toHaveProperty("sarosNext");
  });

  it("eclipse is a SolarEclipse object", () => {
    const r = findNextSolarEclipse(NOW);
    expect(r.eclipse).not.toBeNull();
    expect(r.eclipse).toHaveProperty("unixTime");
    expect(r.eclipse).toHaveProperty("date");
    expect(r.eclipse).toHaveProperty("sarosNumber");
    expect(r.eclipse).toHaveProperty("type");
    expect(r.eclipse).toHaveProperty("latitude");
    expect(r.eclipse).toHaveProperty("longitude");
  });
});

// ── Temporal logic ────────────────────────────────────────────────────────────

describe("temporal ordering", () => {
  it("next eclipse is in the future", () => {
    const r = findNextSolarEclipse(NOW);
    expect(r.eclipse!.unixTime).toBeGreaterThanOrEqual(NOW_TS);
  });

  it("past eclipse is in the past", () => {
    const r = findPastSolarEclipse(NOW);
    expect(r.eclipse!.unixTime).toBeLessThanOrEqual(NOW_TS);
  });

  it("past and next are different eclipses", () => {
    const nxt = findNextSolarEclipse(NOW);
    const pst = findPastSolarEclipse(NOW);
    expect(nxt.eclipse!.globalIndex).not.toBe(pst.eclipse!.globalIndex);
  });

  it("past comes before next", () => {
    const nxt = findNextSolarEclipse(NOW);
    const pst = findPastSolarEclipse(NOW);
    expect(pst.eclipse!.unixTime).toBeLessThan(nxt.eclipse!.unixTime);
  });
});

// ── Out-of-range ──────────────────────────────────────────────────────────────

describe("out-of-range timestamps", () => {
  it("far future returns null eclipse", () => {
    const r = findNextSolarEclipse(FAR_FUTURE_TS);
    expect(r.eclipse).toBeNull();
    expect(r.sarosPrev).toBeNull();
    expect(r.sarosNext).toBeNull();
  });

  it("far past returns null eclipse", () => {
    const r = findPastSolarEclipse(FAR_PAST_TS);
    expect(r.eclipse).toBeNull();
  });
});

// ── Saros neighbours ──────────────────────────────────────────────────────────

describe("Saros neighbours", () => {
  it("at least one neighbour is present for a mid-series eclipse", () => {
    const r = findNextSolarEclipse(NOW);
    expect(r.sarosPrev !== null || r.sarosNext !== null).toBe(true);
  });

  it("neighbours belong to the same Saros series", () => {
    const r = findNextSolarEclipse(NOW);
    const sn = r.eclipse!.sarosNumber;
    if (r.sarosPrev) expect(r.sarosPrev.sarosNumber).toBe(sn);
    if (r.sarosNext) expect(r.sarosNext.sarosNumber).toBe(sn);
  });

  it("prev comes before, next comes after the eclipse", () => {
    const r = findNextSolarEclipse(NOW);
    if (r.sarosPrev) expect(r.sarosPrev.unixTime).toBeLessThan(r.eclipse!.unixTime);
    if (r.sarosNext) expect(r.sarosNext.unixTime).toBeGreaterThan(r.eclipse!.unixTime);
  });
});

// ── Known eclipse: Aug 21 2017 Saros 145 ─────────────────────────────────────

describe("known eclipse — Aug 21 2017 (Saros 145 Total)", () => {
  it("findClosest lands on 2017-08-21", () => {
    const r = findClosestSolarEclipse(BEFORE_2017);
    expect(r.eclipse).not.toBeNull();
    const d = r.eclipse!.date;
    expect(d.getUTCFullYear()).toBe(2017);
    expect(d.getUTCMonth()).toBe(7); // 0-indexed August
  });

  it("type is Total", () => {
    const r = findClosestSolarEclipse(BEFORE_2017);
    expect(r.eclipse!.type).toBe(SolarEclipseType.T);
  });

  it("sarosNumber is 145", () => {
    const r = findClosestSolarEclipse(BEFORE_2017);
    expect(r.eclipse!.sarosNumber).toBe(145);
  });

  it("coordinates are over the central USA", () => {
    const r = findClosestSolarEclipse(BEFORE_2017);
    const e = r.eclipse!;
    expect(e.latitude).toBeGreaterThan(30);
    expect(e.latitude).toBeLessThan(45);
    expect(e.longitude).toBeGreaterThan(-100);
    expect(e.longitude).toBeLessThan(-70);
  });

  it("centralDuration is a positive number of seconds", () => {
    const r = findClosestSolarEclipse(BEFORE_2017);
    expect(r.eclipse!.centralDuration).not.toBeNull();
    expect(r.eclipse!.centralDuration!).toBeGreaterThan(0);
  });
});

// ── SolarEclipse field validity ───────────────────────────────────────────────

describe("SolarEclipse field validity", () => {
  it("sarosNumber is 1–180", () => {
    const e = findNextSolarEclipse(NOW).eclipse!;
    expect(e.sarosNumber).toBeGreaterThanOrEqual(1);
    expect(e.sarosNumber).toBeLessThanOrEqual(180);
  });

  it("sarosPos is >= 0", () => {
    const e = findNextSolarEclipse(NOW).eclipse!;
    expect(e.sarosPos).toBeGreaterThanOrEqual(0);
  });

  it("type is a valid SolarEclipseType", () => {
    const e = findNextSolarEclipse(NOW).eclipse!;
    expect(Object.values(SolarEclipseType)).toContain(e.type);
  });

  it("latitude is in [-90, 90]", () => {
    const e = findNextSolarEclipse(NOW).eclipse!;
    expect(e.latitude).toBeGreaterThanOrEqual(-90);
    expect(e.latitude).toBeLessThanOrEqual(90);
  });

  it("longitude is in [-180, 180]", () => {
    const e = findNextSolarEclipse(NOW).eclipse!;
    expect(e.longitude).toBeGreaterThanOrEqual(-180);
    expect(e.longitude).toBeLessThanOrEqual(180);
  });

  it("centralDuration is null or > 0", () => {
    const e = findNextSolarEclipse(NOW).eclipse!;
    if (e.centralDuration !== null) expect(e.centralDuration).toBeGreaterThan(0);
  });

  it("date is a Date object", () => {
    const e = findNextSolarEclipse(NOW).eclipse!;
    expect(e.date).toBeInstanceOf(Date);
    expect(isNaN(e.date.getTime())).toBe(false);
  });

  it("date matches unixTime", () => {
    const e = findNextSolarEclipse(NOW).eclipse!;
    expect(Math.trunc(e.date.getTime() / 1000)).toBe(e.unixTime);
  });
});

// ── Saros window ──────────────────────────────────────────────────────────────

describe("findSolarSarosWindow", () => {
  it("returns correct sarosNumber", () => {
    const w = findSolarSarosWindow(NOW, 145);
    expect(w.sarosNumber).toBe(145);
  });

  it("Saros 145 is active — both past and future present", () => {
    const w = findSolarSarosWindow(NOW, 145);
    expect(w.past).not.toBeNull();
    expect(w.future).not.toBeNull();
  });

  it("past comes before future", () => {
    const w = findSolarSarosWindow(NOW, 145);
    if (w.past && w.future) {
      expect(w.past.unixTime).toBeLessThan(w.future.unixTime);
    }
  });

  it("past is in the past", () => {
    const w = findSolarSarosWindow(NOW, 145);
    if (w.past) expect(w.past.unixTime).toBeLessThan(NOW_TS);
  });

  it("future is in the future", () => {
    const w = findSolarSarosWindow(NOW, 145);
    if (w.future) expect(w.future.unixTime).toBeGreaterThanOrEqual(NOW_TS);
  });

  it("invalid saros series returns nulls", () => {
    const w = findSolarSarosWindow(NOW, 999);
    expect(w.past).toBeNull();
    expect(w.future).toBeNull();
  });
});

// ── Input type variants ───────────────────────────────────────────────────────

describe("input type flexibility", () => {
  it("accepts a Date object", () => {
    expect(findNextSolarEclipse(new Date()).eclipse).not.toBeNull();
  });

  it("accepts a unix timestamp number", () => {
    expect(findNextSolarEclipse(NOW_TS).eclipse).not.toBeNull();
  });

  it("accepts a float unix timestamp", () => {
    expect(findNextSolarEclipse(NOW_TS + 0.9).eclipse).not.toBeNull();
  });
});

// ── Eclipse type labels ───────────────────────────────────────────────────────

describe("solarEclipseTypeLabel", () => {
  it("returns 'A+' for Aplus", () => {
    expect(solarEclipseTypeLabel(SolarEclipseType.Aplus)).toBe("A+");
  });

  it("returns 'T-' for Tminus", () => {
    expect(solarEclipseTypeLabel(SolarEclipseType.Tminus)).toBe("T-");
  });

  it("returns 'T' for T", () => {
    expect(solarEclipseTypeLabel(SolarEclipseType.T)).toBe("T");
  });

  it("returns 'P' for P", () => {
    expect(solarEclipseTypeLabel(SolarEclipseType.P)).toBe("P");
  });
});

// ── findClosest ───────────────────────────────────────────────────────────────

describe("findClosestSolarEclipse", () => {
  it("returns the nearer eclipse", () => {
    const nxt = findNextSolarEclipse(NOW).eclipse!;
    const pst = findPastSolarEclipse(NOW).eclipse!;
    const cls = findClosestSolarEclipse(NOW).eclipse!;
    const dNxt = Math.abs(nxt.unixTime - NOW_TS);
    const dPst = Math.abs(pst.unixTime - NOW_TS);
    const dCls = Math.abs(cls.unixTime - NOW_TS);
    expect(dCls).toBeLessThanOrEqual(Math.min(dNxt, dPst));
  });
});
