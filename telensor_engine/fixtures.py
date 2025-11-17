from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def load_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Carga un escenario de pruebas desde docs/test_scenarios.json.

    Estructura esperada:
    {
      "scenarios": {
        "id": {
          "servicios": { "SVC1": {"duracion": int, "buffer_previo": int, "buffer_posterior": int} },
          "empleados": [ {"empleado_id": str, "horario_trabajo": [ini_min, fin_min]} ],
          "equipos": [ {"equipo_id": str} ],
          "ocupaciones": [ {"empleado_id": str, "inicio": iso_datetime, "fin": iso_datetime} ]
        }
      }
    }
    """
    # Determinar raíz del proyecto (uno arriba del paquete)
    root = Path(__file__).resolve().parent.parent  # /.../Telensor
    scenarios_path = root / "docs" / "test_scenarios.json"
    if not scenarios_path.exists():
        return None
    try:
        with scenarios_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        scenarios = payload.get("scenarios", {})
        return scenarios.get(scenario_id)
    except Exception:
        return None