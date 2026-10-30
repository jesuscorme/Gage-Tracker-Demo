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
