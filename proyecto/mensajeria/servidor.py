"""Servidor multihilo de mensajería para centro de distribución.

Implementa:
- Servidor TCP en puerto 8000 con SO_REUSEADDR y framing por longitud (Eval 01 y 04).
- Servidor UDP en puerto 8001 para monitoreo de disponibilidad/heartbeat (Eval 01, Req 08).
- Conexión con identidad única y no suplantable (Req 01 y 06).
- Canales fijos por área y mensajes privados (Req 02, 11 y 12).
- Bitácora auditable persistente en disco (Req 07).
- Resiliencia y tolerancia a fallas de estaciones (Req 04, Eval 05).
"""

from __future__ import annotations

import logging
from pathlib import Path
import socket
import threading
import time
from typing import Any
import uuid

from mensajeria.bitacora import BitacoraAuditable
from mensajeria.config import (
    ARCHIVO_BITACORA_POR_DEFECTO,
    CANAL_GENERAL,
    CANALES_FIJOS,
    HOST_POR_DEFECTO,
    INTERVALO_VERIFICACION_DISPONIBILIDAD,
    PUERTO_TCP_POR_DEFECTO,
    PUERTO_UDP_POR_DEFECTO,
    TIEMPO_INACTIVIDAD_SEGUNDOS,
)
from mensajeria.estado import EstadoDisponibilidad, RegistroConectados, Usuario
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
    recibir_mensaje_tcp,
    recibir_mensaje_udp,
)
from mensajeria.utilidades import obtener_timestamp_iso

# Configuración de registro de eventos (logging)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
)
logger = logging.getLogger("ServidorMensajeria")


