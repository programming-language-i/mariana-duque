"""Utilidades puras y funciones auxiliares para el sistema de mensajería."""

from datetime import datetime, timezone
import re
from typing import Final

# Lista de palabras vacías (stopwords) en español para filtrado en reportes de texto
STOPWORDS_ESPANOL: Final[frozenset[str]] = frozenset({
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por",
    "un", "para", "con", "no", "una", "su", "al", "lo", "como", "mas", "más",
    "pero", "sus", "le", "ya", "o", "este", "si", "sí", "porque", "esta",
    "son", "entre", "esta", "cuando", "muy", "sin", "sobre", "ser", "tiene",
    "tambien", "también", "me", "hasta", "hay", "donde", "quien", "desde",
    "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra", "otros",
    "ese", "eso", "ante", "ellos", "e", "esto", "mi", "antes", "algunos",
    "que", "unos", "yo", "otro", "otras", "otra", "el", "ella", "ello"
})

PATRON_TOKEN_PALABRA: Final[re.Pattern[str]] = re.compile(r"\b[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]{3,}\b")


def obtener_timestamp_iso() -> str:
    """Retorna la fecha y hora actual en formato estándar ISO-8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def formatear_hora_corta(iso_timestamp: str) -> str:
    """Convierte un timestamp ISO-8601 a una representación legible HH:MM:SS."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%H:%M:%S")
    except ValueError:
        return iso_timestamp


def extraer_hora_del_dia(iso_timestamp: str) -> int:
    """Extrae la hora del día (0-23) a partir de una cadena ISO-8601.
    
    Retorna -1 si el formato es inválido.
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.hour
    except ValueError:
        return -1


def tokenizar_palabras(texto: str) -> list[str]:
    """Extrae palabras relevantes en minúsculas ignorando puntuación y palabras cortas.
    
    Filtra palabras que sean stopwords comunes o tengan longitud menor a 3.
    """
    palabras = PATRON_TOKEN_PALABRA.findall(texto.lower())
    return [p for p in palabras if p not in STOPWORDS_ESPANOL]
