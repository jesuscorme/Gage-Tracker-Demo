# GAGE TRACKER
## Plan maestro de desarrollo por fases para Claude Code

**Producto:** Gage Tracker — Metrology Management System  
**Industria objetivo:** Automotriz / IATF 16949  
**Tipo de despliegue:** Híbrido (SaaS Cloud + instalación privada)  
**Documento:** Plan de implementación técnica y funcional  
**Versión:** 1.0  
**Fecha:** 29 de octubre de 2026

---

## Estado de implementación

**Última actualización:** 2026-10-29 · **Avance global estimado:** ≈ 18 % · Detalle: `docs/PROGRESS_REPORT_01.md`

| Fase | Estado | Terminado | Parcial / pendiente |
|---|---|---|---|
| 0 · Descubrimiento | ✅ Terminada | Línea base, ADRs, roadmap | — |
| 1 · Fundaciones | ✅ Terminada (con pendientes no bloqueantes) | Monolito modular, config por ambiente, PostgreSQL + Alembic, Organization/Plant/Department/User, RBAC (13 permisos, 5 roles), auth JWT, contexto multi-tenant + alcance por planta, audit trail append-only, errores centralizados, logging JSON, health checks, layout/navegación, selector ES/EN, Docker (sin probar), docs de instalación | OIDC, rate limiting, cookie httpOnly, RLS, validar Docker |
| 2 · Gage Management | 🟡 Parcial (~65 %) | Catálogo de tipos, CRUD con baja lógica, Gage ID único por organización, especificaciones, asignación, frecuencia/fechas, 6 estados con reglas y liberación autorizada, búsqueda/filtros, expediente, historial de estado, auditoría, dashboard inicial | Documentos/adjuntos, exportación, unicidad configurable, asignaciones, vistas guardadas, concurrencia optimista, revisión de cierre |
| 3 – 12 | ⏳ No iniciadas | — | — |

---

## 1. Objetivo del proyecto

Construir Gage Tracker, una plataforma integral para administrar los recursos de medición, calibraciones, verificaciones, estudios MSA y la operación de laboratorio de metrología. El producto debe proporcionar trazabilidad, control operativo, evidencia documental, análisis estadístico y mecanismos de integración con los sistemas y equipos del cliente.

Este plan está organizado para ejecutarse con Claude Code en entregas pequeñas y verificables. Cada fase define:

- Objetivo y alcance.
- Funcionalidades y entregables.
- Criterios de aceptación.
- Pruebas obligatorias.
- Prompt de ejecución para Claude Code.
- Condiciones para avanzar a la siguiente fase.

**Regla de ejecución:** Claude debe trabajar únicamente en la fase solicitada, inspeccionar primero el repositorio y su estado actual, conservar lo que ya funciona y no reescribir módulos completos sin una razón técnica documentada.

---

## 2. Decisiones de producto confirmadas

Estas decisiones se consideran requisitos del proyecto y no deben volver a cuestionarse durante la implementación, salvo que el propietario del producto solicite un cambio.

| Área | Decisión |
|---|---|
| Despliegue | Híbrido: SaaS Cloud e instalación privada |
| Operación de laboratorio | Integral: solicitudes, programación, órdenes de trabajo, técnicos, inspecciones, reportes, seguimiento y capacidad |
| Ingesta de datos | Captura manual, Excel/CSV, conexión con equipos y API |
| MSA | Soporte para múltiples metodologías |
| Configuración | Avanzada: campos, formularios, workflows, aprobaciones, reportes y reglas configurables |
| Mercado | Industria automotriz y organizaciones con sistemas de calidad exigentes |
| Enfoque arquitectónico | Modular, multi-tenant y preparado para despliegue Cloud/Private |

### 2.1 Alcance funcional

1. Dashboard.
2. Gage Management.
3. Calibration Management.
4. MSA Management.
5. Laboratory Operations.
6. Standards Management.
7. OOT & Impact Analysis.
8. Competency Management.
9. Compliance & Audit.
10. Integrations & Data.
11. Administration & Platform Configuration.

### 2.2 Decisiones técnicas aún no ratificadas

El siguiente stack es una propuesta inicial, no una decisión irrevocable. Claude debe validar el estado real del repositorio antes de introducir tecnologías nuevas.

| Capa | Propuesta inicial |
|---|---|
| Frontend | Next.js, React, TypeScript |
| UI | Tailwind CSS |
| Backend | Python + FastAPI |
| Base de datos | PostgreSQL |
| ORM / migraciones | SQLAlchemy + Alembic |
| Estadística | NumPy + SciPy |
| Gráficas | Plotly |
| Cache / colas | Redis y Celery o alternativa equivalente |
| Archivos | Almacenamiento S3-compatible |
| Autenticación | OIDC/OAuth2 |
| Empaquetado | Docker |

**Instrucción:** no migrar un proyecto existente a este stack solo por alinearse con esta tabla. Primero evaluar el código existente, justificar la arquitectura y proponer cualquier cambio importante.

### 2.3 Dos decisiones operativas que se implementarán de forma configurable

Para evitar bloquear el inicio, la plataforma debe diseñarse para soportar:

