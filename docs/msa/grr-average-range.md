# GRR cruzado — método Promedio y Rango (`GRR_CROSSED_AR`, algoritmo 1.0.0)

## Definición
Estima repetibilidad (EV) y reproducibilidad (AV) de un sistema de medición variable con un diseño cruzado: cada evaluador mide cada pieza el mismo número de veces. No separa la interacción evaluador × pieza (use ANOVA para ello).

## Diseño de datos
Observaciones `{operator, part, trial, value}`; factorial completo y balanceado. Rangos admitidos por las constantes tabuladas: 2–3 evaluadores, 2–3 repeticiones, 2–10 piezas. Fuera de ese rango el diseño se rechaza (no se extrapolan constantes).

## Fórmulas implementadas (AIAG MSA 4ª ed., Cap. III, Secc. B)
- R̄ = promedio de los rangos dentro de celda (por evaluador y global); X̄diff = máx − mín de los promedios por evaluador; Rp = máx − mín de los promedios por pieza.
- EV = R̄·K1, K1 = {2: 0.8862, 3: 0.5908}
- AV = √((X̄diff·K2)² − EV²/(n·r)), K2 = {2: 0.7071, 3: 0.5231}; si el radicando es negativo, AV = 0.
- GRR = √(EV² + AV²); PV = Rp·K3 (K3 para 2–10 piezas: 0.7071, 0.5231, 0.4467, 0.4030, 0.3742, 0.3534, 0.3375, 0.3249, 0.3146); TV = √(GRR² + PV²).
- %SV = 100·σ/TV; %Contribución = 100·σ²/TV²; %Tolerancia = 100·k·σ/T (k = 6 o 5.15, parámetro); ndc = ⌊1.41·PV/GRR⌋.
- Control: UCL_R = D4·R̄ (D4 del manual SPC, Ap. E); rangos fuera de control se reportan.

## Supuestos y limitaciones
- K1 tabulado supone g = piezas × evaluadores > 15; con menos celdas se emite advertencia.
- No estima interacción; si se sospecha interacción use `GRR_CROSSED_ANOVA`.
- Datos faltantes, duplicados, etiquetas vacías o valores no numéricos impiden el cálculo (se listan todos).

## Casos de validación (`tests/test_engine_grr.py`)
| Caso | Esperado (AIAG publicado) | Obtenido |
|---|---|---|
| Promedios A/B/C | 0.1903 / 0.0683 / −0.2543 | 0.1903 / 0.0683 / −0.2543 |
| R̄ A/B/C | 0.184 / 0.513 / 0.328 | 0.184 / 0.513 / 0.328 |
| R̄ · X̄diff · Rp | 0.3417 · 0.4446 · 3.511 | 0.341667 · 0.444667 · 3.511111 |
| EV · AV · GRR | 0.20188 · 0.22963 · 0.30575 | 0.201857 · 0.229667 · 0.305766 |
| PV · TV | 1.10456 · 1.14610 | 1.104596 · 1.146135 |
| %EV · %AV · %GRR · %PV | 17.62 · 20.04 · 26.68 · 96.38 | 17.61 · 20.04 · 26.68 · 96.38 |
| ndc | 5 | 5 |

Diferencias < 1·10⁻⁴: el manual redondea R̄ y Rp antes de multiplicar. Otros casos: multiplicador 5.15, rechazo de 4 evaluadores y de 11 piezas, reproducibilidad independiente del orden de entrada.
