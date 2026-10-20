"""Script para iniciar el servidor de mensajería interna del centro de distribución."""

import argparse
from pathlib import Path
import sys
import time

# Permitir importación del paquete mensajeria si se ejecuta directamente el script
DIRECTORIO_RAIZ = Path(__file__).resolve().parent.parent
if str(DIRECTORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_RAIZ))

from mensajeria.config import (
    ARCHIVO_BITACORA_POR_DEFECTO,
    HOST_POR_DEFECTO,
    PUERTO_TCP_POR_DEFECTO,
    PUERTO_UDP_POR_DEFECTO,
)
from mensajeria.servidor import ServidorMensajeria


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Servidor de mensajería interna para centro de distribución."
    )
    parser.add_argument(
        "--host",
        default=HOST_POR_DEFECTO,
        help=f"Dirección IP donde escucha el servidor (por defecto: {HOST_POR_DEFECTO})",
    )
    parser.add_argument(
        "--tcp",
        type=int,
        default=PUERTO_TCP_POR_DEFECTO,
        help=f"Puerto TCP para chat con framing (por defecto: {PUERTO_TCP_POR_DEFECTO})",
    )
    parser.add_argument(
        "--udp",
        type=int,
        default=PUERTO_UDP_POR_DEFECTO,
        help=f"Puerto UDP para monitoreo de disponibilidad/heartbeat (por defecto: {PUERTO_UDP_POR_DEFECTO})",
    )
    parser.add_argument(
        "--bitacora",
        default=ARCHIVO_BITACORA_POR_DEFECTO,
        help=f"Ruta del archivo de bitácora JSONL (por defecto: {ARCHIVO_BITACORA_POR_DEFECTO})",
    )

    args = parser.parse_args()

    print("=" * 65)
    print(" SERVIDOR DE MENSAJERÍA INTERNA - CENTRO DE DISTRIBUCIÓN ")
    print("=" * 65)
    print(f" * Host:          {args.host}")
    print(f" * Puerto TCP:     {args.tcp} (Chat concurrente con framing)")
    print(f" * Puerto UDP:     {args.udp} (Heartbeat y disponibilidad)")
    print(f" * Bitácora:      {args.bitacora}")
    print(" Presione Ctrl + C para detener el servidor.")
    print("=" * 65)

    servidor = ServidorMensajeria(
        host=args.host,
        puerto_tcp=args.tcp,
        puerto_udp=args.udp,
        ruta_bitacora=args.bitacora,
    )

    try:
        servidor.iniciar()
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[AVISO] Señal de interrupción recibida.")
    finally:
        servidor.detener()


if __name__ == "__main__":
    main()
