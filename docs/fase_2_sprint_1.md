# **Fase 2, Sprint 1 — Estado Actual**

Este documento refleja la implementación vigente del Sprint 1 de la Fase 2. Se eliminan referencias históricas (CITEs) y se describe el comportamiento real del sistema.

## **Objetivo**

Implementar la creación de reservas con anti-colisión, memoria persistente en ejecución y confirmación estricta del slot contra la disponibilidad real.

## **Componentes**

- **Memoria en ejecución** (`mock_state.py`):
  - Listas persistentes de `reservas` y `bloqueos`.
  - Operaciones atómicas protegidas por `Lock`.
  - API interna para `add_reserva`, `update_reserva`, `has_conflict`, `add_bloqueo`.

- **Gerente de Disponibilidad** (`api/adapter.py`):
  - Agregación de bloqueos totales desde escenario (`docs/test_scenarios.json`) y memoria (`mock_state`).
  - Cálculo de ventana efectiva por `service_window_policy`.
  - Selección de equipo por intersección estricta con `equipos_asignados`.

- **Director/Endpoints** (`main.py`):
  - `POST /api/v1/reservas` → delega en `gestionar_creacion_reserva`.
  - `POST /api/v1/bloqueos` → delega en `gestionar_creacion_bloqueo`.

## **Flujo de Creación (Doble Chequeo)**

1. Chequeo inmediato de conflicto en memoria (`has_conflict`).
2. Confirmación de slot con `gestionar_busqueda_disponibilidad`, derivando el comportamiento por filtros presentes en la solicitud:
   - Con `empleado_id`: el slot debe coincidir temporalmente y por empleado.
   - Con `equipo_id`: el slot debe coincidir temporalmente y por equipo (se preserva el equipo).
   - Sin filtros: solo coincidencia temporal; recursos pueden variar automáticamente según balanceo de carga.
3. Inserción en memoria con `add_reserva` si ambas validaciones pasan.

## **Bloqueos Operativos y Cascada**

- **Alcances**: `business`, `employee`, `equipment`, `service`.
- **Reglas**:
  - `business`: reservas afectadas → `PENDIENTE_REAGENDA`.
  - Otros alcances: intentar reasignación en el mismo slot excluyendo el recurso bloqueado; si la reserva tiene `equipo_id` (o filtro de equipo), preservar el equipo. Si no hay candidato, fallback conservador a otro empleado elegible; de lo contrario, `PENDIENTE_REAGENDA`.

## **Pruebas de Concurrencia**

- Validan que solo una petición concurrente crea una reserva en el mismo slot (201) y el resto recibe 409.
- El `Lock` del estado y el doble chequeo garantizan consistencia.

## **Estado de Implementación**

- La suite de pruebas integrada pasa con éxito.
- Documentación sincronizada con `docs/Telensor_Engine.md` y `docs/code_registry.json`.
