1. Si olvidas algo, consultar el archivo `docs/Telensor_Engine.md`o `docs/fase1_telensor.md`.
2. La seguridad es primordial. 
3. Lo que construyes debe ser pensando en un producto comercial y profesional que cumpla con los estándares de seguridad.
4. Debe ser escalable.
5. Siempre que vayas a crear una nueva función, clase, endpoint o modelo, REVISA primero `docs/code_registry.json`.
6. Si encuentras un símbolo con el mismo propósito, REUTILIZALO. No crees una variante con otro nombre.
7. Si no existe, créalo y AGREGA una entrada al `docs/code_registry.json`.
8. Todos los símbolos deben tener:
   - `name`
   - `kind` (function, class, dataclass, fastapi_endpoint, sqlalchemy_model)
   - `location.file`
   - `module`
9. Si el símbolo de la API solo envuelve a una función de dominio, agrega `"wraps": "<ruta.funcion.dominio>"`.
10. No elimines entradas del registro; márcalas como `"status": "deprecated"`.