"use client";

import { useI18n } from "@/lib/i18n";
import { csv, num } from "@/lib/lookups";
import { FAMILY, type MsaMethod } from "@/lib/types-b3";
import { Check, Field, Input, Select } from "./ui";

export type Strs = Record<string, string>;
const RULES = ["1", "2", "3", "4", "5", "6", "7", "8"];
const DEFAULT_ON = new Set(["1", "2", "3"]);
const RUNS: Record<string, string> = { "2": "7", "3": "6", "4": "14", "7": "15", "8": "8" };

/** Initial form state from stored design/params. */
export function designState(design: Record<string, unknown> = {}, params: Record<string, unknown> = {}): Strs {
  const s: Strs = {};
  for (const [k, v] of Object.entries(design)) {
    if (v === null || v === undefined) continue;
    if (k === "operator_names" || k === "categories" || k === "part_ids") s[k] = (v as string[]).join(", ");
    else if (k === "part_reference") s[k] = Object.entries(v as Record<string, string>).map(([p, c]) => `${p}=${c}`).join(", ");
    else s[k] = String(v);
  }
  for (const [k, v] of Object.entries(params)) if (k !== "rules" && v !== null && v !== undefined) s[`p_${k}`] = String(v);
  const rules = (params.rules ?? {}) as Record<string, { enabled?: boolean; run?: number }>;
  for (const r of RULES) {
    s[`r${r}`] = String(rules[r]?.enabled ?? DEFAULT_ON.has(r));
    if (RUNS[r]) s[`run${r}`] = String(rules[r]?.run ?? RUNS[r]);
  }
  return s;
}

/** Build the API payload (design + params) for a method from the form state. */
export function designPayload(method: MsaMethod, s: Strs) {
  const fam = FAMILY[method];
  const d: Record<string, unknown> = {};
  const p: Record<string, unknown> = {};
  const put = (o: Record<string, unknown>, k: string, v: unknown) => {
    if (v !== undefined && v !== "" && !(Array.isArray(v) && !v.length)) o[k] = v;
  };
  for (const k of ["unit", "sequence", "notes"]) put(d, k, s[k]);
  for (const k of ["tolerance", "lsl", "usl", "resolution", "reference"]) put(d, k, num(s[k] ?? ""));
  if (fam === "VARIABLE_GRR" || fam === "ATTRIBUTE") {
    for (const k of ["operators", "trials"]) put(d, k, num(s[k] ?? ""));
    put(d, method === "GRR_NESTED_ANOVA" ? "parts_per_operator" : "parts",
      num(s[method === "GRR_NESTED_ANOVA" ? "parts_per_operator" : "parts"] ?? ""));
    put(d, "operator_names", csv(s.operator_names ?? ""));
  }
  if (fam === "ATTRIBUTE") {
    put(d, "categories", csv(s.categories ?? ""));
    const ref = Object.fromEntries(csv(s.part_reference ?? "").map((x) => x.split("=").map((y) => y.trim())).filter((x) => x.length === 2));
    if (Object.keys(ref).length) d.part_reference = ref;
    put(d, "accept_category", s.accept_category);
    put(d, "reject_category", s.reject_category);
  }
  if (fam === "STABILITY") {
    put(d, "subgroup_size", num(s.subgroup_size ?? "1"));
    const rules: Record<string, { enabled: boolean; run?: number }> = {};
    for (const r of RULES) rules[r] = { enabled: s[`r${r}`] === "true", ...(RUNS[r] ? { run: num(s[`run${r}`] ?? RUNS[r]) } : {}) };
    p.rules = rules;
  }
  if (fam === "VARIABLE_GRR") put(p, "study_var_multiplier", num(s.p_study_var_multiplier ?? ""));
  if (method === "GRR_CROSSED_ANOVA") {
    put(p, "interaction_mode", s.p_interaction_mode);
    put(p, "interaction_alpha", num(s.p_interaction_alpha ?? ""));
  }
  if (["ATTRIBUTE", "BIAS", "LINEARITY", "TYPE1"].includes(fam)) put(p, "alpha", num(s.p_alpha ?? ""));
  if (fam === "TYPE1") {
    put(p, "k_percent", num(s.p_k_percent ?? ""));
    put(p, "l_sigma", num(s.p_l_sigma ?? ""));
  }
  return { design: d, params: p };
}

