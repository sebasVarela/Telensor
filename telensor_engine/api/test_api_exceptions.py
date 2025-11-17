from fastapi.testclient import TestClient

from telensor_engine.main import app


client = TestClient(app)


def test_business_exception_blocks_all_slots():
    """
    Con una excepción de negocio (feriado) que cubre toda la ventana solicitada,
    no deben generarse slots aunque servicio y empleado estén disponibles.
    """
    payload = {
        "servicio_id": "SVC1",
        "scenario_id": "business_exception_full",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T14:00:00Z",
        "service_window_policy": "start_only"
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    assert resp.json()["horarios_disponibles"] == []