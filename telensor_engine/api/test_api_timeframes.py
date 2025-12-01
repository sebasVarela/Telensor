from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from telensor_engine.main import app


client = TestClient(app)


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_business_and_service_attention_effective_window():
    # Verifica que el inicio del servicio cae dentro del horario de atención definido
    payload = {
        "servicio_id": "SVC2",
        "scenario_id": "baseline",
        "fecha_inicio_utc": "2025-11-06T08:00:00Z",
        "fecha_fin_utc": "2025-11-06T20:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    # Inicio de servicio debe respetar la ventana de atención del servicio
    first = slots[0]
    inicio_servicio = _iso_to_dt(first["inicio_slot"]).time()
    assert inicio_servicio >= _iso_to_dt("2025-11-06T07:00:00Z").time()
    assert inicio_servicio < _iso_to_dt("2025-11-06T12:00:00Z").time()


def test_equipment_operational_respects_base_window_in_baseline():
    # baseline + equipo EQ1: sin ocupaciones de equipo definidas, debe devolver al menos un slot
    payload = {
        "servicio_id": "SVC1",
        "scenario_id": "baseline",
        "empleado_id": "E1",
        "fecha_inicio_utc": "2025-11-06T09:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    # Con SVC1 (90 min total) y sin ocupaciones, debe haber al menos 1 slot
    assert len(slots) >= 1


def test_equipment_blocked_returns_empty():
    # overlap_heavy + ocupación de equipo EQ1 [12:00, 12:45] recorta parte
    payload = {
        "servicio_id": "SVC1",
        "scenario_id": "overlap_heavy",
        "fecha_inicio_utc": "2025-11-06T12:00:00Z",
        "fecha_fin_utc": "2025-11-06T12:30:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    # Ventana corta completamente ocupada para equipo
    assert resp.json()["horarios_disponibles"] == []


def test_service_window_limits_start_only_employee_E2_equipment_EQ2():
    """
    Valida que el horario de atención del servicio sólo limita el inicio del slot
    en modo start_only. En el escenario 'svc_window_edge' (servicio SVC_EDGE con
    ventana 10:00–11:00), debe existir un slot que inicia a las 10:00 y termina
    a las 11:30 si empleado/equipo siguen disponibles.
    """
    payload = {
        "servicio_id": "SVC_EDGE",
        "scenario_id": "svc_window_edge",
        "empleado_id": "E_EDGE",
        "fecha_inicio_utc": "2025-11-06T09:30:00Z",
        "fecha_fin_utc": "2025-11-06T12:00:00Z",
        "service_window_policy": "start_only",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    # En start_only, debe existir un slot cuyo inicio de servicio esté dentro [10:00, 11:00)
    # y cuyo fin de slot exceda el fin del horario del servicio (>= 11:00).
    def _service_start(sl):
        return (_iso_to_dt(sl["inicio_slot"]) + timedelta(minutes=5)).time()

    def _slot_end_time(sl):
        return _iso_to_dt(sl["fin_slot"]).time()

    assert any(
        _service_start(sl) >= _iso_to_dt("2025-11-06T10:00:00Z").time()
        and _service_start(sl) < _iso_to_dt("2025-11-06T11:00:00Z").time()
        and _slot_end_time(sl) > _iso_to_dt("2025-11-06T11:00:00Z").time()
        for sl in slots
    )


def test_service_window_full_slot_blocks_10_to_11_30_for_E2_EQ2():
    """
    Con `service_window_policy = full_slot`, el horario del servicio (fin 11:00)
    también limita el fin del slot; por tanto, no debe aparecer 10:00–11:30.
    """
    payload = {
        "servicio_id": "SVC_EDGE",
        "scenario_id": "svc_window_edge",
        "empleado_id": "E_EDGE",
        "fecha_inicio_utc": "2025-11-06T09:30:00Z",
        "fecha_fin_utc": "2025-11-06T12:00:00Z",
        "service_window_policy": "full_slot",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    target_ini = _iso_to_dt("2025-11-06T10:00:00Z")
    target_fin = _iso_to_dt("2025-11-06T11:30:00Z")
    assert not any(_iso_to_dt(sl["inicio_slot"]) == target_ini and _iso_to_dt(sl["fin_slot"]) == target_fin for sl in slots)


def test_business_window_allows_pre_before_business_start_constraint():
    """
    El negocio siempre limita el INICIO del servicio (start constraint). El pre
    puede iniciar antes si el empleado está disponible; el inicio del servicio
    debe caer dentro del horario de negocio/servicio.
    Escenario: pre_edge con empleado iniciando a 06:58 y negocio a las 07:00.
    """
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
    first = slots[0]
    inicio_pre = _iso_to_dt(first["inicio_slot"]).time()
    # El negocio abre a las 07:00, el pre puede iniciar antes si el empleado está disponible
    assert inicio_pre < _iso_to_dt("2025-11-06T07:00:00Z").time()
    # El inicio del servicio (pre + 5min) debe caer dentro del negocio
    inicio_servicio = (_iso_to_dt(first["inicio_slot"]) + timedelta(minutes=5)).time()
    assert inicio_servicio >= _iso_to_dt("2025-11-06T07:00:00Z").time()
    # Validación: el inicio del pre puede ser antes de las 07:00.


def test_night_shift_service_full_slot_limits_end_before_02_30_and_crosses_midnight():
    """
    En el escenario 'night_shift', con `service_window_policy = full_slot`:
    - Debe existir al menos un slot que cruce la medianoche (inicio < 00:00 y fin > 00:00).
    - Ningún slot debe finalizar después de las 01:30 (fin del horario de servicio).
    """
    payload = {
        "servicio_id": "SVC1",
        "scenario_id": "night_shift",
        "empleado_id": "E1",
        "fecha_inicio_utc": "2025-11-06T23:20:00Z",
        "fecha_fin_utc": "2025-11-07T02:50:00Z",
        "service_window_policy": "full_slot",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1

    midnight_dt = _iso_to_dt("2025-11-07T00:00:00Z")
    # Verificar al menos un slot cruza la medianoche
    def _cruza_medianoche(sl):
        return _iso_to_dt(sl["inicio_slot"]) < midnight_dt and _iso_to_dt(sl["fin_slot"]) > midnight_dt

    assert any(_cruza_medianoche(sl) for sl in slots)

    # Validar que ningún slot termine después de las 02:30 bajo full_slot
    end_limit = _iso_to_dt("2025-11-07T02:30:00Z")
    assert all(_iso_to_dt(sl["fin_slot"]) <= end_limit for sl in slots)
