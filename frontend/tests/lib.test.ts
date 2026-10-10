import { describe, expect, it } from "vitest";
import { isTokenExpired } from "@/lib/jwt";
import { fmtTemp, trend } from "@/lib/format";
import { formatElapsed, formatMmSs } from "@/lib/time";
import { stressLevel } from "@/design/tokens";

function makeJwt(expSeconds: number): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify({ sub: "u", exp: expSeconds }));
  return `${header}.${payload}.sig`;
}

describe("jwt expiry", () => {
  it("treats a future-exp token as valid", () => {
    expect(isTokenExpired(makeJwt(Math.floor(Date.now() / 1000) + 1000))).toBe(false);
  });
  it("treats a past-exp token as expired", () => {
    expect(isTokenExpired(makeJwt(Math.floor(Date.now() / 1000) - 1000))).toBe(true);
  });
  it("treats null/garbage as expired", () => {
    expect(isTokenExpired(null)).toBe(true);
    expect(isTokenExpired("not-a-jwt")).toBe(true);
  });
});

describe("format helpers", () => {
  it("renders temp, hiding zero/null sensor warmup", () => {
    expect(fmtTemp(36.49)).toBe("36.5");
    expect(fmtTemp(0)).toBe("-");
    expect(fmtTemp(null)).toBe("-");
  });
  it("detects trend direction", () => {
    expect(trend([60, 70])).toBe("up");
    expect(trend([70, 60])).toBe("down");
    expect(trend([60, 60.2])).toBe("flat");
  });
});

describe("time helpers", () => {
  it("formats elapsed", () => {
    expect(formatElapsed(5000)).toBe("5s");
    expect(formatElapsed(65000)).toBe("1m 05s");
  });
  it("formats mm:ss", () => {
    expect(formatMmSs(125)).toBe("2:05");
  });
});

describe("stress level mapping", () => {
  it("maps probability to level", () => {
    expect(stressLevel(0.2)).toBe("calm");
    expect(stressLevel(0.5)).toBe("moderate");
    expect(stressLevel(0.8)).toBe("high");
  });
});
