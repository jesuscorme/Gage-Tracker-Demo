# Estabilidad (`STABILITY`, algoritmo 1.0.0)

## Definición
Carta de control de una pieza de referencia medida en el tiempo: Individuales/Rango móvil (n = 1) o X̄–R (2 ≤ n ≤ 10).

## Fórmulas (AIAG SPC Manual 2ª ed., Apéndice E, pp. 181-182)
- X̄–R: CL = X̿; límites X̿ ± A2·R̄; carta R: D3·R̄ … D4·R̄; σ = R̄/d2.
- I-MR: CL = x̄; límites x̄ ± E2·MR̄ (E2 = 2.660); MR: UCL = D4(2)·MR̄ = 3.267·MR̄; σ = MR̄/1.128.
- σ de la estadística graficada = (UCL − CL)/3 para las reglas.
- Sesgo en el tiempo = media − referencia (si se declara referencia).

## Reglas de causas especiales (Tabla II.1, p. 75), configurables
1 punto > 3σ · 2 n puntos del mismo lado (7) · 3 n crecientes/decrecientes (6) · 4 n alternando (14) · 5 2 de 3 > 2σ mismo lado · 6 4 de 5 > 1σ mismo lado · 7 n dentro de 1σ (15) · 8 n fuera de 1σ (8). Por defecto activas 1, 2 y 3 (el manual deja la selección al usuario); las longitudes son parámetros.

## Limitaciones
Subgrupos incompletos se rechazan. Menos de 20 subgrupos → límites preliminares (advertencia). No hay un conjunto de datos publicado con resultados en este proyecto: la validación es por cálculo independiente.

## Validación
| Caso | Esperado (a mano) | Obtenido |
|---|---|---|
| I-MR con 10, 12, 11, 13, 12 | CL 11.6; MR̄ 1.5; límites 11.6 ± 3.99; σ = 1.5/1.128; UCL_MR 4.9005 | idénticos |
| X̄–R, subgrupos {1,2,3},{2,3,4},{3,4,5} | CL 3; UCL 3 + 1.023·2; R̄ 2; UCL_R 5.148; σ = 2/1.693 | idénticos |
| Cada criterio 1–8 con secuencias construidas (positivas y negativas) | índice del punto que completa el patrón | idénticos |
| Regla 2 con longitud 9 vs 7 | se activa / no se activa | correcto |
| Regla desconocida o longitud inválida | rechazo | rechazado |
