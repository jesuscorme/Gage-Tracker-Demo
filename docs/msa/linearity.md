# Linealidad (`LINEARITY`, algoritmo 1.0.0)

## Definición
g piezas de referencia a lo largo del rango, m lecturas cada una. Se ajusta por mínimos cuadrados el sesgo individual contra el valor de referencia: sesgo = a·ref + b (AIAG MSA 4ª ed., Cap. III, Secc. B).

## Fórmulas
- a = Σ(x − x̄)(y − ȳ)/Σ(x − x̄)²; b = ȳ − a·x̄; s = √(Σ(y − ŷ)²/(g·m − 2)).
- t_a = |a|/(s/√Sxx); t_b = |b|/(s·√(1/(g·m) + x̄²/Sxx)); gl = g·m − 2.
- Bandas de confianza: ŷ(x₀) ± t₍₁₋α/₂₎·s·√(1/(g·m) + (x₀ − x̄)²/Sxx), evaluadas en cada referencia.
- Aceptable estadísticamente si la recta sesgo = 0 está dentro de las bandas en todo el rango estudiado (`zero_line_within_bands`). También se reportan pendiente, intercepto, R², p de pendiente e intercepto y %linealidad = 100·|a|.

## Limitaciones
Una referencia por pieza (inconsistencias se rechazan); se requieren ≥ 2 referencias distintas. Advertencia si hay menos de 5 piezas o menos de 10 lecturas por pieza.

## Validación
| Caso | Esperado (AIAG publicado) | Obtenido |
|---|---|---|
| Sesgo promedio por pieza (ref 2, 4, 6, 8, 10) | 0.491667, 0.125, 0.025, −0.291667, −0.616667 | idénticos (abs. < 1e-6) |
| Pendiente · intercepto | −0.131667 · 0.736667 | −0.131667 · 0.736667 |
| R² | 0.71 | 0.714318 |
| Conclusión | la recta 0 no queda dentro de las bandas → problema de linealidad | `zero_line_within_bands = false`, pendiente significativa |
| Pendiente y p vs `scipy.stats.linregress` | igualdad | rel. < 1e-8 |
