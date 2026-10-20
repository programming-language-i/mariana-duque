"""Cliente de estación para el sistema de mensajería interna.

Proporciona:
- Conexión TCP con framing para envío y recepción asíncrona de mensajes (Hito 1).
- Hilo de reporte de disponibilidad mediante datagramas UDP a puerto 8001 (Req 08).
- Manejo interactivo de canales por área y mensajes privados (Req 11 y 12).
- Interfaz de consola ergonómica y limpia para operarios de la bodega.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from typing import Any

from mensajeria.config import (
    CANAL_GENERAL,
    HOST_POR_DEFECTO,
    INTERVALO_HEARTBEAT_SEGUNDOS,
    PUERTO_TCP_POR_DEFECTO,
    PUERTO_UDP_POR_DEFECTO,
)
from mensajeria.protocolo import (
    ConexionCerradaError,
    TIPO_DIFUSION_CANAL,
    TIPO_DIFUSION_PRIVADA,
    TIPO_ERROR,
    TIPO_HEARTBEAT,
    TIPO_LISTAR_CANALES,
    TIPO_LISTAR_USUARIOS,
    TIPO_LOGIN,
    TIPO_LOGIN_EXITO,
    TIPO_MENSAJE_CANAL,
    TIPO_MENSAJE_PRIVADO,
    TIPO_NOTIFICACION_SISTEMA,
    TIPO_RESPUESTA_CANALES,
    TIPO_RESPUESTA_USUARIOS,
    TIPO_SALIR_CANAL,
    TIPO_UNIR_CANAL,
    TramaInvalidaError,
    enviar_mensaje_tcp,
    enviar_mensaje_udp,
    recibir_mensaje_tcp,
)
from mensajeria.utilidades import formatear_hora_corta


class ClienteMensajeria:
    """Cliente de mensajería para las estaciones de trabajo de la bodega."""

    def __init__(
        self,
        usuario: str,
        host: str = HOST_POR_DEFECTO,
        puerto_tcp: int = PUERTO_TCP_POR_DEFECTO,
        puerto_udp: int = PUERTO_UDP_POR_DEFECTO,
    ) -> None:
        self.usuario: str = usuario.strip()
        self.host: str = host
        self.puerto_tcp: int = puerto_tcp
        self.puerto_udp: int = puerto_udp

        self.canal_actual: str = CANAL_GENERAL
        self.mis_canales: set[str] = {CANAL_GENERAL}

        self._socket_tcp: socket.socket | None = None
        self._socket_udp: socket.socket | None = None
        self._conectado: bool = False

        self._hilo_recepcion: threading.Thread | None = None
        self._hilo_heartbeat: threading.Thread | None = None

    def conectar(self) -> bool:
        """Establece conexión TCP con el servidor y realiza autenticación con identidad (Req 01).
        
        Retorna True si la conexión fue exitosa, False en caso contrario.
        """
        try:
            self._socket_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket_tcp.connect((self.host, self.puerto_tcp))

            # 1. Enviar solicitud de login
            enviar_mensaje_tcp(self._socket_tcp, {"tipo": TIPO_LOGIN, "usuario": self.usuario})

            # 2. Esperar respuesta del servidor
            respuesta = recibir_mensaje_tcp(self._socket_tcp)
            tipo_resp = respuesta.get("tipo")

            if tipo_resp != TIPO_LOGIN_EXITO:
                mensaje_error = respuesta.get("mensaje", "Fallo de autenticación desconocido.")
                print(f"\n[ERROR SERVIDOR] No fue posible ingresar: {mensaje_error}")
                self._socket_tcp.close()
                self._socket_tcp = None
                return False

            self._conectado = True
            canales_iniciales = respuesta.get("canales", [CANAL_GENERAL])
            self.mis_canales = set(canales_iniciales)

            # 3. Iniciar socket UDP para heartbeats
            self._socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # 4. Lanzar hilo de recepción TCP
            self._hilo_recepcion = threading.Thread(
                target=self._bucle_recepcion_tcp,
                name="Cliente-Receptor-TCP",
                daemon=True,
            )
            self._hilo_recepcion.start()

            # 5. Lanzar hilo emisor de heartbeat UDP (Req 08)
            self._hilo_heartbeat = threading.Thread(
                target=self._bucle_envio_heartbeat_udp,
                name="Cliente-Heartbeat-UDP",
                daemon=True,
            )
            self._hilo_heartbeat.start()

            print(f"\n[SISTEMA] Conectado exitosamente como '{self.usuario}'.")
            print(f"[SISTEMA] Canal activo por defecto: {self.canal_actual}")
            print("[SISTEMA] Escribe /ayuda para ver los comandos disponibles.\n")
            return True

        except (ConnectionRefusedError, TimeoutError, OSError) as err:
            print(f"\n[ERROR] No se pudo conectar al servidor en {self.host}:{self.puerto_tcp}: {err}")
            if self._socket_tcp:
                try:
                    self._socket_tcp.close()
                except OSError:
                    pass
                self._socket_tcp = None
            return False

    def desconectar(self) -> None:
        """Cierra ordenadamente los sockets e hilos."""
        self._conectado = False
        if self._socket_tcp:
            try:
                self._socket_tcp.close()
            except OSError:
                pass
            self._socket_tcp = None

        if self._socket_udp:
            try:
                self._socket_udp.close()
            except OSError:
                pass
            self._socket_udp = None

    def enviar_mensaje_canal(self, canal: str, texto: str) -> None:
        """Envía un mensaje a un canal específico del centro de distribución."""
        if not self._socket_tcp or not self._conectado:
            print("[AVISO] No hay conexión activa con el servidor.")
            return

        trama = {
            "tipo": TIPO_MENSAJE_CANAL,
            "canal": canal,
            "texto": texto,
        }
        try:
            enviar_mensaje_tcp(self._socket_tcp, trama)
        except ConexionCerradaError:
            print("\n[DESCONEXIÓN] Se perdió la conexión con el servidor.")
            self.desconectar()

    def enviar_mensaje_privado(self, destinatario: str, texto: str) -> None:
        """Envía un mensaje privado a otro usuario conectado (Req 12)."""
        if not self._socket_tcp or not self._conectado:
            print("[AVISO] No hay conexión activa con el servidor.")
            return

        trama = {
            "tipo": TIPO_MENSAJE_PRIVADO,
            "destinatario": destinatario,
            "texto": texto,
        }
        try:
            enviar_mensaje_tcp(self._socket_tcp, trama)
        except ConexionCerradaError:
            print("\n[DESCONEXIÓN] Se perdió la conexión con el servidor.")
            self.desconectar()

    def unirse_a_canal(self, canal: str) -> None:
        """Solicita al servidor la suscripción a un canal."""
        if not self._socket_tcp or not self._conectado:
            return
        try:
            enviar_mensaje_tcp(self._socket_tcp, {"tipo": TIPO_UNIR_CANAL, "canal": canal})
        except ConexionCerradaError:
            self.desconectar()

    def salir_de_canal(self, canal: str) -> None:
        """Solicita al servidor abandonar un canal."""
        if not self._socket_tcp or not self._conectado:
            return
        try:
            enviar_mensaje_tcp(self._socket_tcp, {"tipo": TIPO_SALIR_CANAL, "canal": canal})
        except ConexionCerradaError:
            self.desconectar()

    def solicitar_lista_canales(self) -> None:
        """Pide al servidor la lista de canales disponibles."""
        if not self._socket_tcp or not self._conectado:
            return
        try:
            enviar_mensaje_tcp(self._socket_tcp, {"tipo": TIPO_LISTAR_CANALES})
        except ConexionCerradaError:
            self.desconectar()

    def solicitar_lista_usuarios(self) -> None:
        """Pide al servidor el listado de operarios conectados y su disponibilidad."""
        if not self._socket_tcp or not self._conectado:
            return
        try:
            enviar_mensaje_tcp(self._socket_tcp, {"tipo": TIPO_LISTAR_USUARIOS})
        except ConexionCerradaError:
            self.desconectar()

    # -------------------------------------------------------------------------
    # Hilos de Fondo: Recepción TCP y Heartbeat UDP
    # -------------------------------------------------------------------------

    def _bucle_recepcion_tcp(self) -> None:
        """Escucha tramas entrantes desde el servidor y las presenta en pantalla."""
        assert self._socket_tcp is not None
        while self._conectado:
            try:
                mensaje = recibir_mensaje_tcp(self._socket_tcp)
                self._mostrar_mensaje_recibido(mensaje)
            except TramaInvalidaError as err:
                print(f"\n[AVISO] Trama corrupta recibida y descartada: {err}")
                continue
            except ConexionCerradaError:
                if self._conectado:
                    print("\n[DESCONEXIÓN] El servidor cerró la conexión.")
                    self.desconectar()
                break

    def _mostrar_mensaje_recibido(self, mensaje: dict[str, Any]) -> None:
        """Formatea los mensajes según su tipo para lectura limpia del operario."""
        tipo = mensaje.get("tipo")
        hora = formatear_hora_corta(str(mensaje.get("timestamp", "")))

        if tipo == TIPO_DIFUSION_CANAL:
            canal = mensaje.get("canal")
            emisor = mensaje.get("emisor")
            texto = mensaje.get("texto")
            print(f"\n[{hora}] [{canal}] <{emisor}>: {texto}")
            self._imprimir_prompt()

        elif tipo == TIPO_DIFUSION_PRIVADA:
            emisor = mensaje.get("emisor")
            destinatario = mensaje.get("destinatario")
            texto = mensaje.get("texto")
            if emisor == self.usuario:
                print(f"\n[{hora}] [PRIVADO -> {destinatario}]: {texto}")
            else:
                print(f"\n[{hora}] [PRIVADO de {emisor}]: {texto}")
            self._imprimir_prompt()

        elif tipo == TIPO_NOTIFICACION_SISTEMA:
            canal = mensaje.get("canal")
            contenido = mensaje.get("mensaje")
            canales_actualizados = mensaje.get("canales")
            if canales_actualizados is not None:
                self.mis_canales = set(canales_actualizados)
            canal_tag = f" [{canal}]" if canal else ""
            print(f"\n[SISTEMA{canal_tag}]: {contenido}")
            self._imprimir_prompt()

        elif tipo == TIPO_RESPUESTA_CANALES:
            disponibles = mensaje.get("canales_disponibles", [])
            mis = mensaje.get("mis_canales", [])
            self.mis_canales = set(mis)
            print("\n--- CANALES DE LA BODEGA ---")
            for c in disponibles:
                marca = "✓ (suscrito)" if c in self.mis_canales else "  (no suscrito)"
                activo_tag = " -> CANAL ACTIVO" if c == self.canal_actual else ""
                print(f"  {c:<15} {marca}{activo_tag}")
            print("----------------------------")
            self._imprimir_prompt()

        elif tipo == TIPO_RESPUESTA_USUARIOS:
            usuarios = mensaje.get("usuarios", [])
            print("\n--- OPERARIOS CONECTADOS ---")
            for u in usuarios:
                nombre = u.get("nombre")
                estado = u.get("estado", "desconocido").upper()
                inactivo_s = u.get("segundos_desde_actividad", 0)
                canales_u = ", ".join(u.get("canales", []))
                print(f"  * {nombre:<15} [{estado:<8}] (Últ. act: hace {inactivo_s}s) Canales: {canales_u}")
            print("----------------------------")
            self._imprimir_prompt()

        elif tipo == TIPO_ERROR:
            contenido = mensaje.get("mensaje", "Error del servidor")
            print(f"\n[ERROR DEL SERVIDOR]: {contenido}")
            self._imprimir_prompt()

    def _bucle_envio_heartbeat_udp(self) -> None:
        """Envía periódicamente un reporte de disponibilidad por UDP al servidor (Req 08)."""
        assert self._socket_udp is not None
        while self._conectado:
            try:
                trama = {
                    "tipo": TIPO_HEARTBEAT,
                    "usuario": self.usuario,
                    "timestamp": time.time(),
                }
                enviar_mensaje_udp(self._socket_udp, trama, (self.host, self.puerto_udp))
            except Exception:
                pass
            time.sleep(INTERVALO_HEARTBEAT_SEGUNDOS)

    def _imprimir_prompt(self) -> None:
        """Muestra el indicador de entrada para el usuario."""
        sys.stdout.write(f"[{self.canal_actual}] > ")
        sys.stdout.flush()

    # -------------------------------------------------------------------------
    # Bucle Interactivo de Consola
    # -------------------------------------------------------------------------

    def ejecutar_consola(self) -> None:
        """Inicia el bucle de interacción por terminal para el operario."""
        if not self._conectado:
            print("[ERROR] Debe conectarse antes de iniciar la consola.")
            return

        while self._conectado:
            try:
                self._imprimir_prompt()
                linea = input().strip()
                if not linea:
                    continue

                if linea.startswith("/"):
                    self._procesar_comando_consola(linea)
                else:
                    # Enviar mensaje al canal activo
                    if self.canal_actual not in self.mis_canales:
                        print(f"[AVISO] No perteneces a {self.canal_actual}. Únete con /unir {self.canal_actual}")
                        continue
                    self.enviar_mensaje_canal(self.canal_actual, linea)

            except (KeyboardInterrupt, EOFError):
                print("\n[SISTEMA] Cerrando sesión del operario...")
                break

        self.desconectar()
        print("[SISTEMA] Sesión finalizada.")

    def _procesar_comando_consola(self, linea: str) -> None:
        """Interpreta y ejecuta los comandos que empiezan con '/'."""
        partes = linea.split(" ", 2)
        comando = partes[0].lower()

        if comando in ("/ayuda", "/help"):
            self._mostrar_ayuda()

        elif comando in ("/canal", "/c"):
            if len(partes) < 2:
                print(f"[USO] /canal <#nombre_canal>. Canal actual: {self.canal_actual}")
                return
            canal_destino = partes[1].strip().lower()
            if not canal_destino.startswith("#"):
                canal_destino = f"#{canal_destino}"
            self.canal_actual = canal_destino
            print(f"[SISTEMA] Canal activo cambiado a: {self.canal_actual}")

        elif comando in ("/unir", "/join"):
            if len(partes) < 2:
                print("[USO] /unir <#nombre_canal>")
                return
            self.unirse_a_canal(partes[1])

        elif comando in ("/salir_canal", "/leave"):
            if len(partes) < 2:
                print("[USO] /salir_canal <#nombre_canal>")
                return
            self.salir_de_canal(partes[1])

        elif comando in ("/canales", "/channels"):
            self.solicitar_lista_canales()

        elif comando in ("/usuarios", "/who", "/quien"):
            self.solicitar_lista_usuarios()

        elif comando in ("/msg", "/privado", "/p"):
            if len(partes) < 3:
                print("[USO] /msg <usuario> <mensaje>")
                return
            destinatario = partes[1]
            texto = partes[2]
            self.enviar_mensaje_privado(destinatario, texto)

        elif comando in ("/desconectar", "/salir", "/exit", "/quit"):
            self.desconectar()

        else:
            print(f"[AVISO] Comando desconocido: '{comando}'. Escribe /ayuda para ver los comandos.")

    def _mostrar_ayuda(self) -> None:
        """Imprime la lista de comandos disponibles en consola."""
        print("""
================ COMANDOS DEL SISTEMA DE MENSAJERÍA ================
  /canal <#canal>             Cambia el canal activo para escribir directamente
  /unir <#canal>              Te une a un canal (#recepcion, #alistamiento, #despacho)
  /salir_canal <#canal>       Sale de un canal (excepto #general)
  /canales                    Lista canales fijos y tus suscripciones
  /usuarios                   Muestra operarios conectados, estado y última actividad
  /msg <usuario> <mensaje>    Envía un mensaje privado directo a otro operario
  /ayuda                      Muestra este menú de ayuda
  /salir                      Cierra la sesión y desconecta la estación
=====================================================================
""")
