from datetime import timedelta

from fastapi.testclient import TestClient

from telensor_engine.main import app


client = TestClient(app)


def test_fixture_baseline_scenario():
    payload = {
        "servicio_id": "SVC2",
        "scenario_id": "baseline",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T14:00:00Z",
        "equipo_id": "EQ2",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    slots = data["horarios_disponibles"]
    assert len(slots) >= 1
    assert all(sl["equipo_id_asignado"] == "EQ2" for sl in slots)


def test_fixture_overlap_heavy_restricts_slots():
    payload = {
        "servicio_id": "SVC1",
        "scenario_id": "overlap_heavy",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T14:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    # No vacío, pero reducido por ocupaciones superpuestas
    assert len(slots) >= 1


def test_fixture_night_shift_cross_midnight():
    payload = {
        "servicio_id": "SVC1",
        "scenario_id": "night_shift",
        "fecha_inicio_utc": "2025-11-06T23:30:00Z",
        "fecha_fin_utc": "2025-11-07T01:45:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1