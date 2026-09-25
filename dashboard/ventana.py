""" 
dashboard/ventana.py 
Interfaz grafica del nodo, escrita con tkinter (viene con Python). 
  
Es programacion orientada a eventos en estado puro: 
  
  - after(ms, funcion) es el temporizador que dispara el refresco; 
    cumple el mismo papel que las marcas de tiempo del nucleo, pero 
    dentro del bucle de la interfaz. 
  - command=funcion registra el manejador de cada boton. Se escribe 
    sin parentesis: se pasa la funcion, no su resultado. 
  - protocol('WM_DELETE_WINDOW', ...) es el manejador del evento de 
    cerrar la ventana. 
  
La ventana nunca bloquea: cada refresco llama a nucleo.ciclo(), que 
devuelve enseguida, y vuelve a programarse. 
""" 
 
import tkinter as tk

import config
import nucleo
import sensores
import almacenamiento as registro


# ==========================================================================
# PALETA DE COLORES PERSONALIZADA
# ==========================================================================

FONDO = "#eef3f8"
TARJETA = "#ffffff"
BORDE = "#c7d3e0"
TEXTO = "#172b4d"
TENUE = "#60748a"

VERDE = "#198754"
AMBAR = "#e0a800"
ROJO = "#dc3545"
MAGENTA = "#7c4dff"
AZUL = "#0d6efd"

# Colores adicionales de personalización
AZUL_OSCURO = "#173b63"
CELESTE = "#dbeafe"


# Colores utilizados según el nivel del evento
COLOR_NIVEL = {
    "INFO": TENUE,
    "AVISO": AMBAR,
    "ALERTA": ROJO,
    "FALLA": MAGENTA
}


ANCHO_BARRA = 300
ALTO_BARRA = 14


# ==========================================================================
# VARIABLES GLOBALES DE LA INTERFAZ
# ==========================================================================

_tarjetas = {}
_pausado = False
_ventana = None
_lista_eventos = None
_lista_procesos = None
_estado_texto = None
_reloj = None
_ultimo_evento = 0


# ==========================================================================
# COLORES DE LAS BARRAS
# ==========================================================================

def _color_barra(clave, lectura):
    """Determina el color de la barra según el estado de la métrica."""

    if lectura is None:
        return BORDE

    p = lectura["porcentaje"]

    if clave == "bateria":

        if lectura["valor"] <= config.BATERIA_BAJA:
            return ROJO

        return VERDE if lectura["extra"]["conectado"] else AZUL

    if p >= 85:
        return ROJO

    if p >= 60:
        return AMBAR

    return VERDE


# ==========================================================================
# CREAR TARJETAS DE MÉTRICAS
# ==========================================================================

def _crear_tarjeta(padre, clave, fila, columna):
    """Construye una tarjeta de métrica y devuelve sus widgets."""

    marco = tk.Frame(
        padre,
        bg=TARJETA,
        highlightbackground=BORDE,
        highlightthickness=1
    )

    marco.grid(
        row=fila,
        column=columna,
        padx=8,
        pady=8,
        sticky="nsew"
    )

    titulo = tk.Label(
        marco,
        text=sensores.etiqueta(clave),
        bg=TARJETA,
        fg=TENUE,
        font=("Segoe UI", 10, "bold"),
        anchor="w"
    )

    titulo.pack(
        fill="x",
        padx=14,
        pady=(12, 0)
    )

    valor = tk.Label(
        marco,
        text="--",
        bg=TARJETA,
        fg=TEXTO,
        font=("Segoe UI", 26, "bold"),
        anchor="w"
    )

    valor.pack(
        fill="x",
        padx=14
    )

    barra = tk.Canvas(
        marco,
        width=ANCHO_BARRA,
        height=ALTO_BARRA,
        bg=FONDO,
        highlightthickness=0
    )

    barra.pack(
        fill="x",
        padx=14,
        pady=(2, 6)
    )

    detalle = tk.Label(
        marco,
        text="sin datos",
        bg=TARJETA,
        fg=TENUE,
        font=("Segoe UI", 9),
        anchor="w",
        justify="left"
    )

    detalle.pack(
        fill="x",
        padx=14,
        pady=(0, 12)
    )

    # LABORATORIO: toda la tarjeta responde al clic sin simular una alarma.
    from alertas import reproductor
    for widget in ((marco, titulo, valor, barra, detalle)
                   if clave in config.SONIDO_CUADROS else ()):
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda evento, metrica=clave:
                    reproductor.sonido_cuadro(metrica))
        # LABORATORIO: red con clic secundario reproduce el pico de tráfico.
        if clave == "red":
            widget.bind("<Button-3>", lambda evento: reproductor.sonido_trafico())

    return {
        "marco": marco,
        "valor": valor,
        "barra": barra,
        "detalle": detalle
    }


