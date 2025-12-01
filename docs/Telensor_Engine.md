# **Sistema de reservación — v1**

Este documento describe la lógica de negocio para un sistema de reservación avanzado.

Este documento explica el **QUÉ** (la lógica de negocio). El documento API_Telensor.md explica el **CÓMO** (la implementación de la API).

## **1\. Marcos de tiempo (Las 5 Capas)**

1. **Horario de trabajo del empleado**: Ventana donde el empleado puede trabajar (ej. \[540, 1020\] o 9:00-17:00).  
2. **Horario de operación del equipo**: Ventana donde el equipo puede ser operado.  
3. **Horario de atención del negocio** (DEPRECADO): Ventana máxima donde se pueden **iniciar** servicios (ej. \[480, 1200\] o 8:00-20:00). Se mantiene por compatibilidad, pero su función operativa se reemplaza por **Excepciones** (cierres globales, feriados, reuniones).  
4. **Horario de atención del servicio**: Ventana opcional que restringe un servicio específico (ej. "Tinte" solo de \[600, 840\] o 10:00-14:00).  
5. **Slot del servicio**: Bloque continuo con **buffer previo \+ servicio \+ buffer posterior**.

## **2\. Modelado de tiempo (Minutos Absolutos \- Eje Continuo)**

A diferencia de versiones anteriores, el motor ya no opera en un solo día (0-1440). Ahora opera en un **eje de tiempo de minutos absolutos y continuos**.

* La API (el "Adaptador") es responsable de traducir las fechas/horas del mundo real a este eje.  
* **Ejemplo (Turno Nocturno):**  
  * Petición: Buscar de 20:00 del Día 1 a 04:00 del Día 2\.  
  * El "Día 1" va de 0 a 1439\.  
  * El "Día 2" va de 1440 a 2879\.  
  * La API le pedirá al motor que busque en la ventana base \[1200, 1680\].  
    * 1200 \= 20 \* 60 (20:00 del Día 1\)  
    * 1680 \= (24 \* 60\) \+ (4 \* 60\) (04:00 del Día 2\)

El motor solo ve números (1200, 1680\) y no sabe nada de "días".

## **3\. Cómo obtener los intervalos libres (Álgebra de Intervalos)**

El método sigue siendo el mismo, pero ahora opera en el eje continuo (números \> 1440 son válidos).

1. Define la **ventana base** (ej. \[1200, 1680\]).  
2. Define los **ocupados** (ej. \[1300, 1330\]).  
3. Libres \= Restar(Ventana Base, Ocupados).  
   * Resultado: \[1200, 1300), \[1330, 1680\)

## **4\. Búsqueda del horario (Estrategia Eje Continuo)**

1. **Paso 0: Construcción del Eje (El Adaptador/API)**  
   * La API recibe la petición (ej. 20:00 Día 1 a 04:00 Día 2).  
   * La API define la ventana base: \[1200, 1680\].  
   * La API carga los ocupados del Día 1: ej. \[1300, 1330\] (21:40-22:10).  
   * La API carga los ocupados del Día 2: ej. \[60, 120\] (01:00-02:00).  
   * **Paso Clave (Desfase):** La API "desfasa" los ocupados del Día 2 sumándoles 1440 (minutos del primer día).  
     * Ocupado Día 2 se convierte en: \[60+1440, 120+1440\] \-\> \[1500, 1560\].  
   * La API crea la lista final de ocupados\_totales \= \[\[1300, 1330\], \[1500, 1560\]\].  
   * Estos son los datos que se pasan al motor.  
2. **Paso 1: Definir Horario de Atención Efectivo**  
   * El motor calcula la intersección entre la Ventana Base (del Paso 0\) y el horario específico del servicio (si existe).  
3. **Paso 2, 3, 4: Calcular Libres Comunes**  
   * El motor calcula los libres del empleado, los libres del equipo y la intersección (libres\_comunes) de forma normal, usando los datos del eje continuo.  
   * Ej: Libres Comunes \= \[1200, 1300), \[1330, 1500), \[1560, 1680\)  
