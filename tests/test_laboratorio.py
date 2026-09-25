# LABORATORIO: pruebas aisladas del enlace y la cola sonora.
import unittest
from unittest.mock import patch
from alertas import conexion
from alertas import reproductor
import config

class PruebasConexion(unittest.TestCase):
    def setUp(self):
        conexion._anterior = None
        conexion._ultima_alerta = None

    def test_flancos_y_recordatorio(self):
        self.assertEqual(conexion.revisar(0, True), [])
        self.assertEqual(conexion.revisar(1, False)[0][0], 'red_desconectada')
        self.assertEqual(conexion.revisar(2, False), [])
        self.assertEqual(conexion.revisar(1 + config.RED_RECORDATORIO_S, False)[0][0], 'red_sigue_desconectada')
        self.assertEqual(conexion.revisar(40, True)[0][0], 'red_conectada')
        self.assertEqual(conexion.revisar(41, True), [])

    def test_sin_falso_flanco_inicial(self):
        self.assertEqual(conexion.revisar(0, False), [])
        self.assertEqual(conexion.revisar(0, False)[0][0], 'red_sigue_desconectada')

    def test_ignora_adaptadores_virtuales_sin_wifi(self):
        import socket
        stats = {
            'vEthernet (WSL)': type('Estado', (), {'isup': True})(),
            'Ethernet 2': type('Estado', (), {'isup': True})(),
            'Wi-Fi': type('Estado', (), {'isup': False})(),
        }
        direcciones = {
            'vEthernet (WSL)': [type('Direccion', (), {
                'family': socket.AF_INET,
                'address': '172.26.224.1',
            })()],
            'Ethernet 2': [type('Direccion', (), {
                'family': socket.AF_INET,
                'address': '192.168.56.1',
            })(), type('Direccion', (), {
                'family': conexion.psutil.AF_LINK,
                'address': '0A-00-27-00-00-10',
            })()],
            'Wi-Fi': [],
        }
        with patch.object(conexion.psutil, 'net_if_stats', return_value=stats), \
             patch.object(conexion.psutil, 'net_if_addrs', return_value=direcciones):
            self.assertFalse(conexion.conectado())

class PruebasCPU(unittest.TestCase):
    def setUp(self):
        from eventos import detectores
        detectores._estado["alarma"].pop("cpu", None)
        detectores._estado["previo"].pop("cpu", None)

    def tearDown(self):
        reproductor.detener()

    def test_cpu_alta_usa_lectura_visible_y_enciende_sonido(self):
        from eventos import detectores, despachador
        lectura = {
            "valor": config.CPU_ALTO + 1,
            "extra": {"nucleos": [config.CPU_ALTO + 1]},
        }
        eventos = detectores.detectar("cpu", lectura)
        self.assertEqual(eventos[0][0], "cpu_alta")
        with patch.object(reproductor, "iniciar"):
            despachador.atender(*eventos[0])
        self.assertEqual(reproductor.estado(), 1)

