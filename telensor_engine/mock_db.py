from datetime import datetime, timedelta
from typing import List, Dict


def get_servicio(servicio_id: str) -> Dict:
    """Simula datos de un servicio (duración y buffers)."""
    return {
        "id": servicio_id,
        "duracion": 30,
        "buffer_previo": 10,
        "buffer_posterior": 5,
    }


def get_horarios_empleados(fecha: datetime) -> List[Dict]:
    """Simula horarios de empleados para un día."""
    return [
        {"empleado_id": "E1", "horario_trabajo": [540, 1020]},
        {"empleado_id": "E2", "horario_trabajo": [600, 1080]},
    ]


def get_ocupaciones(empleados: List[str], fecha_inicio: datetime, fecha_fin: datetime) -> List[Dict]:
    """Simula ocupaciones existentes para empleados en un rango."""
    return [
        {
            "empleado_id": "E1",
            "inicio": fecha_inicio + timedelta(minutes=100),
            "fin": fecha_inicio + timedelta(minutes=130),
        },
    ]