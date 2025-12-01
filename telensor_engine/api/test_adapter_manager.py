from datetime import datetime

from telensor_engine.api.adapter import gestionar_busqueda_disponibilidad
from telensor_engine.main import app, SolicitudDisponibilidad
from fastapi.testclient import TestClient


client = TestClient(app)


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_manager_baseline_matches_endpoint_count():
    """El gerente debe producir el mismo conteo que el endpoint en baseline."""
    payload = {
        "servicio_id": "SVC2",
        "scenario_id": "baseline",
        "fecha_inicio_utc": "2025-11-06T08:00:00Z",
        "fecha_fin_utc": "2025-11-06T20:00:00Z",
    }
    resp = client.post("/api/v1/disponibilidad", json=payload)
    assert resp.status_code == 200
    slots_endpoint = resp.json()["horarios_disponibles"]

    solicitud = SolicitudDisponibilidad(
        servicio_id="SVC2",
        scenario_id="baseline",
        fecha_inicio_utc=_iso_to_dt("2025-11-06T08:00:00Z"),
        fecha_fin_utc=_iso_to_dt("2025-11-06T20:00:00Z"),
    )
    slots_manager = gestionar_busqueda_disponibilidad(solicitud)
    assert len(slots_manager) == len(slots_endpoint)


def test_manager_night_shift_full_slot_end_limit():
    """El gerente respeta el fin 02:30 en night_shift bajo full_slot."""
    solicitud = SolicitudDisponibilidad(
        servicio_id="SVC1",
        scenario_id="night_shift",
        empleado_id="E1",
        fecha_inicio_utc=_iso_to_dt("2025-11-06T23:20:00Z"),
        fecha_fin_utc=_iso_to_dt("2025-11-07T02:50:00Z"),
        service_window_policy="full_slot",
    )
    slots_manager = gestionar_busqueda_disponibilidad(solicitud)
    assert len(slots_manager) >= 1
    end_limit = _iso_to_dt("2025-11-07T02:30:00Z")
    assert all(slot["fin_slot"] <= end_limit for slot in slots_manager)


def test_manager_start_only_allows_end_past_service_window():
    """Con start_only, el fin del slot puede superar el fin del servicio."""
    solicitud = SolicitudDisponibilidad(
        servicio_id="SVC_EDGE",
        scenario_id="svc_window_edge",
        empleado_id="E_EDGE",
        fecha_inicio_utc=_iso_to_dt("2025-11-06T10:00:00Z"),
        fecha_fin_utc=_iso_to_dt("2025-11-06T12:00:00Z"),
        service_window_policy="start_only",
    )
    slots_manager = gestionar_busqueda_disponibilidad(solicitud)
    assert len(slots_manager) >= 1
    service_end = _iso_to_dt("2025-11-06T11:00:00Z")
    assert any(slot["fin_slot"] > service_end for slot in slots_manager)
