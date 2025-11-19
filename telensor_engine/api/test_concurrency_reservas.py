"""
Pruebas de carrera para la creación de reservas.

Este módulo valida que el mecanismo de anti-colisión basado en Lock
evita crear múltiples reservas sobre el mismo slot, tanto a nivel
API (Director/Gerente) como a nivel unidad (mock_state).
"""

import pendulum
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from telensor_engine.main import app
from telensor_engine.mock_state import reset_state, add_reserva


def _obtener_primer_slot_baseline(client: TestClient):
    """Consulta disponibilidad y retorna el primer slot del escenario baseline.

    Se usa service_window_policy=start_only para coherencia con el flujo E2E.
    """
    payload_get = {
        "servicio_id": "SVC2",
        "scenario_id": "baseline",
        "fecha_inicio_utc": "2025-11-06T08:00:00Z",
        "fecha_fin_utc": "2025-11-06T10:00:00Z",
        "service_window_policy": "start_only",
    }
    resp_get = client.post("/api/v1/disponibilidad", json=payload_get)
    assert resp_get.status_code == 200
    slots = resp_get.json()["horarios_disponibles"]
    assert len(slots) >= 1
    return slots[0]


def test_concurrent_reservas_same_slot_only_one_success_api():
    """Simula POST concurrentes al mismo slot y verifica 1x201 y (n-1)x409.

    - Resetea el estado.
    - Obtiene un slot base vía disponibilidad.
    - Dispara N solicitudes concurrentes de creación de reserva sobre el mismo slot.
    - Valida que solo una se crea y las demás devuelven conflicto.
    """
    reset_state()
    client = TestClient(app)

    slot0 = _obtener_primer_slot_baseline(client)

    payload_post = {
        "servicio_id": "SVC2",
        "empleado_id": slot0["empleado_id_asignado"],
        "inicio_slot": slot0["inicio_slot"],
        "fin_slot": slot0["fin_slot"],
        "scenario_id": "baseline",
        "service_window_policy": "start_only",
    }
    if slot0.get("equipo_id_asignado") is not None:
        payload_post["equipo_id"] = slot0["equipo_id_asignado"]

    def _post_once():
        resp = client.post("/api/v1/reservas", json=payload_post)
        return resp.status_code

    workers = 6
    with ThreadPoolExecutor(max_workers=workers) as ex:
        codes = list(ex.map(lambda _i: _post_once(), range(workers)))

    assert codes.count(201) == 1
    assert codes.count(409) == workers - 1


def test_concurrent_add_reserva_lock_enforced_unit():
    """Valida a nivel unidad que el Lock evita duplicados en el mismo slot.

    - Resetea el estado.
    - Dispara N llamadas concurrentes a add_reserva con los mismos datos.
    - Verifica que solo una reserva fue creada y el resto falla por conflicto.
    """
    reset_state()

    servicio_id = "SVC2"
    empleado_id = "E1"
    equipo_id = None
    inicio_dt = pendulum.parse("2025-11-06T08:00:00Z").in_timezone("UTC")
    # SVC2: duracion 30 + buffer_previo 10 + buffer_posterior 5 = 45 minutos
    fin_dt = inicio_dt.add(minutes=45)

    results = []
    errors = []

    def _add_once(_i: int):
        try:
            r = add_reserva(
                servicio_id=servicio_id,
                empleado_id=empleado_id,
                equipo_id=equipo_id,
                inicio_slot=inicio_dt,
                fin_slot=fin_dt,
            )
            results.append(r)
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))

    workers = 6
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(_add_once, range(workers)))

    assert len(results) == 1
    # Al menos uno de los errores debe mencionar conflicto
    assert any("Conflicto" in msg for msg in errors)