4. **Paso 5: Iterar y Generar Opciones ("Empaquetado")**  
   * Arranque alineado: el primer intento dentro de cada libre común se fija en `max(libre_ini, atencion_efectiva_ini - buffer_previo)` para garantizar que el inicio del **servicio** ocurra dentro de la ventana efectiva.  
   * Iteración por "salto de slot": se avanza sumando `duracion_total_slot` (sin rejilla fija de 10 minutos).  
   * Validaciones: Regla 1 (inicio de servicio dentro de atención efectiva) y Regla 2 (slot completo dentro del límite duro de trabajo del empleado).  
   * Nota: el `buffer_previo` puede caer fuera del inicio de atención efectiva; se garantiza que `inicio_servicio` ∈ `[atencion_efectiva_ini, atencion_efectiva_fin)`.  
   * Ejemplo: si `atencion_efectiva_ini = 480` y `buffer_previo = 10`, el primer intento se alinea a `inicio_pre = 470` (servicio a `480`).  
  * Política de Ventana de Servicio (`service_window_policy`):  
    - `start_only` (por defecto): el horario de atención del servicio limita únicamente el inicio del slot; el fin puede caer fuera si empleado/equipo siguen libres.  
    - `full_slot`: el horario de atención del servicio limita inicio y fin del slot; se recortan los libres por la ventana del servicio antes del empaquetado.  
  * Política de Ventana de Negocio: Eliminada. La ventana de negocio siempre limita el INICIO del servicio (start constraint). Los cierres y recortes operativos se gestionan mediante **Excepciones**.
5. **Paso 6: De-traducción (El Adaptador/API)**  
   * El motor devuelve los minutos absolutos (ej. inicio\_pre \= 1560).  
   * La API recibe este número y lo traduce de vuelta al mundo real:  
     * ¿1560 es mayor que 1439 (último min del Día 1)? **Sí.**  
     * minutos\_dia\_2 \= 1560 \- 1440 \= 120\.  
     * 120 minutos \= 02:00.  
     * Resultado para el cliente: "Día 2, 02:00".

## **5\. Gestión de Citas y Conflictos**

Esta sección define cómo manejar excepciones cuando una cita existente no puede realizarse. La lógica de la "Cascada de Resolución" sigue siendo la misma que en versiones anteriores, pero ahora opera sobre los **intervalos de minutos absolutos** del eje continuo.

### **1\. Modelado de Inactividad y Conflictos**

* **La Inactividad es un "Ocupado" más**: La "inactividad" (ej. enfermedad de un empleado, mantenimiento de un equipo) no es un estado booleano. Se modela de forma idéntica al resto del sistema: como un **nuevo "intervalo ocupado"** que se añade al calendario del empleado o equipo (en la tabla ocupaciones para esa fecha\_base).  
* **Excepciones del Negocio/Servicio**: Los cierres globales (feriados, reuniones) y restricciones puntuales de servicio se modelan como **Excepciones**. El Adaptador las agrega a la lista de **bloqueos totales** antes de llamar al motor, manteniendo el motor puro en álgebra de intervalos.  
* **Detección de Conflicto**: Cuando se añade un nuevo intervalo de inactividad, el sistema debe:  
  1. Buscar todas las citas futuras asignadas a ese empleado/equipo.  
  2. Verificar si el *slot completo* (minuto absoluto) de alguna cita se solapa con el nuevo intervalo de inactividad.  
  3. Toda cita que se solape se marca como "**EN CONFLICTO**" y debe ser resuelta.

### **2\. Cascada de Resolución de Conflictos**

El sistema debe intentar resolver el conflicto automáticamente siguiendo esta jerarquía:

**A. Reasignar (Prioridad 1: Mismo Horario, Mínimo Cambio)**

* **Objetivo**: Mantener el horario del cliente intacto.  
* **Lógica**: El sistema busca una solución de "cambio mínimo" para el *mismo slot de tiempo absoluto exacto*.  
* **Caso 1: Falla el Empleado (E1)**  
  * *Cita original*: \[E1, EQ1, Slot\_Absoluto\]  
  * *El sistema busca*: \[\*\*E2\*\*, EQ1, Slot\_Absoluto\]  
  * (Es decir: Otro Empleado libre \+ Mismo Equipo \+ Mismo Slot)  
