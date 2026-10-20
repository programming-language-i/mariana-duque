"""Generador de bitácora simulada para pruebas de carga y auditoría (Hito 3 - Req 10).

Simula 1 mes de operación de un centro de distribución (~100.000 mensajes, 3.300 al día,
en 3 turnos con ~40 operarios) con vocabulario de bodega realista.
Permite validar que el reporte procesa 100.000 registros sin que la memoria crezca.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import sys
import time
import uuid

DIRECTORIO_RAIZ = Path(__file__).resolve().parent.parent
if str(DIRECTORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_RAIZ))

from mensajeria.config import (
    ARCHIVO_BITACORA_POR_DEFECTO,
    CANAL_ALISTAMIENTO,
    CANAL_DESPACHO,
    CANAL_GENERAL,
    CANAL_RECEPCION,
)

OPERARIOS_BODEGA = [
    # Turno 1 (Mañana 06:00 - 14:00)
    "supervisor_t1", "juan_rec1", "maria_rec2", "pedro_rec3", "andres_ali1",
    "laura_ali2", "camila_ali3", "felipe_ali4", "carlos_des1", "diego_des2",
    "sofia_des3", "daniela_des4", "oscar_mon1",
    # Turno 2 (Tarde 14:00 - 22:00)
    "supervisor_t2", "esteban_rec4", "natalia_rec5", "jorge_rec6", "paula_ali5",
    "mateo_ali6", "valentina_ali7", "sebastian_ali8", "julian_des5", "ricardo_des6",
    "tatiana_des7", "gabriel_des8", "monica_mon2",
    # Turno 3 (Noche 22:00 - 06:00)
    "supervisor_t3", "hugo_rec7", "fernando_rec8", "claudia_ali9", "mauricio_ali10",
    "lucia_ali11", "alvaro_des9", "alejandro_des10", "marcela_des11", "patricia_des12",
    "jefe_operaciones", "analista_inventario", "coordinador_seguridad", "calidad_auditor",
]

FRASES_RECEPCION = [
    "Llegó tractomula con 40 estibas de mercancía importada",
    "Falta remisión del proveedor en muelle 3",
    "Descargue finalizado en muelle 1, mercancía lista para conteo",
    "Incidencia detectada: caja averiada en lote 5410",
    "Camión con materia prima esperando autorización en portería",
    "Conteo físico completado sin novedades en recepción",
    "Estiba con sobrepeso, reubicando en zona de pesaje",
]

FRASES_ALISTAMIENTO = [
    "Iniciando picking para pedido corporativo lote B",
    "Faltan 15 unidades de referencia A320 en estantería 12",
    "Pedido prioritario listo para embalaje y etiquetado",
    "Pallet consolidado en zona de búfer 2",
    "Se requiere recarga de montacargas eléctrico en pasillo 4",
    "Verificación de código de barras completada para pedido 8892",
    "Alistamiento de línea de farmacia al 90%",
]

FRASES_DESPACHO = [
    "Camión de ruta norte cargado al 100%, sellando precinto",
    "Retraso de 20 minutos por verificación de factura en rampa 5",
    "Despacho completado con 120 bultos hacia la sucursal centro",
    "Faltó una guía de transporte para la ruta sur",
    "Vehículo despachado con éxito a las instalaciones del cliente",
    "Muelle 4 despejado y listo para la siguiente carga",
]

FRASES_GENERAL = [
    "Reunión de cambio de turno en 10 minutos en sala operativa",
    "Recordatorio: uso obligatorio de botas y chaleco reflectivo",
    "Supervisor solicita reporte de novedades del turno",
    "Capacitación de seguridad industrial para nuevos operarios",
    "Aviso general: limpieza programada de pasillos a las 18:00",
]


def generar_bitacora_simulada(
    ruta_archivo: Path,
    cantidad_mensajes: int = 100000,
    dias_simulados: int = 30,
) -> None:
    """Genera archivo JSONL con volumen realista para Hito 3."""
    print(f"Generando {cantidad_mensajes:,} mensajes en '{ruta_archivo}'...")
    tiempo_inicio = time.perf_counter()

    fecha_base = datetime.now(timezone.utc) - timedelta(days=dias_simulados)
    delta_segundos_total = int(dias_simulados * 24 * 3600)

    canales = [CANAL_GENERAL, CANAL_RECEPCION, CANAL_ALISTAMIENTO, CANAL_DESPACHO]

    # Preparamos el archivo
    if ruta_archivo.parent and not ruta_archivo.parent.exists():
        ruta_archivo.parent.mkdir(parents=True, exist_ok=True)

    with open(ruta_archivo, "w", encoding="utf-8") as archivo:
        for i in range(1, cantidad_mensajes + 1):
            # Asignar timestamp proporcional en el tiempo simulado
            segundo_offset = int((i / cantidad_mensajes) * delta_segundos_total)
            # Agregar algo de ruido aleatorio para realismo horario
            segundo_offset += random.randint(-60, 60)
            segundo_offset = max(0, min(segundo_offset, delta_segundos_total))
            timestamp_dt = fecha_base + timedelta(seconds=segundo_offset)

            emisor = random.choice(OPERARIOS_BODEGA)
            es_privado = (random.random() < 0.15)  # 15% de mensajes privados

            if es_privado:
                destinatarios = [u for u in OPERARIOS_BODEGA if u != emisor]
                destinatario = random.choice(destinatarios)
                texto = f"Revisemos urgente la novedad en el pedido de {random.choice(['repuestos', 'electrónica', 'ropa', 'alimentos'])}."
                registro = {
                    "tipo": "difusion_privada",
                    "id": str(uuid.uuid4()),
                    "emisor": emisor,
                    "destinatario": destinatario,
                    "texto": texto,
                    "timestamp": timestamp_dt.isoformat(),
                }
            else:
                canal = random.choice(canales)
                if canal == CANAL_RECEPCION:
                    frase_base = random.choice(FRASES_RECEPCION)
                elif canal == CANAL_ALISTAMIENTO:
                    frase_base = random.choice(FRASES_ALISTAMIENTO)
                elif canal == CANAL_DESPACHO:
                    frase_base = random.choice(FRASES_DESPACHO)
                else:
                    frase_base = random.choice(FRASES_GENERAL)

                texto = f"{frase_base}. Código {random.randint(100, 999)}."
                registro = {
                    "tipo": "difusion_canal",
                    "id": str(uuid.uuid4()),
                    "emisor": emisor,
                    "canal": canal,
                    "texto": texto,
                    "timestamp": timestamp_dt.isoformat(),
                }

            archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")

            if i % 25000 == 0:
                print(f"  * {i:,} / {cantidad_mensajes:,} mensajes escritos...")

    tiempo_total = time.perf_counter() - tiempo_inicio
    tamano_mb = ruta_archivo.stat().st_size / (1024 * 1024)
    print(f"Generación completada en {tiempo_total:.2f} s. Tamaño del archivo: {tamano_mb:.2f} MB.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera una bitácora simulada de mensajes para el centro de distribución."
    )
    parser.add_argument(
        "--cantidad",
        type=int,
        default=100000,
        help="Cantidad de mensajes a generar (por defecto: 100000)",
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=30,
        help="Días de operación a simular (por defecto: 30)",
    )
    parser.add_argument(
        "--salida",
        default=ARCHIVO_BITACORA_POR_DEFECTO,
        help=f"Ruta del archivo de salida (por defecto: {ARCHIVO_BITACORA_POR_DEFECTO})",
    )

    args = parser.parse_args()
    generar_bitacora_simulada(
        ruta_archivo=Path(args.salida),
        cantidad_mensajes=args.cantidad,
        dias_simulados=args.dias,
    )


if __name__ == "__main__":
    main()
