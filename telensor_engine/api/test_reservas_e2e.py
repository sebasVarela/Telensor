from fastapi.testclient import TestClient

from telensor_engine.main import app
from telensor_engine.mock_state import reset_state


client = TestClient(app)


def test_reservas_e2e_creacion_y_conflicto_baseline():
    """Flujo E2E: GET disponibilidad -> POST reserva -> GET sin slot -> POST 409."""
    # Asegurar estado limpio
    reset_state()

    # 1) Consultar disponibilidad en baseline para SVC2
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

    # Seleccionar primer slot
    slot0 = slots[0]

    # 2) Crear reserva sobre ese slot exacto
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

    resp_post = client.post("/api/v1/reservas", json=payload_post)
    assert resp_post.status_code == 201
    data_created = resp_post.json()
    assert "reserva_id" in data_created

    # 3) Reconsultar disponibilidad; el slot ya no debe aparecer para ese empleado
    resp_get2 = client.post("/api/v1/disponibilidad", json=payload_get)
    assert resp_get2.status_code == 200
    slots2 = resp_get2.json()["horarios_disponibles"]
    assert not any(
        s["inicio_slot"] == slot0["inicio_slot"]
        and s["empleado_id_asignado"] == slot0["empleado_id_asignado"]
        for s in slots2
    )

    # 4) Intentar crear de nuevo la misma reserva debe fallar con 409
    resp_post_conflict = client.post("/api/v1/reservas", json=payload_post)
    assert resp_post_conflict.status_code == 409