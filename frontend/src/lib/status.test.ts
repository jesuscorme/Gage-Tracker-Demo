import { describe, expect, it } from "vitest";
import { GAGE_STATUSES, STATUS_TONE, transitionsFrom } from "./status";

describe("status metadata", () => {
  it("defines a tone for every status", () => {
    for (const s of GAGE_STATUSES) expect(STATUS_TONE[s]).toBeTruthy();
  });

  it("offers release only with the release permission", () => {
    for (const from of ["ACTIVE", "OUT_OF_SERVICE", "IN_CALIBRATION", "INACTIVE"] as const) {
      for (const o of transitionsFrom(from)) {
        if (o.target === "ACTIVE") expect(o.permission).toBe("gages:release");
        else expect(o.permission).not.toBe("gages:release");
      }
    }
  });

  it("only allows reactivation from INACTIVE", () => {
    expect(transitionsFrom("INACTIVE").map((o) => o.target)).toEqual(["ACTIVE"]);
  });
});
