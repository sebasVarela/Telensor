import pendulum
from pathlib import Path
from telensor_engine.fixtures import load_scenario
from telensor_engine.engine.engine import restar_intervalos, calcular_interseccion, encontrar_slots


def main():
    inicio_dt = pendulum.parse("2025-11-06T23:30:00Z").in_timezone("UTC")
    fin_dt = pendulum.parse("2025-11-07T01:45:00Z").in_timezone("UTC")
    base_midnight = inicio_dt.start_of("day")
    inicio_min = int((inicio_dt - base_midnight).total_seconds() // 60)
    fin_min = int((fin_dt - base_midnight).total_seconds() // 60)
    print("inicio_min, fin_min:", inicio_min, fin_min)
    cruza_noche = fin_min > 1440
    day_offsets = [0] + ([1440] if cruza_noche else [])
    print("day_offsets:", day_offsets)

    escenario = load_scenario("night_shift")
    root = Path(__file__).resolve().parents[2]
    print("root:", root)
    print("scenarios_exists:", (root / "docs" / "test_scenarios.json").exists())
    print("escenario existe:", escenario is not None)
    horarios = escenario["empleados"]
    for h in horarios:
        empleado_id = h["empleado_id"]
        trabajo_ini, trabajo_fin = h["horario_trabajo"]
        intervalos_trabajo_abs = [[trabajo_ini + d, trabajo_fin + d] for d in day_offsets]
        print("intervalos_trabajo_abs", empleado_id, intervalos_trabajo_abs)
        libres = restar_intervalos(intervalos_trabajo_abs, [])
        inter = calcular_interseccion(libres, [[inicio_min, fin_min]])
        print("interseccion", inter)
        inicios = encontrar_slots([inicio_min, fin_min], inter, 45, 10, 5)
        print("inicios", inicios)


if __name__ == "__main__":
    main()