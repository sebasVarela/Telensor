from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from telensor_engine.main import app


client = TestClient(app)


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_api_baseline_returns_slots(monkeypatch):
    # Monkeypatch de datos deterministas (misma lógica que mock_db por defecto)
    from telensor_engine import main as api

    monkeypatch.setattr(
        api,
        "get_servicio",
        lambda sid: {
            "id": sid,
            "duracion": 30,
            "buffer_previo": 10,
            "buffer_posterior": 5,
        },
    )

    monkeypatch.setattr(
        api,
        "get_horarios_empleados",
        lambda fecha, servicio_id=None, equipo_id=None: [
            {"empleado_id": "E1", "horario_trabajo": [540, 1020]},
            {"empleado_id": "E2", "horario_trabajo": [600, 1080]},
        ],
    )

    def occ(empleados, fi, ff):
        return [
            {
                "empleado_id": "E1",
                "inicio": fi + timedelta(minutes=100),
                "fin": fi + timedelta(minutes=130),
            }
        ]

    monkeypatch.setattr(api, "get_ocupaciones", occ)

    payload = {
        "servicio_id": "SVC1",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T14:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    slots = data["horarios_disponibles"]
    assert len(slots) >= 1
    # Verificar duración de 45 minutos
    for s in slots[:3]:
        assert (_iso_to_dt(s["fin_slot"]) - _iso_to_dt(s["inicio_slot"])) == timedelta(minutes=45)
    # Verificar empleados asignados
    assert all(sl["empleado_id_asignado"] in ("E1", "E2") for sl in slots)


def test_api_filter_by_employee(monkeypatch):
    from telensor_engine import main as api

    monkeypatch.setattr(
        api,
        "get_horarios_empleados",
        lambda fecha, servicio_id=None, equipo_id=None: [
            {"empleado_id": "E1", "horario_trabajo": [540, 1020]},
            {"empleado_id": "E2", "horario_trabajo": [600, 1080]},
        ],
    )

    monkeypatch.setattr(api, "get_servicio", lambda sid: {"id": sid, "duracion": 30, "buffer_previo": 10, "buffer_posterior": 5})
    monkeypatch.setattr(api, "get_ocupaciones", lambda e, fi, ff: [])

    payload = {
        "servicio_id": "SVC1",
        "empleado_id": "E1",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T12:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    assert all(sl["empleado_id_asignado"] == "E1" for sl in slots)


def test_api_heavy_occupancy_returns_empty(monkeypatch):
    from telensor_engine import main as api

    monkeypatch.setattr(
        api,
        "get_horarios_empleados",
        lambda fecha, servicio_id=None, equipo_id=None: [
            {"empleado_id": "E1", "horario_trabajo": [540, 1020]},
            {"empleado_id": "E2", "horario_trabajo": [600, 1080]},
        ],
    )
    monkeypatch.setattr(api, "get_servicio", lambda sid: {"id": sid, "duracion": 30, "buffer_previo": 10, "buffer_posterior": 5})

    def occ_full(empleados, fi, ff):
        # Ocupa toda la ventana solicitada para todos los empleados
        return [{"empleado_id": eid, "inicio": fi, "fin": ff} for eid in empleados]

    monkeypatch.setattr(api, "get_ocupaciones", occ_full)

    payload = {
        "servicio_id": "SVC1",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T14:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    assert resp.json()["horarios_disponibles"] == []


def test_api_cross_midnight_slots(monkeypatch):
    from telensor_engine import main as api

    # Trabajador nocturno: 00:00–02:00 (día siguiente)
    monkeypatch.setattr(
        api,
        "get_horarios_empleados",
        lambda fecha, servicio_id=None, equipo_id=None: [
            {"empleado_id": "N1", "horario_trabajo": [0, 120]},
        ],
    )
    monkeypatch.setattr(api, "get_servicio", lambda sid: {"id": sid, "duracion": 30, "buffer_previo": 10, "buffer_posterior": 5})
    monkeypatch.setattr(api, "get_ocupaciones", lambda e, fi, ff: [])

    payload = {
        "servicio_id": "SVC1",
        "fecha_inicio_utc": "2025-11-06T23:30:00Z",
        "fecha_fin_utc": "2025-11-07T01:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    # El primer slot debería comenzar a las 00:00Z del día siguiente
    assert slots[0]["inicio_slot"] == "2025-11-07T00:00:00Z"


def test_api_equipment_id_passthrough(monkeypatch):
    from telensor_engine import main as api

    monkeypatch.setattr(api, "get_horarios_empleados", lambda fecha, servicio_id=None, equipo_id=None: [{"empleado_id": "E1", "horario_trabajo": [540, 1020]}])
    monkeypatch.setattr(api, "get_servicio", lambda sid: {"id": sid, "duracion": 30, "buffer_previo": 10, "buffer_posterior": 5})
    monkeypatch.setattr(api, "get_ocupaciones", lambda e, fi, ff: [])

    payload = {
        "servicio_id": "SVC1",
        "equipo_id": "EQ1",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots = resp.json()["horarios_disponibles"]
    assert len(slots) >= 1
    assert all(sl["equipo_id_asignado"] == "EQ1" for sl in slots)


def test_api_strict_filter_returns_empty_when_no_qualified_employees():
    """Con filtrado por equipo sin empleado, si ningún empleado califica por servicio/equipo, no hay slots."""
    # Usamos la función por defecto de mock_db (sin monkeypatch) para filtrar:
    # - E1: servicios [SVC1,SVC2], equipos [EQ1]
    # - E2: servicios [SVC2], equipos [EQ1,EQ2]
    # Para servicio SVC1 con equipo EQ2, ningún empleado cumple ambos filtros.
    # Validamos el filtro por equipo sin empleado.
    monkeypatch = pytest.MonkeyPatch()
    from telensor_engine import main as api
    monkeypatch.setattr(api, "get_servicio", lambda sid: {"id": sid, "duracion": 30, "buffer_previo": 10, "buffer_posterior": 5})

    payload = {
        "servicio_id": "SVC1",
        "equipo_id": "EQ2",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T11:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    assert resp.json()["horarios_disponibles"] == []


def test_api_invalid_range_returns_400():
    payload = {
        "servicio_id": "SVC1",
        "fecha_inicio_utc": "2025-11-06T10:00:00Z",
        "fecha_fin_utc": "2025-11-06T10:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 400


def test_api_equipo_ids_is_forbidden_422():
    """Enviar campo `equipo_ids` debe resultar en 422 (campo prohibido)."""
    payload = {
        "servicio_id": "SVC2",
        "empleado_id": "E2",
        "equipo_ids": ["EQ1", "EQ2"],
        "fecha_inicio_utc": "2025-11-06T08:00:00Z",
        "fecha_fin_utc": "2025-11-06T12:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 422


def test_api_equipo_id_y_equipo_ids_forbidden_422():
    """Enviar ambos 'equipo_id' y 'equipo_ids' también resulta en 422 por campo extra."""
    payload = {
        "servicio_id": "SVC2",
        "empleado_id": "E2",
        "equipo_id": "EQ1",
        "equipo_ids": ["EQ1", "EQ2"],
        "fecha_inicio_utc": "2025-11-06T08:00:00Z",
        "fecha_fin_utc": "2025-11-06T10:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 422
