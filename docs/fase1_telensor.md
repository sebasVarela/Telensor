# **Plan de Desarrollo \- Fase 1: Motor de Reservas (FastAPI)**

**Objetivo de la Fase:** Tener un microservicio de FastAPI funcional y desplegado, donde podamos probar la lógica completa del motor usando datos *mock* (simulados) a través de la interfaz de Swagger UI.

## **Sprint 1: Fundación, Modelos y Entorno**

**Meta:** Tener un servidor FastAPI corriendo con los *endpoints* vacíos y los modelos de datos (contratos) definidos.

1. **Configurar el Entorno de Desarrollo:**  
   * Crear la carpeta del proyecto (ej. telensor\_engine).  
   * Crear un entorno virtual de Python (python \-m venv venv).  
   * Instalar las dependencias base: pip install fastapi uvicorn pendulum httpx  
     * fastapi: El framework.  
     * uvicorn: El servidor para correrlo.  
     * pendulum: Una librería excelente para el manejo de fechas y traducciones (tu "Adaptador" la amará).  
     * httpx: Para hacer llamadas a Directus (aunque lo simularemos primero).  
2. **Definir la Estructura del Proyecto:**  
   * Crear la estructura de archivos que discutimos:  
     telensor\_engine/  
     ├── main.py            \# El Adaptador (FastAPI)  
     ├── engine/  
     │   ├── \_\_init\_\_.py  
     │   └── engine.py       \# El Motor (Lógica Pura)  
     ├── mock\_db.py         \# Módulo para simular la BD de Directus  
     ├── requirements.txt  
     └── .gitignore

3. **Definir los Contratos (Modelos Pydantic):**  
   * En main.py, definir los modelos Pydantic que tu API recibirá y devolverá. Esto es clave para Swagger UI.  
   * **SolicitudDisponibilidad (Entrada):**  
     * servicio\_id: str  
     * empleado\_id: Optional\[str\] (si el cliente elige uno)  
     * equipo\_id: Optional\[str\]  
     * fecha\_inicio\_utc: datetime (ej. "2025-11-20T09:00:00Z")  
     * fecha\_fin\_utc: datetime (ej. "2025-11-20T17:00:00Z")  
     * service\_window\_policy: ServiceWindowPolicy ("start_only" por defecto)  
   * **SlotDisponible (Salida):**  
     * inicio\_slot: datetime  
     * fin\_slot: datetime  
     * empleado\_id\_asignado: str  
     * equipo\_id\_asignado: str  
   * **RespuestaDisponibilidad (Salida):**  
     * horarios\_disponibles: List\[SlotDisponible\]  
4. **Crear el Endpoint (Vacío):**  
   * En main.py, crear el endpoint principal que use estos modelos. Por ahora, solo devolverá datos de ejemplo.  
     \# (Importaciones de FastAPI, Pydantic, datetime...)

     app \= FastAPI()

     \# (Definición de modelos Pydantic aquí...)

     @app.post("/api/v1/disponibilidad", response\_model=RespuestaDisponibilidad)  
     async def buscar\_disponibilidad(solicitud: SolicitudDisponibilidad):  
         \# Lógica (aún no hecha)  
         return {"horarios\_disponibles": \[\]}

5. **Crear el Módulo de Mocking (mock\_db.py):**  
   * Crear funciones que simulen las llamadas a Directus. Esto es **crucial** para probar la Fase 1\.  
   * def get\_servicio(servicio\_id): \-\> Devuelve un servicio con { duracion: 30, buffer\_previo: 10, ... }  
   * def get\_horarios\_empleados(fecha): \-\> Devuelve los horarios (con la lógica de *horario default*).  
   * def get\_ocupaciones(empleados, fecha\_inicio, fecha\_fin): \-\> Devuelve una lista de citas ya existentes (ej. \[{empleado: 'E1', inicio: '...', fin: '...'}, ...\]).

**✅ Resultado del Sprint 1:** Al correr uvicorn main:app \--reload, puedes ir a http://127.0.0.1:8000/docs, ver tu endpoint, enviarle un JSON de prueba y recibir una respuesta vacía (\[\]).

## **Sprint 2: El Cerebro (Implementación del Motor Puro)**

**Meta:** Implementar la lógica de álgebra de intervalos en engine/engine.py. Esta parte no sabe nada de FastAPI ni de fechas.

1. **Implementar Álgebra de Intervalos:**  
   * En engine/engine.py, crear las funciones "helper" que son la base de todo.  
   * def calcular\_interseccion(lista\_a: List\[List\[int\]\], lista\_b: List\[List\[int\]\]) \-\> List\[List\[int\]\]  
   * def restar\_intervalos(base: List\[List\[int\]\], ocupados: List\[List\[int\]\]) \-\> List\[List\[int\]\]  
2. **Implementar el "Empaquetado" (Paso 5 del .md):**  
   * Crear la función principal del motor: def encontrar\_slots(...).  
   * Esta función recibe la ventana\_base\_efectiva, los libres\_comunes (empleado \+ equipo), y las reglas del slot (duración total, buffer previo, etc.).  
   * Implementa la lógica de iteración (el "salto de slot") y las validaciones de "Arranque Alineado".  
   * Devuelve una lista de minutos absolutos de inicio: \[540, 580, 620, ...\].  
