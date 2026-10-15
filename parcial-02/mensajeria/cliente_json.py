"""
PARCIAL 2 · Cliente de consola para el Nivel 3 (completo: no se modifica)

    python3 -m mensajeria.cliente_json camilo            se conecta al puerto 8000
    python3 -m mensajeria.cliente_json camilo 8050       o al que se le diga

Igual que cliente.py, pero después del saludo cada trama es un objeto JSON:

    texto                    →  {"tipo": "mensaje", "contenido": "texto"}
    /privado luis texto      →  {"tipo": "privado", "destino": "luis", "contenido": "texto"}

El cliente no envía emisor ni timestamp: los pone el servidor. Se sale con 0.
"""

import json
import socket
import sys
import threading

from mensajeria.protocolo import enviar_mensaje, recibir_mensaje

HOST = "127.0.0.1"
PUERTO = 8000


def mostrar(texto: str) -> str:
    """Convierte una trama del servidor en la línea que se muestra."""
    try:
        datos = json.loads(texto)
        tipo = datos.get("tipo")
        if tipo == "mensaje":
            return f"[#{datos.get('canal')}] {datos.get('emisor')}: {datos.get('contenido')}"
        if tipo == "privado":
            return f"[privado] {datos.get('emisor')}: {datos.get('contenido')}"
        if tipo == "error":
            return f"[error] {datos.get('detalle')}"
    except (json.JSONDecodeError, AttributeError):
        pass
    return f"[sin formato] {texto}"


def recibir_mensajes(conexion: socket.socket) -> None:
    while True:
        try:
            texto = recibir_mensaje(conexion)
        except OSError:
            texto = None
        if texto is None:
            print("\nServidor desconectado. Escriba 0 para salir.")
            break
        print(f"\n{mostrar(texto)}")
        print("> ", end="", flush=True)


def a_pedido(texto: str) -> dict[str, str] | None:
    """Traduce lo que se escribió en la consola al objeto que se envía."""
    if not texto.startswith("/privado"):
        return {"tipo": "mensaje", "contenido": texto}
    partes = texto.split(maxsplit=2)
    if len(partes) < 3:
        print("Uso: /privado <destino> <texto>")
        return None
    return {"tipo": "privado", "destino": partes[1], "contenido": partes[2]}


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python3 -m mensajeria.cliente_json <nombre> [puerto]")
        return
    nombre = sys.argv[1]
    puerto = int(sys.argv[2]) if len(sys.argv) > 2 else PUERTO
    sys.stdout.reconfigure(
        errors="replace"
    )  # una consola sin emojis no tumba al cliente

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:
        cliente.connect((HOST, puerto))
        enviar_mensaje(cliente, nombre)  # el saludo no cambia: texto plano
        respuesta = recibir_mensaje(cliente)
        if respuesta != "OK":
            print(f"El servidor respondió: {respuesta}")
            return

        print(
            f"Conectado como {nombre}. Texto o /privado <destino> <texto>; 0 para terminar."
        )
        threading.Thread(target=recibir_mensajes, args=(cliente,), daemon=True).start()

        while True:
            try:
                texto = input("> ")
            except (EOFError, KeyboardInterrupt):
                break
            if texto == "0":
                break
            if not texto:
                continue
            pedido = a_pedido(texto)
            if pedido is None:
                continue
            try:
                enviar_mensaje(cliente, json.dumps(pedido, ensure_ascii=False))
            except OSError:
                print("No se pudo enviar: la conexión se cerró.")
                break


if __name__ == "__main__":
    main()