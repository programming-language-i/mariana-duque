"""Módulo de protocolo y framing de red para mensajería interna.

Implementa framing estricto por prefijo de longitud de 4 bytes (big-endian),
serialización/deserialización JSON en UTF-8 y manejo resiliente de errores.
Cumple con las directrices de seguridad (sin pickle) y robustez ante tramas
incompletas o datos corruptos.
"""

from __future__ import annotations

import json
import socket
import struct
from typing import Any, Final

from mensajeria.config import (
    BUFFER_RECEPCION_SOCKET_BYTES,
    MAXIMO_TAMANO_PAYLOAD_BYTES,
    TAMANO_PREFIJO_LONGITUD_BYTES,
)

# Constantes de tipos de mensajes
TIPO_LOGIN: Final[str] = "login"
TIPO_LOGIN_EXITO: Final[str] = "login_exito"
TIPO_ERROR: Final[str] = "error"
TIPO_MENSAJE_CANAL: Final[str] = "mensaje_canal"
TIPO_DIFUSION_CANAL: Final[str] = "difusion_canal"
TIPO_MENSAJE_PRIVADO: Final[str] = "mensaje_privado"
TIPO_DIFUSION_PRIVADA: Final[str] = "difusion_privada"
TIPO_UNIR_CANAL: Final[str] = "unir_canal"
TIPO_SALIR_CANAL: Final[str] = "salir_canal"
TIPO_LISTAR_CANALES: Final[str] = "listar_canales"
TIPO_RESPUESTA_CANALES: Final[str] = "respuesta_canales"
TIPO_LISTAR_USUARIOS: Final[str] = "listar_usuarios"
TIPO_RESPUESTA_USUARIOS: Final[str] = "respuesta_usuarios"
TIPO_HEARTBEAT: Final[str] = "heartbeat"
TIPO_NOTIFICACION_SISTEMA: Final[str] = "notificacion_sistema"


class ErrorProtocolo(Exception):
    """Excepción base para fallas en el protocolo de comunicación."""


class ConexionCerradaError(ErrorProtocolo):
    """Lanzada cuando un socket se cierra limpiamente por el otro extremo."""


class TramaInvalidaError(ErrorProtocolo):
    """Lanzada cuando una trama contiene datos corruptos, tamaño inválido o JSON mal formado."""