# ==========================================================================
# DIBUJAR BARRA DE PROGRESO
# ==========================================================================

def _dibujar_barra(canvas, porcentaje, color):
    """Dibuja la barra de porcentaje de la métrica."""

    canvas.delete("all")

    ancho = max(
        canvas.winfo_width(),
        ANCHO_BARRA
    )

    # Fondo de la barra
    canvas.create_rectangle(
        0,
        0,
        ancho,
        ALTO_BARRA,
        fill=BORDE,
        width=0
    )

    # Porcentaje de llenado
    largo = (
        max(0, min(100.0, porcentaje))
        / 100.0
        * ancho
    )

    if largo > 0:

        canvas.create_rectangle(
            0,
            0,
            largo,
            ALTO_BARRA,
            fill=color,
            width=0
        )


# ==========================================================================
# ACTUALIZAR TARJETAS
# ==========================================================================

def _actualizar_tarjetas(lecturas):

    for clave, widgets in _tarjetas.items():

        lectura = lecturas.get(clave)

        if lectura is None:

            widgets["valor"].config(
                text="--",
                fg=TENUE
            )

            widgets["detalle"].config(
                text="sensor no disponible"
            )

            _dibujar_barra(
                widgets["barra"],
                0,
                BORDE
            )

            continue

        widgets["valor"].config(
            text=f"{lectura['valor']:g} {lectura['unidad']}",
            fg=TEXTO
        )

        # LABORATORIO: el tráfico y el estado de conexión se muestran juntos.
        detalle = lectura["detalle"]
        if clave == "red":
            from alertas import conexion
            estado_red = "CONECTADA" if conexion.conectado() else "DESCONECTADA"
            detalle = f"{estado_red} | {detalle}"
        widgets["detalle"].config(text=detalle)

        _dibujar_barra(
            widgets["barra"],
            lectura["porcentaje"],
            _color_barra(clave, lectura)
        )


# ==========================================================================
# ACTUALIZAR PROCESOS
# ==========================================================================

def _actualizar_procesos(lecturas):

    lectura = lecturas.get("procesos")

    _lista_procesos.delete(
        0,
        tk.END
    )

    if lectura is None:

        _lista_procesos.insert(
            tk.END,
            "  sensor no disponible"
        )

        return

    _lista_procesos.insert(
        tk.END,
        f"  {'PID':>7}  {'PROCESO':<24}"
        f"{'CPU':>7}{'RAM':>7}"
    )

    for p in lectura["extra"]["top"]:

        _lista_procesos.insert(
            tk.END,
            f"  {p['pid']:>7}  "
            f"{p['nombre']:<24}"
            f"{p['cpu']:>6.1f}%"
            f"{p['ram']:>6.1f}%"
        )


# ==========================================================================
# ACTUALIZAR EVENTOS
# ==========================================================================