3. **Pruebas Unitarias (Opcional pero recomendado):**  
   * Instalar pip install pytest.  
   * Crear un archivo engine/test\_engine.py.  
   * Escribir pruebas *específicas* para la lógica del motor:  
     * test\_restar\_intervalos\_simples()  
     * test\_restar\_intervalos\_complejos()  
     * test\_turno\_nocturno() (usando minutos absolutos \> 1440\)  
     * test\_empaquetado\_con\_buffer\_previo() (el "Arranque Alineado")

**✅ Resultado del Sprint 2:** El módulo engine/engine.py está 100% terminado y probado. Es un "cerebro" funcional que aún no está conectado a la API.

## **Sprint 3: El Adaptador y Prueba E2E (End-to-End)**

**Meta:** Conectar el "Cerebro" (Motor) con la "Boca" (FastAPI) y probar el flujo completo usando Swagger UI.

1. **Implementar el "Adaptador" (Paso 0 y 6):**  
   * Volver a main.py, al endpoint @app.post("/api/v1/disponibilidad").  
   * **Paso 0 (Traducción):**  
     * Usar pendulum para convertir solicitud.fecha\_inicio\_utc en la ventana\_base de minutos absolutos.  
     * Llamar a tus funciones de mock\_db.py para obtener los datos.  
     * Llamar a engine/engine.py para calcular los libres\_comunes (intersección, resta, etc.).  
   * **Llamar al Motor:**  
     * Llamar a engine.motor.encontrar\_slots(...) con todos los datos puros.  
   * **Paso 6 (De-traducción):**  
     * Tomar la lista de minutos absolutos \[540, 580, ...\] devuelta por el motor.  
     * Usar pendulum para convertir esos minutos de vuelta en objetos datetime UTC.  
     * Poblar el modelo RespuestaDisponibilidad y devolverlo.  
2. **Prueba E2E con Swagger UI:**  
   * Correr uvicorn main:app \--reload.  
   * Ir a http://127.0.0.1:8000/docs.  
   * Usar la interfaz de Swagger para enviar una solicitud real.  
   * **Prueba 1 (Día Normal):** Buscar en un día de 9:00 a 17:00. Verificar que los slots devueltos sean correctos según tus datos en mock\_db.py.  
   * **Prueba 2 (Turno Nocturno):** Buscar de 20:00 de un día a 04:00 del día siguiente. Verificar que el motor y el adaptador manejen correctamente el eje continuo.  
   * **Prueba 3 (Sin Disponibilidad):** Buscar en un día donde el empleado está totalmente ocupado en mock\_db.py. Verificar que la respuesta sea \[\].  
3. **(Opcional) Despliegue en Cloud Run:**  
   * Crear un Procfile: web: uvicorn main:app \--host 0.0.0.0 \--port $PORT  
   * Crear requirements.txt: pip freeze \> requirements.txt  
   * Instalar gcloud CLI.  
   * Correr gcloud run deploy mi-motor-reservas \--source . \--allow-unauthenticated  
   * En 2 minutos, tendrás una URL pública para tu motor.

**✅ Resultado del Sprint 3:** ¡Fase 1 completada\! Tienes un endpoint de API desplegado en la nube que implementa tu lógica de negocio completa y está listo para ser consumido por el WhatsApp Flow.

## **Actualización Fase 1: Modelo de Excepciones y Bloqueos Unificados**

Para simplificar la configuración y mantener el motor puro, se adopta un **modelo unificado de Excepciones** que reemplaza la dependencia operativa en el "Horario de Negocio". El control de inicio/fin de slots permanece con `service_window_policy`.

- **Disponibilidad Bruta**: Intersección `servicio ∩ empleado ∩ equipo` en el eje continuo de minutos absolutos.
- **Bloqueos Totales**: Unión de ocupaciones (reservas existentes, inactividad de empleado, mantenimiento de equipo) + **Excepciones** (cierres globales/feriados, restricciones puntuales de servicio, excepciones por empleado/equipo).
- **Adaptador (FastAPI)**: Nueva función `telensor_engine.api.adapter.build_total_blockings` que:
  - Traduce fechas/horas al eje continuo (con `_to_minute_range`).
  - Agrega bloqueos por `empleado`, por `equipo` y `globales` (scope: `business`, `employee`, `equipment`, `service`).
  - Permite inyección de `get_ocupaciones` desde `main.py` para habilitar monkeypatch en tests y mocking.
  - Devuelve tres colecciones listas para restar del eje: `(bloqueos_empleado, bloqueos_equipo, bloqueos_globales)`.

### Políticas
- **`service_window_policy`** (vigente):
  - `start_only`: restringe el inicio del servicio.
  - `full_slot`: recorta inicio y fin del slot por el horario del servicio.
### Políticas y Compatibilidad
- La Política de Ventana de Negocio fue eliminada. La ventana de negocio funciona como restricción de INICIO del servicio (start constraint) y los cierres se modelan como **Excepciones**.
- Se mantiene compatibilidad mediante escenarios de prueba (`test_scenarios.json`) y pruebas que validan excepciones y políticas de servicio (`service_window_policy`).

### Beneficios
- Configuración más simple para el usuario (cambios en cierres/feriados en un solo lugar).
- Motor libre de reglas operativas, centrado en álgebra de intervalos.
- Adaptador orquesta políticas y contexto, permitiendo trazabilidad y pruebas más claras.
### Excepciones en Fase 1
- Para pruebas, las excepciones se definen en `docs/test_scenarios.json`.
- Para producción, deben provenir de la fuente de datos (p. ej., Directus).