class ServidorMensajeria:
    """Servidor concurrente multihilo de mensajería interna con soporte TCP y UDP."""

    def __init__(
        self,
        host: str = HOST_POR_DEFECTO,
        puerto_tcp: int = PUERTO_TCP_POR_DEFECTO,
        puerto_udp: int = PUERTO_UDP_POR_DEFECTO,
        ruta_bitacora: str | Path = ARCHIVO_BITACORA_POR_DEFECTO,
    ) -> None:
        self.host: str = host
        self.puerto_tcp: int = puerto_tcp
        self.puerto_udp: int = puerto_udp
        self.registro: RegistroConectados = RegistroConectados()
        self.bitacora: BitacoraAuditable = BitacoraAuditable(ruta_bitacora)

        self._activo: bool = False
        self._socket_tcp: socket.socket | None = None
        self._socket_udp: socket.socket | None = None

        self._hilo_tcp: threading.Thread | None = None
        self._hilo_udp: threading.Thread | None = None
        self._hilo_disponibilidad: threading.Thread | None = None

    def iniciar(self) -> None:
        """Inicia los sockets del servidor y los hilos de escucha y monitoreo."""
        self._activo = True

        # 1. Configuración de socket TCP (Eval 01 y Eval 04)
        self._socket_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket_tcp.bind((self.host, self.puerto_tcp))
        self._socket_tcp.listen()
        logger.info("Servidor TCP escuchando en %s:%d", self.host, self.puerto_tcp)

        # 2. Configuración de socket UDP para heartbeats (Eval 01, Req 08)
        self._socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket_udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket_udp.bind((self.host, self.puerto_udp))
        logger.info("Servidor UDP escuchando heartbeats en %s:%d", self.host, self.puerto_udp)

        # 3. Lanzar hilo de aceptación de conexiones TCP
        self._hilo_tcp = threading.Thread(
            target=self._bucle_aceptar_tcp,
            name="Hilo-TCP-Acceptor",
            daemon=True,
        )
        self._hilo_tcp.start()

        # 4. Lanzar hilo de recepción de datagramas UDP
        self._hilo_udp = threading.Thread(
            target=self._bucle_escuchar_udp,
            name="Hilo-UDP-Heartbeat",
            daemon=True,
        )
        self._hilo_udp.start()

        # 5. Lanzar hilo de verificación de disponibilidad
        self._hilo_disponibilidad = threading.Thread(
            target=self._bucle_verificar_disponibilidad,
            name="Hilo-Monitor-Disponibilidad",
            daemon=True,
        )
        self._hilo_disponibilidad.start()

    def detener(self) -> None:
        """Detiene limpiamente el servidor y cierra los sockets asociados."""
        logger.info("Deteniendo servidor de mensajería...")
        self._activo = False

        if self._socket_tcp:
            try:
                self._socket_tcp.close()
            except OSError:
                pass

        if self._socket_udp:
            try:
                self._socket_udp.close()
            except OSError:
                pass

        # Cerrar sockets de usuarios conectados
        for usuario in self.registro.obtener_todos():
            try:
                usuario.socket_tcp.close()
            except OSError:
                pass

        logger.info("Servidor detenido correctamente.")

    # -------------------------------------------------------------------------
    # Bucle TCP Acceptor y Atención de Clientes
    # -------------------------------------------------------------------------

    def _bucle_aceptar_tcp(self) -> None:
        """Acepta conexiones TCP entrantes y delega cada una en un hilo independiente (Req 03)."""
        assert self._socket_tcp is not None
        while self._activo:
            try:
                sock_cliente, direccion = self._socket_tcp.accept()
                logger.info("Nueva conexión TCP desde %s:%d", direccion[0], direccion[1])
                hilo_cliente = threading.Thread(
                    target=self._atender_cliente_tcp,
                    args=(sock_cliente, direccion),
                    name=f"Cliente-{direccion[0]}:{direccion[1]}",
                    daemon=True,
                )
                hilo_cliente.start()
            except OSError:
                break

    def _atender_cliente_tcp(self, sock: socket.socket, direccion: tuple[str, int]) -> None:
        """Maneja el ciclo de vida completo de un cliente TCP conectado.
        
        Garantiza que errores en una estación no afecten a las demás (Req 04, Eval 05).
        """
        usuario_actual: Usuario | None = None
        try:
            # 1. Proceso de autenticación / Login inicial (Req 01)
            datos_login = recibir_mensaje_tcp(sock)
            if datos_login.get("tipo") != TIPO_LOGIN:
                enviar_mensaje_tcp(
                    sock,
                    {"tipo": TIPO_ERROR, "mensaje": "Se esperaba mensaje de autenticación 'login'."},
                )
                return

            nombre_solicitado = str(datos_login.get("usuario", "")).strip()
            exito, mensaje_auth, usuario_creado = self.registro.registrar_usuario(
                nombre_solicitado, sock, direccion
            )

            if not exito or usuario_creado is None:
                logger.warning("Rechazada conexión para '%s': %s", nombre_solicitado, mensaje_auth)
                enviar_mensaje_tcp(sock, {"tipo": TIPO_ERROR, "mensaje": mensaje_auth})
                return

            usuario_actual = usuario_creado
            logger.info("Usuario '%s' autenticado exitosamente desde %s", usuario_actual.nombre, direccion)

            # Confirmar login exitoso al cliente
            enviar_mensaje_tcp(
                sock,
                {
                    "tipo": TIPO_LOGIN_EXITO,
                    "usuario": usuario_actual.nombre,
                    "canales": sorted(list(usuario_actual.canales)),
                    "todos_los_canales": list(CANALES_FIJOS),
                    "mensaje": f"Bienvenido al sistema de mensajería interna, {usuario_actual.nombre}.",
                },
            )

            # Notificar llegada a los miembros del canal general
            self._difundir_sistema_canal(
                CANAL_GENERAL,
                f"El operario '{usuario_actual.nombre}' ha ingresado al turno y se ha conectado.",
            )

            # 2. Bucle de procesamiento de tramas del cliente
            while self._activo:
                try:
                    mensaje = recibir_mensaje_tcp(sock)
                except TramaInvalidaError as err_trama:
                    # Eval 05: Entrada inválida no tumba el servidor, se descarta y el servicio sigue
                    logger.warning(
                        "Trama inválida descartada de '%s': %s",
                        usuario_actual.nombre,
                        err_trama,
                    )
                    try:
                        enviar_mensaje_tcp(
                            sock,
                            {"tipo": TIPO_ERROR, "mensaje": f"Trama descartada por error de protocolo: {err_trama}"},
                        )
                    except Exception:
                        break
                    continue

                # Actualizar última actividad del usuario con cada mensaje TCP recibido
                usuario_actual.actualizar_actividad()

                # Procesar comando / tipo de mensaje
                tipo = mensaje.get("tipo")
                self._procesar_mensaje_cliente(usuario_actual, tipo, mensaje)

        except ConexionCerradaError:
            logger.info(
                "Desconexión detectada para %s (%s)",
                usuario_actual.nombre if usuario_actual else "anónimo",
                direccion,
            )
        except Exception as err:
            logger.error(
                "Excepción no controlada en cliente %s: %s",
                usuario_actual.nombre if usuario_actual else direccion,
                err,
            )
        finally:
            self._limpiar_desconexion(sock, usuario_actual)

    def _procesar_mensaje_cliente(
        self, usuario: Usuario, tipo: str | None, mensaje: dict[str, Any]
    ) -> None:
        """Despacha las solicitudes recibidas según su tipo."""
        if tipo == TIPO_MENSAJE_CANAL:
            self._manejar_mensaje_canal(usuario, mensaje)
        elif tipo == TIPO_MENSAJE_PRIVADO:
            self._manejar_mensaje_privado(usuario, mensaje)
        elif tipo == TIPO_UNIR_CANAL:
            self._manejar_unir_canal(usuario, mensaje)
        elif tipo == TIPO_SALIR_CANAL:
            self._manejar_salir_canal(usuario, mensaje)
        elif tipo == TIPO_LISTAR_CANALES:
            self._manejar_listar_canales(usuario)
        elif tipo == TIPO_LISTAR_USUARIOS:
            self._manejar_listar_usuarios(usuario)
        else:
            enviar_mensaje_tcp(
                usuario.socket_tcp,
                {"tipo": TIPO_ERROR, "mensaje": f"Tipo de mensaje '{tipo}' no reconocido por el servidor."},
            )

    # -------------------------------------------------------------------------
    # Manejadores de Mensajes y Autoría No Suplantable (Req 06, 07, 11, 12)
    # -------------------------------------------------------------------------

    def _manejar_mensaje_canal(self, usuario: Usuario, mensaje: dict[str, Any]) -> None:
        """Distribuye un mensaje en un canal específico tras auditarlo y sellar autoría."""
        canal = str(mensaje.get("canal", "")).strip().lower()
        texto = str(mensaje.get("texto", "")).strip()

        if not texto:
            enviar_mensaje_tcp(usuario.socket_tcp, {"tipo": TIPO_ERROR, "mensaje": "El mensaje no puede estar vacío."})
            return

        if canal not in usuario.canales:
            enviar_mensaje_tcp(
                usuario.socket_tcp,
                {
                    "tipo": TIPO_ERROR,
                    "mensaje": f"No puedes publicar en '{canal}' porque no eres miembro de ese canal.",
                },
            )
            return

        # Req 06: Autoría no suplantable: el servidor inyecta emisor, id y timestamp UTC
        id_mensaje = str(uuid.uuid4())
        timestamp_iso = obtener_timestamp_iso()

        trama_evento = {
            "tipo": TIPO_DIFUSION_CANAL,
            "id": id_mensaje,
            "emisor": usuario.nombre,
            "canal": canal,
            "texto": texto,
            "timestamp": timestamp_iso,
        }

        # Req 07: Bitácora auditable: persistir en disco inmediatamente
        self.bitacora.registrar_mensaje(trama_evento)

        # Enviar a todos los miembros suscritos a este canal
        miembros = self.registro.obtener_destinatarios_canal(canal)
        for miembro in miembros:
            try:
                enviar_mensaje_tcp(miembro.socket_tcp, trama_evento)
            except ConexionCerradaError:
                # Si un miembro perdió conexión, se desconectará en su propio hilo
                pass

    def _manejar_mensaje_privado(self, usuario: Usuario, mensaje: dict[str, Any]) -> None:
        """Entrega un mensaje directo entre dos usuarios (Req 12) con auditoría."""
        destinatario_nombre = str(mensaje.get("destinatario", "")).strip()
        texto = str(mensaje.get("texto", "")).strip()

        if not texto:
            enviar_mensaje_tcp(usuario.socket_tcp, {"tipo": TIPO_ERROR, "mensaje": "El mensaje privado no puede estar vacío."})
            return

        destinatario = self.registro.obtener_usuario(destinatario_nombre)
        if not destinatario:
            enviar_mensaje_tcp(
                usuario.socket_tcp,
                {"tipo": TIPO_ERROR, "mensaje": f"El destinatario '{destinatario_nombre}' no está conectado."},
            )
            return

        if destinatario.nombre.lower() == usuario.nombre.lower():
            enviar_mensaje_tcp(
                usuario.socket_tcp,
                {"tipo": TIPO_ERROR, "mensaje": "No tiene sentido enviarse un mensaje privado a uno mismo."},
            )
            return

        id_mensaje = str(uuid.uuid4())
        timestamp_iso = obtener_timestamp_iso()

        trama_privada = {
            "tipo": TIPO_DIFUSION_PRIVADA,
            "id": id_mensaje,
            "emisor": usuario.nombre,
            "destinatario": destinatario.nombre,
            "texto": texto,
            "timestamp": timestamp_iso,
        }

        # Req 07: Registrar en bitácora auditable
        self.bitacora.registrar_mensaje(trama_privada)

        # Entregar exclusivamente al destinatario y confirmar al emisor
        try:
            enviar_mensaje_tcp(destinatario.socket_tcp, trama_privada)
        except ConexionCerradaError:
            enviar_mensaje_tcp(
                usuario.socket_tcp,
                {"tipo": TIPO_ERROR, "mensaje": f"Fallo al entregar mensaje a '{destinatario.nombre}'."},
            )
            return

        # Confirmación / eco al emisor
        try:
            enviar_mensaje_tcp(usuario.socket_tcp, trama_privada)
        except ConexionCerradaError:
            pass

    def _manejar_unir_canal(self, usuario: Usuario, mensaje: dict[str, Any]) -> None:
        """Une al operario a un canal por área."""
        canal = str(mensaje.get("canal", ""))
        exito, razon = self.registro.unir_a_canal(usuario.nombre, canal)
        enviar_mensaje_tcp(
            usuario.socket_tcp,
            {
                "tipo": TIPO_NOTIFICACION_SISTEMA,
                "mensaje": razon,
                "exito": exito,
                "canales": sorted(list(usuario.canales)),
            },
        )
        if exito:
            canal_normalizado = canal.strip().lower()
            if not canal_normalizado.startswith("#"):
                canal_normalizado = f"#{canal_normalizado}"
            self._difundir_sistema_canal(
                canal_normalizado,
                f"El operario '{usuario.nombre}' se ha unido al canal {canal_normalizado}.",
                excluir_usuario=usuario.nombre,
            )

    def _manejar_salir_canal(self, usuario: Usuario, mensaje: dict[str, Any]) -> None:
        """Retira al operario de un canal por área (excepto #general)."""
        canal = str(mensaje.get("canal", ""))
        exito, razon = self.registro.salir_de_canal(usuario.nombre, canal)
        enviar_mensaje_tcp(
            usuario.socket_tcp,
            {
                "tipo": TIPO_NOTIFICACION_SISTEMA,
                "mensaje": razon,
                "exito": exito,
                "canales": sorted(list(usuario.canales)),
            },
        )
        if exito:
            canal_normalizado = canal.strip().lower()
            if not canal_normalizado.startswith("#"):
                canal_normalizado = f"#{canal_normalizado}"
            self._difundir_sistema_canal(
                canal_normalizado,
                f"El operario '{usuario.nombre}' ha salido del canal {canal_normalizado}.",
            )

    def _manejar_listar_canales(self, usuario: Usuario) -> None:
        """Envía lista de canales fijos y membresías activas del usuario."""
        enviar_mensaje_tcp(
            usuario.socket_tcp,
            {
                "tipo": TIPO_RESPUESTA_CANALES,
                "canales_disponibles": list(CANALES_FIJOS),
                "mis_canales": sorted(list(usuario.canales)),
            },
        )

    def _manejar_listar_usuarios(self, usuario: Usuario) -> None:
        """Envía lista de operarios conectados con estado y tiempo de inactividad."""
        todos = [u.to_dict() for u in self.registro.obtener_todos()]
        enviar_mensaje_tcp(
            usuario.socket_tcp,
            {
                "tipo": TIPO_RESPUESTA_USUARIOS,
                "usuarios": todos,
            },
        )

    def _difundir_sistema_canal(
        self, canal: str, mensaje: str, excluir_usuario: str | None = None
    ) -> None:
        """Difunde un aviso del sistema a todos los miembros de un canal."""
        trama = {
            "tipo": TIPO_NOTIFICACION_SISTEMA,
            "canal": canal,
            "mensaje": mensaje,
            "timestamp": obtener_timestamp_iso(),
        }
        for u in self.registro.obtener_destinatarios_canal(canal):
            if excluir_usuario and u.nombre == excluir_usuario:
                continue
            try:
                enviar_mensaje_tcp(u.socket_tcp, trama)
            except ConexionCerradaError:
                pass

    def _limpiar_desconexion(self, sock: socket.socket, usuario: Usuario | None) -> None:
        """Cierra el socket y actualiza el registro tras una desconexión."""
        try:
            sock.close()
        except OSError:
            pass

        u_eliminado = self.registro.desregistrar_por_socket(sock)
        nombre = usuario.nombre if usuario else (u_eliminado.nombre if u_eliminado else None)

        if nombre:
            logger.info("Operario '%s' desregistrado de la sesión.", nombre)
            self._difundir_sistema_canal(
                CANAL_GENERAL,
                f"El operario '{nombre}' se ha desconectado de la estación.",
            )

    # -------------------------------------------------------------------------
    # Escucha UDP de Heartbeats y Monitor de Disponibilidad (Req 08)
    # -------------------------------------------------------------------------

    def _bucle_escuchar_udp(self) -> None:
        """Escucha datagramas UDP en el puerto 8001 para monitorear disponibilidad."""
        assert self._socket_udp is not None
        while self._activo:
            try:
                datos, direccion = recibir_mensaje_udp(self._socket_udp)
                tipo = datos.get("tipo")
                if tipo == TIPO_HEARTBEAT:
                    nombre_usuario = str(datos.get("usuario", "")).strip()
                    if nombre_usuario:
                        actualizado = self.registro.actualizar_actividad(nombre_usuario)
                        if actualizado:
                            logger.debug("Heartbeat UDP recibido de '%s' (%s)", nombre_usuario, direccion)
            except TramaInvalidaError:
                # Datagramas inválidos se descartan sin tumbar el hilo
                continue
            except OSError:
                break

    def _bucle_verificar_disponibilidad(self) -> None:
        """Verifica periódicamente qué estaciones llevan más de 15s inactivas (Req 08)."""
        while self._activo:
            time.sleep(INTERVALO_VERIFICACION_DISPONIBILIDAD)
            if not self._activo:
                break

            cambios = self.registro.verificar_disponibilidad(TIEMPO_INACTIVIDAD_SEGUNDOS)
            for usuario, nuevo_estado in cambios:
                if nuevo_estado == EstadoDisponibilidad.INACTIVO:
                    logger.info(
                        "Operario '%s' marcado como INACTIVO (>15s sin reportar actividad).",
                        usuario.nombre,
                    )