- Calibraciones externas.
- Calibraciones internas.
- Verificaciones de rutina.

La habilitación de cada flujo debe poder configurarse por organización o planta. La diferencia entre calibración y verificación debe conservarse en los datos, reportes y workflows.

Para equipos, diseñar una arquitectura de conectores extensibles. La implementación física se hará por etapas: primero importación/captura y una interfaz de adaptadores; después conectores específicos para equipos digitales, CMM y otros fabricantes.

---

## 3. Principios de desarrollo obligatorios

1. **Modularidad:** iniciar con un monolito modular bien delimitado; no introducir microservicios prematuramente.
2. **Multi-tenancy:** toda entidad de negocio debe quedar asociada a una organización y, cuando aplique, a una planta.
3. **Aislamiento:** impedir que un usuario consulte o modifique información de otra organización.
4. **Trazabilidad:** registrar quién hizo qué, cuándo, sobre qué entidad y qué cambió.
5. **Reproducibilidad estadística:** guardar datos originales, metodología, versión del algoritmo, parámetros, reglas de aceptación y resultados.
6. **Configurabilidad controlada:** permitir personalización sin convertir reglas críticas en código arbitrario editable por usuarios.
7. **Seguridad por defecto:** permisos mínimos, validación en backend, secretos fuera del repositorio y manejo seguro de archivos.
8. **Calidad:** pruebas unitarias, integración y extremo a extremo para los flujos críticos.
9. **Evolución de esquema:** toda modificación de base de datos debe tener migración versionada.
10. **Evidencia:** documentos, certificados, reportes y registros deben tener metadatos, control de acceso y trazabilidad.
11. **No inventar cumplimiento:** el software debe facilitar evidencia y control; no declarar automáticamente que una organización cumple o está certificada.
12. **Compatibilidad híbrida:** evitar dependencias exclusivas de un proveedor cloud cuando exista una alternativa portable razonable.

---

## 4. Arquitectura funcional objetivo

### 4.1 Módulos

| Módulo | Responsabilidad principal |
|---|---|
| Dashboard | Indicadores, alertas, vencimientos y actividad |
| Gage Management | Expediente, identificación, ubicación, estado e historial del instrumento |
| Calibration Management | Plan, solicitudes, ejecución, resultados, certificados, revisión y liberación |
| MSA Management | Configuración, ejecución, cálculos, criterios y reportes MSA |
| Laboratory Operations | Solicitudes de servicio, agenda, órdenes, asignación, ejecución, informes y capacidad |
| Standards Management | Patrones, masters, referencias, certificados y vigencias |
| OOT & Impact Analysis | Fuera de tolerancia, bloqueo, evaluación retrospectiva e impacto |
| Competency Management | Competencias, autorizaciones, formación y evidencias |
| Compliance & Audit | Evidencias, trazabilidad, consultas y preparación de auditoría |
| Integrations & Data | Captura, importaciones, conectores, API y monitoreo |
| Administration | Organizaciones, plantas, usuarios, roles, configuración y catálogos |

### 4.2 Flujos principales

**Ciclo de vida del instrumento**

Alta → clasificación → asignación → uso controlado → calibración/verificación → revisión → liberación → seguimiento → baja.

**Calibración**

Planificación → solicitud → programación → ejecución → captura As Found → evaluación → ajustes/reparación si aplica → captura As Left → certificado/evidencia → revisión técnica → aprobación → actualización de vigencia.

**MSA**

Configuración del estudio → selección de metodología → captura/importación de datos → validación del diseño → cálculo → evaluación contra criterios → revisión → reporte → conservación de datos y versión de cálculo.

**Operación de laboratorio**

Solicitud → revisión → aprobación → programación → orden de trabajo → asignación de técnico → ejecución → revisión técnica → informe → entrega/cierre.

**OOT e impacto**

Detección → evaluación de condición → restricción/bloqueo del equipo → identificación de uso desde última condición aceptable → evaluación de producto/proceso → acciones y disposición → aprobación de cierre.

---

## 5. Plan maestro por fases

## Fase 0 — Descubrimiento del repositorio y definición técnica

**Objetivo:** conocer el estado real del proyecto y establecer una línea base antes de modificar código.

**Trabajo**
- Inspeccionar estructura, tecnologías, dependencias y convenciones.
- Identificar funcionalidades existentes, deuda técnica y componentes reutilizables.
- Revisar configuración, variables de entorno, scripts, pruebas y despliegue.
- Confirmar el stack real y documentar diferencias frente a la propuesta.
- Elaborar mapa de módulos y límites de dominio.
- Identificar riesgos y decisiones que requieren aprobación.