class PruebasSonido(unittest.TestCase):
    def tearDown(self):
        reproductor.detener()

    def test_cooldown_y_evento_desconocido(self):
        with patch.object(reproductor, 'iniciar'):
            self.assertTrue(reproductor.encolar('cpu_alta', 10))
            self.assertFalse(reproductor.encolar('cpu_alta', 11))
            self.assertFalse(reproductor.encolar('cpu_alta', 10 + config.SONIDO_COOLDOWN_S))
            reproductor._cola.clear()  # simula que el hilo ya terminó el sonido
            self.assertTrue(reproductor.encolar('cpu_alta', 10 + config.SONIDO_COOLDOWN_S))
            self.assertFalse(reproductor.encolar('no_existe', 100))

    def test_recordatorio_hasta_normalizar(self):
        with patch.object(reproductor, 'iniciar'):
            reproductor.observar('cpu_alta', 10)
            self.assertEqual(reproductor.recordar(10 + config.SONIDO_RECORDATORIO_S - 1), [])
            self.assertEqual(reproductor.recordar(10 + config.SONIDO_RECORDATORIO_S), ['cpu_alta'])
            reproductor.observar('cpu_normal', 50)
            self.assertEqual(reproductor.recordar(100), [])

    def test_alarma_auto_dura_dos_minutos(self):
        with patch.object(reproductor, 'iniciar'):
            reproductor.observar('red_pico', 10)
            self.assertEqual(reproductor.recordar(10 + config.SONIDO_RECORDATORIO_S), ['red_pico'])
            reproductor._cola.clear()
            self.assertEqual(reproductor.recordar(10 + config.SONIDO_DURACION_RED_PICO_S - 1), ['red_pico'])
            reproductor._cola.clear()
            self.assertEqual(reproductor.recordar(10 + config.SONIDO_DURACION_RED_PICO_S), [])
            self.assertEqual(reproductor.recordar(999), [])

    def test_sonido_de_cada_tarjeta_y_red_caida(self):
        from pathlib import Path
        import wave
        carpeta = Path(reproductor.__file__).parent / 'sonidos'
        self.assertEqual(len(config.SONIDO_ARCHIVOS), 6)
        self.assertEqual(len(set(config.SONIDO_ARCHIVOS.values())), 4)
        self.assertEqual({config.SONIDO_ARCHIVOS[evento] for evento in
                          ('red_conectada', 'red_desconectada', 'red_sigue_desconectada')},
                         {'alarma-sismo.wav'})
        self.assertEqual({archivo.name for archivo in carpeta.iterdir()},
                         set(config.SONIDO_ARCHIVOS.values()))
        self.assertEqual(set(config.SONIDO_CUADROS), {'cpu', 'memoria', 'red'})
        for archivo in config.SONIDO_ARCHIVOS.values():
            with wave.open(str(carpeta / archivo)) as sonido:
                self.assertAlmostEqual(sonido.getnframes() / sonido.getframerate(),
                                       config.SONIDO_CLIP_S, places=1)
        with patch.object(config, 'SONIDO_SILENCIOSO', False), \
             patch.object(reproductor, 'iniciar'), \
             patch.object(conexion, 'conectado', return_value=False):
            self.assertTrue(reproductor.sonido_cuadro('cpu'))
            self.assertTrue(reproductor.sonido_cuadro('memoria'))
            self.assertFalse(reproductor.sonido_cuadro('disco'))
            self.assertFalse(reproductor.sonido_cuadro('procesos'))
            self.assertFalse(reproductor.sonido_cuadro('bateria'))
            reproductor._red_ya_probada_desconectada = False
            self.assertTrue(reproductor.sonido_cuadro('red'))
            self.assertTrue(reproductor.sonido_cuadro('red'))
            self.assertTrue(reproductor.sonido_trafico())
            self.assertEqual(reproductor.estado(), 5)
            with patch.object(conexion, 'conectado', return_value=True):
                self.assertTrue(reproductor.sonido_cuadro('red'))
                self.assertFalse(reproductor._red_ya_probada_desconectada)
            self.assertEqual(reproductor.recordar(99999), [])
        with patch.object(config, 'SONIDO_SILENCIOSO', True):
            self.assertFalse(reproductor.sonido_cuadro('cpu'))

    def test_cola_acotada(self):
        with patch.object(config, 'SONIDO_COLA_MAX', 1), patch.object(reproductor, 'iniciar'):
            self.assertTrue(reproductor.encolar('ram_alta', 10))
            self.assertFalse(reproductor.encolar('red_pico', 10))

# LABORATORIO: prueba de integración del despacho y del ciclo durante audio.
class PruebasIntegracion(unittest.TestCase):
    def tearDown(self):
        reproductor.detener()

    def test_eventos_reales_encolan_cada_sonido(self):
        from eventos import despachador
        datos = {
            'cpu_alta': {'valor': 90, 'umbral': 70},
            'ram_alta': {'valor': 90},
            'red_pico': {'valor': 900},
            'red_desconectada': {'conectado': False},
            'red_sigue_desconectada': {'conectado': False},
            'red_conectada': {'conectado': True},
        }
        with patch.object(reproductor, 'iniciar'):
            for nombre, dato in datos.items():
                registro = despachador.atender(nombre, dato)
                self.assertEqual(registro['origen'], nombre)
            self.assertEqual(reproductor.estado(), len(config.SONIDO_ARCHIVOS))

    def test_ciclo_avanza_mientras_audio_suena(self):
        from threading import Event
        from unittest.mock import patch
        import nucleo
        import time
        sonando = Event()
        terminar = Event()

        def sonido_lento(nombre):
            sonando.set()
            terminar.wait(config.SONIDO_RECORDATORIO_S)

        with patch.object(reproductor, '_emitir', side_effect=sonido_lento), \
             patch.object(nucleo.conexion, 'revisar', return_value=[('red_conectada', {'conectado': True})]), \
             patch.object(nucleo, '_leer_grupo', return_value=[]), \
             patch.object(nucleo, 'generar_reporte', return_value=None):
            reproductor.encolar('cpu_alta')
            try:
                self.assertTrue(sonando.wait(config.PERIODO_LENTO))
                inicio = time.monotonic()
                resultado = nucleo.ciclo()
                self.assertLess(time.monotonic() - inicio, config.PERIODO_RAPIDO)
                self.assertEqual(resultado['eventos'][0]['origen'], 'red_conectada')
            finally:
                terminar.set()

    def test_inicio_sin_red_dispara_alerta(self):
        import nucleo
        with patch.object(nucleo.sensores, 'disponibles', return_value=[]), \
             patch.object(nucleo.conexion, 'iniciar', return_value=False), \
             patch.object(nucleo.alertas, 'iniciar'), \
             patch.object(nucleo.eventos, 'atender') as atender:
            nucleo.iniciar()
            atender.assert_any_call('red_desconectada', {'conectado': False})

if __name__ == '__main__':
    unittest.main()