def _actualizar_eventos():
    """Agrega a la lista los eventos que todavía no se han mostrado."""

    global _ultimo_evento

    todos = registro.eventos()

    # Si la bitácora fue limpiada
    if len(todos) < _ultimo_evento:

        _ultimo_evento = 0

        _lista_eventos.delete(
            0,
            tk.END
        )

    # Agregar eventos nuevos
    for e in todos[_ultimo_evento:]:

        linea = (
            f" {e['hora']}  "
            f"[{e['nivel']:<6}] "
            f"{e['mensaje']}"
        )

        _lista_eventos.insert(
            tk.END,
            linea
        )

        _lista_eventos.itemconfig(
            tk.END,
            fg=COLOR_NIVEL.get(
                e["nivel"],
                TEXTO
            )
        )

    if len(todos) > _ultimo_evento:

        _lista_eventos.see(
            tk.END
        )

    _ultimo_evento = len(todos)


# ==========================================================================
# MANEJADORES DE LOS BOTONES
# ==========================================================================

def _alternar_pausa():

    global _pausado

    _pausado = not _pausado

    registro.registrar_evento(
        "INFO",
        "usuario",
        "Monitoreo en pausa"
        if _pausado
        else "Monitoreo reanudado"
    )


def _forzar_reporte():

    nucleo.generar_reporte()


def _limpiar():

    global _ultimo_evento

    registro.limpiar_eventos()

    _ultimo_evento = 0

    _lista_eventos.delete(
        0,
        tk.END
    )


def _salir():

    # LABORATORIO: detener la cola sonora al cerrar.
    import alertas
    alertas.detener()
    _ventana.destroy()


# ==========================================================================
# BUCLE DE REFRESCO
# ==========================================================================

def _refrescar():
    """
    Se ejecuta cada REFRESCO_MS.
    Es el manejador del temporizador.
    """

    if not _pausado:

        resultado = nucleo.ciclo()

        _actualizar_tarjetas(
            resultado["lecturas"]
        )

        _actualizar_procesos(
            resultado["lecturas"]
        )

        _actualizar_eventos()

    # LABORATORIO: mostrar la cola sonora y el modo en la barra de estado.
    _modo_audio = "SILENCIO" if config.SONIDO_SILENCIOSO else "AUDIO"
    import alertas
    # Actualizar estado
    _estado_texto.config(
        text=(
            ("● PAUSADO" if _pausado else "● MONITOREANDO")
            + f" | {_modo_audio} | cola {alertas.estado()}"
        ),
        fg=(
            AMBAR
            if _pausado
            else VERDE
        )
    )

    # Actualizar reloj
    _reloj.config(
        text=__import__("time").strftime(
            "%H:%M:%S"
        )
    )

    # Programar siguiente actualización
    _ventana.after(
        config.REFRESCO_MS,
        _refrescar
    )


# ==========================================================================
# INICIAR INTERFAZ
# ==========================================================================

