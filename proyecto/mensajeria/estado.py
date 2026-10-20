"""Módulo de gestión de estado y registro de conexiones.

Gestiona de forma concurrente y segura (thread-safe):
- Identidad de usuarios únicos (Requisito 01).
- Canales fijos por área y membresías dinámicas (Requisito 11).
- Registro de conectados, estado y última actividad (Requisitos 05 y 08).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import socket
import threading
import time
from typing import Any

from mensajeria.config import (
    CANAL_GENERAL,
    CANALES_FIJOS,
    TIEMPO_INACTIVIDAD_SEGUNDOS,
)


class EstadoDisponibilidad(str, Enum):
    """Estado de disponibilidad del operario en su estación."""
    ACTIVO = "activo"
    INACTIVO = "inactivo"


@dataclass
class Usuario:
    """Representa a un operario conectado al sistema de mensajería."""
    nombre: str
    socket_tcp: socket.socket
    direccion_ip: str
    puerto_tcp: int
    canales: set[str] = field(default_factory=lambda: {CANAL_GENERAL})
    estado: EstadoDisponibilidad = EstadoDisponibilidad.ACTIVO
    ultima_actividad: float = field(default_factory=time.time)
    conectado_en: float = field(default_factory=time.time)

    def actualizar_actividad(self) -> None:
        """Actualiza el timestamp de última actividad y restaura el estado a ACTIVO."""
        self.ultima_actividad = time.time()
        self.estado = EstadoDisponibilidad.ACTIVO

    def to_dict(self) -> dict[str, Any]:
        """Serializa la información pública del usuario."""
        segundos_inactivo = max(0.0, time.time() - self.ultima_actividad)
        return {
            "nombre": self.nombre,
            "estado": self.estado.value,
            "canales": sorted(list(self.canales)),
            "direccion_ip": self.direccion_ip,
            "segundos_desde_actividad": round(segundos_inactivo, 1),
            "conectado_en": self.conectado_en,
        }


class RegistroConectados:
    """Registro concurrente (thread-safe) de usuarios, sockets y canales."""

    def __init__(self) -> None:
        self._lock: threading.RLock = threading.RLock()
        self._usuarios: dict[str, Usuario] = {}
        self._sockets_a_usuarios: dict[socket.socket, str] = {}

    def registrar_usuario(
        self, nombre: str, sock: socket.socket, direccion: tuple[str, int]
    ) -> tuple[bool, str, Usuario | None]:
        """Registra un nuevo usuario asegurando unicidad de identidad (Requisito 01).
        
        Retorna (exito, mensaje_explicativo, usuario_creado).
        """
        nombre_normalizado = nombre.strip()
        if not nombre_normalizado:
            return False, "El nombre de usuario no puede estar vacío.", None

        if len(nombre_normalizado) > 30:
            return False, "El nombre de usuario no debe superar 30 caracteres.", None

        with self._lock:
            # Validación de colisión de identidad insensible a mayúsculas
            for usuario_existente in self._usuarios.values():
                if usuario_existente.nombre.lower() == nombre_normalizado.lower():
                    return (
                        False,
                        f"Ya existe una sesión activa con el nombre '{nombre_normalizado}'.",
                        None,
                    )

            ip, puerto = direccion
            nuevo_usuario = Usuario(
                nombre=nombre_normalizado,
                socket_tcp=sock,
                direccion_ip=ip,
                puerto_tcp=puerto,
                canales={CANAL_GENERAL},
                estado=EstadoDisponibilidad.ACTIVO,
                ultima_actividad=time.time(),
                conectado_en=time.time(),
            )
            self._usuarios[nombre_normalizado] = nuevo_usuario
            self._sockets_a_usuarios[sock] = nombre_normalizado
            return True, "Conexión autorizada.", nuevo_usuario

    def desregistrar_por_socket(self, sock: socket.socket) -> Usuario | None:
        """Elimina la sesión asociada a un socket TCP desconectado."""
        with self._lock:
            nombre = self._sockets_a_usuarios.pop(sock, None)
            if nombre is not None:
                return self._usuarios.pop(nombre, None)
            return None

    def desregistrar_por_nombre(self, nombre: str) -> Usuario | None:
        """Elimina a un usuario por su nombre."""
        with self._lock:
            usuario = self._usuarios.pop(nombre, None)
            if usuario is not None:
                self._sockets_a_usuarios.pop(usuario.socket_tcp, None)
            return usuario

    def obtener_usuario(self, nombre: str) -> Usuario | None:
        """Obtiene un usuario por su nombre."""
        with self._lock:
            # Búsqueda exacta o insensible a mayúsculas
            if nombre in self._usuarios:
                return self._usuarios[nombre]
            nombre_l = nombre.lower()
            for u in self._usuarios.values():
                if u.nombre.lower() == nombre_l:
                    return u
            return None

    def obtener_usuario_por_socket(self, sock: socket.socket) -> Usuario | None:
        """Obtiene un usuario a partir de su socket TCP."""
        with self._lock:
            nombre = self._sockets_a_usuarios.get(sock)
            if nombre:
                return self._usuarios.get(nombre)
            return None

    def actualizar_actividad(self, nombre: str) -> bool:
        """Registra actividad reciente para un usuario y renueva su estado a ACTIVO."""
        with self._lock:
            usuario = self.obtener_usuario(nombre)
            if usuario:
                usuario.actualizar_actividad()
                return True
            return False

    def unir_a_canal(self, nombre: str, canal: str) -> tuple[bool, str]:
        """Añade al usuario a un canal fijo del centro de distribución."""
        canal_formateado = canal.strip().lower()
        if not canal_formateado.startswith("#"):
            canal_formateado = f"#{canal_formateado}"

        if canal_formateado not in CANALES_FIJOS:
            canales_validos = ", ".join(CANALES_FIJOS)
            return False, f"Canal desconocido '{canal}'. Canales válidos: {canales_validos}"

        with self._lock:
            usuario = self.obtener_usuario(nombre)
            if not usuario:
                return False, f"Usuario '{nombre}' no encontrado."
            if canal_formateado in usuario.canales:
                return False, f"Ya perteneces al canal {canal_formateado}."
            usuario.canales.add(canal_formateado)
            usuario.actualizar_actividad()
            return True, f"Te has unido con éxito al canal {canal_formateado}."

    def salir_de_canal(self, nombre: str, canal: str) -> tuple[bool, str]:
        """Retira al usuario de un canal. No permite salir de #general."""
        canal_formateado = canal.strip().lower()
        if not canal_formateado.startswith("#"):
            canal_formateado = f"#{canal_formateado}"

        if canal_formateado == CANAL_GENERAL:
            return False, f"No puedes abandonar el canal común obligatorio {CANAL_GENERAL}."

        with self._lock:
            usuario = self.obtener_usuario(nombre)
            if not usuario:
                return False, f"Usuario '{nombre}' no encontrado."
            if canal_formateado not in usuario.canales:
                return False, f"No formas parte del canal {canal_formateado}."
            usuario.canales.remove(canal_formateado)
            usuario.actualizar_actividad()
            return True, f"Has salido del canal {canal_formateado}."

    def obtener_destinatarios_canal(self, canal: str) -> list[Usuario]:
        """Obtiene la lista de usuarios suscritos a un canal determinado."""
        with self._lock:
            return [u for u in self._usuarios.values() if canal in u.canales]

    def obtener_todos(self) -> list[Usuario]:
        """Retorna una copia de la lista de todos los usuarios conectados."""
        with self._lock:
            return list(self._usuarios.values())

    def verificar_disponibilidad(
        self, umbral_segundos: float = TIEMPO_INACTIVIDAD_SEGUNDOS
    ) -> list[tuple[Usuario, EstadoDisponibilidad]]:
        """Verifica la inactividad de las estaciones y actualiza estados (Requisito 08).
        
        Retorna la lista de tuplas (usuario, nuevo_estado) para aquellos usuarios
        cuyo estado haya cambiado.
        """
        ahora = time.time()
        cambios: list[tuple[Usuario, EstadoDisponibilidad]] = []

        with self._lock:
            for usuario in self._usuarios.values():
                diferencia = ahora - usuario.ultima_actividad
                if diferencia > umbral_segundos and usuario.estado == EstadoDisponibilidad.ACTIVO:
                    usuario.estado = EstadoDisponibilidad.INACTIVO
                    cambios.append((usuario, EstadoDisponibilidad.INACTIVO))

        return cambios