def codificar_trama_tcp(datos: dict[str, Any]) -> bytes:
    """Codifica un diccionario a bytes con prefijo de longitud de 4 bytes big-endian.
    
    Estructura: [ 4 bytes unsigned int longitud ][ payload en JSON UTF-8 ]
    """
    try:
        payload_bytes = json.dumps(datos, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as err:
        raise TramaInvalidaError(f"No se pudo serializar mensaje a JSON: {err}") from err

    longitud = len(payload_bytes)
    if longitud > MAXIMO_TAMANO_PAYLOAD_BYTES:
        raise TramaInvalidaError(
            f"El tamaño del mensaje ({longitud} bytes) excede el máximo permitido ({MAXIMO_TAMANO_PAYLOAD_BYTES} bytes)"
        )

    prefijo = struct.pack("!I", longitud)
    return prefijo + payload_bytes


def _recibir_exactamente(sock: socket.socket, cantidad_bytes: int) -> bytes:
    """Lee exactamente 'cantidad_bytes' del socket TCP acumulando lecturas.
    
    Lanza ConexionCerradaError si se detecta EOF antes de recibir bytes,
    o TramaInvalidaError si la conexión se cierra abruptamente a mitad de lectura.
    """
    buffer = bytearray()
    while len(buffer) < cantidad_bytes:
        faltantes = cantidad_bytes - len(buffer)
        try:
            fragmento = sock.recv(min(faltantes, BUFFER_RECEPCION_SOCKET_BYTES))
        except (ConnectionResetError, BrokenPipeError, TimeoutError) as err:
            raise ConexionCerradaError(f"Conexión interrumpida por la red: {err}") from err
        except OSError as err:
            raise ConexionCerradaError(f"Error de socket durante lectura: {err}") from err

        if not fragmento:
            # Si no hemos leído nada y se cerró, es un cierre limpio de conexión
            if len(buffer) == 0:
                raise ConexionCerradaError("El extremo remoto cerró la conexión.")
            # Si se cerró a mitad de una trama esperada, la trama quedó incompleta
            raise TramaInvalidaError(
                f"Conexión cerrada inesperadamente a mitad de trama ({len(buffer)}/{cantidad_bytes} bytes recibidos)"
            )

        buffer.extend(fragmento)

    return bytes(buffer)


def recibir_mensaje_tcp(sock: socket.socket) -> dict[str, Any]:
    """Recibe y decodifica un mensaje TCP completo con framing por longitud.
    
    Lanza:
        ConexionCerradaError: si el cliente se desconecta limpiamente.
        TramaInvalidaError: si la trama está corrupta o el JSON es inválido.
    """
    # 1. Leer exactamente 4 bytes del encabezado de longitud
    prefijo_bytes = _recibir_exactamente(sock, TAMANO_PREFIJO_LONGITUD_BYTES)
    longitud = struct.unpack("!I", prefijo_bytes)[0]

    if longitud <= 0 or longitud > MAXIMO_TAMANO_PAYLOAD_BYTES:
        raise TramaInvalidaError(
            f"Longitud de trama recibida inválida: {longitud} bytes (límite: {MAXIMO_TAMANO_PAYLOAD_BYTES})"
        )

    # 2. Leer exactamente el payload indicado por el prefijo
    payload_bytes = _recibir_exactamente(sock, longitud)

    # 3. Decodificar UTF-8 y deserializar JSON
    try:
        texto = payload_bytes.decode("utf-8")
        datos = json.loads(texto)
        if not isinstance(datos, dict):
            raise TramaInvalidaError("El payload recibido no es un objeto JSON.")
        return datos
    except UnicodeDecodeError as err:
        raise TramaInvalidaError(f"La trama no contiene texto UTF-8 válido: {err}") from err
    except json.JSONDecodeError as err:
        raise TramaInvalidaError(f"JSON mal formado en la trama: {err}") from err


def enviar_mensaje_tcp(sock: socket.socket, datos: dict[str, Any]) -> None:
    """Envía un diccionario por TCP utilizando framing por longitud."""
    trama = codificar_trama_tcp(datos)
    try:
        sock.sendall(trama)
    except (ConnectionResetError, BrokenPipeError, TimeoutError) as err:
        raise ConexionCerradaError(f"No se pudo enviar mensaje, conexión cerrada: {err}") from err
    except OSError as err:
        raise ConexionCerradaError(f"Error de socket al enviar: {err}") from err


def enviar_mensaje_udp(sock: socket.socket, datos: dict[str, Any], direccion: tuple[str, int]) -> None:
    """Envía un mensaje en JSON codificado en UTF-8 mediante un datagrama UDP."""
    try:
        payload = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        sock.sendto(payload, direccion)
    except Exception as err:
        raise ErrorProtocolo(f"Error al enviar datagrama UDP a {direccion}: {err}") from err


def recibir_mensaje_udp(
    sock: socket.socket, buffer_size: int = BUFFER_RECEPCION_SOCKET_BYTES
) -> tuple[dict[str, Any], tuple[str, int]]:
    """Recibe un datagrama UDP y deserializa su JSON.
    
    Retorna una tupla con (datos_dict, direccion_remota).
    Lanza TramaInvalidaError si el contenido no es JSON válido.
    """
    datos_bytes, direccion = sock.recvfrom(buffer_size)
    try:
        texto = datos_bytes.decode("utf-8")
        datos = json.loads(texto)
        if not isinstance(datos, dict):
            raise TramaInvalidaError("El datagrama UDP recibido no es un objeto JSON.")
        return datos, direccion
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise TramaInvalidaError(f"Datagrama UDP con payload inválido: {err}") from err
