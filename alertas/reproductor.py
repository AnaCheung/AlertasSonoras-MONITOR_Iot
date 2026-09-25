# LABORATORIO: cola sonora atendida por un hilo; nunca bloquea tkinter.
from collections import deque
from threading import Event, Lock, Thread
import sys
from pathlib import Path
import time
import config

_cola = deque()
_marcas = {}
# LABORATORIO: estado de las alarmas que requieren recordatorio.
_activas = {}
_inicios = {}
_cerro = Event()
_bloqueo = Lock()
_hilo = None


# LABORATORIO: los WAV derivados de los MP3 se reproducen fuera del hilo de tkinter.
def _emitir(nombre):
    if config.SONIDO_SILENCIOSO:
        return
    ruta = Path(__file__).resolve().parent / "sonidos" / config.SONIDO_ARCHIVOS[nombre]
    if not ruta.is_file():
        raise FileNotFoundError(f"No se encuentra el sonido: {ruta}")
    if sys.platform == "win32":
        import winsound
        # Esta espera sucede solamente en el hilo del reproductor.
        winsound.PlaySound(str(ruta), winsound.SND_FILENAME)
    else:
        # Vista previa fuera de Windows cuando ffplay esté instalado.
        import shutil
        import subprocess
        player = shutil.which("ffplay")
        if player:
            subprocess.run([player, "-nodisp", "-autoexit", "-loglevel", "error",
                            str(ruta)], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()

def _trabajar():
    while not _cerro.is_set():
        with _bloqueo:
            nombre = _cola.popleft() if _cola else None
        if nombre is None:
            _cerro.wait(config.SONIDO_ESPERA_S)
            continue
        try:
            _emitir(nombre)
        except (OSError, ValueError, ImportError) as error:
            print(f"Audio no disponible: {error}", file=sys.stderr)


def iniciar():
    global _hilo
    if _hilo is None or not _hilo.is_alive():
        _cerro.clear()
        _hilo = Thread(target=_trabajar, name="alertas-sonoras", daemon=True)
        _hilo.start()


def encolar(nombre, ahora=None):
    if nombre not in config.SONIDO_EVENTOS:
        return False
    if ahora is None:
        ahora = time.monotonic()
    with _bloqueo:
        if ahora - _marcas.get(nombre, -float("inf")) < config.SONIDO_COOLDOWN_S:
            return False
        # LABORATORIO: una repetición pendiente basta si coinciden alarmas.
        if nombre in _cola or len(_cola) >= config.SONIDO_COLA_MAX:
            return False
        _cola.append(nombre)
        _marcas[nombre] = ahora
    iniciar()
    return True


# LABORATORIO: registra flancos sin repetir inmediatamente el sonido.
def observar(nombre, ahora=None):
    if ahora is None:
        ahora = time.monotonic()
    with _bloqueo:
        if nombre in config.SONIDO_FIN_ALARMA:
            alarma = config.SONIDO_FIN_ALARMA[nombre]
            _activas.pop(alarma, None)
            _inicios.pop(alarma, None)
        elif nombre in config.SONIDO_ALARMAS_PERSISTENTES:
            if nombre not in _activas:
                _activas[nombre] = ahora
                _inicios[nombre] = ahora
    encolar(nombre, ahora)


# LABORATORIO: recordatorio por marcas de tiempo, sin esperar en el ciclo.
def recordar(ahora=None):
    if ahora is None:
        ahora = time.monotonic()
    pendientes = []
    with _bloqueo:
        for nombre, ultima in tuple(_activas.items()):
            if (nombre == "red_pico" and
                    ahora - _inicios[nombre] >= config.SONIDO_DURACION_RED_PICO_S):
                del _activas[nombre]
                del _inicios[nombre]
                continue
            if ahora - ultima >= config.SONIDO_RECORDATORIO_S:
                _activas[nombre] = ahora
                pendientes.append(nombre)
    for nombre in pendientes:
        encolar(nombre, ahora)
    return pendientes


def estado():
    with _bloqueo:
        return len(_cola)


def detener():
    _cerro.set()
    with _bloqueo:
        _cola.clear()
        _marcas.clear()
        _activas.clear()
        _inicios.clear()

# LABORATORIO: escucha un solo archivo sin disparar eventos reales.
def probar_sonido(nombre):
    if config.SONIDO_SILENCIOSO or nombre not in config.SONIDO_ARCHIVOS:
        return False
    with _bloqueo:
        # LABORATORIO: una repetición pendiente basta si coinciden alarmas.
        if nombre in _cola or len(_cola) >= config.SONIDO_COLA_MAX:
            return False
        _cola.append(nombre)
    iniciar()
    return True


# LABORATORIO: el clic de red muestra sus tres estados sin cambiar el sensor.
_red_ya_probada_desconectada = False
_red_estado_click = None


def sonido_cuadro(clave):
    global _red_ya_probada_desconectada, _red_estado_click
    nombre = config.SONIDO_CUADROS.get(clave)
    if clave == "red":
        from . import conexion
        conectado = conexion.conectado()
        if conectado != _red_estado_click:
            _red_ya_probada_desconectada = False
            _red_estado_click = conectado
        if conectado:
            _red_ya_probada_desconectada = False
            nombre = "red_conectada"
        else:
            nombre = ("red_sigue_desconectada" if _red_ya_probada_desconectada
                      else "red_desconectada")
            # Solo cambia el estado de la vista previa si se puso en la cola.
            if probar_sonido(nombre):
                _red_ya_probada_desconectada = True
                return True
            return False
    return probar_sonido(nombre)


# LABORATORIO: clic secundario en red para escuchar el aviso de tráfico alto.
def sonido_trafico():
    return probar_sonido("red_pico")
