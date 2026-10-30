import { describe, expect, it } from "vitest";
import { designPayload, designState } from "@/components/msa-design";
import { enB3, esB3 } from "./messages-b3";

describe("MSA design form", () => {
  it("builds a crossed GRR payload with parts and operator names", () => {
    const { design, params } = designPayload("GRR_CROSSED_ANOVA", {
      operators: "3", parts: "10", trials: "3", tolerance: "0,4", operator_names: "Ana, Luis ,Eva",
      p_interaction_mode: "include", p_study_var_multiplier: "6",
    });
    expect(design).toEqual({ operators: 3, parts: 10, trials: 3, tolerance: 0.4, operator_names: ["Ana", "Luis", "Eva"] });
    expect(params).toEqual({ study_var_multiplier: 6, interaction_mode: "include" });
  });

  it("uses parts_per_operator for nested designs and omits empty values", () => {
    const { design } = designPayload("GRR_NESTED_ANOVA", { operators: "2", parts_per_operator: "5", trials: "2", unit: "" });
    expect(design).toEqual({ operators: 2, parts_per_operator: 5, trials: 2 });
  });

  it("parses attribute categories and part references", () => {
    const { design } = designPayload("ATTRIBUTE_AGREEMENT", {
      categories: "G, NG", part_reference: "1=G, 2=NG", accept_category: "G", reject_category: "NG",
    });
    expect(design.categories).toEqual(["G", "NG"]);
    expect(design.part_reference).toEqual({ "1": "G", "2": "NG" });
  });

  it("round-trips stability rules through the form state", () => {
    const s = designState({ subgroup_size: 1, reference: 5 }, { rules: { "2": { enabled: true, run: 9 }, "1": { enabled: false } } });
    const { design, params } = designPayload("STABILITY", s);
    expect(design).toMatchObject({ subgroup_size: 1, reference: 5 });
    const rules = params.rules as Record<string, { enabled: boolean; run?: number }>;
    expect(rules["2"]).toEqual({ enabled: true, run: 9 });
    expect(rules["1"].enabled).toBe(false);
    expect(rules["3"].enabled).toBe(true);
  });
});

describe("block 3 messages", () => {
  it("has an English translation for every Spanish key", () => {
    expect(Object.keys(enB3).sort()).toEqual(Object.keys(esB3).sort());
    expect(Object.values(enB3).every((v) => v.trim().length > 0)).toBe(true);
  });
});