* **Caso 2: Falla el Equipo (EQ1)**  
  * *Cita original*: \[E1, EQ1, Slot\_Absoluto\]  
  * *El sistema busca*: \[E1, \*\*EQ2\*\*, Slot\_Absoluto\]  
  * (Es decir: Mismo Empleado \+ Otro Equipo libre \+ Mismo Slot)  
* **Resultado**: Si se encuentra un match, la cita se actualiza. Esta acción puede ser automática, requiriendo solo una notificación al cliente (ej. "Ahora te atenderá Ana en lugar de Juan").

**B. Reagendar (Prioridad 2: Nuevo Horario)**

* **Activación**: Si "Reasignar" (mismo horario) falla.  
* **Lógica**: El sistema libera el slot en conflicto y realiza una **búsqueda de disponibilidad completamente nueva** (usando la Estrategia Eje Continuo).  
* **Resultado**: Esto implica un **nuevo horario** y potencialmente un nuevo empleado y/o equipo.  
* **Acción Requerida**: Esta acción **requiere confirmación del cliente**, ya que su horario cambia. El sistema debe *proponer* los nuevos slots libres encontrados.

**C. Cancelar (Última opción)**

* **Activación**: Si el cliente no acepta la "reagenda" o si el cliente lo solicita directamente.  
* **Lógica**: El sistema simplemente elimina el "intervalo ocupado" que representaba la cita de los calendarios del empleado y equipo originales.

## **6\. Horarios por Día (dia_semana) y Ventana Efectiva**

La API calcula el `dia_semana` a partir de la `fecha_base` de la solicitud y usa ese valor para cargar horarios diarios específicos:

- **HorarioServicio**: si existe para el `dia_semana`, se establece en el dominio como `horario_atencion_especifico` del servicio. El motor intersecta la ventana base con este intervalo para definir la **ventana efectiva de atención**.
- **HorarioEmpleado**: si existe para el `dia_semana`, se usa como `horario_trabajo` del empleado; si no existe, se **hace fallback** al intervalo general (ventana base) para ese empleado en el día.

Efectos sobre la búsqueda:

- La **ventana efectiva** de búsqueda se reduce por la intersección entre: ventana base (eje continuo) ∩ `horario_atencion_especifico` del servicio (si presente).  
- Los **libres del empleado** se calculan dentro de su `horario_trabajo` del día, manteniendo la coherencia con el eje continuo.  
- Si un empleado no tiene horario para ese día, el sistema no bloquea la búsqueda, pero su disponibilidad se limita por la ventana base.

Ejemplo rápido:

- `dia_semana = 2` (Miércoles); Servicio A tiene `HorarioServicio[2] = [600, 840]` (10:00–14:00).  
- Ventana base: `[480, 1200]` (8:00–20:00).  
- Ventana efectiva: `[600, 840]` (intersección).  
- Con `service_window_policy = start_only`, se valida que el inicio del servicio caiga dentro de `[600, 840]`. Con `full_slot`, además se recortan los libres por `[600, 840]` para forzar que el fin del slot también caiga dentro.  
- Empleado E1 tiene `HorarioEmpleado[2] = [540, 1020]` (9:00–17:00): sus libres se calculan dentro de `[540, 1020]` pero el motor sólo considera la intersección con la ventana efectiva del servicio.
\
## **7\. Modelo de Excepciones y Agregación de Bloqueos (Fase 1)**

- **Disponibilidad Bruta**: `servicio ∩ empleado ∩ equipo` en el eje continuo de minutos absolutos.  
- **Bloqueos Totales**: Unión de ocupaciones (reservas existentes, inactividad de empleado, mantenimiento de equipo) + **Excepciones** (feriados, cierres globales, restricciones puntuales de servicio).  
- **Agregador del Adaptador**: `telensor_engine.api.adapter.build_total_blockings` traduce fechas al eje, combina bloqueos por empleado, por equipo y globales, y los aplica antes del empaquetado.  
- **Ventaja**: El motor permanece puro (álgebra de intervalos), mientras que el Adaptador configura contexto operativo y políticas.
\
### **Patrón Director/Gerente**

