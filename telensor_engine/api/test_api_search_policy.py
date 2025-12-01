from datetime import datetime

from fastapi.testclient import TestClient

from telensor_engine.main import app


client = TestClient(app)


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_employee_mode_validation_and_success():
    """Servicio centrado en empleado:
    - Rechaza equipo_id.
    - Requiere empleado_id.
    - Éxito sin equipo asignado (servicio sin equipos_compatibles).
    """
    # Caso 1: viene equipo_id -> 400
    payload_bad_eq = {
        "servicio_id": "SVC_EMP",
        "scenario_id": "policy_demo",
        "equipo_id": "EQX",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_bad_eq)
    assert resp.status_code == 400

    # Caso 2: falta empleado_id -> 400
    payload_missing_emp = {
        "servicio_id": "SVC_EMP",
        "scenario_id": "policy_demo",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_missing_emp)
    assert resp.status_code == 400

    # Caso 3: éxito con empleado_id y sin equipo
    payload_ok = {
        "servicio_id": "SVC_EMP",
        "scenario_id": "policy_demo",
        "empleado_id": "E_EMP",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_ok)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    # SVC_EMP no requiere equipo, equipo_id_asignado debe ser None
    assert all(sl.get("equipo_id_asignado") is None for sl in slots)

    # Caso 4: viene empleado_id y equipo_id a la vez -> 400 (estricto)
    payload_emp_and_eq = {
        "servicio_id": "SVC_EMP",
        "scenario_id": "policy_demo",
        "empleado_id": "E_EMP",
        "equipo_id": "EQX",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_emp_and_eq)
    assert resp.status_code == 400


def test_equipment_mode_validation_and_success():
    """Servicio centrado en equipo:
    - Rechaza empleado_id.
    - Requiere equipo_id.
    - Éxito con equipo asignado.
    """
    # Caso 1: viene empleado_id -> 400
    payload_bad_emp = {
        "servicio_id": "SVC_EQ",
        "scenario_id": "policy_demo",
        "empleado_id": "E_EQ",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_bad_emp)
    assert resp.status_code == 400

    # Caso 2: falta equipo_id -> 400
    payload_missing_eq = {
        "servicio_id": "SVC_EQ",
        "scenario_id": "policy_demo",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_missing_eq)
    assert resp.status_code == 400

    # Caso 3: éxito con equipo_id
    payload_ok = {
        "servicio_id": "SVC_EQ",
        "scenario_id": "policy_demo",
        "equipo_id": "EQX",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_ok)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    assert all(sl.get("equipo_id_asignado") == "EQX" for sl in slots)

    # Caso 4: equipo_id no compatible con el servicio -> 400
    payload_incompatible_eq = {
        "servicio_id": "SVC_EQ",
        "scenario_id": "policy_demo",
        "equipo_id": "EQP1",  # no está en equipos_compatibles de SVC_EQ
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_incompatible_eq)
    assert resp.status_code == 400


def test_general_mode_rejects_specific_resources_and_pools_with_auto_assignment():
    """Servicio general (pool):
    - Rechaza empleado_id y equipo_id.
    - Devuelve slots agregados y autoasignación de equipo si el servicio lo requiere.
    """
    # Caso 1: viene empleado_id -> 400
    payload_bad_emp = {
        "servicio_id": "SVC_POOL",
        "scenario_id": "policy_demo",
        "empleado_id": "E_POOL1",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_bad_emp)
    assert resp.status_code == 400

    # Caso 2: viene equipo_id -> 400
    payload_bad_eq = {
        "servicio_id": "SVC_POOL",
        "scenario_id": "policy_demo",
        "equipo_id": "EQP1",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_bad_eq)
    assert resp.status_code == 400

    # Caso 3: éxito en pool, autoasignación de equipo si compatibles
    payload_ok = {
        "servicio_id": "SVC_POOL",
        "scenario_id": "policy_demo",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_ok)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    # Todos los slots deben estar autoasignados a un equipo compatible (EQP1)
    assert all(sl.get("equipo_id_asignado") == "EQP1" for sl in slots)
