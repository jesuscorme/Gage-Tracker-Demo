# Manual de usuario

Gage Tracker organiza el control de instrumentos de medición, calibraciones, laboratorio, MSA y casos fuera de tolerancia. Cada pantalla muestra solo lo que su rol permite. El idioma se cambia con **ES / EN** en la barra superior.

## Primeros pasos

1. Inicie sesión con su correo y contraseña. Tras 5 intentos fallidos la cuenta se bloquea 15 minutos; el administrador puede darle un enlace para restablecerla.
2. Si pertenece a varias organizaciones, elíjala en la barra superior.
3. En **Mi cuenta** puede cambiar su contraseña, elegir el idioma de reportes y cerrar la sesión en todos sus dispositivos.

## Tablero ejecutivo

- Muestra indicadores de instrumentos, calibraciones, laboratorio, MSA, OOT, patrones y competencias.
- Se filtra por planta, departamento, tipo, estado, responsable y periodo, con el botón **Aplicar**. Cada indicador abre su listado de origen.
- Las cifras se calculan sobre la misma población filtrada y coinciden con los listados.

## Instrumentos

- **Instrumentos → + Nuevo**: datos del instrumento, frecuencia y campos personalizados de su organización.
- El **estado** se calcula a partir del vencimiento (Calibrado / Por vencer / Vencido) o del estado controlado (Fuera de servicio, En calibración, Inactivo). Un instrumento no disponible no puede usarse en mediciones ni en estudios MSA.
- En el expediente del instrumento: datos generales, calibraciones, MSA y OOT, documentos e historial. **Transferir** cambia el responsable o la ubicación con un motivo.

## Calibraciones y verificaciones

Flujo: planificar → solicitar → programar → ejecutar → capturar As Found / As Left → enviar a revisión → revisión técnica → aprobación → liberación.
- Ejecutar, revisar y aprobar requieren autorizaciones personales vigentes; quien ejecuta no puede revisar ni aprobar.
- Las correcciones de lecturas reemplazan a la lectura original, que se conserva.
- Al liberar, se actualiza el vencimiento del instrumento. Si el As Found salió fuera de tolerancia, se abre un **caso OOT**.

## Laboratorio

**Solicitud** → aprobación con fecha comprometida → **orden de trabajo** → programación (técnico autorizado y equipos disponibles) → ejecución y captura de mediciones → **informe de medición** PDF emitido por un revisor autorizado.

## MSA

1. **MSA → + Nuevo estudio**: método, característica, instrumento, diseño (operadores, piezas, repeticiones, tolerancia, etc.).
2. Pestaña **Datos**: captura fila por fila, pegado desde Excel o importación de archivo. La sección *Validación del diseño* dice qué falta.
3. Pestaña **Resultados** → **Calcular** (requiere la autorización `MSA_EVALUATION`). Verá indicadores, componentes, ANOVA, gráficas, la evaluación contra los criterios aprobados y la verificación de reproducibilidad.
4. **Enviar a revisión** → el revisor registra la conclusión y aprueba.
5. Pestaña **Reportes**: emite el PDF en el idioma de su interfaz.

Sin criterios aprobados, el resultado es solo estadístico: no constituye una aceptación.

## OOT

Cada caso muestra:
- el instrumento restringido y su estado previo;
- el análisis retrospectivo: periodo afectado, mediciones, órdenes, estudios y lecturas;
- los registros manuales (lotes, envíos) y la evaluación del impacto de cada registro;
- las acciones y el flujo de revisión, aprobación y cierre.

La liberación del instrumento requiere una calibración aceptable posterior a la detección y un aprobador autorizado.

## Reportes

**Reportes**: elija el reporte, los filtros y **Generar** para ver la vista previa. Descárguelo en **PDF**, **XLSX** o **CSV**; el documento lleva el identificador del reporte, la organización, la planta, quién lo generó y la fecha. Cada descarga queda registrada.

## Cumplimiento y auditoría

Muestra la matriz de evidencias por proceso y cláusula, los pendientes, las aprobaciones, los certificados y el expediente por instrumento, exportable a Excel. Gage Tracker **no certifica** a la organización: organiza la evidencia.

## Uso en tableta o móvil

Las pantallas principales (tablero, instrumentos, solicitudes, órdenes, reportes, cumplimiento) se adaptan a 390 px de ancho sin desplazamiento horizontal de la página. Las tablas anchas se desplazan dentro de su recuadro.
