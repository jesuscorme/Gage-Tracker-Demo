# Motor estadístico MSA — documentación de métodos y validación

Motor: `backend/app/engine/` (versión del motor **1.0.0**). Independiente de la API y de la base de datos: recibe JSON (`design`, `observations`, `params`) y devuelve JSON (`metrics`, `tables`, `charts`, `intermediate`, `warnings`).

## Estado de las metodologías

| Método (código) | Documento | Algoritmo | Estado | Evidencia de validación |
|---|---|---|---|---|
| GRR cruzado · Promedio y Rango (`GRR_CROSSED_AR`) | [grr-average-range.md](grr-average-range.md) | 1.0.0 | **VALIDADO** | Ejemplo publicado AIAG MSA 4ª ed. reproducido (todos los valores intermedios) |
| GRR cruzado · ANOVA (`GRR_CROSSED_ANOVA`) | [grr-anova-crossed.md](grr-anova-crossed.md) | 1.0.0 | **VALIDADO** | Tabla ANOVA publicada AIAG (SS y gl); statsmodels en 12 diseños aleatorios |
| GRR anidado · ANOVA (`GRR_NESTED_ANOVA`) | [grr-anova-nested.md](grr-anova-nested.md) | 1.0.0 | **VALIDADO** | Cálculo a mano; statsmodels (suma de cuadrados extra) en 8 diseños aleatorios |
| Concordancia por atributos (`ATTRIBUTE_AGREEMENT`) | [attribute-agreement.md](attribute-agreement.md) | 1.0.0 | **VALIDADO** | Ejemplo publicado de Fleiss (κ = 0.210); statsmodels (Cohen y Fleiss); conteo a mano |
| Sesgo (`BIAS`) | [bias.md](bias.md) | 1.0.0 | **VALIDADO** | Ejemplo publicado AIAG reproducido; scipy `ttest_1samp` |
| Linealidad (`LINEARITY`) | [linearity.md](linearity.md) | 1.0.0 | **VALIDADO** | Ejemplo publicado AIAG reproducido; scipy `linregress` |
| Estabilidad (`STABILITY`) | [stability.md](stability.md) | 1.0.0 | **VALIDADO** (sin ejemplo publicado) | Constantes del manual SPC AIAG; límites calculados a mano; 8 criterios con secuencias construidas |
| Estudio tipo 1 (`TYPE1`) | [type1.md](type1.md) | 1.0.0 | **VALIDADO** (sin ejemplo publicado) | Fórmulas Bosch Booklet 10 calculadas a mano; recomputación independiente |

«VALIDADO» significa: las pruebas automatizadas (`backend/tests/test_engine_grr.py`, `test_engine_other.py`, 48 casos) reproducen resultados publicados y/o una implementación independiente, y cubren límites, datos incompletos, diseños inválidos y reproducibilidad. No es una certificación externa del software. Las dos últimas filas no tienen un conjunto de datos publicado con resultados conocidos disponible en este proyecto; su validación es por cálculo independiente.

## Fuentes y limitaciones de las referencias

- **AIAG MSA Reference Manual, 4ª ed. (2010)**: el manual **no está disponible en el equipo de desarrollo**. Los conjuntos de datos AIAG (GRR, sesgo, linealidad) se transcribieron y la transcripción se verificó reproduciendo **todos** los valores intermedios que el manual publica (promedios y rangos por evaluador, R̄, X̄diff, Rp, SS del ANOVA, desviación de repetibilidad, intervalo de confianza del sesgo, sesgo promedio por pieza). Las referencias citan capítulo y sección; **los números de página no se verificaron** contra el texto. Recomendación: confirmar contra la copia controlada de la organización.
- **AIAG SPC Manual, 2ª ed. (2005)**: disponible localmente. Constantes A2, d2, D3, D4, E2 tomadas de Apéndice E, pp. 181-182; criterios de causas especiales de la Tabla II.1, p. 75.
- **Robert Bosch GmbH, Booklet No. 10** (Cg/Cgk): no disponible localmente; se implementan las fórmulas con K y L configurables. Verificar contra la edición vigente.
- **Fleiss (1971)**: ejemplo de 10 sujetos × 14 evaluadores × 5 categorías, κ publicado = 0.210.

