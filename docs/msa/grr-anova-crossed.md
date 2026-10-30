# GRR cruzado — método ANOVA (`GRR_CROSSED_ANOVA`, algoritmo 1.0.0)

## Definición
Modelo de efectos aleatorios de dos factores con interacción: yᵢⱼₖ = μ + Pᵢ + Oⱼ + (PO)ᵢⱼ + εᵢⱼₖ. Estima componentes de varianza a partir de los cuadrados medios esperados (AIAG MSA 4ª ed., Cap. III, Secc. B, método ANOVA; Montgomery & Runger).

## Diseño de datos
`{operator, part, trial, value}`, factorial completo balanceado; ≥ 2 piezas, ≥ 2 evaluadores, ≥ 2 repeticiones (sin máximo).

## Fórmulas
- SS_P = o·r·Σ(ȳᵢ.. − ȳ)², SS_O = p·r·Σ(ȳ.ⱼ. − ȳ)², SS_PO = r·ΣΣ(ȳᵢⱼ. − ȳᵢ.. − ȳ.ⱼ. + ȳ)², SS_E = ΣΣΣ(y − ȳᵢⱼ.)²; gl = p−1, o−1, (p−1)(o−1), p·o·(r−1).
- Modelo completo: F_PO = MS_PO/MS_E; F_P = MS_P/MS_PO; F_O = MS_O/MS_PO. σ²_E = MS_E; σ²_PO = (MS_PO − MS_E)/r; σ²_O = (MS_O − MS_PO)/(p·r); σ²_P = (MS_P − MS_PO)/(o·r).
- Modelo reducido (interacción agrupada): MS_pool = (SS_PO + SS_E)/(gl_PO + gl_E); σ²_E = MS_pool; σ²_O = (MS_O − MS_pool)/(p·r); σ²_P = (MS_P − MS_pool)/(o·r).
- Selección (`interaction_mode`): `auto` usa el modelo completo si p(F_PO) ≤ `interaction_alpha` (por defecto 0.25, convención de software estadístico de uso común, **no** requisito AIAG; configurable), `include` o `exclude` lo fuerzan.
- EV = σ_E; AV = σ_O; INT = σ_PO; GRR = √(σ²_E + σ²_O + σ²_PO); PV = σ_P; TV = √(GRR² + PV²). Mismos indicadores que el método AR (%SV, %Contribución, %Tolerancia, ndc).

## Supuestos y limitaciones
Normalidad de errores, balance, efectos aleatorios. Varianzas negativas → 0 con advertencia. Repetibilidad nula (lecturas idénticas) → ndc indefinido, advertencia de resolución.

## Validación
| Caso | Esperado | Obtenido |
|---|---|---|
| SS Evaluador/Piezas/Interacción/Equipo/Total (AIAG publicado) | 3.1673 / 88.3619 / 0.3590 / 2.7589 / 94.6471 | 3.167262 / 88.361934 / 0.358982 / 2.758933 / 94.647112 |
| gl | 2 / 9 / 18 / 60 / 89 | idénticos |
| SS vs statsmodels (OLS `C(part)*C(operator)`, tipo II) | igualdad | rel. < 1e-10 |
| p de interacción vs statsmodels | igualdad | rel. < 1e-8 |
| 12 diseños aleatorios (2–4 evaluadores, 2–10 piezas, 2–4 repeticiones, con y sin interacción): componentes de varianza vs EMS calculados desde statsmodels | igualdad | abs. < 1e-12 |
| Ejemplo AIAG, modo auto | interacción agrupada (p ≈ 0.974 > 0.25) | p = 0.97411; reducido |
| Ejemplo AIAG, resultados del modelo reducido | — | EV 0.19993, AV 0.22684, GRR 0.30237, PV 1.0423, %GRR 27.86, ndc 4 |

Nota: con estos datos ANOVA da ndc = 4, mientras Promedio y Rango da 5; son métodos distintos y el registro conserva cuál produjo cada resultado.