- **Director (API)**: `telensor_engine.main.buscar_disponibilidad` valida la entrada HTTP y delega la lógica de negocio.  
- **Gerente (Adaptador)**: `telensor_engine.api.adapter.gestionar_busqueda_disponibilidad` realiza la carga del escenario, aplica políticas (`ServiceWindowPolicy`), agrega bloqueos, calcula ventanas efectivas y empaqueta los slots usando `encontrar_slots`.  
- **Beneficio**: Reutilización de la lógica en Fase 2 (Cascada de Resolución de Conflictos) sin duplicar código y con mejor testabilidad.
\
### **Intersección de Capacidades (Selección Inteligente de Equipo)**

- **Objetivo**: Asignar automáticamente el equipo correcto cuando se solicita disponibilidad para un `empleado_id` sin especificar `equipo_id`.
- **Definición**: Cada Servicio puede declarar `equipos_compatibles` y cada Empleado define `equipos_asignados`.  
- **Algoritmo**:
  - Modo empleado: se cruza respetando el orden declarado por el servicio y se selecciona el primer equipo coincidente.
  - **Modo general (Pool)**: se prueban TODOS los equipos en la intersección servicio∩empleado para cada candidato de slot; se agregan los resultados y se deduplican por horario `(inicio, fin)` ignorando el equipo. Si más de un equipo habilita el mismo horario, se selecciona uno de forma determinista (manteniendo balanceo por carga de empleado).
  - Implementación:
    - Utilidad: `telensor_engine.api.adapter.seleccionar_equipo_por_interseccion(servicio, empleado)`.
    - Utilidad (intersección múltiple): `telensor_engine.api.adapter.obtener_equipos_compatibles_para_empleado(servicio, empleado)`.
    - Camino empleado sin equipo: el Gerente autoasigna el equipo y calcula disponibilidad conjunta Empleado ∩ Equipo.
    - Estricto: si el servicio declara `equipos_compatibles` y no existe intersección con los `equipos_asignados` del empleado, ese empleado no genera slots (no hay fallback a "solo servicio").
    - **Efecto en Respuesta**: `equipo_id_asignado` se completa con el equipo seleccionado en cada slot.

### **Fuente de Excepciones**

- Las excepciones deben definirse en `docs/test_scenarios.json` (para pruebas) o en la fuente de datos externa (p. ej., Directus) para producción.
- El endpoint no acepta excepciones en el cuerpo de la solicitud; se agregan vía escenario o capa de datos.

## **8. Creación de Reservas (Fase 2, Sprint 1)**

- **Endpoint**: `POST /api/v1/reservas`  
  - Director: `telensor_engine.main.crear_reserva`  
  - Gerente: `telensor_engine.api.adapter.gestionar_creacion_reserva`  
  - Entrada: `SolicitudReserva` (servicio_id, empleado_id, inicio_slot, fin_slot, scenario_id, service_window_policy).  
  - Salida: `ReservaCreada` (reserva_id, servicio_id, empleado_id, equipo_id?, inicio_slot, fin_slot, creada_en, version).

- **Doble Chequeo Anti-colisión**:  
  1) Chequeo inmediato de conflicto en memoria (`mock_state.has_conflict`). Si existe, se devuelve 409.  
  2) Confirmación de validez del slot con el Gerente de disponibilidad (misma política de ventana, escenario y buffers). Si el slot deja de ser válido, se devuelve 400.

- **Bloqueos por Reservas**:  
  `build_total_blockings` agrega las reservas existentes en memoria como bloqueos del empleado y del equipo. La disponibilidad se actualiza inmediatamente tras una creación.

## **9. Política de Servicio: start_only vs full_slot**

- `start_only` (por defecto):  
  - Restringe únicamente el inicio del servicio por la ventana del servicio.  
  - El fin del slot puede exceder la ventana si el empleado/equipo están libres.  
  - Útil para servicios con buffers que pueden caer fuera de la ventana de atención.

