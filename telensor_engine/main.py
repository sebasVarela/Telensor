from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
import pendulum
import logging
from enum import Enum

from .engine.engine import (
    calcular_interseccion,
    restar_intervalos,
    encontrar_slots,
)
from .mock_db import (
    get_servicio,
    get_horarios_empleados,
    get_ocupaciones,
)
from .fixtures import load_scenario
from .api.adapter import build_total_blockings
from .api.adapter import gestionar_busqueda_disponibilidad
from .api.adapter import gestionar_creacion_reserva

app = FastAPI(title="Telensor Engine API", version="0.1.0")
logging.basicConfig(level=logging.INFO)


class ServiceWindowPolicy(str, Enum):
    """Política sobre cómo aplicar el horario de atención del servicio.

    - start_only: el horario del servicio limita solo el inicio del slot.
    - full_slot: el horario del servicio limita el inicio y también el fin del slot.
    """
    start_only = "start_only"
    full_slot = "full_slot"




class SolicitudDisponibilidad(BaseModel):
    """Modelo de request para búsqueda de disponibilidad.

    Cambios:
    - Se elimina el soporte para múltiples equipos en el request. Solo se permite `equipo_id` único.
    - Se mantiene la semántica por servicio (sin `empleado_id`) y por empleado (con `empleado_id`).
    - Validación estricta de campos extra para evitar envíos de `equipo_ids` u otros.
    """

    servicio_id: str
    empleado_id: Optional[str] = None
    equipo_id: Optional[str] = None
    fecha_inicio_utc: datetime
    fecha_fin_utc: datetime
    scenario_id: Optional[str] = None
    service_window_policy: ServiceWindowPolicy = ServiceWindowPolicy.start_only

    # Pydantic v2: usar ConfigDict para eliminar advertencia de clase Config
    model_config = ConfigDict(extra="forbid")


class SlotDisponible(BaseModel):
    inicio_slot: datetime
    fin_slot: datetime
    empleado_id_asignado: Optional[str] = None
    equipo_id_asignado: Optional[str] = None


class RespuestaDisponibilidad(BaseModel):
    horarios_disponibles: List[SlotDisponible] = []


class SolicitudReserva(BaseModel):
    """Modelo de entrada para crear una reserva.

    Comentarios:
    - `inicio_slot` y `fin_slot` deben corresponder exactamente a la duración
      total del servicio (duración + buffers) para el `servicio_id` indicado.
    - `empleado_id` es obligatorio; `equipo_id` es opcional.
    - `service_window_policy` se mantiene para coherencia con la búsqueda.
    - `scenario_id` permite reproducir escenarios de pruebas.
    """

    servicio_id: str
    empleado_id: str
    equipo_id: Optional[str] = None
    inicio_slot: datetime
    fin_slot: datetime
    scenario_id: Optional[str] = None
    service_window_policy: ServiceWindowPolicy = ServiceWindowPolicy.start_only

    # Validación estricta de campos extra en creación de reservas
    model_config = ConfigDict(extra="forbid")


class ReservaCreada(BaseModel):
    """Salida estándar tras creación exitosa de una reserva."""

    reserva_id: str
    estado: str = Field(default="confirmada")
    servicio_id: str
    empleado_id: str
    equipo_id: Optional[str] = None
    inicio_slot: datetime
    fin_slot: datetime
    creada_en: datetime
    version: int = 1