export function DesignFields({ method, value, onChange, disabled }: {
  method: MsaMethod; value: Strs; onChange: (s: Strs) => void; disabled?: boolean;
}) {
  const { t } = useI18n();
  const fam = FAMILY[method];
  const f = (k: string, label: Parameters<typeof t>[0], type = "text") => (
    <Field label={t(label)} key={k}>
      <Input type={type} inputMode={type === "number" ? "decimal" : undefined} step="any" disabled={disabled}
        value={value[k] ?? ""} onChange={(e) => onChange({ ...value, [k]: e.target.value })} />
    </Field>
  );
  const grid = "grid gap-3 sm:grid-cols-3";
  return (
    <div className="space-y-3">
      <div className={grid}>
        {(fam === "VARIABLE_GRR" || fam === "ATTRIBUTE") && <>
          {f("operators", "msa.operators", "number")}
          {method === "GRR_NESTED_ANOVA" ? f("parts_per_operator", "msa.partsPerOperator", "number") : f("parts", "msa.parts", "number")}
          {f("trials", "msa.trials", "number")}
        </>}
        {f("unit", "msa.unit")}
        {fam !== "ATTRIBUTE" && fam !== "STABILITY" && <>{f("tolerance", "msa.tolerance", "number")}{f("resolution", "msa.resolution", "number")}</>}
        {["BIAS", "TYPE1", "STABILITY"].includes(fam) && f("reference", "msa.reference", "number")}
        {fam === "STABILITY" && f("subgroup_size", "msa.subgroupSize", "number")}
      </div>
      {(fam === "VARIABLE_GRR" || fam === "ATTRIBUTE") && method !== "GRR_NESTED_ANOVA" && (
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
          {f("operator_names", "msa.operatorNames")}
          <Field label={t("msa.sequence")}>
            <Select disabled={disabled} value={value.sequence ?? ""} onChange={(e) => onChange({ ...value, sequence: e.target.value })}>
              <option value="">—</option><option value="RANDOMIZED">RANDOMIZED</option>
              <option value="SEQUENTIAL">SEQUENTIAL</option><option value="BLIND">BLIND</option>
            </Select>
          </Field>
        </div>
      )}
      {fam === "ATTRIBUTE" && <div className="grid gap-3 sm:grid-cols-2">
        {f("categories", "msa.categories")}{f("part_reference", "msa.partReference")}
        {f("accept_category", "msa.accept")}{f("reject_category", "msa.reject")}
      </div>}
      <div className="border-t border-line pt-3">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{t("msa.params")}</div>
        <div className={grid}>
          {fam === "VARIABLE_GRR" && (
            <Field label={t("msa.multiplier")}>
              <Select disabled={disabled} value={value.p_study_var_multiplier ?? "6"} onChange={(e) => onChange({ ...value, p_study_var_multiplier: e.target.value })}>
                <option value="6">6</option><option value="5.15">5.15</option>
              </Select>
            </Field>
          )}
          {method === "GRR_CROSSED_ANOVA" && <>
            <Field label={t("msa.interactionMode")}>
              <Select disabled={disabled} value={value.p_interaction_mode ?? "auto"} onChange={(e) => onChange({ ...value, p_interaction_mode: e.target.value })}>
                {(["auto", "include", "exclude"] as const).map((m) => <option key={m} value={m}>{t(`msa.interaction.${m}`)}</option>)}
              </Select>
            </Field>
            {f("p_interaction_alpha", "msa.interactionAlpha", "number")}
          </>}
          {["ATTRIBUTE", "BIAS", "LINEARITY", "TYPE1"].includes(fam) && f("p_alpha", "msa.alpha", "number")}
          {fam === "TYPE1" && <>{f("p_k_percent", "msa.kPercent", "number")}{f("p_l_sigma", "msa.lSigma", "number")}</>}
        </div>
        {fam === "STABILITY" && (
          <div className="mt-2">
            <div className="mb-1 text-[12px] text-ink-2">{t("msa.rules")}</div>
            <div className="grid gap-2 sm:grid-cols-4">
              {RULES.map((r) => (
                <div key={r} className="flex items-center gap-2">
                  <Check label={t("msa.rule", { n: r })} checked={value[`r${r}`] === "true"} disabled={disabled}
                    onChange={(c) => onChange({ ...value, [`r${r}`]: String(c) })} />
                  {RUNS[r] && <Input aria-label={`${t("msa.runLength")} ${r}`} className="w-14" type="number" disabled={disabled}
                    value={value[`run${r}`] ?? RUNS[r]} onChange={(e) => onChange({ ...value, [`run${r}`]: e.target.value })} />}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
