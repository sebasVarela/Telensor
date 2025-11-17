from typing import List
import logging


def _merge_intervals(intervalos: List[List[int]]) -> List[List[int]]:
    if not intervalos:
        return []
    ordenados = sorted(intervalos, key=lambda x: (x[0], x[1]))
    merged: List[List[int]] = []
    cur_s, cur_e = ordenados[0]
    for s, e in ordenados[1:]:
        if s <= cur_e:  # trata [s,e) como semiabierto, une adyacentes
            if e > cur_e:
                cur_e = e
        else:
            merged.append([cur_s, cur_e])
            cur_s, cur_e = s, e
    merged.append([cur_s, cur_e])
    return merged


def calcular_interseccion(lista_a: List[List[int]], lista_b: List[List[int]]) -> List[List[int]]:
    """
    Intersección de dos listas de intervalos [ini, fin) en minutos absolutos.
    Acepta intervalos desordenados y solapados; retorna lista normalizada.
    """
    a = _merge_intervals(lista_a)
    b = _merge_intervals(lista_b)
    if not a or not b:
        return []
    i = j = 0
    res: List[List[int]] = []
    while i < len(a) and j < len(b):
        s = max(a[i][0], b[j][0])
        e = min(a[i][1], b[j][1])
        if s < e:
            res.append([s, e])
        # avanzar el que termina primero
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return res


def restar_intervalos(base: List[List[int]], ocupados: List[List[int]]) -> List[List[int]]:
    """
    Resta la unión de "ocupados" a la lista "base" y devuelve los libres.
    Opera en el eje continuo con intervalos [ini, fin) en minutos absolutos.
    """
    if not base:
        return []
    base_n = _merge_intervals(base)
    occ_n = _merge_intervals(ocupados)
    libres: List[List[int]] = []
    j = 0
    for bs, be in base_n:
        cursor = bs
        # avanzar ocupados que terminan antes del inicio de base
        while j < len(occ_n) and occ_n[j][1] <= bs:
            j += 1
        k = j
        while k < len(occ_n) and occ_n[k][0] < be:
            os, oe = occ_n[k]
            # tramo libre antes del ocupado
            if os > cursor:
                libres.append([cursor, min(os, be)])
            # mover cursor al final del ocupado si solapa
            if oe > cursor:
                cursor = max(cursor, oe)
            k += 1
        if cursor < be:
            libres.append([cursor, be])
    return libres


def encontrar_slots(
    ventana_base_efectiva: List[int],
    libres_comunes: List[List[int]],
    duracion_total_slot: int,
    buffer_previo: int,
    buffer_posterior: int,
) -> List[int]:
    """
    Itera por "saltos de slot" dentro de cada libre común y devuelve los
    inicios "pre" (minuto absoluto) de cada slot válido.

    Validaciones:
    - Inicio de servicio dentro de la ventana efectiva [eff_ini, eff_fin).
    - Slot completo dentro del libre común: inicio_pre + duracion_total <= libre_fin.
    """
    if not libres_comunes:
        return []
    eff_ini, eff_fin = ventana_base_efectiva
    inicios: List[int] = []
    for libre_ini, libre_fin in libres_comunes:
        arranque = max(libre_ini, eff_ini - buffer_previo)
        logging.info(
            "slots: libre=[%d,%d], eff=[%d,%d], dur=%d, pre=%d, post=%d",
            libre_ini,
            libre_fin,
            eff_ini,
            eff_fin,
            duracion_total_slot,
            buffer_previo,
            buffer_posterior,
        )
        while arranque + duracion_total_slot <= libre_fin:
            inicio_servicio = arranque + buffer_previo
            if eff_ini <= inicio_servicio < eff_fin:
                inicios.append(arranque)
            arranque += duracion_total_slot
    return inicios