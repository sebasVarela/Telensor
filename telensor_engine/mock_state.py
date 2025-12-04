"""
Memoria simulada de reservas e inactividades para la Fase 2.

Este módulo mantiene un estado en memoria seguro para pruebas locales,
con funciones utilitarias para agregar, listar y resetear reservas.

Notas de diseño:
- Las reservas se almacenan con tiempos en UTC (datetime aware).
- Se provee un candado (Lock) para proteger escrituras concurrentes.
- Se expone un chequeo de solapamiento simple para anti-colisión.

IMPORTANTE: En producción esto se reemplazará por una base de datos
real con garantías de concurrencia. Esta implementación está enfocada
en pruebas y E2E locales del Sprint.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# Candado global para operaciones de escritura
_lock = threading.Lock()


@dataclass
class Reserva:
    """Representa una reserva creada en el sistema.

    Atributos:
    - reserva_id: identificador único de la reserva
    - servicio_id: id del servicio reservado
    - empleado_id: id del empleado asignado
    - equipo_id: id del equipo asignado (opcional)
    - inicio_slot: inicio del slot del servicio (UTC)
    - fin_slot: fin del slot del servicio (UTC)
    - creada_en: timestamp de creación (UTC)
    - version: número de versión para futuras estrategias de concurrencia
    """

    reserva_id: str
    servicio_id: str
    empleado_id: str
    equipo_id: Optional[str]
    inicio_slot: datetime
    fin_slot: datetime
    creada_en: datetime
    estado: str = "confirmada"
    scenario_id: Optional[str] = None
    version: int = 1


# Estado en memoria
MOCK_RESERVAS: List[Reserva] = []
MOCK_INACTIVIDADES: List[Dict[str, Any]] = []  # Espacio para inactividades futuras
MOCK_BLOQUEOS: List[Dict[str, Any]] = []  # Bloqueos operativos (business/employee/equipment/service)


def reset_state() -> None:
    """Resetea el estado de memoria (reservas e inactividades)."""
    global MOCK_RESERVAS, MOCK_INACTIVIDADES, MOCK_BLOQUEOS
    with _lock:
        MOCK_RESERVAS = []
        MOCK_INACTIVIDADES = []
        MOCK_BLOQUEOS = []


def _gen_reserva_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"R-{ts}-{len(MOCK_RESERVAS) + 1}"


def list_reservas() -> List[Reserva]:
    """Devuelve una copia superficial de las reservas actuales."""
    return list(MOCK_RESERVAS)


def get_reservas_en_rango(inicio_dt: datetime, fin_dt: datetime) -> List[Reserva]:
    """Obtiene reservas que se solapan con el rango [inicio_dt, fin_dt]."""
    solapadas: List[Reserva] = []
    for r in MOCK_RESERVAS:
        # Solapamiento si inicio < fin_reserva y fin > inicio_reserva
        if inicio_dt < r.fin_slot and fin_dt > r.inicio_slot:
            solapadas.append(r)
    return solapadas


def has_conflict(
    *,
    empleado_id: str,
    equipo_id: Optional[str],
    inicio_dt: datetime,
    fin_dt: datetime,
) -> bool:
    """Indica si existe conflicto de solapamiento para empleado/equipo.

    La política es conservadora: cualquier solapamiento en el mismo empleado
    o, si se especifica, en el mismo equipo, se considera conflicto.
    """
    for r in MOCK_RESERVAS:
        if r.empleado_id != empleado_id:
            continue
        if equipo_id is not None and r.equipo_id != equipo_id:
            continue
        if inicio_dt < r.fin_slot and fin_dt > r.inicio_slot:
            return True
    return False


def add_reserva(
    *,
    servicio_id: str,
    empleado_id: str,
    equipo_id: Optional[str],
    inicio_slot: datetime,
    fin_slot: datetime,
    scenario_id: Optional[str] = None,
) -> Reserva:
    """Agrega una reserva al estado si no existe conflicto.

    Lanza ValueError si existe conflicto o si el rango es inválido.
    """
    if fin_slot <= inicio_slot:
        raise ValueError("Rango de tiempo inválido para la reserva")

    with _lock:
        if has_conflict(
            empleado_id=empleado_id,
            equipo_id=equipo_id,
            inicio_dt=inicio_slot,
            fin_dt=fin_slot,
        ):
            raise ValueError("Conflicto: el slot ya no está disponible")

        reserva = Reserva(
            reserva_id=_gen_reserva_id(),
            servicio_id=servicio_id,
            empleado_id=empleado_id,
            equipo_id=equipo_id,
            inicio_slot=inicio_slot,
            fin_slot=fin_slot,
            creada_en=datetime.now(timezone.utc),
            scenario_id=scenario_id,
        )
        MOCK_RESERVAS.append(reserva)
        return reserva


def update_reserva(
    *,
    reserva_id: str,
    empleado_id: Optional[str] = None,
    equipo_id: Optional[str] = None,
    estado: Optional[str] = None,
) -> Optional[Reserva]:
    """Actualiza campos de una reserva existente.

    Si no se encuentra, retorna None.
    """
    with _lock:
        for r in MOCK_RESERVAS:
            if r.reserva_id == reserva_id:
                if empleado_id is not None:
                    r.empleado_id = empleado_id
                if equipo_id is not None:
                    r.equipo_id = equipo_id
                if estado is not None:
                    r.estado = estado
                return r
    return None


def add_bloqueo(bloqueo: Dict[str, Any]) -> Dict[str, Any]:
    """Agrega un bloqueo operativo en memoria.

    Espera claves: inicio_utc (datetime), fin_utc (datetime), motivo (str),
    scope ("business"|"employee"|"equipment"|"service"), y listas opcionales
    empleado_ids, equipo_ids, servicio_ids.
    """
    with _lock:
        bloqueo_id = f"B-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-{len(MOCK_BLOQUEOS)+1}"
        rec = dict(bloqueo)
        rec["id"] = bloqueo_id
        MOCK_BLOQUEOS.append(rec)
        return rec


def get_bloqueos_intersecting(
    inicio_dt: datetime,
    fin_dt: datetime,
    recursos: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
    """Devuelve bloqueos que se solapan con [inicio_dt, fin_dt) y, si se
    especifican recursos, que aplican a esos IDs.

    recursos puede incluir: empleado_ids, equipo_ids, servicio_ids.
    Los bloqueos con scope="business" siempre aplican.
    """
    recursos = recursos or {}
    empleados = set(recursos.get("empleado_ids", []) or [])
    equipos = set(recursos.get("equipo_ids", []) or [])
    servicios = set(recursos.get("servicio_ids", []) or [])

    res: List[Dict[str, Any]] = []
    for b in list(MOCK_BLOQUEOS):
        bi = b.get("inicio_utc")
        bf = b.get("fin_utc")
        if not isinstance(bi, datetime) or not isinstance(bf, datetime):
            continue
        # Solapamiento temporal
        if not (inicio_dt < bf and fin_dt > bi):
            continue
        sc = str(b.get("scope", "")).lower()
        if sc == "business":
            res.append(b)
            continue
        if sc == "employee":
            ids = set(b.get("empleado_ids", []) or [])
            if not ids:
                continue
            if not empleados:
                # Si no se especifican recursos, consideramos que aplica
                res.append(b)
            elif ids & empleados:
                res.append(b)
            continue
        if sc == "equipment":
            ids = set(b.get("equipo_ids", []) or [])
            if not ids:
                continue
            if not equipos:
                res.append(b)
            elif ids & equipos:
                res.append(b)
            continue
        if sc == "service":
            ids = set(b.get("servicio_ids", []) or [])
            if not ids:
                continue
            if not servicios:
                res.append(b)
            elif ids & servicios:
                res.append(b)
            continue
    return res