@app.post("/api/v1/disponibilidad", response_model=RespuestaDisponibilidad)
async def buscar_disponibilidad(solicitud: SolicitudDisponibilidad) -> RespuestaDisponibilidad:
    """Búsqueda de disponibilidad usando el eje continuo (Sprint 3)."""
    # Validación básica del rango
    if solicitud.fecha_fin_utc <= solicitud.fecha_inicio_utc:
        raise HTTPException(status_code=400, detail="Rango de fechas inválido")

    # No hay validación de múltiples equipos: el request solo acepta `equipo_id` único.

    # Delegación al Gerente: toda la lógica pesada vive en el adaptador.
    try:
        resultados_dict = gestionar_busqueda_disponibilidad(
            solicitud,
            get_servicio_fn=get_servicio,
            get_horarios_empleados_fn=get_horarios_empleados,
            get_ocupaciones_fn=get_ocupaciones,
        )
    except ValueError as e:
        # Mapear errores de validación del Gerente a HTTP 400 para el cliente
        raise HTTPException(status_code=400, detail=str(e))
    resultados_gerente: List[SlotDisponible] = [
        SlotDisponible(
            inicio_slot=item["inicio_slot"],
            fin_slot=item["fin_slot"],
            empleado_id_asignado=item.get("empleado_id_asignado"),
            equipo_id_asignado=item.get("equipo_id_asignado"),
        )
        for item in resultados_dict
    ]
    return RespuestaDisponibilidad(horarios_disponibles=resultados_gerente)

    # Paso 0: Construcción del eje continuo
    inicio_dt = pendulum.instance(solicitud.fecha_inicio_utc).in_timezone("UTC")
    fin_dt = pendulum.instance(solicitud.fecha_fin_utc).in_timezone("UTC")
    base_midnight = inicio_dt.start_of("day")

    inicio_min = int((inicio_dt - base_midnight).total_seconds() // 60)
    fin_min = int((fin_dt - base_midnight).total_seconds() // 60)
    if fin_min <= inicio_min:
        raise HTTPException(status_code=400, detail="Ventana base inválida")

    # Datos de dominio simulados o cargados por escenario
    escenario = load_scenario(solicitud.scenario_id) if solicitud.scenario_id else None
    if escenario and "servicios" in escenario and solicitud.servicio_id in escenario["servicios"]:
        servicio = escenario["servicios"][solicitud.servicio_id]
    else:
        servicio = get_servicio(solicitud.servicio_id)
    buffer_previo = int(servicio.get("buffer_previo", 0))
    buffer_posterior = int(servicio.get("buffer_posterior", 0))
    duracion_servicio = int(servicio.get("duracion", 0))
    duracion_total_slot = buffer_previo + duracion_servicio + buffer_posterior

    # Horarios de empleados y ocupaciones simuladas
    if escenario and "empleados" in escenario:
        horarios = escenario["empleados"]
    else:
        horarios = get_horarios_empleados(base_midnight)  # horario_trabajo en minutos del día
    if solicitud.empleado_id:
        horarios = [h for h in horarios if h["empleado_id"] == solicitud.empleado_id]
        if not horarios:
            return RespuestaDisponibilidad(horarios_disponibles=[])

    empleados_ids = [h["empleado_id"] for h in horarios]
    # Bloqueos totales (empleados, equipo, globales) agregados vía adaptador
    ocupados_por_empleado, ocupados_por_equipo, bloqueos_globales = build_total_blockings(
        base_midnight=base_midnight,
        inicio_dt=inicio_dt,
        fin_dt=fin_dt,
        escenario=escenario,
        empleados_ids=empleados_ids,
        equipo_id=solicitud.equipo_id,
        servicio_id=solicitud.servicio_id,
        get_ocupaciones_fn=get_ocupaciones,
    )

    # Construcción de offsets de día para manejar cruce de medianoche
    cruza_noche = fin_min > 1440
    day_offsets = [0] + ([1440] if cruza_noche else [])
    resultados: List[SlotDisponible] = []

    # 1) Ventanas de atención (restricciones de INICIO)
    # Negocio y servicio delimitan CUÁNDO puede iniciar un slot (inicio de servicio).
    # El recorte de "libres" por negocio/servicio se controla por políticas separadas.
    start_constraint_windows: List[List[int]] = [[inicio_min, fin_min]]
    negocio_windows_abs: List[List[int]] = []
    if escenario and isinstance(escenario.get("horario_atencion_negocio"), list):
        negocio_ini, negocio_fin = escenario["horario_atencion_negocio"]
        negocio_windows_abs = [[negocio_ini + d, negocio_fin + d] for d in day_offsets]
        # Negocio SIEMPRE limita el INICIO (start constraint)
        start_constraint_windows = calcular_interseccion(start_constraint_windows, negocio_windows_abs)

    # Horario de atención específico del servicio (solo restricción de inicio por defecto)
    servicio_windows_abs: List[List[int]] = []
    if escenario and "servicios" in escenario:
        svc = escenario["servicios"].get(solicitud.servicio_id)
        if svc and isinstance(svc.get("horario_atencion"), list):
            svc_att = svc["horario_atencion"]
            servicio_windows_abs = [[svc_att[0] + d, svc_att[1] + d] for d in day_offsets]
            start_constraint_windows = calcular_interseccion(start_constraint_windows, servicio_windows_abs)

    # Si la ventana de inicio efectiva es vacía, no hay atención posible
    if not start_constraint_windows:
        return RespuestaDisponibilidad(horarios_disponibles=[])

    logging.info(
        "Disponibilidad: policy service=%s; start=%s, negocio=%s, servicio=%s, base=[%d,%d]",
        solicitud.service_window_policy,
        start_constraint_windows,
        negocio_windows_abs,
        servicio_windows_abs,
        inicio_min,
        fin_min,
    )

    # Preparar ocupaciones por equipo si corresponde
    ocupados_por_equipo: dict = {}
    equipo_operativo_abs: List[List[int]] = []
    if solicitud.equipo_id:
        # Buscar equipo operativo
        if escenario and "equipos" in escenario:
            eq_list = escenario["equipos"]
            eq_match = next((e for e in eq_list if e.get("equipo_id") == solicitud.equipo_id), None)
            if eq_match and isinstance(eq_match.get("horario_operativo"), list):
                op_ini, op_fin = eq_match["horario_operativo"]
                equipo_operativo_abs = [[op_ini + d, op_fin + d] for d in day_offsets]
        # Si no hay horario operativo definido, asumimos operativo dentro de la ventana base
        if not equipo_operativo_abs:
            equipo_operativo_abs = [[inicio_min, fin_min]]

        # Ocupaciones de equipo ya fueron agregadas por el adaptador si aplican.

    for h in horarios:
        empleado_id = h["empleado_id"]
        trabajo_ini, trabajo_fin = h["horario_trabajo"]
        intervalos_trabajo_abs = [[trabajo_ini + d, trabajo_fin + d] for d in day_offsets]

        # Resta ocupaciones del empleado + bloqueos globales (excepciones de negocio/servicio)
        bloqueos_emp = (ocupados_por_empleado.get(empleado_id, []) or []) + (bloqueos_globales or [])
        libres_empleado = restar_intervalos(intervalos_trabajo_abs, bloqueos_emp)

        # Si hay equipo, calcular libres del equipo
        libres_equipo: List[List[int]] = []
        if solicitud.equipo_id:
            bloqueos_eq = (ocupados_por_equipo.get(solicitud.equipo_id, []) or []) + (bloqueos_globales or [])
            libres_equipo = restar_intervalos(equipo_operativo_abs, bloqueos_eq)

        # Recorte por ventana base para no salir de la búsqueda solicitada
        libres_emp_en_base = calcular_interseccion(libres_empleado, [[inicio_min, fin_min]])
        libres_comunes_base = libres_emp_en_base
        if solicitud.equipo_id:
            libres_comunes_base = calcular_interseccion(libres_emp_en_base, libres_equipo)

        # Para cada ventana efectiva de INICIO (negocio ∩ servicio ∩ base)
        for eff_ini, eff_fin in start_constraint_windows:
            # Aplicación de políticas de recorte del FIN del slot
            libres_para_pack = libres_comunes_base
            # Negocio: la ventana de negocio siempre limita el INICIO; ya aplicada en start_constraint_windows.
            # No recortamos el FIN del slot por negocio; el recorte completo lo gobierna service_window_policy.
            # Servicio recorta fin del slot solo si policy=full_slot
            if solicitud.service_window_policy == ServiceWindowPolicy.full_slot and servicio_windows_abs:
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
                logging.info(
                    "slot generado: empleado=%s, equipo=%s, inicio_pre=%d, dur_total=%d, inicio=%s, fin=%s",
                    empleado_id,
                    solicitud.equipo_id,
                    inicio_pre,
                    duracion_total_slot,
                    inicio_dt_abs.to_iso8601_string(),
                    fin_dt_abs.to_iso8601_string(),
                )
                resultados.append(
                    SlotDisponible(
                        inicio_slot=inicio_dt_abs,
                        fin_slot=fin_dt_abs,
                        empleado_id_asignado=empleado_id,
                        equipo_id_asignado=solicitud.equipo_id,
                    )
                )

    # Ordenar por inicio de slot
    resultados.sort(key=lambda s: s.inicio_slot)
    return RespuestaDisponibilidad(horarios_disponibles=resultados)


@app.post("/api/v1/reservas", response_model=ReservaCreada, status_code=201)
async def crear_reserva(solicitud: SolicitudReserva) -> ReservaCreada:
    """Crea una reserva validando disponibilidad y previniendo colisiones.

    Este endpoint actúa como "Director" y delega en el Gerente
    `gestionar_creacion_reserva` toda la lógica de negocio.
    """
    # Validación básica del rango
    if solicitud.fin_slot <= solicitud.inicio_slot:
        raise HTTPException(status_code=400, detail="Rango de fechas inválido para la reserva")

    try:
        creada = gestionar_creacion_reserva(
            solicitud,
            get_servicio_fn=get_servicio,
            get_horarios_empleados_fn=get_horarios_empleados,
            get_ocupaciones_fn=get_ocupaciones,
        )
    except ValueError as e:
        msg = str(e)
        if "Conflicto" in msg or "conflicto" in msg:
            raise HTTPException(status_code=409, detail="Conflicto: el slot ya no está disponible")
        raise HTTPException(status_code=400, detail=msg or "Error de validación en la creación de reserva")

    return ReservaCreada(**creada)