## Reglas comunes

- Cada ejecución guarda: datos de entrada exactos (instantánea), huella SHA-256, método, versión del algoritmo y del motor, criterios usados (instantánea), resultados, usuario y fecha. Las filas son de solo inserción (trigger en BD).
- `POST /msa/runs/{id}/verify` recalcula una ejecución histórica con el motor actual sin modificarla y reporta diferencias.
- Los criterios de aceptación **no** están en el motor: los define y aprueba cada organización (versionados, segundo aprobador). Sin criterios aprobados la decisión es `NO_CRITERIA`; si falta un indicador requerido, `INCONCLUSIVE`.
- Un método con estado distinto de VALIDADO nunca produce una decisión de aceptación (`NO_CRITERIA`).
- Varianzas negativas estimadas se truncan a cero y se informa en `warnings`.

## Auditoría técnica previa a la liberación (bloque 4, 2026-10-30)

Para cada método se revisaron diseño, fórmulas, entradas, salidas, datasets de referencia, resultados intermedios, reproducibilidad, gráficas, criterios y versionado:
- Las fórmulas coinciden con la documentación de cada método.
- La validación de diseño rechaza datos faltantes, duplicados e inválidos.
- La salida completa (indicadores, tablas, gráficas e intermedios) se congeló en `tests/msa_golden.json` y la compara `test_engine_regression.py`.
- El versionado se comprobó: algoritmo 1.0.0, huella de los datos, ejecuciones inmutables y endpoint `verify`.

No se modificó ningún resultado histórico ni criterio de aceptación.

| Metodología (encargo) | Código | Implementada | Validada | Lista para producción |
|---|---|---|---|---|
| Gage R&R Crossed | `GRR_CROSSED_AR` / `GRR_CROSSED_ANOVA` | Sí | Sí: ejemplo AIAG publicado + statsmodels | Sí, sujeta a UAT |
| Gage R&R Nested | `GRR_NESTED_ANOVA` | Sí | Sí: cálculo a mano + statsmodels (8 diseños) | Sí, sujeta a UAT |
| ANOVA | `GRR_CROSSED_ANOVA` | Sí | Sí: tabla de SS AIAG + 12 diseños aleatorios | Sí, sujeta a UAT |
| Average & Range | `GRR_CROSSED_AR` | Sí | Sí: todos los intermedios AIAG reproducidos | Sí, sujeta a UAT |
| Attribute Agreement | `ATTRIBUTE_AGREEMENT` | Sí | Sí: ejemplo de Fleiss publicado + statsmodels + conteo a mano | Sí, sujeta a UAT. La variante de detección de señales de AIAG no está implementada |
| Bias | `BIAS` | Sí | Sí: ejemplo AIAG + scipy | Sí, sujeta a UAT |
| Linearity | `LINEARITY` | Sí | Sí: ejemplo AIAG + scipy | Sí, sujeta a UAT |
| Stability | `STABILITY` | Sí | Sí, **sin dataset publicado**: constantes del manual SPC y cálculo a mano | **Condicional**: confirmar con un caso de referencia del cliente durante UAT |
| Type 1 | `TYPE1` | Sí | Sí, **sin dataset publicado**: fórmulas de Bosch Booklet 10 a mano | **Condicional**: confirmar con un caso de referencia (p. ej. software certificado del cliente) durante UAT |

Observaciones:
- Gráficas: se generan para los 8 métodos; la representación en pantalla se verificó en el navegador para GRR (E2E 3), y el PDF de los 8 métodos en español e inglés en `test_engine_regression::test_msa_pdf_report_renders_for_every_method` (16 casos).
- Criterios: hay plantillas para todas las familias. Siempre los aprueba un segundo usuario. Sin criterios no hay decisión.
