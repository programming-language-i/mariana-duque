"""Script para generar el reporte de operación y auditoría sobre la bitácora (Hito 3)."""

import argparse
from pathlib import Path
import sys
import time

DIRECTORIO_RAIZ = Path(__file__).resolve().parent.parent
if str(DIRECTORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_RAIZ))

from mensajeria.config import ARCHIVO_BITACORA_POR_DEFECTO
from mensajeria.reporte import generar_reporte_desde_archivo, generar_texto_reporte


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera el reporte de operación sobre la bitácora auditable usando streaming funcional."
    )
    parser.add_argument(
        "--bitacora",
        default=ARCHIVO_BITACORA_POR_DEFECTO,
        help=f"Ruta del archivo de bitácora a procesar (por defecto: {ARCHIVO_BITACORA_POR_DEFECTO})",
    )
    parser.add_argument(
        "--top-emisores",
        type=int,
        default=10,
        help="Número de emisores a mostrar en el ranking (por defecto: 10)",
    )
    parser.add_argument(
        "--top-palabras",
        type=int,
        default=15,
        help="Número de palabras más repetidas a listar (por defecto: 15)",
    )
    parser.add_argument(
        "--salida",
        default="",
        help="Ruta de archivo opcional para exportar el reporte generado",
    )

    args = parser.parse_args()
    ruta_archivo = Path(args.bitacora)

    if not ruta_archivo.exists():
        print(f"[ERROR] El archivo de bitácora '{ruta_archivo}' no existe.")
        print("Sugerencia: Inicie el servidor y envíe mensajes, o use 'python scripts/simular_bitacora.py' para generar datos de prueba.")
        sys.exit(1)

    t_inicio = time.perf_counter()
    metricas = generar_reporte_desde_archivo(ruta_archivo)
    t_fin = time.perf_counter()

    texto_informe = generar_texto_reporte(
        metricas,
        top_emisores_n=args.top_emisores,
        top_palabras_n=args.top_palabras,
    )

    print(texto_informe)
    print(f"Tiempo de procesamiento en streaming: {(t_fin - t_inicio):.4f} segundos.")

    if args.salida:
        ruta_salida = Path(args.salida)
        ruta_salida.write_text(texto_informe, encoding="utf-8")
        print(f"Reporte exportado exitosamente a: {ruta_salida.resolve()}")


if __name__ == "__main__":
    main()
