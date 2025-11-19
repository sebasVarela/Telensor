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
    version: int = 1


# Estado en memoria
MOCK_RESERVAS: List[Reserva] = []
MOCK_INACTIVIDADES: List[Dict[str, Any]] = []  # Espacio para inactividades futuras


def reset_state() -> None:
    """Resetea el estado de memoria (reservas e inactividades)."""
    global MOCK_RESERVAS, MOCK_INACTIVIDADES
    with _lock:
        MOCK_RESERVAS = []
        MOCK_INACTIVIDADES = []


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
        )
        MOCK_RESERVAS.append(reserva)
        return reserva