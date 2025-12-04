# **Estado — Fase 1 (Motor de Reservas) Completada**

Este documento resume el estado actual del sistema tras completar la Fase 1. Se eliminan instrucciones históricas de entorno y despliegue para evitar contenido obsoleto. Para detalles de negocio y políticas, consultar `docs/Telensor_Engine.md`.

## **Arquitectura Implementada**

- **Motor (Puro)**: `telensor_engine/engine/engine.py` implementa álgebra de intervalos (intersecciones, resta y empaquetado de slots).
- **Adaptador/API (FastAPI)**: `telensor_engine/main.py` expone endpoints y delega la lógica de negocio al módulo `telensor_engine/api/adapter.py`.
- **Capa de Datos Simulada**:
  - `mock_db.py`: servicios, horarios y ocupaciones simuladas.
  - `mock_state.py`: memoria persistente en ejecución para reservas y bloqueos, con verificaciones de conflicto y operaciones atómicas.

## **Endpoints Vigentes**

- `POST /api/v1/disponibilidad` → Director: `buscar_disponibilidad`, Gerente: `gestionar_busqueda_disponibilidad`.
- `POST /api/v1/reservas` → Director: `crear_reserva`, Gerente: `gestionar_creacion_reserva` (doble chequeo anti-colisión y validación derivada por filtros de solicitud: `empleado_id`/`equipo_id`).
- `POST /api/v1/bloqueos` → Director: `crear_bloqueo`, Gerente: `gestionar_creacion_bloqueo` (cascada de resolución, reasignación en mismo slot, fallback conservador y marcación `PENDIENTE_REAGENDA`).

## **Políticas Clave**

- **Ventana de Servicio (`service_window_policy`)**: `start_only` y `full_slot` (vigentes; ver Telensor_Engine.md §9).
- **Derivación por Filtros**: sin política explícita; la búsqueda se deriva por los filtros presentes. Con `empleado_id`, el pool se restringe al empleado. Con `equipo_id`, el pool se restringe al equipo y se preserva cuando aplica. Sin filtros, pool general con balanceo por carga. Ver Telensor_Engine.md §16.
- **Excepciones y Bloqueos**: modelo unificado gestionado por el Adaptador (`build_total_blockings`). Las reservas existentes en memoria se consideran bloqueos operativos.

## **Pruebas y Concurrencia**

- Suite de pruebas pasa con éxito (incluye disponibilidad, políticas, bloqueos y anti-colisión).
- Concurrencia: inserción protegida por `Lock` en `mock_state` y doble chequeo en la creación de reservas.

## **Registro de Símbolos**

- `docs/code_registry.json` mantiene el inventario de clases, funciones y endpoints activos. No se eliminan entradas; las obsoletas se marcan como `deprecated`.

## **Notas de Operación**

- La validación y manejo de errores en API mapea problemas de negocio a HTTP 400/409 sin exponer información sensible.
- La disponibilidad se calcula en un eje continuo de minutos absolutos y se traduce desde/hacia UTC en el Adaptador.
