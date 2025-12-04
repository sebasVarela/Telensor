import pendulum
from fastapi.testclient import TestClient

from telensor_engine.main import app
from telensor_engine import mock_state


client = TestClient(app)


def _iso(dt):
    return pendulum.instance(dt).in_timezone("UTC").to_iso8601_string()


def test_bloqueo_empleado_reasigna_cita():
    # Resetear memoria
    mock_state.reset_state()

    # Buscar disponibilidad en escenario baseline para SVC2 (pool general)
    inicio = pendulum.parse("2025-11-06T08:00:00Z")
    fin = pendulum.parse("2025-11-06T11:00:00Z")

    resp = client.post(
        "/api/v1/disponibilidad",
        json={
            "servicio_id": "SVC2",
            "fecha_inicio_utc": _iso(inicio),
            "fecha_fin_utc": _iso(fin),
            "scenario_id": "baseline",
            "service_window_policy": "start_only",
        },
    )
    assert resp.status_code == 200, resp.text
    slots = resp.json()["horarios_disponibles"]
    # Elegir un slot asignado a E1 para poder bloquearlo
    slot_e1 = next((s for s in slots if s.get("empleado_id_asignado") == "E1"), None)
    assert slot_e1, "No se encontró slot asignado a E1 en baseline"

    # Crear reserva sobre ese slot
    reserva_resp = client.post(
        "/api/v1/reservas",
        json={
            "servicio_id": "SVC2",
            "empleado_id": slot_e1["empleado_id_asignado"],
            "equipo_id": slot_e1.get("equipo_id_asignado"),
            "inicio_slot": slot_e1["inicio_slot"],
            "fin_slot": slot_e1["fin_slot"],
            "scenario_id": "baseline",
            "service_window_policy": "start_only",
        },
    )
    assert reserva_resp.status_code == 201, reserva_resp.text
    creada = reserva_resp.json()
    rid = creada["reserva_id"]

    # Bloquear empleado E1 en el rango exacto del slot
    bloqueo_resp = client.post(
        "/api/v1/bloqueos",
        json={
            "inicio_utc": creada["inicio_slot"],
            "fin_utc": creada["fin_slot"],
            "motivo": "Enfermedad",
            "scope": "employee",
            "empleado_ids": ["E1"],
        },
    )
    assert bloqueo_resp.status_code == 201, bloqueo_resp.text
    resultado = bloqueo_resp.json()
    assert resultado.get("bloqueo_id"), "Bloqueo no registró ID"

    # Verificar que la reserva fue reasignada a E2
    reservas = mock_state.list_reservas()
    victim = next(r for r in reservas if r.reserva_id == rid)
    assert victim.estado == "REASIGNADA"
    assert victim.empleado_id == "E2"


def test_bloqueo_negocio_reagenda_todo():
    # Resetear memoria
    mock_state.reset_state()

    # Crear dos reservas en baseline, SVC2 (pool general)
    inicio = pendulum.parse("2025-11-06T08:00:00Z")
    fin = pendulum.parse("2025-11-06T12:00:00Z")
    disp = client.post(
        "/api/v1/disponibilidad",
        json={
            "servicio_id": "SVC2",
            "fecha_inicio_utc": _iso(inicio),
            "fecha_fin_utc": _iso(fin),
            "scenario_id": "baseline",
            "service_window_policy": "start_only",
        },
    )
    assert disp.status_code == 200, disp.text
    slots = disp.json()["horarios_disponibles"]
    assert len(slots) >= 2, "Se requieren al menos dos slots para la prueba"

    rids = []
    for s in slots[:2]:
        r = client.post(
            "/api/v1/reservas",
            json={
                "servicio_id": "SVC2",
                "empleado_id": s["empleado_id_asignado"],
                "equipo_id": s.get("equipo_id_asignado"),
                "inicio_slot": s["inicio_slot"],
                "fin_slot": s["fin_slot"],
                "scenario_id": "baseline",
                "service_window_policy": "start_only",
            },
        )
        assert r.status_code == 201, r.text
        rids.append(r.json()["reserva_id"])

    # Bloqueo de negocio que cubre toda la ventana
    bloqueado = client.post(
        "/api/v1/bloqueos",
        json={
            "inicio_utc": _iso(inicio),
            "fin_utc": _iso(fin),
            "motivo": "Corte de energía",
            "scope": "business",
        },
    )
    assert bloqueado.status_code == 201, bloqueado.text
    res = mock_state.list_reservas()
    estados = {r.reserva_id: r.estado for r in res if r.reserva_id in rids}
    assert all(v == "PENDIENTE_REAGENDA" for v in estados.values())

