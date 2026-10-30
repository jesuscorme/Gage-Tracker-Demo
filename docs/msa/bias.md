# Sesgo — muestra independiente (`BIAS`, algoritmo 1.0.0)

## Definición
n mediciones repetidas de una pieza de referencia. sesgoᵢ = xᵢ − referencia; se prueba sesgo promedio = 0 con t bilateral (AIAG MSA 4ª ed., Cap. III, Secc. B).

## Fórmulas
- sesgo = x̄ − ref; s = desviación estándar muestral de las lecturas (repetibilidad); σ_b = s/√n; t = sesgo/σ_b; gl = n − 1.
- IC (1−α): sesgo ± t₍₁₋α/₂, n−1₎·σ_b. Sesgo estadísticamente aceptable si 0 ∈ IC (`bias_significant = false`).
- Opcional: %sesgo respecto a la tolerancia = 100·|sesgo|/T.

## Limitaciones
Supone lecturas independientes y aproximadamente normales. n < 10 → advertencia (AIAG recomienda ≥ 10). s = 0 → t indefinido.

## Validación
| Caso | Esperado (AIAG publicado) | Obtenido |
|---|---|---|
| 15 lecturas, referencia 6.00: sesgo | 0.0067 | 0.006667 |
| s (repetibilidad) | 0.2120 | 0.212020 |
| σ_b | 0.05474 | 0.054743 |
| IC 95 % | −0.1107 … 0.1241 | −0.110746 … 0.124079 |
| p vs `scipy.stats.ttest_1samp` | igualdad | rel. < 1e-10 |
| Sesgo grande (≈ 0.21) | significativo | significativo |
| Lectura no numérica, repetición duplicada, referencia faltante | rechazo | rechazado |
