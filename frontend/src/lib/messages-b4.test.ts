import { describe, expect, it } from "vitest";
import { enB4, esB4 } from "./messages-b4";

describe("block 4 messages", () => {
  it("has an English translation for every Spanish key, none empty", () => {
    expect(Object.keys(enB4).sort()).toEqual(Object.keys(esB4).sort());
    expect(Object.values(enB4).every((v) => v.trim().length > 0)).toBe(true);
  });

  it("keeps the same placeholders in both languages", () => {
    const vars = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(",");
    for (const k of Object.keys(esB4) as (keyof typeof esB4)[]) expect(vars(enB4[k])).toBe(vars(esB4[k]));
  });
});
