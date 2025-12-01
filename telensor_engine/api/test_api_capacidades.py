from datetime import datetime

from fastapi.testclient import TestClient

from telensor_engine.main import app


client = TestClient(app)


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_no_slots_when_employee_has_no_compatible_equipment_baseline():
    """Con SVC1 (compatibles EQ1) y E2 (asignados EQ2) no hay intersección.
    Debe devolver cero slots (estricto: requiere equipo compatible)."""
    payload = {
        "servicio_id": "SVC1",
        "scenario_id": "baseline",
        "empleado_id": "E2",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
        "service_window_policy": "start_only",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert slots == []


def test_auto_assignment_when_equipment_matches_pre_edge():
    """En pre_edge, E_PRE tiene EQ1 asignado y el servicio requiere EQ1;
    el sistema debe autoasignar EQ1 y devolver al menos un slot."""
    payload = {
        "servicio_id": "SVC1",
        "scenario_id": "pre_edge",
        "empleado_id": "E_PRE",
        "fecha_inicio_utc": "2025-11-06T06:30:00Z",
        "fecha_fin_utc": "2025-11-06T08:40:00Z",
        "service_window_policy": "start_only",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    assert all(sl.get("equipo_id_asignado") == "EQ1" for sl in slots)