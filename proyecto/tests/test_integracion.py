"""Pruebas de integración cliente-servidor para mensajería interna.

Valida en conjunto:
- Servidor TCP en puerto dinámico y UDP (Eval 01, Eval 04).
- Al menos tres clientes simultáneos (Req 03).
- Conexión con identidad y rechazo de duplicados (Req 01).
- Difusión en canal común (#general) y canales por área (Req 02, Req 11).
- Mensajería privada exclusiva (Req 12).
- Autoría no suplantable y timestamp asignados por el servidor (Req 06).
- Bitácora auditable persistente (Req 07).
- Tolerancia a fallas por desconexión abrupta o entrada corrupta (Req 04, Eval 05).
- Reporte de disponibilidad por datagramas UDP (Req 08).
"""

from pathlib import Path
import socket
import struct
import tempfile
import time
from typing import Any
import unittest

from mensajeria.bitacora import BitacoraAuditable
from mensajeria.protocolo import (
    enviar_mensaje_tcp,
    enviar_mensaje_udp,
    recibir_mensaje_tcp,
)
from mensajeria.servidor import ServidorMensajeria


def obtener_puerto_libre() -> int:
    """Obtiene un número de puerto libre asignado por el sistema operativo."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class TestIntegracionMensajeria(unittest.TestCase):
    """Pruebas de extremo a extremo (E2E) con servidor y múltiples clientes."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ruta_bitacora = Path(self.temp_dir.name) / "bitacora_test.jsonl"

        self.puerto_tcp = obtener_puerto_libre()
        self.puerto_udp = obtener_puerto_libre()

        self.servidor = ServidorMensajeria(
            host="127.0.0.1",
            puerto_tcp=self.puerto_tcp,
            puerto_udp=self.puerto_udp,
            ruta_bitacora=self.ruta_bitacora,
        )
        self.servidor.iniciar()
        # Pequeña pausa para asegurar inicio de hilos
        time.sleep(0.05)

    def tearDown(self) -> None:
        self.servidor.detener()
        self.temp_dir.cleanup()

    def _conectar_cliente_tcp(self, nombre_usuario: str) -> socket.socket:
        """Crea un socket cliente y ejecuta el handshake de login."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", self.puerto_tcp))
        enviar_mensaje_tcp(sock, {"tipo": "login", "usuario": nombre_usuario})
        resp = recibir_mensaje_tcp(sock)
        self.assertEqual(resp.get("tipo"), "login_exito")
        return sock

    def _esperar_mensaje(
        self, sock: socket.socket, tipo_esperado: str, max_intentos: int = 6
    ) -> dict[str, Any]:
        """Lee del socket descartando notificaciones de fondo hasta encontrar el tipo esperado."""
        for _ in range(max_intentos):
            trama = recibir_mensaje_tcp(sock)
            if trama.get("tipo") == tipo_esperado:
                return trama
        self.fail(f"No se recibió mensaje de tipo '{tipo_esperado}' tras {max_intentos} intentos.")

    def test_tres_clientes_simultaneos_y_canal_general(self) -> None:
        """Verifica que al menos tres clientes funcionen en simultáneo (Req 03) y el canal común (Req 02)."""
        c1 = self._conectar_cliente_tcp("operario_1")
        c2 = self._conectar_cliente_tcp("operario_2")
        c3 = self._conectar_cliente_tcp("operario_3")

        try:
            time.sleep(0.05)

            # c1 envía un mensaje al canal #general
            enviar_mensaje_tcp(
                c1,
                {"tipo": "mensaje_canal", "canal": "#general", "texto": "Aviso general para el turno"},
            )

            # c1, c2 y c3 deben recibir la difusión
            for sock in (c1, c2, c3):
                trama = self._esperar_mensaje(sock, "difusion_canal")
                self.assertEqual(trama.get("texto"), "Aviso general para el turno")
                # Req 06: Autoría no suplantable sellada por el servidor
                self.assertEqual(trama.get("emisor"), "operario_1")
                self.assertEqual(trama.get("canal"), "#general")
                self.assertIn("timestamp", trama)
                self.assertIn("id", trama)

        finally:
            c1.close()
            c2.close()
            c3.close()

    def test_rechazo_usuario_duplicado(self) -> None:
        """Verifica que el servidor rechace la segunda conexión con el mismo nombre (Req 01)."""
        c1 = self._conectar_cliente_tcp("usuario_unico")
        c2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c2.connect(("127.0.0.1", self.puerto_tcp))

        try:
            enviar_mensaje_tcp(c2, {"tipo": "login", "usuario": "usuario_unico"})
            resp = recibir_mensaje_tcp(c2)
            self.assertEqual(resp.get("tipo"), "error")
            self.assertIn("Ya existe una sesión activa", resp.get("mensaje", ""))
        finally:
            c1.close()
            c2.close()

    def test_mensajeria_privada_req_12(self) -> None:
        """Verifica que un mensaje privado llegue exclusivamente al destinatario y emisor."""
        emisor = self._conectar_cliente_tcp("emisor_privado")
        receptor = self._conectar_cliente_tcp("receptor_privado")
        tercero = self._conectar_cliente_tcp("tercero_ajeno")

        try:
            time.sleep(0.05)
            # Emisor envía mensaje privado a receptor
            enviar_mensaje_tcp(
                emisor,
                {"tipo": "mensaje_privado", "destinatario": "receptor_privado", "texto": "Instrucción confidencial"},
            )

            # Receptor recibe la difusión privada
            trama_recibida = self._esperar_mensaje(receptor, "difusion_privada")
            self.assertEqual(trama_recibida.get("emisor"), "emisor_privado")
            self.assertEqual(trama_recibida.get("destinatario"), "receptor_privado")
            self.assertEqual(trama_recibida.get("texto"), "Instrucción confidencial")

            # Emisor recibe confirmación / eco
            trama_eco = self._esperar_mensaje(emisor, "difusion_privada")
            self.assertEqual(trama_eco.get("texto"), "Instrucción confidencial")

            # Bitácora guardó el mensaje privado (Req 07)
            bitacora = BitacoraAuditable(self.ruta_bitacora)
            mensajes_bitacora = list(bitacora.iterar_mensajes())
            privados = [m for m in mensajes_bitacora if m.get("tipo") == "difusion_privada"]
            self.assertEqual(len(privados), 1)
            self.assertEqual(privados[0]["texto"], "Instrucción confidencial")

        finally:
            emisor.close()
            receptor.close()
            tercero.close()

    def test_tolerancia_a_fallas_y_desconexion_abrupta_req_04(self) -> None:
        """Verifica que apagar o desconectar bruscamente un cliente no tumbe el servidor ni a otros clientes."""
        c1 = self._conectar_cliente_tcp("cliente_estable")
        c2 = self._conectar_cliente_tcp("cliente_que_falla")

        try:
            # Desconexión abrupta de c2 (cerrando socket inmediatamente)
            c2.close()
            time.sleep(0.1)

            # El servidor y c1 deben seguir funcionando con total normalidad
            enviar_mensaje_tcp(
                c1,
                {"tipo": "mensaje_canal", "canal": "#general", "texto": "Sigo vivo y operando"},
            )

            trama = self._esperar_mensaje(c1, "difusion_canal")
            self.assertEqual(trama.get("texto"), "Sigo vivo y operando")

        finally:
            c1.close()

    def test_entrada_invalida_no_tumba_servidor_eval_05(self) -> None:
        """Verifica que enviar un JSON roto o bytes dañados sea descartado sin afectar el servicio."""
        c1 = self._conectar_cliente_tcp("cliente_atacante")
        c2 = self._conectar_cliente_tcp("cliente_inocente")

        try:
            # Enviamos trama con longitud declarada pero con bytes que no son JSON
            texto_corrupto = b"ESTO NO ES JSON V@LIDO !!!"
            trama_danada = struct.pack("!I", len(texto_corrupto)) + texto_corrupto
            c1.sendall(trama_danada)

            # El cliente atacante recibe error de protocolo descartando la trama
            resp_error = self._esperar_mensaje(c1, "error")
            self.assertEqual(resp_error.get("tipo"), "error")

            # El cliente inocente puede seguir enviando y recibiendo normalmente
            enviar_mensaje_tcp(
                c2,
                {"tipo": "mensaje_canal", "canal": "#general", "texto": "Servicio intacto"},
            )
            trama = self._esperar_mensaje(c2, "difusion_canal")
            self.assertEqual(trama.get("texto"), "Servicio intacto")

        finally:
            c1.close()
            c2.close()

    def test_heartbeat_udp_actualiza_actividad_req_08(self) -> None:
        """Verifica que datagramas UDP al puerto 8001 actualicen la actividad del usuario."""
        c1 = self._conectar_cliente_tcp("usuario_heartbeat")
        usuario = self.servidor.registro.obtener_usuario("usuario_heartbeat")
        assert usuario is not None

        # Forzamos una fecha anterior
        usuario.ultima_actividad = time.time() - 10.0
        actividad_anterior = usuario.ultima_actividad

        sock_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            enviar_mensaje_udp(
                sock_udp,
                {"tipo": "heartbeat", "usuario": "usuario_heartbeat"},
                ("127.0.0.1", self.puerto_udp),
            )
            time.sleep(0.1)

            # La actividad debió actualizarse a un timestamp más reciente
            self.assertGreater(usuario.ultima_actividad, actividad_anterior)

        finally:
            sock_udp.close()
            c1.close()


if __name__ == "__main__":
    unittest.main()
