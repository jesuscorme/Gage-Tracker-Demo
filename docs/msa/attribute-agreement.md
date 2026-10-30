# Concordancia por atributos (`ATTRIBUTE_AGREEMENT`, algoritmo 1.0.0)

## Definición
Evalúa sistemas de medición que clasifican en categorías nominales. Solo usa estadísticos categóricos: ninguna fórmula de variables continuas.

## Diseño de datos
`{operator, part, trial, category}`; categorías declaradas (≥ 2); referencia conocida por pieza (opcional); categorías de aceptación/rechazo (opcional, para efectividad).

## Indicadores
- % de acuerdo con IC exacto de Clopper-Pearson (α configurable): dentro del evaluador (todas las repeticiones iguales), evaluador vs referencia (todas las repeticiones iguales a la referencia), entre evaluadores (todas las calificaciones de la pieza iguales), todos vs referencia.
- κ de Cohen a partir de tablas cruzadas: cada par de evaluadores (emparejando pieza y repetición) y cada evaluador vs referencia (todas las repeticiones). Enfoque de tablas cruzadas de AIAG MSA 4ª ed., Cap. III, Secc. C.
- κ de Fleiss: dentro del evaluador (repeticiones como calificadores) y entre evaluadores (todas las calificaciones de la pieza).
- Efectividad, tasa de falsos rechazos (*false alarm*) y de aceptaciones erróneas (*miss rate*) por evaluador (AIAG MSA 4ª ed., Cap. III, Secc. C).
- Matrices de concordancia (evaluador × referencia, evaluador × evaluador).

## Limitaciones
Diseño completo requerido (cada evaluador califica cada pieza en cada repetición). κ indefinido cuando la concordancia esperada es 1 (se devuelve nulo con advertencia). Sin piezas de rechazo en la referencia, la tasa de *miss* es indefinida.

## Validación
| Caso | Esperado | Obtenido |
|---|---|---|
| Ejemplo Fleiss (1971): 10 sujetos, 14 evaluadores, 5 categorías | κ = 0.210 | 0.209931 (igual a statsmodels con rel. < 1e-12) |
| Ejemplo 2×2 de Cohen (20/5/10/15) | κ = 0.4 | 0.4 |
| 10 tablas 3×3 aleatorias vs statsmodels `cohens_kappa` | igualdad | rel. < 1e-10 |
| Caso construido 3 evaluadores × 6 piezas × 2 rep.: acuerdos dentro 6/5/6, vs referencia 6/4/5, entre 3, efectividad B 75 %, miss 33.3 %, falsa alarma 16.7 % | conteo a mano | idénticos; IC de 5/6 igual a `scipy.stats.beta` |
| Categoría no declarada / sin referencia de una pieza | rechazo | rechazado |
