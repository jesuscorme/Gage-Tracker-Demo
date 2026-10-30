# Estudio tipo 1 — Cg/Cgk (`TYPE1`, algoritmo 1.0.0)

## Definición
Capacidad del sistema de medición sobre una pieza de referencia (Robert Bosch GmbH, Booklet No. 10; adoptado en VDA 5). No forma parte del manual AIAG MSA.

## Fórmulas
- Cg = (K/100·T)/(L·s); Cgk = (K/200·T − |x̄ − x_m|)/(L/2·s); K = 20 % y L = 6 por defecto, ambos configurables.
- Prueba t del sesgo (como en `BIAS`) e intervalo de confianza; resolución como % de la tolerancia.
- Carta de lecturas con referencia ± K/2 % de T.

## Limitaciones
Requiere tolerancia. s = 0 → Cg/Cgk indefinidos (advertencia de resolución). Menos de 25 lecturas → advertencia (Booklet 10 pide al menos 25 y prefiere 50; verificar contra su edición). El umbral 1.33 **no** está en el motor: es una plantilla de criterio que la organización debe aprobar. Sin ejemplo publicado disponible: la validación es a mano.

## Validación
| Caso | Esperado (a mano) | Obtenido |
|---|---|---|
| 10 lecturas alrededor de 10.000, T = 0.1: s | √(30·10⁻⁶/9) = 0.0018257 | idéntico (rel. < 1e-9) |
| Cg · Cgk (sesgo 0) | 1.8257 · 1.8257 | idénticos |
| Desplazamiento +0.001 | sesgo 0.001; Cgk = 0.009/(3s) = 1.6432 | idénticos |
| K = 15, L = 4 | Cg = 0.015/(4s) | idéntico |
| Sin tolerancia / lecturas idénticas | rechazo / Cg nulo con advertencia | correcto |
