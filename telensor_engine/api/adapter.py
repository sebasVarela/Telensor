from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable

import pendulum

# Nota: evitamos importar get_ocupaciones aquí para permitir que tests
# hagan monkeypatch sobre la referencia en telensor_engine.main y así
# inyectar ocupaciones personalizadas.


def _to_minute_range(base_midnight, inicio: Any, fin: Any) -> List[int]:
    """
    Convierte un par (inicio, fin) que puede venir como datetime o ISO string
    a un intervalo [min_inicio, min_fin) en minutos absolutos del eje continuo
    cuyo origen es `base_midnight` (inicio del día en UTC).
    """
    ini_dt = (
        pendulum.instance(inicio).in_timezone("UTC")
        if isinstance(inicio, datetime)
        else pendulum.parse(str(inicio)).in_timezone("UTC")
    )
    fin_dt = (
        pendulum.instance(fin).in_timezone("UTC")
        if isinstance(fin, datetime)
        else pendulum.parse(str(fin)).in_timezone("UTC")
    )
    s_min = int((ini_dt - base_midnight).total_seconds() // 60)
    e_min = int((fin_dt - base_midnight).total_seconds() // 60)
    return [s_min, e_min]


def build_total_blockings(
    *,
    base_midnight,
    inicio_dt,
    fin_dt,
    escenario: Optional[Dict[str, Any]],
    empleados_ids: List[str],
    equipo_id: Optional[str],
    servicio_id: Optional[str] = None,
    get_ocupaciones_fn: Optional[Callable[[List[str], Any, Any], List[Dict[str, Any]]]] = None,
    excepciones_inline: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, List[List[int]]], Dict[str, List[List[int]]], List[List[int]]]:
    """
    Agrega una lista unificada de bloqueos (ocupaciones + excepciones) por empleado,
    por equipo y globales, listos para ser restados del eje continuo.

    Parámetros:
    - base_midnight: datetime de inicio del día en UTC (origen del eje en minutos).
    - inicio_dt / fin_dt: ventana de búsqueda en UTC.
    - escenario: diccionario del fixture de pruebas (puede ser None).
    - empleados_ids: IDs a considerar.
    - equipo_id: ID de equipo a considerar (opcional).
    - servicio_id: ID del servicio solicitado (opcional, para excepciones con scope=service).

    Retorna:
    - (bloqueos_por_empleado, bloqueos_por_equipo, bloqueos_globales)

    Notas:
    - "Excepciones" se modelan como bloqueos neutrales al motivo; el motor no
      distingue el origen, solo resta intervalos.
    - Soporta `ocupaciones` y `ocupaciones_equipo` definidos en escenarios.
    - Si no hay escenario, consulta `get_ocupaciones` para empleados.
    """
    bloqueos_empleado: Dict[str, List[List[int]]] = {eid: [] for eid in empleados_ids}
    bloqueos_equipo: Dict[str, List[List[int]]] = {}
    bloqueos_globales: List[List[int]] = []

    # 1) Ocupaciones de empleados
    ocupaciones_src: List[Dict[str, Any]] = []
    if escenario and isinstance(escenario.get("ocupaciones"), list):
        ocupaciones_src = escenario["ocupaciones"]
    else:
        # Fallback: usar función inyectada por main (permite monkeypatch en tests)
        if get_ocupaciones_fn is not None:
            ocupaciones_src = get_ocupaciones_fn(empleados_ids, inicio_dt, fin_dt)
        else:
            # Último recurso: importación perezosa desde mock_db
            from telensor_engine.mock_db import get_ocupaciones as fallback_get_ocupaciones
            ocupaciones_src = fallback_get_ocupaciones(empleados_ids, inicio_dt, fin_dt)

    for oc in ocupaciones_src:
        eid = oc.get("empleado_id")
        if not eid or eid not in bloqueos_empleado:
            continue
        rng = _to_minute_range(base_midnight, oc["inicio"], oc["fin"])
        bloqueos_empleado[eid].append(rng)

    # 2) Ocupaciones de equipo (si hay escenario y equipo)
    if equipo_id:
        bloqueos_equipo[equipo_id] = []
        if escenario and isinstance(escenario.get("ocupaciones_equipo"), list):
            for occ in escenario["ocupaciones_equipo"]:
                if occ.get("equipo_id") == equipo_id:
                    rng = _to_minute_range(base_midnight, occ["inicio"], occ["fin"])
                    bloqueos_equipo[equipo_id].append(rng)

    # 3) Excepciones (business/employee/equipment/service)
    exc_list: List[Dict[str, Any]] = []
    if escenario and isinstance(escenario.get("excepciones"), list):
        exc_list.extend(escenario["excepciones"])
    if excepciones_inline:
        exc_list.extend(excepciones_inline)

    for exc in exc_list:
        scope = exc.get("scope")
        rng = _to_minute_range(base_midnight, exc.get("start"), exc.get("end"))
        if scope == "business":
            bloqueos_globales.append(rng)
        elif scope == "employee":
            tgt = exc.get("empleado_id")
            if tgt and tgt in bloqueos_empleado:
                bloqueos_empleado[tgt].append(rng)
        elif scope == "equipment":
            tgt = exc.get("equipo_id")
            if equipo_id and tgt == equipo_id:
                bloqueos_equipo.setdefault(equipo_id, []).append(rng)
        elif scope == "service":
            tgt = exc.get("servicio_id")
            if servicio_id and tgt == servicio_id:
                # Una excepción a nivel servicio afecta a todos los empleados y equipos
                bloqueos_globales.append(rng)

    return bloqueos_empleado, bloqueos_equipo, bloqueos_globales