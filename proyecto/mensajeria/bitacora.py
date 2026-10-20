"""Módulo de persistencia y bitácora auditable para mensajería interna.

Garantiza que cada mensaje aceptado por el servidor se guarde inmediatamente en disco
en formato JSON Lines con codificación UTF-8 y vaciado forzado (fsync).
Soporta lectura perezosa (streaming) para procesar bitácoras de más de 100.000
mensajes sin incrementar el uso de memoria.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import threading
from typing import Any, Iterator

from mensajeria.config import ARCHIVO_BITACORA_POR_DEFECTO


class BitacoraAuditable:
    """Gestiona el registro auditable y persistente de mensajes en disco."""

    def __init__(self, ruta_archivo: str | Path = ARCHIVO_BITACORA_POR_DEFECTO) -> None:
        self.ruta_archivo: Path = Path(ruta_archivo)
        self._lock: threading.Lock = threading.Lock()
        # Aseguramos que el directorio padre exista
        if self.ruta_archivo.parent and not self.ruta_archivo.parent.exists():
            self.ruta_archivo.parent.mkdir(parents=True, exist_ok=True)

    def registrar_mensaje(self, datos_mensaje: dict[str, Any]) -> None:
        """Registra un mensaje en disco de forma atómica y thread-safe.
        
        Realiza flush y fsync inmediato para garantizar que ante un fallo de energía
        o apagado del servidor no se pierda ningún mensaje.
        """
        linea = json.dumps(datos_mensaje, ensure_ascii=False) + "\n"
        linea_bytes = linea.encode("utf-8")

        with self._lock:
            # Abrimos en modo append binario para control exacto de bytes y fsync
            with open(self.ruta_archivo, "ab") as archivo:
                archivo.write(linea_bytes)
                archivo.flush()
                os.fsync(archivo.fileno())

    def iterar_mensajes(self) -> Iterator[dict[str, Any]]:
        """Generador perezoso que lee mensajes línea por línea desde el archivo de bitácora.
        
        No carga todo el archivo en memoria (memoria O(1) adicional con respecto
        al tamaño de la bitácora).
        """
        if not self.ruta_archivo.exists():
            return

        with open(self.ruta_archivo, "r", encoding="utf-8", errors="replace") as archivo:
            for numero_linea, linea in enumerate(archivo, start=1):
                linea_limpia = linea.strip()
                if not linea_limpia:
                    continue
                try:
                    registro = json.loads(linea_limpia)
                    if isinstance(registro, dict):
                        yield registro
                except json.JSONDecodeError:
                    # Se descartan líneas corruptas según Eval 05
                    continue

    def contar_mensajes(self) -> int:
        """Cuenta la cantidad total de mensajes válidos en la bitácora mediante streaming."""
        return sum(1 for _ in self.iterar_mensajes())
