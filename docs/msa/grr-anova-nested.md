# GRR anidado — ANOVA (`GRR_NESTED_ANOVA`, algoritmo 1.0.0)

## Definición
Para ensayos destructivos o piezas que no pueden circular: cada evaluador mide sus propias piezas. Modelo yᵢⱼₖ = μ + Oᵢ + P(O)ⱼ₍ᵢ₎ + εₖ₍ᵢⱼ₎, efectos aleatorios. La interacción evaluador × pieza no es estimable (confundida con la variación entre piezas), por eso **no** se reutilizan las fórmulas cruzadas.

## Diseño de datos
`{operator, part, trial, value}`; cada etiqueta de pieza pertenece a un solo evaluador; mismo número de piezas por evaluador y de repeticiones por pieza; se declara `parts_per_operator`.

## Fórmulas
- SS_O = p·r·Σ(ȳᵢ.. − ȳ)²; SS_P(O) = r·ΣΣ(ȳᵢⱼ. − ȳᵢ..)²; SS_E = ΣΣΣ(y − ȳᵢⱼ.)²; gl = o−1, o(p−1), o·p(r−1).
- E[MS_E] = σ²_E; E[MS_P(O)] = σ²_E + r·σ²_P; E[MS_O] = σ²_E + r·σ²_P + p·r·σ²_O.
- σ²_E = MS_E; σ²_P = (MS_P(O) − MS_E)/r; σ²_O = (MS_O − MS_P(O))/(p·r); negativos → 0.
- GRR = √(σ²_E + σ²_O); PV = σ_P; TV = √(GRR² + PV²); %SV, %Contribución, %Tolerancia, ndc como en el cruzado. F_O = MS_O/MS_P(O); F_P(O) = MS_P(O)/MS_E.

## Limitaciones
Requiere homogeneidad de las piezas asignadas a cada evaluador (supuesto del diseño). Diseños desbalanceados se rechazan.

## Validación
| Caso | Esperado | Obtenido |
|---|---|---|
| Cálculo a mano (2 evaluadores × 2 piezas × 2 rep.) SS_O/SS_P(O)/SS_E/SS_T | 98 / 20 / 8 / 126 | idénticos |
| σ²_E, σ²_P, σ²_O | 2, 4, 22 | idénticos; GRR = √24, PV = 2, ndc 0 |
| 8 diseños aleatorios vs statsmodels por suma de cuadrados extra (`y ~ C(operator)` vs `y ~ C(part)`) | igualdad | rel. < 1e-9; gl idénticos |
| Datos cruzados enviados como anidados | rechazo `part_not_nested` | rechazado |
| Diseño desbalanceado | rechazo `unbalanced_design` | rechazado |

**Defecto de referencia encontrado:** la tabla ANOVA secuencial de statsmodels con `C(operator) + C(part)` en datos anidados no es una descomposición válida (matriz de diseño singular: sus SS suman 168.97 cuando el SS del modelo es 168.73). Por eso la validación independiente usa comparación de modelos y no esa tabla.
