from telensor_engine.engine.engine import (
    calcular_interseccion,
    restar_intervalos,
    encontrar_slots,
)


def test_restar_intervalos_simples():
    base = [[1200, 1680]]
    ocupados = [[1300, 1330]]
    libres = restar_intervalos(base, ocupados)
    assert libres == [[1200, 1300], [1330, 1680]]


def test_restar_intervalos_complejos():
    base = [[540, 1020]]
    ocupados = [[600, 650], [700, 710], [750, 800]]
    libres = restar_intervalos(base, ocupados)
    assert libres == [[540, 600], [650, 700], [710, 750], [800, 1020]]


def test_turno_nocturno_resta():
    base = [[1200, 1680]]  # 20:00 Día 1 a 04:00 Día 2
    ocupados_totales = [[1300, 1330], [1500, 1560]]  # día 2 desfasado +1440
    libres = restar_intervalos(base, ocupados_totales)
    assert libres == [[1200, 1300], [1330, 1500], [1560, 1680]]


def test_interseccion_basica():
    a = [[480, 1200]]
    b = [[600, 840]]
    inter = calcular_interseccion(a, b)
    assert inter == [[600, 840]]


def test_empaquetado_con_buffer_previo():
    ventana_efectiva = [600, 840]  # 10:00-14:00
    libres_comunes = [[540, 1020]]  # empleado libre 9:00-17:00
    duracion_total_slot = 45  # 10 + 30 + 5
    buffer_previo = 10
    buffer_posterior = 5

    inicios = encontrar_slots(
        ventana_efectiva,
        libres_comunes,
        duracion_total_slot,
        buffer_previo,
        buffer_posterior,
    )

    # El arranque alineado debe comenzar en max(540, 600-10)=590
    # Saltos de 45: 590, 635, 680, 725, 770, 815, 860...
    # El inicio de servicio (arranque+10) debe estar < 840
    assert inicios[:6] == [590, 635, 680, 725, 770, 815]
    # 860 (servicio a 870) no debe incluirse por exceder ventana efectiva
    assert 860 not in inicios