def iniciar():
    """Arma la ventana y entra en el bucle de eventos de tkinter."""

    global _ventana
    global _lista_eventos
    global _lista_procesos
    global _estado_texto
    global _reloj

    # Iniciar núcleo del sistema
    nucleo.iniciar()

    # ----------------------------------------------------------------------
    # VENTANA PRINCIPAL
    # ----------------------------------------------------------------------

    _ventana = tk.Tk()

    _ventana.title(
        f"Monitor IoT - {config.NODO}"
    )

    _ventana.configure(
        bg=FONDO
    )

    _ventana.geometry(
        "1120x740"
    )

    _ventana.minsize(
        900,
        640
    )

    # ----------------------------------------------------------------------
    # ENCABEZADO
    # ----------------------------------------------------------------------

    cabecera = tk.Frame(
        _ventana,
        bg=AZUL_OSCURO,
        padx=16,
        pady=10,
        highlightbackground=BORDE,
        highlightthickness=1
    )

    cabecera.pack(
        fill="x",
        padx=14,
        pady=(12, 6)
    )

    # Nombre del sistema
    tk.Label(
        cabecera,
        text=f"MONITOR IoT  •  {config.NODO}",
        bg=AZUL_OSCURO,
        fg="white",
        font=("Segoe UI", 15, "bold")
    ).pack(
        side="left"
    )

    # Ubicación
    tk.Label(
        cabecera,
        text=f"  |  {config.UBICACION}",
        bg=AZUL_OSCURO,
        fg=CELESTE,
        font=("Segoe UI", 10)
    ).pack(
        side="left"
    )

    # Reloj
    _reloj = tk.Label(
        cabecera,
        text="",
        bg=AZUL_OSCURO,
        fg="white",
        font=("Consolas", 11)
    )

    _reloj.pack(
        side="right",
        padx=(10, 0)
    )

    # Estado del sistema
    _estado_texto = tk.Label(
        cabecera,
        text="● MONITOREANDO",
        bg=AZUL_OSCURO,
        fg=VERDE,
        font=("Segoe UI", 10, "bold")
    )

    _estado_texto.pack(
        side="right"
    )

    # ----------------------------------------------------------------------
    # TARJETAS DE MÉTRICAS
    # ----------------------------------------------------------------------

    grilla = tk.Frame(
        _ventana,
        bg=FONDO
    )

    grilla.pack(
        fill="x",
        padx=6,
        pady=6
    )

    for c in range(3):

        grilla.columnconfigure(
            c,
            weight=1,
            uniform="col"
        )

    for i, clave in enumerate(
        sensores.LECTORES
    ):

        _tarjetas[clave] = _crear_tarjeta(
            grilla,
            clave,
            i // 3,
            i % 3
        )

    # ----------------------------------------------------------------------
    # PANELES INFERIORES
    # ----------------------------------------------------------------------

    inferior = tk.Frame(
        _ventana,
        bg=FONDO
    )

    inferior.pack(
        fill="both",
        expand=True,
        padx=6,
        pady=(0, 6)
    )

    inferior.columnconfigure(
        0,
        weight=1
    )

    inferior.columnconfigure(
        1,
        weight=1
    )

    inferior.rowconfigure(
        0,
        weight=1
    )

    # ======================================================================
    # PANEL DE PROCESOS
    # ======================================================================

    izq = tk.Frame(
        inferior,
        bg=TARJETA,
        highlightbackground=BORDE,
        highlightthickness=1
    )

    izq.grid(
        row=0,
        column=0,
        sticky="nsew",
        padx=8,
        pady=4
    )

    tk.Label(
        izq,
        text="Procesos con mayor consumo",
        bg=TARJETA,
        fg=AZUL_OSCURO,
        font=("Segoe UI", 10, "bold"),
        anchor="w"
    ).pack(
        fill="x",
        padx=12,
        pady=(10, 4)
    )

    _lista_procesos = tk.Listbox(
        izq,
        bg=TARJETA,
        fg=TEXTO,
        bd=0,
        font=("Consolas", 9),
        highlightthickness=0,
        selectbackground=CELESTE,
        activestyle="none"
    )

    _lista_procesos.pack(
        fill="both",
        expand=True,
        padx=6,
        pady=(0, 10)
    )

    # ======================================================================
    # PANEL DE EVENTOS
    # ======================================================================

    der = tk.Frame(
        inferior,
        bg=TARJETA,
        highlightbackground=BORDE,
        highlightthickness=1
    )

    der.grid(
        row=0,
        column=1,
        sticky="nsew",
        padx=8,
        pady=4
    )

    tk.Label(
        der,
        text="Bitácora de eventos",
        bg=TARJETA,
        fg=AZUL_OSCURO,
        font=("Segoe UI", 10, "bold"),
        anchor="w"
    ).pack(
        fill="x",
        padx=12,
        pady=(10, 4)
    )

    contenedor = tk.Frame(
        der,
        bg=TARJETA
    )

    contenedor.pack(
        fill="both",
        expand=True,
        padx=6,
        pady=(0, 10)
    )

    # Scroll vertical
    scroll_y = tk.Scrollbar(
        contenedor,
        orient="vertical"
    )

    scroll_y.pack(
        side="right",
        fill="y"
    )

    # Scroll horizontal
    scroll_x = tk.Scrollbar(
        contenedor,
        orient="horizontal"
    )

    scroll_x.pack(
        side="bottom",
        fill="x"
    )

    _lista_eventos = tk.Listbox(
        contenedor,
        bg=TARJETA,
        fg=TEXTO,
        bd=0,
        font=("Consolas", 9),
        highlightthickness=0,
        selectbackground=CELESTE,
        activestyle="none",
        yscrollcommand=scroll_y.set,
        xscrollcommand=scroll_x.set
    )

    _lista_eventos.pack(
        side="left",
        fill="both",
        expand=True
    )

    scroll_y.config(
        command=_lista_eventos.yview
    )

    scroll_x.config(
        command=_lista_eventos.xview
    )

    # LABORATORIO: mandos de audio sin cambiar los sensores ni crear falsos eventos.
    controles_audio = tk.Frame(_ventana, bg=FONDO)
    controles_audio.pack(fill="x", padx=14, pady=(2, 5))
    from alertas import reproductor

    def cambiar_audio():
        config.SONIDO_SILENCIOSO = not config.SONIDO_SILENCIOSO
        boton_audio.config(text="Activar sonido" if config.SONIDO_SILENCIOSO
                           else "Silenciar sonido")

    boton_audio = tk.Button(
        controles_audio, text="Activar sonido" if config.SONIDO_SILENCIOSO
        else "Silenciar sonido", command=cambiar_audio, bg=AZUL_OSCURO,
        fg="white", padx=12, pady=5
    )
    boton_audio.pack(side="left", padx=(0, 8))
    tk.Label(controles_audio,
             bg=FONDO, fg=TENUE).pack(side="left", padx=12)

    # ----------------------------------------------------------------------
    # PIE DE LA INTERFAZ
    # ----------------------------------------------------------------------

    pie = tk.Frame(
        _ventana,
        bg=FONDO
    )

    pie.pack(
        fill="x",
        padx=14,
        pady=(0, 12)
    )

    # Identificación del estudiante
    tk.Label(
        pie,
        text="Autor: Ana Cheung  |  8-1033-725  |  Grupo 1GS132",
        bg=FONDO,
        fg=AZUL_OSCURO,
        font=("Segoe UI", 8, "bold")
    ).pack(
        side="left",
        pady=(2, 0)
    )

    # ----------------------------------------------------------------------
    # FUNCIÓN PARA CREAR BOTONES
    # ----------------------------------------------------------------------

    def boton(texto, comando, color=BORDE):

        b = tk.Button(
            pie,
            text=texto,
            command=comando,
            bg=color,
            fg="white",
            bd=0,
            padx=16,
            pady=7,
            font=("Segoe UI", 9, "bold"),
            activebackground=AZUL,
            activeforeground="white",
            cursor="hand2"
        )

        b.pack(
            side="left",
            padx=(0, 8)
        )

        return b

    # Botones
    boton(
        " Pausar / Reanudar",
        _alternar_pausa,
        AZUL_OSCURO
    )

    boton(
        "Generar reporte",
        _forzar_reporte,
        VERDE
    )

    boton(
        "Limpiar bitácora",
        _limpiar,
        AMBAR
    )

    boton(
        "Salir",
        _salir,
        ROJO
    )

    # ----------------------------------------------------------------------
    # INFORMACIÓN DE UMBRALES
    # ----------------------------------------------------------------------

    tk.Label(
        pie,
        text=(
            f"umbrales: "
            f"CPU {config.CPU_ALTO:g}%  ·  "
            f"RAM {config.RAM_ALTA:g}%  ·  "
            f"disco {config.DISCO_LLENO:g}%  ·  "
            f"red {config.RED_PICO_KBS:g} KB/s"
        ),
        bg=FONDO,
        fg=TENUE,
        font=("Segoe UI", 8)
    ).pack(
        side="right"
    )

    # ----------------------------------------------------------------------
    # EVENTOS DE LA VENTANA
    # ----------------------------------------------------------------------

    _ventana.protocol(
        "WM_DELETE_WINDOW",
        _salir
    )

    # Iniciar temporizador
    _ventana.after(
        config.REFRESCO_MS,
        _refrescar
    )

    # Iniciar interfaz
    _ventana.mainloop()