- `full_slot`:  
  - Restringe inicio y fin del slot por la ventana del servicio.  
  - Se recortan los libres por la ventana del servicio antes del empaquetado.  
  - Útil para servicios que deben concluir dentro de la ventana (operación estricta).

- **Validación y Tests**:  
  - Se incluye un test `test_manager_start_only_allows_end_past_service_window` que valida que `start_only` permite que el fin del slot exceda la ventana de servicio en el escenario `svc_window_edge`.  
  - Para creación de reservas, se mantiene la misma política utilizada en la búsqueda para coherencia.

## **10. Pruebas de Carrera y Concurrencia**

- **Objetivo**: garantizar que la creación de reservas es segura bajo acceso concurrente y que el sistema devuelve `409 Conflict` cuando otro proceso ya creó el mismo slot.  
- **Mecánica**: `telensor_engine.mock_state` implementa un `Lock` que protege la sección crítica de inserción; además, el Gerente (`gestionar_creacion_reserva`) realiza un doble chequeo: conflicto inmediato y validación de disponibilidad.

- **Pruebas incluidas**:  
  - `test_concurrent_reservas_same_slot_only_one_success_api`: simula múltiples `POST /api/v1/reservas` concurrentes contra el mismo slot y valida que solo una petición obtiene `201 Created` y el resto `409 Conflict`.  
  - `test_concurrent_add_reserva_lock_enforced_unit`: dispara llamadas concurrentes a `mock_state.add_reserva` y verifica que el `Lock` evita duplicados, resultando en una sola reserva creada.

- **Resultados**: la suite de pruebas de carrera pasa y confirma la robustez del mecanismo anti-colisión en API y a nivel de estado en memoria.

## **11. Asignación de Servicios y Equipos por Empleado**

- **Objetivo**: garantizar que la búsqueda de disponibilidad solo considere empleados calificados para el servicio solicitado y con permiso para el equipo indicado.
- **Fuente de Datos (Simulada)**: `telensor_engine/mock_db.py` ahora define por empleado:
  - `servicios_asignados`: lista de IDs de servicios que puede realizar.
  - `equipos_asignados`: lista de IDs de equipos que puede usar.
- **Consulta de Horarios (Modo Estricto)**: `get_horarios_empleados(fecha, servicio_id?, equipo_id?)` aplica filtros opcionales y retorna únicamente empleados que cumplan ambos filtros (si están presentes). Si los filtros dejan la lista vacía, retorna **lista vacía**.
- **Gerente de Disponibilidad**: `telensor_engine/api/adapter.py` en `gestionar_busqueda_disponibilidad` pasa explícitamente `servicio_id` y `equipo_id` a `get_horarios_empleados`, asegurando que la disponibilidad solo se calcule para empleados válidos.
- **Efecto en la API**: al solicitar disponibilidad con `servicio_id` y opcionalmente `equipo_id`, los slots devueltos siempre asignarán empleados calificados y equipos permitidos, reforzando la integridad operativa.
 - **Escenarios con Asignaciones**: `docs/test_scenarios.json` puede definir por empleado `servicios_asignados` y `equipos_asignados`. Cuando estas claves existen en el escenario cargado, el Gerente aplica filtrado estricto sobre los empleados del escenario para respetar dichas asignaciones. Si dichas claves no están presentes, se mantiene compatibilidad sin filtrado adicional.

## **12. Estado: `equipo_ids` deprecado**


## **13. Política de Búsqueda (search_mode) — Estricta**

- Todo servicio debe operar bajo un `search_mode` explícito. Si no se define, el sistema aplica el valor por defecto `general` de forma estricta.
- Modos admitidos:
 - `employee`: la solicitud debe incluir `empleado_id` y no debe incluir `equipo_id` (estricto). Si el servicio requiere equipo (`equipos_compatibles`), se autoasigna por intersección; si no hay intersección válida, se responde 400.
  - `equipment`: la solicitud debe incluir `equipo_id` y no debe incluir `empleado_id` (estricto).
    - Si el servicio declara `equipos_compatibles`, el `equipo_id` solicitado debe pertenecer a esa lista; de lo contrario, la API responde `400 Bad Request` con mensaje "Equipo no compatible para el servicio".
  - `general`: no se permite enviar `empleado_id` ni `equipo_id`. El sistema opera en modo Pool y, si el servicio requiere equipo (`equipos_compatibles`), autoasigna por intersección con `equipos_asignados` del empleado; empleados sin intersección no generan slots.