**Entregables**
- `docs/PROJECT_BASELINE.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- `docs/IMPLEMENTATION_ROADMAP.md`
- Inventario de módulos y estado actual.
- Lista priorizada de riesgos y pendientes.

**Criterios de aceptación**
- El proyecto puede ejecutarse localmente o se documentan claramente los bloqueos.
- Se conoce qué existe y qué falta.
- No se han realizado refactorizaciones destructivas.
- Las decisiones técnicas relevantes están justificadas.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 0 del plan maestro de Gage Tracker. Inspecciona el repositorio completo antes de modificar archivos. No implementes funcionalidades todavía. Documenta el stack real, arquitectura actual, módulos existentes, scripts, pruebas, configuración, riesgos y brechas contra el alcance objetivo. No reemplaces tecnologías ni reestructures el proyecto. Genera los entregables indicados en la Fase 0 y termina con un resumen de hallazgos, archivos creados/modificados y recomendaciones. Si el repositorio está vacío, propón una estructura inicial y justifícala, pero espera aprobación antes de construirla.

---

## Fase 1 — Fundaciones de plataforma

**Objetivo:** crear la base segura y extensible de la aplicación.

**Trabajo**
- Estructura modular del backend y frontend.
- Configuración por ambiente.
- Conexión a PostgreSQL y migraciones.
- Modelo de Organization y Plant.
- Usuarios, autenticación y sesiones.
- Roles y permisos (RBAC).
- Contexto de tenant y aislamiento de datos.
- Audit trail base.
- Manejo de errores, logging y health checks.
- Layout general, navegación y selector de idioma preparado.
- Docker y configuración de desarrollo.

**Entregables**
- Aplicación ejecutable.
- Migraciones iniciales.
- Autenticación y autorización funcionales.
- Aislamiento multi-tenant probado.
- Navegación base.
- Documentación para instalación local.

**Criterios de aceptación**
- Un usuario autenticado solo accede a organizaciones/plantes autorizadas.
- Los endpoints protegidos validan permisos en backend.
- Se registra la actividad crítica.
- La base de datos se crea desde cero mediante migraciones.
- La aplicación arranca siguiendo instrucciones documentadas.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 1. Usa la línea base aprobada y conserva las convenciones del repositorio. Implementa la fundación modular, configuración por ambiente, PostgreSQL/migraciones, Organization, Plant, usuarios, autenticación, RBAC, contexto multi-tenant, audit trail, logging, health checks, layout y navegación. Prioriza seguridad en backend: nunca dependas únicamente de ocultar elementos en frontend. Incluye pruebas automatizadas para autenticación, autorización y aislamiento entre tenants. No avances a módulos de metrología. Actualiza la documentación y entrega instrucciones reproducibles para levantar el sistema.

---

## Fase 2 — Gage Management

**Objetivo:** administrar el expediente y ciclo de vida de los instrumentos de medición.

**Trabajo**
- Catálogo configurable de tipos de instrumentos.
- Alta, edición, consulta y baja lógica.
- Identificación única por organización/planta según regla configurable.
- Fabricante, modelo, número de serie, rango, resolución y exactitud.
- Departamento, ubicación, responsable y criticidad.
- Frecuencia, última fecha y próxima fecha.
- Estados: Calibrated, Due Soon, Overdue, Out of Service, In Calibration, Inactive.
- Historial de cambios y documentos asociados.
- Búsqueda, filtros, vistas y exportación básica.

**Entregables**
- CRUD de instrumentos.
- Modelo de datos y migraciones.
- Vistas de listado y expediente.
- Historial y documentos.
- Pruebas de reglas de estado.

**Criterios de aceptación**
- No se permiten duplicados según el alcance de unicidad definido.
- Los estados se calculan de forma consistente y documentada.
- Un equipo fuera de servicio o vencido no aparece como disponible para uso normal.
- Toda modificación crítica queda auditada.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 2: Gage Management. Implementa el expediente del instrumento, catálogos configurables, estados, historial, documentos, filtros y pruebas. Define claramente qué estados son calculados y cuáles son controlados por workflow; evita que una edición manual pueda liberar un equipo bloqueado. Respeta multi-tenancy y permisos. No implementes aún el flujo completo de calibración ni MSA. Entrega migraciones, endpoints, interfaz, pruebas y documentación.

---

## Fase 3 — Calibration Management

**Objetivo:** controlar calibraciones externas/internas y verificaciones de rutina con trazabilidad.

**Trabajo**
- Plan de calibración y calendario de vencimientos.
- Solicitudes y órdenes de calibración.
- Tipos de actividad diferenciados: calibración externa, calibración interna y verificación de rutina.
- Proveedor/laboratorio, método, patrón y trazabilidad.
- Resultados As Found y As Left.
- Tolerancia, incertidumbre cuando aplique y resultado.
- Certificado y anexos.
- Revisión técnica, aprobación y liberación.
- Reprogramación, cancelación y excepciones autorizadas.
- Actualización del estado y siguiente vencimiento del instrumento.
- Notificaciones configurables.

**Entregables**
- Flujo de calibración de punta a punta.
- Gestión de certificados y evidencias.
- Calendario y alertas.
- Historial de calibraciones por instrumento.
- Pruebas del workflow y reglas de estado.

**Criterios de aceptación**
- No se puede liberar una calibración sin los datos/evidencias requeridos por su configuración.
- As Found y As Left se conservan como registros separados.
- La aprobación queda identificada con usuario y fecha.
- La actividad no se confunde entre calibración y verificación.
- El historial previo no se sobrescribe.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 3: Calibration Management. Implementa el flujo de planificación, solicitud, ejecución, resultados As Found/As Left, patrón, proveedor/laboratorio, certificado, revisión, aprobación y liberación. Soporta los tres tipos de actividad como categorías distintas y configurables. Conserva registros históricos inmutables o versionados; no sobrescribas resultados aprobados. Implementa permisos por etapa, audit trail, notificaciones básicas y pruebas de transición de estados. No implementes todavía OOT completo ni MSA.

---

## Fase 4 — Standards Management y Competency Management

**Objetivo:** controlar patrones de referencia y la autorización/competencia del personal.

**Trabajo — Standards Management**
- Catálogo de patrones, bloques patrón, masters, instrumentos de referencia y patrones ambientales.
- Identificación, rango, resolución, ubicación y custodio.
- Certificados, vigencias, historial y estado.
- Relación entre patrón y calibración/actividad donde fue utilizado.
- Alertas de vencimiento y restricción por estado.

**Trabajo — Competency Management**
- Perfiles de técnicos, verificadores y evaluadores MSA.
- Matriz de competencias.
- Formación y evaluaciones.
- Autorizaciones por actividad, equipo o método.
- Evidencias y fechas de vigencia.
- Validación de autorización antes de asignar o aprobar tareas.

**Entregables**
- Catálogo y expediente de patrones.
- Matriz de competencias.
- Reglas de autorización.
- Vínculos con calibraciones y órdenes de trabajo.

**Criterios de aceptación**
- Una actividad puede identificar qué patrón y qué persona participaron.
- No se asignan actividades restringidas a personal sin autorización vigente.
- Se alerta sobre patrones y competencias vencidas.
- La trazabilidad histórica se conserva aunque cambie el estado actual.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 4. Implementa Standards Management y Competency Management integrados con los módulos existentes. Relaciona patrones con actividades de calibración y registra personal ejecutor/revisor/aprobador. Implementa autorizaciones por tipo de actividad y vigencia. No inventes requisitos normativos: haz que las reglas sean configurables y documenta las decisiones de producto. Añade migraciones, interfaz, permisos y pruebas de integración.

---

## Fase 5 — Laboratory Operations

**Objetivo:** administrar la operación integral del laboratorio de metrología.

**Trabajo**
- Catálogo de servicios.
- Solicitudes internas/externas.
- Revisión, cotización o aprobación cuando aplique.
- Agenda y capacidad.
- Órdenes de trabajo.
- Asignación de técnico y equipo.
- Priorización y fechas compromiso.
- Ejecución y captura de resultados.
- Inspección dimensional y registro de características.
- Reportes de medición.
- Revisión técnica y entrega.
- Cierre, tiempos, historial y métricas operativas.
- Identificación QR/código de barras como capacidad opcional.

**Entregables**
- Portal de solicitudes.
- Calendario y tablero de trabajo.
- Órdenes de trabajo.
- Captura de mediciones.
- Generación y control de informes.
- Métricas de carga y tiempos.

**Criterios de aceptación**
- Una solicitud puede seguirse desde su creación hasta el cierre.
- Cada orden identifica servicio, responsable, equipo, fechas y estado.
- Las mediciones y reportes conservan trazabilidad.
- La agenda evita asignaciones incompatibles según reglas configuradas.
- Los usuarios solo ven y ejecutan las tareas autorizadas.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 5: Laboratory Operations. Construye el flujo integral de solicitudes, revisión, programación, órdenes de trabajo, asignación de técnicos, ejecución, captura dimensional, revisión, informe y cierre. Integra Gage, Standards y Competency Management sin duplicar entidades. Implementa calendario, estados, capacidad y métricas básicas. Mantén los flujos configurables y auditables. Añade pruebas de extremo a extremo para el ciclo de una solicitud. No implementes aún conectividad directa con instrumentos.

---

## Fase 6 — MSA Management y motor estadístico

**Objetivo:** construir un motor MSA confiable, reproducible, versionado y separado de la interfaz.

**Metodologías objetivo**
- Gage R&R Crossed.
- Gage R&R Nested.
- ANOVA y Average & Range, según diseño aplicable.
- Attribute Agreement Analysis.
- Bias.
- Linearity.
- Stability.
- Type 1 Study.

**Trabajo**
- Configurador de estudio y diseño experimental.
- Participantes, piezas, repeticiones, operadores y secuencia.
- Captura manual e importación.
- Validación del diseño y datos faltantes/duplicados.
- Motor de cálculo separado de API y UI.
- Resultados, componentes de variación e indicadores propios de cada método.
- Gráficas adecuadas al método.
- Motor de criterios de aceptación configurable.
- Versionado de algoritmo, metodología y reglas.
- Reporte y conservación de datos originales.
- Casos de referencia y pruebas estadísticas.

**Reglas críticas**
- No aplicar una fórmula única a todos los diseños.
- No mezclar metodologías ni cambiar criterios silenciosamente.
- Guardar entradas originales y parámetros usados.
- Identificar la versión del motor y de las reglas en cada resultado.
- Validar resultados contra casos de referencia documentados antes de liberar.
- La referencia AIAG MSA y los requisitos específicos del cliente deben tratarse según la edición/licencia/documentación aplicable; no inventar tablas ni criterios.

**Entregables**
- Motor estadístico independiente.
- API de estudios MSA.
- Interfaz de configuración y resultados.
- Reportes y gráficas.
- Suite de validación estadística.
- Documento metodológico por estudio.

**Criterios de aceptación**
- Cada método solo acepta diseños válidos para ese método.
- Los resultados son reproducibles con los mismos datos, parámetros y versiones.
- Los casos de referencia pasan dentro de tolerancias definidas.
- Un cambio de algoritmo genera nueva versión y no altera resultados históricos.
- Los criterios de aceptación pueden configurarse con control de cambios y permisos.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 6: MSA Management. Antes de programar, define contratos de entrada/salida y metodología para cada tipo de estudio. Separa el motor estadístico del backend web y de la interfaz. Implementa primero una metodología completa y validada, luego las demás en incrementos, sin simular cálculos que todavía no estén implementados. Incluye pruebas con datasets de referencia, validación de diseños, manejo de datos inválidos, versionado del algoritmo y versionado de criterios. No inventes valores de aceptación ni reproduzcas tablas protegidas: permite configurar criterios documentados por el cliente y registra su fuente. Entrega un informe de validación técnica por metodología.

---

## Fase 7 — OOT & Impact Analysis

**Objetivo:** administrar resultados fuera de tolerancia y evaluar el posible impacto sobre producto y proceso.

**Trabajo**
- Registro de evento OOT.
- Vínculo al instrumento y certificado/actividad que lo detectó.
- Bloqueo o restricción del instrumento.
- Identificación de última condición aceptable.
- Periodo potencialmente afectado.
- Vínculo con procesos, líneas, características, lotes y órdenes.
- Evaluación de riesgo y disposición.
- Reinspección, contención y acciones.
- Escalamiento y notificación.
- Aprobación y cierre.
- Historial y reportes.

**Entregables**
- Workflow OOT.
- Registro de impacto y decisiones.
- Integración con Gage y Calibration.
- Tablero de casos abiertos y vencidos.
- Evidencia de cierre.

**Criterios de aceptación**
- Un OOT puede restringir el instrumento conforme a reglas autorizadas.
- Se puede identificar la ventana temporal investigada y su fundamento.
- Las decisiones y aprobaciones son trazables.
- El cierre exige completar las actividades configuradas.
- No se afirma que el sistema determine automáticamente el impacto sin datos suficientes.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 7: OOT & Impact Analysis. Implementa el registro de eventos, restricción del equipo, identificación de última condición aceptable, análisis retrospectivo, relaciones con proceso/producto/lote y seguimiento de acciones. Si no existen integraciones para conocer lotes o producto, crea relaciones y captura manual configurables; no inventes datos. Mantén la decisión de riesgo y disposición bajo aprobación humana autorizada. Incluye pruebas de bloqueo, escalamiento, trazabilidad y cierre.

---

## Fase 8 — Integrations & Data

**Objetivo:** habilitar intercambio de datos seguro y escalable con archivos, instrumentos y sistemas empresariales.

**Trabajo**
- Importador Excel/CSV con plantillas.
- Mapeo de columnas y validación previa.
- Reporte de errores por fila.
- Procesamiento idempotente y registro de importación.
- API versionada y documentación OpenAPI.
- API keys/OAuth según caso de uso.
- Webhooks y eventos de integración.
- Arquitectura de adaptadores para equipos.
- Edge Connector para instalaciones privadas/redes locales.
- Cola de trabajos, reintentos y monitoreo.
- Integraciones ERP/MES/QMS por contratos definidos.

**Entregables**
- Importación Excel/CSV.
- API documentada.
- Registro y monitoreo de integraciones.
- Contrato de adaptadores.
- Diseño del Edge Connector.
- Al menos un conector de demostración o simulador.

**Criterios de aceptación**
- Los archivos inválidos no generan datos parciales silenciosos.
- Las importaciones se pueden auditar y rastrear.
- Las API validan identidad, permisos, tenant y esquema.
- Los reintentos no duplican transacciones.
- Los adaptadores no escriben directamente en tablas internas sin pasar por servicios de dominio.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 8: Integrations & Data. Implementa importación Excel/CSV robusta, API versionada, autenticación, autorización, idempotencia, logs, webhooks y arquitectura de adaptadores. Define el contrato del Edge Connector para despliegue privado, pero no afirmes compatibilidad con un fabricante sin un adaptador probado. Crea un simulador de dispositivo para probar el flujo extremo a extremo. Documenta los contratos OpenAPI y los formatos soportados. Añade pruebas de seguridad, errores y reintentos.

---

## Fase 9 — Platform Configuration, Compliance & Audit

**Objetivo:** permitir configuración avanzada y facilitar la preparación de auditorías.

**Trabajo — Platform Configuration**
- Campos personalizados tipados.
- Formularios configurables.
- Workflows y matrices de aprobación.
- Reglas de negocio configurables.
- Catálogos por organización/planta.
- Plantillas de notificación.
- Reportes configurables.
- Permisos por módulo, acción y alcance.
- Versionado y aprobación de cambios de configuración.

**Trabajo — Compliance & Audit**
- Matriz de evidencia por proceso/cláusula.
- Búsqueda de registros y certificados.
- Expediente de auditoría.
- Exportación de evidencia.
- Historial de cambios.
- Reportes de brechas y pendientes.

**Criterios de aceptación**
- Los cambios de configuración quedan versionados y auditados.
- No se permite que campos o reglas configurables omitan controles de seguridad.
- La matriz de evidencia es orientativa y configurable; no declara certificación.
- Los reportes muestran origen, fecha y responsable de los datos.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 9. Implementa configuración avanzada de campos, formularios, workflows, aprobaciones, catálogos y reportes con versionado y permisos. Construye Compliance & Audit como una capa de consulta/evidencia sobre los módulos existentes, sin duplicar datos maestros. Distingue controles del producto de requisitos normativos que deben validar el cliente. Añade pruebas para cambios de configuración, permisos y exportación de evidencia.

---

## Fase 10 — Dashboard, reportes ejecutivos y experiencia de usuario

**Objetivo:** consolidar la experiencia del usuario y ofrecer visibilidad ejecutiva y operativa.

**Trabajo**
- KPIs de instrumentos por estado.
- Vencimientos próximos y vencidos.
- Calibraciones pendientes.
- Estudios MSA abiertos y resultados.
- Solicitudes y órdenes de laboratorio.
- Casos OOT abiertos.
- Patrones y competencias próximos a vencer.
- Filtros por organización, planta, área y periodo.
- Reportes operativos y ejecutivos.
- Exportación PDF/Excel cuando aplique.
- Diseño responsive.
- Español e inglés.
- Accesibilidad y consistencia visual.

**Criterios de aceptación**
- Los KPIs coinciden con los datos fuente y filtros aplicados.
- No se muestran cifras de ejemplo como si fueran reales.
- Las gráficas identifican periodo, unidad y alcance.
- Los reportes respetan permisos y aislamiento multi-tenant.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 10. Integra dashboards y reportes usando datos reales de los módulos existentes. No hardcodees KPIs ni datos ficticios en vistas productivas. Implementa filtros por alcance autorizado, consistencia entre tarjetas y gráficas, exportaciones necesarias, responsive y selector español/inglés. Incluye pruebas de agregaciones, filtros y permisos. Documenta cualquier indicador cuya definición dependa de configuración.

---

## Fase 11 — Seguridad, pruebas integrales y preparación de producción

**Objetivo:** validar el sistema completo y preparar una versión candidata a producción.

**Trabajo**
- Pruebas unitarias, integración y E2E.
- Pruebas de aislamiento multi-tenant.
- Revisión RBAC y escalamiento de privilegios.
- Validación de cargas y archivos.
- Revisión de secretos y dependencias.
- Pruebas de rendimiento y concurrencia.
- Backups y restauración.
- Observabilidad, logs y alertas.
- Migraciones y rollback.
- Docker images y despliegue Cloud/Private.
- Manuales de instalación, operación y recuperación.
- UAT con usuarios clave.
- Matriz de defectos y liberación.

**Criterios de aceptación**
- No hay defectos críticos o altos abiertos sin aceptación formal de riesgo.
- Se demuestra restauración de respaldo.
- Se demuestra instalación en entorno privado.
- Se demuestra despliegue cloud.
- Los flujos críticos tienen pruebas automatizadas.
- Existe procedimiento de soporte, actualización y recuperación.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 11. No agregues funcionalidades nuevas salvo correcciones necesarias. Realiza una revisión integral de seguridad, permisos, aislamiento, integridad de datos, rendimiento, dependencias, backups, restauración, observabilidad y despliegues Cloud/Private. Ejecuta la suite de pruebas y documenta resultados reales; no marques pruebas como exitosas si no se ejecutaron. Corrige defectos, registra riesgos residuales y prepara checklist de release y UAT.

---

## Fase 12 — Liberación y evolución

**Objetivo:** liberar el producto de forma controlada y establecer el ciclo de mejora.

**Trabajo**
- Release candidate y versionado semántico.
- Notas de versión.
- Migración de datos inicial.
- Onboarding de organización y plantas.
- Capacitación y manuales.
- Soporte y gestión de incidencias.
- Telemetría de uso con privacidad.
- Backlog priorizado.
- Plan de conectores adicionales.
- Revisión de métricas de adopción y estabilidad.

**Criterios de aceptación**
- Aprobación de UAT.
- Documentación de operación y soporte.
- Procedimiento de actualización y rollback.
- Plan de mantenimiento y evolución.

**Prompt para Claude Code**
> Ejecuta únicamente la Fase 12. Prepara la liberación basada en los resultados aprobados de pruebas y UAT. Genera notas de versión, documentación de instalación/actualización, checklist de operación, plan de soporte y backlog de evolución. No declares el producto listo si existen criterios de aceptación incumplidos; enumera claramente los bloqueos.

---

## 6. Modelo de datos: dominios y entidades principales

El modelo físico definitivo debe diseñarse durante Fase 0/1 y evolucionar con migraciones. Esta lista es el mapa inicial, no un DDL definitivo.

### Plataforma
- `organizations`
- `plants`
- `departments`
- `users`
- `roles`
- `permissions`
- `user_organization_memberships`
- `user_plant_memberships`
- `audit_events`
- `attachments`
- `notifications`
- `configuration_versions`

### Metrología
- `gages`
- `gage_types`
- `gage_status_history`
- `gage_assignments`
- `calibration_plans`
- `calibration_activities`
- `calibration_results`
- `calibration_points`
- `calibration_certificates`
- `calibration_reviews`

### Patrones y competencias
- `standards`
- `standard_certificates`
- `standard_usage_records`
- `personnel_profiles`
- `competencies`
- `competency_records`
- `authorizations`

### Laboratorio
- `service_catalog`
- `service_requests`
- `work_orders`
- `work_order_assignments`
- `work_order_operations`
- `measurement_characteristics`
- `measurement_results`
- `measurement_reports`
- `lab_schedules`

### MSA
- `msa_studies`
- `msa_study_designs`
- `msa_participants`
- `msa_parts`
- `msa_trials`
- `msa_raw_measurements`
- `msa_calculation_runs`
- `msa_results`
- `msa_acceptance_policies`
- `msa_algorithm_versions`

### OOT e integración
- `oot_cases`
- `oot_impact_records`
- `oot_actions`
- `integration_connections`
- `import_jobs`
- `import_job_rows`
- `device_adapters`
- `device_events`
- `api_clients`
- `webhook_subscriptions`

### Configuración y auditoría
- `custom_field_definitions`
- `custom_field_values`
- `workflow_definitions`
- `workflow_instances`
- `approval_steps`
- `business_rules`
- `report_definitions`

**Reglas de modelado**
- Incluir `organization_id` en entidades tenant-owned y `plant_id` cuando el alcance sea por planta.
- Definir claves foráneas, índices y restricciones únicas con el alcance correcto.
- Usar `created_at`, `created_by`, `updated_at`, `updated_by` en entidades que lo requieran.
- Mantener historial para estados y decisiones críticas.
- Evitar almacenar resultados calculados sin conservar los datos y parámetros que los originaron.
- Usar borrado lógico solo cuando sea apropiado; no borrar físicamente evidencia histórica.
- No guardar certificados ni archivos binarios directamente en tablas relacionales; almacenar referencias seguras y metadatos.

---

## 7. Arquitectura lógica de referencia

```text
Usuarios
   |
   v
