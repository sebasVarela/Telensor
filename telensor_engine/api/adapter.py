from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable

import pendulum
import logging

from telensor_engine.engine.engine import (
    calcular_interseccion,
    restar_intervalos,
    encontrar_slots,
)
from telensor_engine.fixtures import load_scenario
from telensor_engine import mock_state as mock_state
from telensor_engine.mock_db import (
    get_servicio as default_get_servicio,
    get_horarios_empleados as default_get_horarios_empleados,
)


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

    # 4) Reservas en memoria (anti-colisión): se consideran como bloqueos.
    #    Esto garantiza que las disponibilidades reflejen inmediatamente las
    #    reservas creadas durante las pruebas E2E.
    reservas = mock_state.get_reservas_en_rango(inicio_dt, fin_dt)
    for r in reservas:
        # Bloqueo por empleado
        if r.empleado_id in bloqueos_empleado:
            rng = _to_minute_range(base_midnight, r.inicio_slot, r.fin_slot)
            bloqueos_empleado[r.empleado_id].append(rng)
        # Bloqueo por equipo (si aplica)
        if equipo_id and r.equipo_id == equipo_id:
            rng = _to_minute_range(base_midnight, r.inicio_slot, r.fin_slot)
            bloqueos_equipo.setdefault(equipo_id, []).append(rng)

    return bloqueos_empleado, bloqueos_equipo, bloqueos_globales


