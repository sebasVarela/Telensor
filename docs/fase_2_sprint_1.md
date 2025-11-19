# **Plan de Desarrollo \- Fase 2, Sprint 1**

**Meta:** Implementar la lógica para *crear* una reserva. Esto incluye un nuevo endpoint (POST) y la lógica de negocio fundamental para prevenir que dos personas reserven el mismo slot a la vez (anti-colisión).

Seguiremos 100% en modo local, sin conectarnos aún a la base de datos real.

### **Tarea 1: Crear una "Base de Datos Simulada" con Memoria**

**El Problema:** Nuestros *mocks* actuales (test\_scenarios.json \[cite: sebasvarela/telensor/Telensor-b658f2048ca4af73df618a476adc311ca0f7d488/docs/test\_scenarios.json\]) son de solo lectura. Si creamos una reserva en una prueba, desaparece en la siguiente llamada. No tenemos "memoria" entre peticiones.

**La Solución:**

1. Crearemos un nuevo archivo (mock\_state.py) que actuará como nuestra base de datos en memoria.  
2. Este archivo contendrá listas vacías para MOCK\_RESERVAS y MOCK\_INACTIVIDADES.  
3. También tendrá una función para "limpiar" estas listas, asegurando que cada prueba comience desde cero.

### **Tarea 2: Actualizar el "Gerente" de Disponibilidad (Lectura)**

**El Problema:** Nuestro "Gerente" de disponibilidad (gestionar\_busqueda\_disponibilidad \[cite: sebasvarela/telensor/Telensor-b658f2048ca4af73df618a476adc311ca0f7d488/telensor\_engine/api/adapter.py\]) solo sabe leer los escenarios estáticos \[cite: sebasvarela/telensor/Telensor-b658f2048ca4af73df618a476adc311ca0f7d488/docs/test\_scenarios.json\]. No sabe que existen las nuevas reservas que crearemos en mock\_state.

**La Solución:**

1. Modificaremos la lógica del "Gerente" de disponibilidad.  
2. Cuando construya la lista de "Bloqueos Totales" \[cite: sebasvarela/telensor/Telensor-b658f2048ca4af73df618a476adc311ca0f7d488/telensor\_engine/api/adapter.py\], ahora deberá combinar **dos** fuentes:  
   * Los bloqueos del escenario (test\_scenarios.json).  
   * Los bloqueos de la memoria (mock\_state.MOCK\_RESERVAS).  
3. Esto asegura que una reserva creada en memoria bloquee la disponibilidad en la siguiente llamada GET.

### **Tarea 3: Definir los Contratos de Datos (POST)**

**La Tarea:** Definiremos formalmente las "plantillas" JSON para la creación de reservas en main.py \[cite: sebasvarela/telensor/Telensor-b658f2048ca4af73df618a476adc311ca0f7d488/telensor\_engine/main.py\].

1. **Solicitud de Reserva (Entrada):** Qué datos esperamos del cliente (ej. ID del servicio, ID del empleado, hora de inicio, hora de fin).  
2. **Reserva Creada (Salida):** Qué datos le devolveremos al cliente (ej. ID de la reserva, estado "confirmada", horas).

### **Tarea 4: Implementar la Lógica de Creación (El "Doble Chequeo")**

Esta es la tarea central del sprint.

1. **Crear el "Director" (Endpoint):**  
   * Crearemos un nuevo endpoint POST /api/v1/reservas en main.py \[cite: sebasvarela/telensor/Telensor-b658f2048ca4af73df618a476adc311ca0f7d488/telensor\_engine/main.py\].  
   * Siguiendo nuestro patrón, este endpoint será "tonto": solo recibirá la solicitud y se la pasará a un nuevo "Gerente" de creación.  
2. **Crear el "Gerente" (Lógica de Creación):**  
   * Crearemos una nueva función "Gerente" en el adaptador (ej. gestionar\_creacion\_reserva).  
   * Esta función implementará la lógica crucial de **"Doble Chequeo" (Anti-Colisión)**.

**Flujo del "Doble Chequeo":**

1. El "Gerente" recibe la solicitud para reservar (ej. "10:00 con Empleado A").  
2. **Verifica de Nuevo:** Vuelve a consultar la disponibilidad *exacta* para "10:00 con Empleado A", mirando **todos** los bloqueos (de escenarios Y de mock\_state).  
3. **Decide:**  
   * **Si el slot sigue libre:** La reserva es válida. La añade a la lista mock\_state.MOCK\_RESERVAS y devuelve un éxito (201 Created).  
   * **Si el slot está ocupado:** (Significa que otro usuario lo reservó hace milisegundos). Rechaza la solicitud con un error de "Conflicto" (409).

### **Tarea 5: Criterio de Éxito (El Plan de Prueba)**

Sabremos que el sprint fue un éxito si podemos ejecutar la siguiente prueba *End-to-End* en nuestra interfaz de Swagger local:

1. **Llamada 1 (GET):** Pedimos disponibilidad. Vemos que el slot "10:00" está **libre**.  
2. **Llamada 2 (POST):** Creamos una reserva para el slot "10:00". La API responde **Éxito (201)**.  
3. **Llamada 3 (GET):** Pedimos disponibilidad *otra vez*. El slot "10:00" ahora aparece **ocupado** (gracias a mock\_state).  
4. **Llamada 4 (POST):** Intentamos crear una reserva para "10:00" *de nuevo*. La API responde **Fallo (409 Conflicto)** (gracias al "Doble Chequeo").