from fastapi.testclient import TestClient
from telensor_engine.main import app


client = TestClient(app)


def test_pool_general_picks_least_loaded():
    """En modo general (Pool), cuando dos empleados están libres para el mismo horario,
    el sistema debe seleccionar al empleado con menos minutos ocupados ese día.

    Escenario: load_balance_demo
    - E_A: 60 minutos ocupados (09:00-10:00)
    - E_B: 15 minutos ocupados (09:30-09:45)
    Servicio: SVC_LBG (search_mode=general, sin equipos requeridos)
    """

    payload = {
        "servicio_id": "SVC_LBG",
        "fecha_inicio_utc": "2025-11-06T09:45:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
        "scenario_id": "load_balance_demo",
    }

    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    slots = data.get("horarios_disponibles", [])
    assert slots, "Se esperaban slots de disponibilidad en modo pool general"

    # Verificar que al menos un slot asignado corresponde al empleado menos cargado (E_B).
    empleados = {s.get("empleado_id_asignado") for s in slots}
    assert "E_B" in empleados, "El balanceo debe seleccionar E_B en horarios compartidos"

    # Deduplicación por horario en modo general: para cada (inicio, fin) debe haber un único empleado.
    agrupados = {}
    for s in slots:
        key = (s.get("inicio_slot"), s.get("fin_slot"))
        agrupados.setdefault(key, set()).add(s.get("empleado_id_asignado"))
    assert all(len(emps) == 1 for emps in agrupados.values()), (
        "En modo general se debe deduplicar por horario, ignorando el equipo"
    )


def test_equipment_mode_picks_least_loaded():
    """En modo por equipo, cuando dos empleados están libres para el mismo horario
    del equipo solicitado, se selecciona al empleado con menos carga diaria.

    Escenario: load_balance_demo
    Equipo: EQ_LB
    Servicio: SVC_LBEQ (search_mode=equipment, requiere EQ_LB)
    """

    payload = {
        "servicio_id": "SVC_LBEQ",
        "equipo_id": "EQ_LB",
        "fecha_inicio_utc": "2025-11-06T09:45:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
        "scenario_id": "load_balance_demo",
    }

    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    slots = data.get("horarios_disponibles", [])
    assert slots, "Se esperaban slots de disponibilidad en modo por equipo"

    # Verificar que al menos un slot asignado corresponde al empleado menos cargado (E_B).
    empleados = {s.get("empleado_id_asignado") for s in slots}
    assert "E_B" in empleados, "El balanceo debe seleccionar E_B en horarios compartidos por equipo"


def test_tiebreaker_general_prefers_lower_id_when_equal_load():
    """Si dos empleados tienen la misma carga en el día, el tie-breaker
    debe seleccionar determinísticamente el empleado con menor id lexicográfico.

    Escenario: tie_break_demo (ambos empleados sin ocupaciones, misma carga=0)
    Servicio: SVC_TB (search_mode=general)
    """

    payload = {
        "servicio_id": "SVC_TB",
        "fecha_inicio_utc": "2025-11-06T09:45:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
        "scenario_id": "tie_break_demo",
    }

    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    slots = data.get("horarios_disponibles", [])
    assert slots, "Se esperaban slots en modo pool general"

    # Deduplicación por horario y selección por menor id
    for s in slots:
        assert s.get("empleado_id_asignado") in {"E_T1", "E_T2"}
    # Elegido debe ser E_T1 (menor lexicográficamente)
    assert all(s.get("empleado_id_asignado") == "E_T1" for s in slots), (
        "Tie-breaker debe preferir el menor empleado_id lexicográfico"
    )