def gestionar_busqueda_disponibilidad(
    solicitud: Any,
    *,
    get_servicio_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    get_horarios_empleados_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    get_ocupaciones_fn: Optional[Callable[[List[str], Any, Any], List[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    """
    Función "Gerente" que realiza toda la lógica de búsqueda de disponibilidad.

    - Traduce fechas al eje continuo de minutos absolutos.
    - Carga escenario/servicio/horarios y agrega bloqueos (ocupaciones + excepciones).
    - Calcula restricciones de inicio (negocio ∩ servicio ∩ base).
    - Aplica la política de ventana del servicio (start_only vs full_slot).
    - Empaqueta slots con el motor y devuelve una lista de dicts listos para la API.

    Parámetros:
    - solicitud: instancia con atributos del modelo de entrada (SolicituDisponibilidad compatible).
    - get_servicio_fn, get_horarios_empleados_fn, get_ocupaciones_fn: dependencias inyectables para pruebas.

    Retorna:
    - Lista de dicts con claves: inicio_slot (datetime), fin_slot (datetime), empleado_id_asignado, equipo_id_asignado.
    """
    # Validación básica del rango
    if solicitud.fecha_fin_utc <= solicitud.fecha_inicio_utc:
        logging.warning("Gerente: rango inválido: %s >= %s", solicitud.fecha_inicio_utc, solicitud.fecha_fin_utc)
        return []

    # Paso 0: Construcción del eje continuo (UTC)
    inicio_dt = pendulum.instance(solicitud.fecha_inicio_utc).in_timezone("UTC")
    fin_dt = pendulum.instance(solicitud.fecha_fin_utc).in_timezone("UTC")
    base_midnight = inicio_dt.start_of("day")

    inicio_min = int((inicio_dt - base_midnight).total_seconds() // 60)
    fin_min = int((fin_dt - base_midnight).total_seconds() // 60)
    if fin_min <= inicio_min:
        logging.warning("Gerente: ventana base inválida: [%d,%d]", inicio_min, fin_min)
        return []

    # Datos de dominio (escenario o mock_db)
    escenario = load_scenario(solicitud.scenario_id) if getattr(solicitud, "scenario_id", None) else None

    # Servicio y reglas de slot
    get_servicio = get_servicio_fn or default_get_servicio
    if escenario and "servicios" in escenario and solicitud.servicio_id in escenario["servicios"]:
        servicio = escenario["servicios"][solicitud.servicio_id]
    else:
        servicio = get_servicio(solicitud.servicio_id)
    buffer_previo = int(servicio.get("buffer_previo", 0))
    buffer_posterior = int(servicio.get("buffer_posterior", 0))
    duracion_servicio = int(servicio.get("duracion", 0))
    duracion_total_slot = buffer_previo + duracion_servicio + buffer_posterior

    # Horarios de empleados
    get_horarios_empleados = get_horarios_empleados_fn or default_get_horarios_empleados
    if escenario and "empleados" in escenario:
        horarios = escenario["empleados"]
        # Si el escenario define asignaciones por empleado, aplicar filtrado estricto
        serv_key_present = any("servicios_asignados" in h for h in horarios)
        eq_key_present = any("equipos_asignados" in h for h in horarios)
        if serv_key_present and solicitud.servicio_id:
            horarios = [h for h in horarios if solicitud.servicio_id in h.get("servicios_asignados", [])]
        if eq_key_present and getattr(solicitud, "equipo_id", None):
            horarios = [h for h in horarios if getattr(solicitud, "equipo_id", None) in h.get("equipos_asignados", [])]
        if not horarios:
            return []
    else:
        # Pasar filtros de servicio/equipo para asegurar empleados válidos
        horarios = get_horarios_empleados(
            base_midnight,
            servicio_id=solicitud.servicio_id,
            equipo_id=getattr(solicitud, "equipo_id", None),
        )
    if getattr(solicitud, "empleado_id", None):
        horarios = [h for h in horarios if h.get("empleado_id") == solicitud.empleado_id]
        if not horarios:
            return []

    empleados_ids = [h["empleado_id"] for h in horarios]

    # Agregación de bloqueos (ocupaciones + excepciones)
    bloqueos_por_empleado, bloqueos_por_equipo, bloqueos_globales = build_total_blockings(
        base_midnight=base_midnight,
        inicio_dt=inicio_dt,
        fin_dt=fin_dt,
        escenario=escenario,
        empleados_ids=empleados_ids,
        equipo_id=getattr(solicitud, "equipo_id", None),
        servicio_id=solicitud.servicio_id,
        get_ocupaciones_fn=get_ocupaciones_fn,
    )

    # Offsets de día (manejar cruce de medianoche)
    cruza_noche = fin_min > 1440
    day_offsets = [0] + ([1440] if cruza_noche else [])

    # Ventanas de atención (restricción de INICIO)
    start_constraint_windows: List[List[int]] = [[inicio_min, fin_min]]
    negocio_windows_abs: List[List[int]] = []
    if escenario and isinstance(escenario.get("horario_atencion_negocio"), list):
        negocio_ini, negocio_fin = escenario["horario_atencion_negocio"]
        negocio_windows_abs = [[negocio_ini + d, negocio_fin + d] for d in day_offsets]
        start_constraint_windows = calcular_interseccion(start_constraint_windows, negocio_windows_abs)

    servicio_windows_abs: List[List[int]] = []
    if escenario and "servicios" in escenario:
        svc = escenario["servicios"].get(solicitud.servicio_id)
        if svc and isinstance(svc.get("horario_atencion"), list):
            svc_att = svc["horario_atencion"]
            servicio_windows_abs = [[svc_att[0] + d, svc_att[1] + d] for d in day_offsets]
            start_constraint_windows = calcular_interseccion(start_constraint_windows, servicio_windows_abs)

    if not start_constraint_windows:
        return []

    # Determinar política de servicio (admite Enum o string)
    policy_value = getattr(solicitud.service_window_policy, "value", solicitud.service_window_policy)

    logging.info(
        "Gerente: policy=%s; start=%s, negocio=%s, servicio=%s, base=[%d,%d]",
        policy_value,
        start_constraint_windows,
        negocio_windows_abs,
        servicio_windows_abs,
        inicio_min,
        fin_min,
    )

    # Configuración operativa de equipo
    equipo_operativo_abs: List[List[int]] = []
    if getattr(solicitud, "equipo_id", None):
        if escenario and "equipos" in escenario:
            eq_list = escenario["equipos"]
            eq_match = next((e for e in eq_list if e.get("equipo_id") == solicitud.equipo_id), None)
            if eq_match and isinstance(eq_match.get("horario_operativo"), list):
                op_ini, op_fin = eq_match["horario_operativo"]
                equipo_operativo_abs = [[op_ini + d, op_fin + d] for d in day_offsets]
        if not equipo_operativo_abs:
            equipo_operativo_abs = [[inicio_min, fin_min]]

    resultados: List[Dict[str, Any]] = []

    for h in horarios:
        empleado_id = h["empleado_id"]
        trabajo_ini, trabajo_fin = h["horario_trabajo"]
        intervalos_trabajo_abs = [[trabajo_ini + d, trabajo_fin + d] for d in day_offsets]

        # Libres de empleado
        bloqueos_emp = (bloqueos_por_empleado.get(empleado_id, []) or []) + (bloqueos_globales or [])
        libres_empleado = restar_intervalos(intervalos_trabajo_abs, bloqueos_emp)

        # Libres de equipo
        libres_equipo: List[List[int]] = []
        if getattr(solicitud, "equipo_id", None):
            bloqueos_eq = (bloqueos_por_equipo.get(solicitud.equipo_id, []) or []) + (bloqueos_globales or [])
            libres_equipo = restar_intervalos(equipo_operativo_abs, bloqueos_eq)

        # Recorte por ventana base
        libres_emp_en_base = calcular_interseccion(libres_empleado, [[inicio_min, fin_min]])
        libres_comunes_base = libres_emp_en_base
        if getattr(solicitud, "equipo_id", None):
            libres_comunes_base = calcular_interseccion(libres_emp_en_base, libres_equipo)

        for eff_ini, eff_fin in start_constraint_windows:
            libres_para_pack = libres_comunes_base
            if policy_value == "full_slot" and servicio_windows_abs:
                libres_para_pack = calcular_interseccion(libres_para_pack, servicio_windows_abs)

            inicios_pre = encontrar_slots(
                [eff_ini, eff_fin],
                libres_para_pack,
                duracion_total_slot,
                buffer_previo,
                buffer_posterior,
            )

            for inicio_pre in inicios_pre:
                inicio_dt_abs = base_midnight.add(minutes=inicio_pre)
                fin_dt_abs = inicio_dt_abs.add(minutes=duracion_total_slot)
                resultados.append(
                    {
                        "inicio_slot": inicio_dt_abs,
                        "fin_slot": fin_dt_abs,
                        "empleado_id_asignado": empleado_id,
                        "equipo_id_asignado": getattr(solicitud, "equipo_id", None),
                    }
                )

    resultados.sort(key=lambda s: s["inicio_slot"])  # ordenar por inicio
    return resultados


def gestionar_creacion_reserva(
    solicitud: Any,
    *,
    get_servicio_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    get_horarios_empleados_fn: Optional[Callable[[Any], List[Dict[str, Any]]]] = None,
    get_ocupaciones_fn: Optional[Callable[[List[str], Any, Any], List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Gerente de creación de reservas con doble chequeo anti-colisión.

    - Valida rango y coherencia con el servicio.
    - Reusa el gerente de disponibilidad para confirmar el slot.
    - Revalida contra memoria simulada y crea la reserva.
    """
    logging.info(
        "Gerente(creación): servicio=%s, empleado=%s, equipo=%s, inicio=%s, fin=%s, escenario=%s",
        getattr(solicitud, "servicio_id", None),
        getattr(solicitud, "empleado_id", None),
        getattr(solicitud, "equipo_id", None),
        getattr(solicitud, "inicio_slot", None),
        getattr(solicitud, "fin_slot", None),
        getattr(solicitud, "scenario_id", None),
    )

    if solicitud.fin_slot <= solicitud.inicio_slot:
        raise ValueError("Rango inválido: fin_slot debe ser mayor que inicio_slot")

    # Servicio y cálculo de duración total
    # Servicio: preferir definición del escenario si existe
    escenario = load_scenario(getattr(solicitud, "scenario_id", None)) if getattr(solicitud, "scenario_id", None) else None
    get_servicio = get_servicio_fn or default_get_servicio
    if escenario and "servicios" in escenario and solicitud.servicio_id in escenario["servicios"]:
        svc = escenario["servicios"][solicitud.servicio_id]
    else:
        svc = get_servicio(solicitud.servicio_id)
    if not svc:
        raise ValueError("Servicio no encontrado")

    duracion = int(svc.get("duracion", 0))
    buffer_previo = int(svc.get("buffer_previo", 0))
    buffer_posterior = int(svc.get("buffer_posterior", 0))
    duracion_total_slot = duracion + buffer_previo + buffer_posterior

    delta_min = int((solicitud.fin_slot - solicitud.inicio_slot).total_seconds() // 60)
    if delta_min != duracion_total_slot:
        raise ValueError("Rango del slot no coincide con duración+buffers del servicio")

    # Construir solicitud mínima de disponibilidad centrada en el slot
    solicitud_disp = {
        "servicio_id": solicitud.servicio_id,
        "empleado_id": getattr(solicitud, "empleado_id", None),
        "equipo_id": getattr(solicitud, "equipo_id", None),
        "scenario_id": getattr(solicitud, "scenario_id", None),
        "fecha_inicio_utc": solicitud.inicio_slot,
        "fecha_fin_utc": solicitud.fin_slot,
        "service_window_policy": getattr(solicitud, "service_window_policy", "start_only"),
    }

    # Chequeo de conflicto primero: si existe, retornar 409 desde la API
    if mock_state.has_conflict(
        empleado_id=solicitud.empleado_id,
        equipo_id=getattr(solicitud, "equipo_id", None),
        inicio_dt=solicitud.inicio_slot,
        fin_dt=solicitud.fin_slot,
    ):
        # Se detecta una colisión inmediata; el slot está ocupado.
        raise ValueError("Conflicto: el slot ya no está disponible")

    # Si no hay conflicto, confirmar que el slot solicitado sigue siendo válido
    slots_libres = gestionar_busqueda_disponibilidad(
        solicitud=type("_S", (), solicitud_disp)(),
        get_servicio_fn=get_servicio_fn,
        get_horarios_empleados_fn=get_horarios_empleados_fn,
        get_ocupaciones_fn=get_ocupaciones_fn,
    )

    # Coincidencia exacta del slot solicitado
    def _match(slot: Dict[str, Any]) -> bool:
        # Comparación robusta de tiempos (normalizar a UTC y tipo pendulum)
        s_ini = pendulum.instance(slot.get("inicio_slot")).in_timezone("UTC")
        s_fin = pendulum.instance(slot.get("fin_slot")).in_timezone("UTC")
        rq_ini = pendulum.instance(solicitud.inicio_slot).in_timezone("UTC")
        rq_fin = pendulum.instance(solicitud.fin_slot).in_timezone("UTC")
        if s_ini != rq_ini:
            return False
        if s_fin != rq_fin:
            return False
        if solicitud.empleado_id and slot.get("empleado_id_asignado") != solicitud.empleado_id:
            return False
        if getattr(solicitud, "equipo_id", None) and slot.get("equipo_id_asignado") != solicitud.equipo_id:
            return False
        return True

    candidato = next((s for s in slots_libres if _match(s)), None)
    if not candidato:
        # Re-chequeo inmediato: si ahora hay conflicto en memoria, mapear a 409
        if mock_state.has_conflict(
            empleado_id=solicitud.empleado_id,
            equipo_id=getattr(solicitud, "equipo_id", None),
            inicio_dt=solicitud.inicio_slot,
            fin_dt=solicitud.fin_slot,
        ):
            raise ValueError("Conflicto: el slot ya no está disponible")
        raise ValueError("El slot solicitado no está disponible")

    # Inserción en memoria
    nueva = mock_state.add_reserva(
        servicio_id=solicitud.servicio_id,
        empleado_id=solicitud.empleado_id,
        equipo_id=getattr(solicitud, "equipo_id", None),
        inicio_slot=solicitud.inicio_slot,
        fin_slot=solicitud.fin_slot,
    )

    return {
        "reserva_id": nueva.reserva_id,
        "servicio_id": nueva.servicio_id,
        "empleado_id": nueva.empleado_id,
        "equipo_id": nueva.equipo_id,
        "inicio_slot": nueva.inicio_slot,
        "fin_slot": nueva.fin_slot,
        "creada_en": nueva.creada_en,
        "version": nueva.version,
    }