Frontend Web (Next.js / React)
   |
   v
API / Backend
   |
   +-- Identity & Tenant Context
   +-- Gage Management
   +-- Calibration Management
   +-- MSA Management
   +-- Laboratory Operations
   +-- Standards Management
   +-- Competency Management
   +-- OOT & Impact Analysis
   +-- Integrations & Data
   +-- Compliance & Audit
   |
   +--------------------+
   |                    |
   v                    v
PostgreSQL          Job Queue / Workers
   |                    |
   v                    v
Audit / History     Imports / Reports / Notifications
   |
   v
Object Storage (certificados, evidencias, reportes)

Equipos / ERP / MES / QMS
   |
   v
Integration Gateway / Edge Connector
   |
   v
API y servicios de dominio
```

### Despliegue híbrido

**Cloud SaaS**
- Plataforma compartida con aislamiento lógico por tenant.
- Servicios centrales, base de datos administrada y almacenamiento de objetos.
- Backups, monitoreo y actualizaciones controladas.

**Private deployment**
- Mismo código y artefactos de contenedor.
- Instalación en infraestructura del cliente o entorno privado acordado.
- Configuración de base de datos, almacenamiento, identidad y respaldos del entorno.
- Actualizaciones versionadas y procedimiento de migración.

**Edge Connector**
- Servicio local opcional para comunicación con instrumentos o redes aisladas.
- Comunicación saliente segura hacia la plataforma.
- Cola local y reintentos controlados cuando no exista conectividad.
- Adaptadores por fabricante/protocolo; cada uno requiere pruebas con el equipo real.

---

## 8. Estrategia de ejecución con Claude Code

### 8.1 Cómo ejecutar cada fase

1. Mantener este archivo en el repositorio como `docs/MASTER_IMPLEMENTATION_PLAN.md`.
2. Abrir Claude Code en la raíz del repositorio.
3. Proporcionar el prompt de la fase actual.
4. Pedir que inspeccione el estado antes de editar.
5. Revisar el plan de cambios que Claude propone.
6. Autorizar la implementación de esa fase.
7. Ejecutar pruebas y revisar los resultados.
8. Hacer commit cuando los criterios de aceptación se cumplan.
9. Actualizar el estado de la fase en este documento.
10. Solo entonces iniciar la fase siguiente.

### 8.2 Prompt maestro reutilizable

Usar este prompt antes de cada fase, junto con el prompt específico de la fase:

> Trabaja como arquitecto de software y desarrollador senior del producto Gage Tracker. Sigue `docs/MASTER_IMPLEMENTATION_PLAN.md` y ejecuta exclusivamente la fase que te indique. Primero inspecciona el repositorio y el estado de la implementación. No repitas trabajo ya completado. No elimines ni reemplaces funcionalidades existentes sin justificación y aprobación. Antes de modificar, presenta un plan breve de archivos, cambios, dependencias y riesgos. Implementa en incrementos pequeños. Mantén arquitectura modular, multi-tenancy, RBAC, audit trail, migraciones y pruebas. No inventes requisitos normativos, criterios estadísticos ni compatibilidades con equipos. Si falta información, registra el supuesto y usa una solución configurable cuando sea razonable. Ejecuta las pruebas afectadas y reporta exactamente cuáles pasaron, fallaron o no se ejecutaron. Actualiza documentación y termina con: alcance completado, archivos modificados, migraciones, pruebas, riesgos, pendientes y recomendación para la siguiente fase. No avances automáticamente a otra fase.

### 8.3 Prompt de cierre de fase

> Realiza una revisión de cierre de la fase actual contra sus criterios de aceptación en `docs/MASTER_IMPLEMENTATION_PLAN.md`. No agregues nuevas funcionalidades. Inspecciona el diff, ejecuta las pruebas relevantes, busca regresiones, problemas de seguridad, inconsistencias de datos y documentación desactualizada. Corrige solo defectos dentro del alcance de esta fase. Entrega una tabla de criterios con estado PASS / FAIL / NOT TESTED y evidencia concreta. Si hay criterios FAIL o NOT TESTED, no declares la fase terminada.

### 8.4 Política de commits

Recomendación de commits por fase:
- `phase-0: document repository baseline`
- `phase-1: establish platform foundation`
- `phase-2: implement gage management`
- `phase-3: implement calibration workflows`
- Continuar con el mismo patrón para cada fase.

No mezclar en un mismo commit cambios de varias fases salvo que exista una dependencia urgente y documentada.

---

## 9. Orden recomendado y entregas demostrables

| Hito | Fases | Resultado demostrable |
|---|---|---|
| M0 | 0 | Diagnóstico y arquitectura aprobada |
| M1 | 1 | Login, tenants, plantas, permisos y navegación |
| M2 | 2 | Inventario de instrumentos operativo |
| M3 | 3 | Ciclo de calibración trazable |
| M4 | 4 | Patrones y competencias integrados |
| M5 | 5 | Operación integral del laboratorio |
| M6 | 6 | Estudios MSA calculados y reproducibles |
| M7 | 7 | Gestión OOT e impacto |
| M8 | 8 | Importaciones y API; base para conectores |
| M9 | 9 | Configuración avanzada y evidencia de auditoría |
| M10 | 10 | Dashboard y reportes consolidados |
| M11 | 11–12 | Candidato a producción y liberación |

**Prioridad del MVP funcional:** Fases 0 a 5.  
**Capacidad diferenciadora avanzada:** Fases 6 a 9.  
**Preparación comercial y producción:** Fases 10 a 12.

---

## 10. Definition of Done global

Una fase se considera terminada solo si:

- El alcance está implementado y documentado.
- Los criterios de aceptación se verificaron.
- Las pruebas relevantes se ejecutaron y sus resultados son conocidos.
- Las migraciones funcionan desde una base limpia y desde la versión anterior.
- Se validaron permisos y aislamiento multi-tenant cuando aplique.
- No hay errores críticos conocidos sin documentar.
- No existen secretos o datos sensibles en el repositorio.
- La interfaz maneja estados de carga, vacío y error.
- Los logs y eventos críticos son útiles y no exponen información sensible.
- Se actualizaron instrucciones y documentación.
- Se registraron decisiones, limitaciones y pendientes.

---

## 11. Riesgos que deben vigilarse

| Riesgo | Mitigación |
|---|---|
| Alcance demasiado amplio | Entregar por fases y mantener el MVP enfocado |
| Sobreingeniería con microservicios | Monolito modular hasta que exista una necesidad medible |
| Fuga entre tenants | Pruebas sistemáticas de aislamiento y autorización en backend |
| Cálculos MSA incorrectos | Casos de referencia, revisión metodológica y versionado |
| Criterios de aceptación no confirmados | Configuración controlada y fuente documentada |
| Integraciones de equipos no homogéneas | Adaptadores independientes y validación por modelo/protocolo |
| Evidencia histórica modificable | Auditoría, versionado y restricciones de actualización |
| Personalización difícil de mantener | Configuración declarativa y límites claros; evitar código arbitrario |
| Dependencia de proveedor cloud | Contenedores, PostgreSQL y almacenamiento compatible |
| Confusión entre calibración y verificación | Tipos de actividad y workflows diferenciados |

---

## 12. Instrucción final para el equipo

Gage Tracker debe construirse como una plataforma de metrología industrial, no como un simple calendario de calibraciones. La prioridad es establecer una base confiable de datos, trazabilidad y permisos; después construir los procesos de metrología y laboratorio; y finalmente incorporar estadística avanzada, integraciones y personalización.

**No sacrificar exactitud, trazabilidad ni seguridad para acelerar una demostración.** Los datos de ejemplo deben identificarse como demostrativos, y los cálculos estadísticos deben estar validados antes de presentarse como resultados técnicos.