- Implementación: `telensor_engine.api.adapter.gestionar_busqueda_disponibilidad` aplica esta validación y mapea errores a HTTP 400 en `telensor_engine.main.buscar_disponibilidad`.
- Escenarios: `docs/test_scenarios.json` incluye `search_mode` para todos los servicios relevantes (p. ej., `night_shift` usa `employee`; los demás usan `general`).

## **14. Balanceo de Carga — Menos Cargado**

- Objetivo: cuando hay múltiples empleados libres para el mismo horario, seleccionar el empleado con **menos minutos ocupados** ese día.
- Alcance:
  - Modo `equipment` (búsqueda por equipo): agrupa resultados por `(inicio_slot, fin_slot, equipo_id)` y elige el candidato con menor carga diaria.
  - Modo `general` (Pool): agrupa por `(inicio_slot, fin_slot)` ignorando el equipo y elige un único candidato por horario. Si el servicio requiere equipo, la autoasignación respeta la intersección estricta por empleado, pero la competencia sigue siendo "slot por slot".
- Cómputo de carga: utilidad `_sumar_minutos_interseccion(intervalos, ventana_dia)` suma los minutos ocupados del empleado dentro de la ventana `[offset_dia, offset_dia+1440)`, contemplando cruce de medianoche.
- Implementación: en el Gerente, tras empaquetar slots por empleado, se realiza una selección por grupo para retornar un único slot óptimo por horario.
- Escenario de prueba: `load_balance_demo` define dos empleados (`E_A`, `E_B`) con cargas distintas (60 vs 15 minutos) para validar que el sistema selecciona `E_B` en horarios compartidos.

## **15. Logging y Métricas**

- Logging: el Gerente emite trazas al seleccionar equipos por intersección y al aplicar la política de ventana. Se recomienda añadir métricas de validación (rechazos por `search_mode`) para auditoría.
- Seguridad: entradas HTTP estrictamente validadas; no se exponen detalles internos en errores.
- Rendimiento: el agrupamiento y selección por carga se realiza en memoria y es lineal respecto al número de slots generados.

- El campo `equipo_ids` ya no está soportado en el request de disponibilidad.
- En su lugar, se admite `equipo_id` único o consulta por servicio sin equipo.
- Validación: enviar `equipo_ids` produce `422 Unprocessable Entity` por política estricta `extra = "forbid"` en el modelo Pydantic.
- Logging y métricas: se mantienen para el camino de equipo único y servicio-only.

## **13. Validación de Política de Búsqueda (search_mode)**

- **Propósito**: Asegurar que la API rechace solicitudes que contradigan la naturaleza operativa del servicio.
- **Definición**: Cada Servicio puede declarar `search_mode` con valores:
  - `employee`: el cliente debe elegir un `empleado_id` y no puede enviar `equipo_id`.
  - `equipment`: el cliente debe elegir un `equipo_id` y no puede enviar `empleado_id`.
  - `general`: el cliente no debe elegir recursos específicos; la API opera en modo pool y agrega slots de todos los empleados calificados.
- **Validación (Gerente)**: `gestionar_busqueda_disponibilidad` valida el `search_mode` si está presente en la definición del servicio y en caso de incoherencia levanta `ValueError` con mensaje claro. El Director (`main.buscar_disponibilidad`) lo mapea a `HTTP 400`.
- **Ejecución de Pool (general)**:
  - Si el servicio declara `equipos_compatibles`, la API autoasigna equipo por intersección por empleado y omite empleados sin match.
  - Si el servicio no declara `equipos_compatibles`, la API devuelve slots con `equipo_id_asignado = null`.
- **Compatibilidad**: Para no romper casos existentes, la validación sólo aplica si el servicio define explícitamente `search_mode`. El valor por defecto en escenarios sin esa propiedad es comportamiento previo (sin validación de política).
