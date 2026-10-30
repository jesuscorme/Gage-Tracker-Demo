import { describe, expect, it } from "vitest";
import { en as enBase, es as esBase, format } from "./messages";
import { enModules, esModules } from "./messages-modules";

const es = { ...esBase, ...esModules };
const en = { ...enBase, ...enModules };

describe("messages", () => {
  it("has the same keys in both languages and no empty strings", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(es).sort());
    for (const dict of [es, en]) for (const v of Object.values(dict)) expect(v.trim()).not.toBe("");
  });

  it("uses the same placeholders in both languages", () => {
    const vars = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
    for (const k of Object.keys(es) as (keyof typeof es)[]) expect(vars(en[k])).toEqual(vars(es[k]));
  });

  it("formats placeholders", () => {
    expect(format("{n} d", { n: 5 })).toBe("5 d");
    expect(format("x {missing}", {})).toBe("x {missing}");
  });
});
