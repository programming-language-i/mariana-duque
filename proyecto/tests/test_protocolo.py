"""Pruebas unitarias para el módulo de protocolo y framing."""

import json
import socket
import struct
import unittest

from mensajeria.protocolo import (
    ConexionCerradaError,
    TramaInvalidaError,
    codificar_trama_tcp,
    enviar_mensaje_tcp,
    enviar_mensaje_udp,
    recibir_mensaje_tcp,
    recibir_mensaje_udp,
)


class TestProtocoloFraming(unittest.TestCase):
    """Verifica el framing estricto por longitud y la resiliencia ante datos corruptos."""

    def test_codificar_trama_agrega_prefijo_correcto(self) -> None:
        datos = {"tipo": "mensaje_canal", "texto": "Hola mundo"}
        trama = codificar_trama_tcp(datos)

        # Primeros 4 bytes son la longitud big-endian
        longitud_declarada = struct.unpack("!I", trama[:4])[0]
        payload = trama[4:]

        self.assertEqual(len(payload), longitud_declarada)
        datos_recuperados = json.loads(payload.decode("utf-8"))
        self.assertEqual(datos_recuperados, datos)

    def test_envio_y_recepcion_loopback_tcp(self) -> None:
        """Verifica que enviar y recibir a través de un par de sockets conectados funcione exactamente."""
        servidor_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor_sock.bind(("127.0.0.1", 0))
        servidor_sock.listen(1)
        puerto = servidor_sock.getsockname()[1]

        cliente_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente_sock.connect(("127.0.0.1", puerto))
        sock_aceptado, _ = servidor_sock.accept()

        try:
            datos_envio = {"tipo": "login", "usuario": "sergio_operario", "turno": 1}
            enviar_mensaje_tcp(cliente_sock, datos_envio)

            datos_recibidos = recibir_mensaje_tcp(sock_aceptado)
            self.assertEqual(datos_recibidos, datos_envio)
        finally:
            cliente_sock.close()
            sock_aceptado.close()
            servidor_sock.close()

    def test_recibir_json_danado_lanza_trama_invalida(self) -> None:
        """Verifica que un JSON roto lance TramaInvalidaError sin tumbar la aplicación (Eval 05)."""
        sock_a, sock_b = socket.socketpair()
        try:
            texto_danado = '{"tipo": "invalido", texto_sin_cerrar'
            payload_bytes = texto_danado.encode("utf-8")
            cabecera = struct.pack("!I", len(payload_bytes))
            sock_a.sendall(cabecera + payload_bytes)

            with self.assertRaises(TramaInvalidaError):
                recibir_mensaje_tcp(sock_b)
        finally:
            sock_a.close()
            sock_b.close()

    def test_desconexion_a_mitad_de_trama_lanza_trama_invalida(self) -> None:
        """Verifica que si la conexión se corta a mitad del payload esperado, se detecte."""
        sock_a, sock_b = socket.socketpair()
        try:
            cabecera_longitud_100 = struct.pack("!I", 100)
            sock_a.sendall(cabecera_longitud_100 + b"12345")  # Solo 5 bytes de 100
            sock_a.close()  # Cierre abrupto

            with self.assertRaises(TramaInvalidaError):
                recibir_mensaje_tcp(sock_b)
        finally:
            sock_b.close()

    def test_desconexion_limpia_lanza_conexion_cerrada(self) -> None:
        sock_a, sock_b = socket.socketpair()
        try:
            sock_a.close()
            with self.assertRaises(ConexionCerradaError):
                recibir_mensaje_tcp(sock_b)
        finally:
            sock_b.close()

    def test_comunicacion_udp_loopback(self) -> None:
        """Verifica el envío y recepción de datagramas UDP para heartbeats."""
        sock_receptor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_receptor.bind(("127.0.0.1", 0))
        puerto = sock_receptor.getsockname()[1]

        sock_emisor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            datos_hb = {"tipo": "heartbeat", "usuario": "sergio"}
            enviar_mensaje_udp(sock_emisor, datos_hb, ("127.0.0.1", puerto))

            recibido, direccion = recibir_mensaje_udp(sock_receptor)
            self.assertEqual(recibido, datos_hb)
        finally:
            sock_emisor.close()
            sock_receptor.close()


if __name__ == "__main__":
    unittest.main()
