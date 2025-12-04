from datetime import datetime

from fastapi.testclient import TestClient

from telensor_engine.main import app


client = TestClient(app)


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_employee_mode_validation_and_success():
    """Servicio por empleado (derivación por filtros):
    - Acepta `equipo_id`, pero si el servicio no requiere equipo y el empleado no lo tiene asignado, retorna 200 con lista vacía.
    - `empleado_id` opcional: sin él, opera en pool general.
    - Éxito sin equipo asignado cuando el servicio no requiere equipos.
    """
    # Caso 1: viene equipo_id -> 200 con lista vacía (E_EMP no tiene EQX asignado y SVC_EMP no requiere equipo)
    payload_bad_eq = {
        "servicio_id": "SVC_EMP",
        "scenario_id": "policy_demo",
        "equipo_id": "EQX",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_bad_eq)
    assert resp.status_code == 200
    assert resp.json()["horarios_disponibles"] == []

    # Caso 2: falta empleado_id -> 200 en pool general (servicio sin equipos)
    payload_missing_emp = {
        "servicio_id": "SVC_EMP",
        "scenario_id": "policy_demo",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_missing_emp)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    assert all(sl.get("equipo_id_asignado") is None for sl in slots)

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

    # Caso 4: viene empleado_id y equipo_id a la vez -> 200 con lista vacía por filtros incompatibles
    payload_emp_and_eq = {
        "servicio_id": "SVC_EMP",
        "scenario_id": "policy_demo",
        "empleado_id": "E_EMP",
        "equipo_id": "EQX",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_emp_and_eq)
    assert resp.status_code == 200
    assert resp.json()["horarios_disponibles"] == []


def test_equipment_mode_validation_and_success():
    """Servicio por equipo (derivación por filtros):
    - Acepta `empleado_id` y `equipo_id`.
    - Si falta `equipo_id` y el servicio requiere equipo, opera en pool general con autoasignación.
    - Debe asignar el equipo solicitado o autoasignado cuando aplica.
    """
    # Caso 1: viene empleado_id -> 200 (pool general con autoasignación EQX)
    payload_bad_emp = {
        "servicio_id": "SVC_EQ",
        "scenario_id": "policy_demo",
        "empleado_id": "E_EQ",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_bad_emp)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    assert all(sl.get("equipo_id_asignado") == "EQX" for sl in slots)

    # Caso 2: falta equipo_id -> 200 (pool general con autoasignación EQX)
    payload_missing_eq = {
        "servicio_id": "SVC_EQ",
        "scenario_id": "policy_demo",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_missing_eq)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    assert all(sl.get("equipo_id_asignado") == "EQX" for sl in slots)

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


def test_general_mode_accepts_filters_and_pools_with_auto_assignment():
    """Servicio general (pool, derivación por filtros):
    - Acepta `empleado_id` y `equipo_id` como filtros.
    - Devuelve slots agregados y autoasignación de equipo si el servicio lo requiere.
    """
    # Caso 1: viene empleado_id -> 200 (filtrado por empleado)
    payload_bad_emp = {
        "servicio_id": "SVC_POOL",
        "scenario_id": "policy_demo",
        "empleado_id": "E_POOL1",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_bad_emp)
    assert resp.status_code == 200
    assert len(resp.json()["horarios_disponibles"]) >= 1

    # Caso 2: viene equipo_id -> 200 (filtrado por equipo)
    payload_bad_eq = {
        "servicio_id": "SVC_POOL",
        "scenario_id": "policy_demo",
        "equipo_id": "EQP1",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload_bad_eq)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    assert all(sl.get("equipo_id_asignado") == "EQP1" for sl in slots)

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
