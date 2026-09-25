# LABORATORIO: detección de flanco de enlace y recordatorio por tiempo.
import ipaddress
import time
import psutil
import config

_anterior = None
_ultima_alerta = None


def _es_virtual(nombre, direcciones):
    nombre_normalizado = nombre.casefold()
    palabras_virtuales = ("virtual", "vEthernet", "loopback", "bluetooth",
                          "area local*", "local area connection")
    if any(palabra.casefold() in nombre_normalizado
           for palabra in palabras_virtuales):
        return True
    macs_virtuales = ("00-15-5d", "08-00-27", "0a-00-27")
    return any(direccion.address.casefold().startswith(macs_virtuales)
               for direccion in direcciones
               if direccion.family == psutil.AF_LINK)


def conectado():
    """Comprueba una interfaz física activa con una dirección no local."""
    estados = psutil.net_if_stats()
    direcciones = psutil.net_if_addrs()
    for nombre, estado in estados.items():
        interfaces = direcciones.get(nombre, ())
        if not estado.isup or _es_virtual(nombre, interfaces):
            continue
        for direccion in interfaces:
            try:
                ip = ipaddress.ip_address(direccion.address.split("%", maxsplit=1)[0])
            except ValueError:
                continue
            if not (ip.is_loopback or ip.is_link_local or ip.is_unspecified):
                return True
    return False


def iniciar():
    global _anterior, _ultima_alerta
    _anterior = conectado()
    _ultima_alerta = time.monotonic() if not _anterior else None
    return _anterior


def revisar(ahora=None, estado=None):
    global _anterior, _ultima_alerta
    if ahora is None:
        ahora = time.monotonic()
    if estado is None:
        estado = conectado()
    if _anterior is None:
        _anterior = estado
        return []
    if estado != _anterior:
        _anterior = estado
        _ultima_alerta = ahora if not estado else None
        nombre = "red_conectada" if estado else "red_desconectada"
        return [(nombre, {"conectado": estado})]
    if not estado and (_ultima_alerta is None or
                       ahora - _ultima_alerta >= config.RED_RECORDATORIO_S):
        _ultima_alerta = ahora
        return [("red_sigue_desconectada", {"conectado": False})]
    return []
