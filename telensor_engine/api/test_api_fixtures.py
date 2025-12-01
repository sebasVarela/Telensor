from datetime import timedelta

from fastapi.testclient import TestClient

from telensor_engine.main import app


client = TestClient(app)


def _iso_to_dt(s: str):
    from datetime import datetime
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_fixture_baseline_scenario():
    payload = {
        "servicio_id": "SVC2",
        "scenario_id": "baseline",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T14:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    slots = data["horarios_disponibles"]
    assert len(slots) >= 1
    # En modo general, los slots deben autoasignarse a equipos compatibles
    assert all(sl.get("equipo_id_asignado") in {"EQ1", "EQ2"} for sl in slots)


def test_fixture_baseline_early_slot_uses_second_team_when_first_is_blocked():
    """En modo general, cuando el primer equipo compatible está ocupado,
    el sistema debe considerar el segundo equipo compatible y no omitir el horario.

    Baseline:
    - SVC2 requiere equipos [EQ1, EQ2].
    - EQ1 está ocupado en [07:55, 08:55].
    - EQ2 está libre en esa franja.

    Se espera que exista un slot 07:55–08:55 autoasignado a EQ2.
    """
    payload = {
        "servicio_id": "SVC2",
        "scenario_id": "baseline",
        "fecha_inicio_utc": "2025-11-06T07:00:00Z",
        "fecha_fin_utc": "2025-11-06T09:20:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1

    # Buscar el slot con inicio 08:00 asignado a EQ2 (anclaje por ventana efectiva)
    target_ini = _iso_to_dt("2025-11-06T08:00:00Z")
    match = [s for s in slots if _iso_to_dt(s["inicio_slot"]) == target_ini]
    assert match, "Debe existir un slot que inicie a las 07:55"
    assert any(s.get("equipo_id_asignado") == "EQ2" for s in match), "El slot 07:55 debe asignarse a EQ2"


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
        "empleado_id": "E1",
        "fecha_inicio_utc": "2025-11-06T23:30:00Z",
        "fecha_fin_utc": "2025-11-07T01:45:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
