"""Configuración y constantes para el sistema de mensajería interna.

Define puertos, direcciones por defecto, canales del centro de distribución,
tiempos de disponibilidad y límites de seguridad para el protocolo.
"""

from typing import Final

# Parámetros de red
HOST_POR_DEFECTO: Final[str] = "127.0.0.1"
PUERTO_TCP_POR_DEFECTO: Final[int] = 8000
PUERTO_UDP_POR_DEFECTO: Final[int] = 8001

# Disponibilidad y tiempos (Hito 2 - Requisito 08)
# Quien lleve más de 15 segundos sin reportar aparece como inactivo
TIEMPO_INACTIVIDAD_SEGUNDOS: Final[float] = 15.0
INTERVALO_HEARTBEAT_SEGUNDOS: Final[float] = 5.0
INTERVALO_VERIFICACION_DISPONIBILIDAD: Final[float] = 1.0

# Canales por área fijos (Hito 2 - Requisito 11)
CANAL_GENERAL: Final[str] = "#general"
CANAL_RECEPCION: Final[str] = "#recepcion"
CANAL_ALISTAMIENTO: Final[str] = "#alistamiento"
CANAL_DESPACHO: Final[str] = "#despacho"

CANALES_FIJOS: Final[tuple[str, ...]] = (
    CANAL_GENERAL,
    CANAL_RECEPCION,
    CANAL_ALISTAMIENTO,
    CANAL_DESPACHO,
)

CANAL_POR_DEFECTO: Final[str] = CANAL_GENERAL

# Persistencia y auditoría (Hito 2 - Requisito 07)
ARCHIVO_BITACORA_POR_DEFECTO: Final[str] = "bitacora_mensajes.jsonl"

# Seguridad y límites de protocolo (Eval 04 y 05)
TAMANO_PREFIJO_LONGITUD_BYTES: Final[int] = 4
MAXIMO_TAMANO_PAYLOAD_BYTES: Final[int] = 65536  # 64 KB por trama TCP
BUFFER_RECEPCION_SOCKET_BYTES: Final[int] = 4096
