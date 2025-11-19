from datetime import datetime, timedelta
from typing import List, Dict, Optional


def get_servicio(servicio_id: str) -> Dict:
    """Simula datos de un servicio (duración y buffers)."""
    return {
        "id": servicio_id,
        "duracion": 30,
        "buffer_previo": 10,
        "buffer_posterior": 5,
    }


def get_horarios_empleados(
    fecha: datetime,
    *,
    servicio_id: Optional[str] = None,
    equipo_id: Optional[str] = None,
) -> List[Dict]:
    """Simula horarios de empleados para un día con asignaciones y filtros.

    - servicios_asignados: IDs de servicios que el empleado puede realizar.
    - equipos_asignados: IDs de equipos que el empleado puede usar.
    - Filtros opcionales:
      - servicio_id: devuelve solo empleados que tengan ese servicio asignado.
      - equipo_id: devuelve solo empleados que tengan ese equipo asignado.
    - Modo estricto: si los filtros dejan la lista vacía, retorna lista vacía
      para asegurar que solo se consideren empleados calificados.
    """

    base = [
        {
            "empleado_id": "E1",
            "horario_trabajo": [540, 1020],
            "servicios_asignados": ["SVC1", "SVC2"],
            "equipos_asignados": ["EQ1"],
        },
        {
            "empleado_id": "E2",
            "horario_trabajo": [600, 1080],
            "servicios_asignados": ["SVC2"],
            "equipos_asignados": ["EQ1", "EQ2"],
        },
    ]

    filtered = base
    if servicio_id:
        filtered = [e for e in filtered if servicio_id in e.get("servicios_asignados", [])]
    if equipo_id:
        filtered = [e for e in filtered if equipo_id in e.get("equipos_asignados", [])]

    # Modo estricto: devolver solo los empleados que cumplen filtros (o vacío)
    return filtered


def get_ocupaciones(empleados: List[str], fecha_inicio: datetime, fecha_fin: datetime) -> List[Dict]:
    """Simula ocupaciones existentes para empleados en un rango."""
    return [
        {
            "empleado_id": "E1",
            "inicio": fecha_inicio + timedelta(minutes=100),
            "fin": fecha_inicio + timedelta(minutes=130),
        },
    ]