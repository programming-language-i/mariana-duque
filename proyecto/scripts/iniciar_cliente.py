"""Script para iniciar una estación de cliente en el centro de distribución."""

import argparse
from pathlib import Path
import sys

DIRECTORIO_RAIZ = Path(__file__).resolve().parent.parent
if str(DIRECTORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_RAIZ))

from mensajeria.cliente import ClienteMensajeria
from mensajeria.config import (
    HOST_POR_DEFECTO,
    PUERTO_TCP_POR_DEFECTO,
    PUERTO_UDP_POR_DEFECTO,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estación de cliente de mensajería para operarios de bodega."
    )
    parser.add_argument(
        "-u",
        "--usuario",
        default="",
        help="Nombre de usuario del operario (ej. sergio, carlos, supervisor_turno1)",
    )
    parser.add_argument(
        "--host",
        default=HOST_POR_DEFECTO,
        help=f"Dirección IP del servidor (por defecto: {HOST_POR_DEFECTO})",
    )
    parser.add_argument(
        "--tcp",
        type=int,
        default=PUERTO_TCP_POR_DEFECTO,
        help=f"Puerto TCP del servidor (por defecto: {PUERTO_TCP_POR_DEFECTO})",
    )
    parser.add_argument(
        "--udp",
        type=int,
        default=PUERTO_UDP_POR_DEFECTO,
        help=f"Puerto UDP de heartbeats del servidor (por defecto: {PUERTO_UDP_POR_DEFECTO})",
    )

    args = parser.parse_args()

    usuario = args.usuario.strip()
    if not usuario:
        try:
            print("=====================================================")
            print(" ESTACIÓN DE TRABAJO - SISTEMA DE MENSAJERÍA INTERNA ")
            print("=====================================================")
            usuario = input("Ingrese su nombre de usuario / operario: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelado por el usuario.")
            return

    if not usuario:
        print("[ERROR] El nombre de usuario no puede estar vacío.")
        sys.exit(1)

    cliente = ClienteMensajeria(
        usuario=usuario,
        host=args.host,
        puerto_tcp=args.tcp,
        puerto_udp=args.udp,
    )

    exito = cliente.conectar()
    if exito:
        cliente.ejecutar_consola()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
