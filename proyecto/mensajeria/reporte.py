"""Módulo de reporte y análisis funcional sobre la bitácora de operación (Hito 3).

Aplica conceptos de programación funcional:
- Funciones puras de extracción y transformación.
- Generadores perezosos (streaming) para procesar bitácoras de más de 100.000 mensajes (~1 mes)
  sin que la memoria crezca linealmente con el tamaño del archivo (O(1) memoria adicional).
- Reducción funcional (fold/reduce) para agregar métricas clave:
  1. Quiénes envían más mensajes (top emisores).
  2. Cuántos mensajes hay por hora del día (0-23).
  3. Qué palabras se repiten más (filtrado de stopwords y tokenización).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import functools
from pathlib import Path
from typing import Any, Callable, Final, Iterable, Iterator

from mensajeria.bitacora import BitacoraAuditable
from mensajeria.config import ARCHIVO_BITACORA_POR_DEFECTO
from mensajeria.utilidades import extraer_hora_del_dia, tokenizar_palabras

TOP_EMISORES_DEFECTO: Final[int] = 10
TOP_PALABRAS_DEFECTO: Final[int] = 15


@dataclass(frozen=True)
class MetricasOperacion:
    """Estructura inmutable para acumular estadísticas operativas de forma funcional."""
    total_mensajes: int = 0
    conteo_emisores: Counter[str] = field(default_factory=Counter)
    conteo_horas: tuple[int, ...] = field(default_factory=lambda: tuple([0] * 24))
    conteo_palabras: Counter[str] = field(default_factory=Counter)
    conteo_canales: Counter[str] = field(default_factory=Counter)


# -----------------------------------------------------------------------------
# Funciones Puras de Extracción (Mapeo Funcional)
# -----------------------------------------------------------------------------

def extraer_emisor(mensaje: dict[str, Any]) -> str:
    """Función pura que obtiene el emisor del mensaje o 'DESCONOCIDO'."""
    return str(mensaje.get("emisor", "DESCONOCIDO")).strip()


def extraer_canal(mensaje: dict[str, Any]) -> str:
    """Función pura que obtiene el canal o etiqueta del mensaje."""
    if "canal" in mensaje:
        return str(mensaje["canal"])
    if "destinatario" in mensaje:
        return "[MENSAJE PRIVADO]"
    return "[SISTEMA]"


def extraer_hora(mensaje: dict[str, Any]) -> int:
    """Función pura que extrae la hora del día (0-23) desde el timestamp ISO."""
    timestamp = str(mensaje.get("timestamp", ""))
    return extraer_hora_del_dia(timestamp)


def extraer_palabras_mensaje(mensaje: dict[str, Any]) -> list[str]:
    """Función pura que tokeniza y limpia el texto del mensaje."""
    texto = str(mensaje.get("texto", ""))
    return tokenizar_palabras(texto)


def es_mensaje_valido(mensaje: dict[str, Any]) -> bool:
    """Predicado puro que determina si un registro contiene texto y emisor."""
    return bool(mensaje.get("texto") and mensaje.get("emisor"))


# -----------------------------------------------------------------------------
# Pipelines y Transformaciones Funcionales de Streaming
# -----------------------------------------------------------------------------

def filtrar_mensajes(
    iterador: Iterable[dict[str, Any]], predicado: Callable[[dict[str, Any]], bool]
) -> Iterator[dict[str, Any]]:
    """Generador funcional de filtrado perezoso."""
    return (m for m in iterador if predicado(m))


def acumulador_reduccion(
    acumulado: MetricasOperacion, mensaje: dict[str, Any]
) -> MetricasOperacion:
    """Paso reductor funcional que incorpora un mensaje al acumulador sin mutar el original."""
    emisor = extraer_emisor(mensaje)
    canal = extraer_canal(mensaje)
    hora = extraer_hora(mensaje)
    palabras = extraer_palabras_mensaje(mensaje)

    # Actualizar contadores de forma acumulativa
    nuevo_conteo_emisores = Counter(acumulado.conteo_emisores)
    nuevo_conteo_emisores[emisor] += 1

    nuevo_conteo_canales = Counter(acumulado.conteo_canales)
    nuevo_conteo_canales[canal] += 1

    nuevo_conteo_palabras = Counter(acumulado.conteo_palabras)
    nuevo_conteo_palabras.update(palabras)

    # Actualizar distribución horaria (tupla de 24 elementos)
    lista_horas = list(acumulado.conteo_horas)
    if 0 <= hora <= 23:
        lista_horas[hora] += 1

    return MetricasOperacion(
        total_mensajes=acumulado.total_mensajes + 1,
        conteo_emisores=nuevo_conteo_emisores,
        conteo_horas=tuple(lista_horas),
        conteo_palabras=nuevo_conteo_palabras,
        conteo_canales=nuevo_conteo_canales,
    )


def procesar_bitacora_stream(
    stream_mensajes: Iterable[dict[str, Any]]
) -> MetricasOperacion:
    """Procesa el flujo de mensajes de forma funcional con O(1) de memoria adicional.
    
    Aplica filter + reduce sin materializar listas completas en RAM.
    """
    mensajes_filtrados = filtrar_mensajes(stream_mensajes, es_mensaje_valido)
    estado_inicial = MetricasOperacion()

    return functools.reduce(acumulador_reduccion, mensajes_filtrados, estado_inicial)


def generar_reporte_desde_archivo(
    ruta_bitacora: str | Path = ARCHIVO_BITACORA_POR_DEFECTO,
) -> MetricasOperacion:
    """Crea un lector de streaming sobre el archivo y genera las métricas operativas."""
    bitacora = BitacoraAuditable(ruta_bitacora)
    return procesar_bitacora_stream(bitacora.iterar_mensajes())


# -----------------------------------------------------------------------------
# Formateo y Presentación de Resultados
# -----------------------------------------------------------------------------

def generar_texto_reporte(
    metricas: MetricasOperacion,
    top_emisores_n: int = TOP_EMISORES_DEFECTO,
    top_palabras_n: int = TOP_PALABRAS_DEFECTO,
) -> str:
    """Genera un informe detallado y formateado listo para ser presentado al cliente."""
    lineas: list[str] = []
    lineas.append("======================================================================")
    lineas.append("        REPORTE DE OPERACIÓN Y AUDITORÍA - CENTRO DE DISTRIBUCIÓN      ")
    lineas.append("======================================================================")
    lineas.append(f"Total de mensajes analizados en la bitácora: {metricas.total_mensajes:,}")
    lineas.append("")

    # 1. Quiénes envían más mensajes (Req 09)
    lineas.append("--- 1. TOP EMISORES DE MENSAJES (QUIÉNES ENVIARON MÁS MENSAJES) ---")
    emisores_ordenados = metricas.conteo_emisores.most_common(top_emisores_n)
    if not emisores_ordenados:
        lineas.append("  (No hay datos de emisores registrados)")
    else:
        for puesto, (emisor, cantidad) in enumerate(emisores_ordenados, start=1):
            porcentaje = (cantidad / metricas.total_mensajes * 100) if metricas.total_mensajes > 0 else 0
            lineas.append(f"  {puesto:2d}. {emisor:<20} : {cantidad:6,d} mensajes ({porcentaje:5.1f}%)")
    lineas.append("")

    # 2. Distribución de mensajes por hora del día (Req 09)
    lineas.append("--- 2. DISTRIBUCIÓN DE MENSAJES POR HORA DEL DÍA (00:00 A 23:00) ---")
    lineas.append("  Hora  | Mensajes | Gráfica de Intensidad Operativa")
    lineas.append("  ------+----------+---------------------------------------------------")
    max_hora = max(metricas.conteo_horas) if metricas.conteo_horas else 0
    for h in range(24):
        conteo = metricas.conteo_horas[h]
        barra_longitud = int((conteo / max_hora) * 35) if max_hora > 0 else 0
        barra = "#" * barra_longitud
        lineas.append(f"  {h:02d}:00 | {conteo:8,d} | {barra}")
    lineas.append("")

    # 3. Palabras que más se repiten (Req 09)
    lineas.append("--- 3. PALABRAS MÁS FRECUENTES (INCIDENCIAS Y VOCABULARIO OPERATIVO) ---")
    palabras_ordenadas = metricas.conteo_palabras.most_common(top_palabras_n)
    if not palabras_ordenadas:
        lineas.append("  (No se encontraron palabras significativas en los mensajes)")
    else:
        for puesto, (palabra, apariciones) in enumerate(palabras_ordenadas, start=1):
            lineas.append(f"  {puesto:2d}. {palabra:<18} : {apariciones:6,d} repeticiones")
    lineas.append("")

    # 4. Distribución por canal / destino
    lineas.append("--- 4. MENSAJES POR CANAL / ÁREA ---")
    for canal, cant in metricas.conteo_canales.most_common():
        pct = (cant / metricas.total_mensajes * 100) if metricas.total_mensajes > 0 else 0
        lineas.append(f"  * {canal:<20} : {cant:6,d} mensajes ({pct:5.1f}%)")

    lineas.append("======================================================================")
    return "\n".join(lineas)
