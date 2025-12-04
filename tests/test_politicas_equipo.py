import pendulum
from fastapi.testclient import TestClient

# Importamos la app principal del engine
from telensor_engine.main import app
from telensor_engine import mock_state


def test_least_loaded_pool_baseline_svc2():
    """
    Verifica que en el escenario "baseline" con servicio SVC2 (least_loaded),
    cuando ambos equipos son candidatos para el MISMO slot, se selecciona el de menor carga diaria.

    Este caso se observa en el pool general (sin empleado fijado) en el slot 08:55 para el empleado E1,
    donde tanto EQ1 como EQ2 generan el mismo slot y la política least_loaded elige EQ2.
    """
    client = TestClient(app)
    mock_state.reset_state()

    start = pendulum.parse("2025-11-06T08:00:00Z").in_timezone("UTC").to_iso8601_string()
    end = pendulum.parse("2025-11-06T12:00:00Z").in_timezone("UTC").to_iso8601_string()

    resp = client.post(
        "/api/v1/disponibilidad",
        json={
            "servicio_id": "SVC2",
            "fecha_inicio_utc": start,
            "fecha_fin_utc": end,
            "scenario_id": "baseline",
            "service_window_policy": "start_only",
        },
    )
    assert resp.status_code == 200
    slots = resp.json().get("horarios_disponibles", [])

    # Buscamos el slot de 08:55 para E1
    target = None
    for s in slots:
        if (
            s.get("inicio_slot") == "2025-11-06T08:55:00Z"
            and s.get("empleado_id_asignado") == "E1"
        ):
            target = s
            break

    # Debe existir y asignar EQ2 por menor carga diaria
    assert target is not None, "No se encontró el slot 08:55 para E1 en pool general"
    assert target.get("equipo_id_asignado") == "EQ2"


def test_least_loaded_empleado_e2_baseline_svc2():
    """
    Verifica los slots para el empleado E2. En 08:55, solo EQ1 genera slot para E2,
    por la discretización de inicios por duración total (step=60). Aquí documentamos
    el comportamiento esperado: en este slot, no hay múltiples equipos candidatos.
    """
    client = TestClient(app)
    mock_state.reset_state()

    start = pendulum.parse("2025-11-06T08:00:00Z").in_timezone("UTC").to_iso8601_string()
    end = pendulum.parse("2025-11-06T12:00:00Z").in_timezone("UTC").to_iso8601_string()

    resp = client.post(
        "/api/v1/disponibilidad",
        json={
            "servicio_id": "SVC2",
            "fecha_inicio_utc": start,
            "fecha_fin_utc": end,
            "scenario_id": "baseline",
            "service_window_policy": "start_only",
            "empleado_id": "E2",
        },
    )
    assert resp.status_code == 200
    slots = resp.json().get("horarios_disponibles", [])

    # Afirmamos los tres slots observados y su asignación de equipo
    esperados = {
        "2025-11-06T08:00:00Z": "EQ2",
        "2025-11-06T08:55:00Z": "EQ1",
        "2025-11-06T10:55:00Z": "EQ1",
    }
    got = {s["inicio_slot"]: s.get("equipo_id_asignado") for s in slots}
    for ini, eq in esperados.items():
        assert got.get(ini) == eq, f"Para {ini} esperado {eq}, obtenido {got.get(ini)}"

