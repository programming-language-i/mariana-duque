"""Pruebas unitarias para la gestión de estado, identidad y canales (Hitos 1 y 2)."""

import socket
import time
import unittest

from mensajeria.config import CANAL_GENERAL, CANAL_RECEPCION
from mensajeria.estado import EstadoDisponibilidad, RegistroConectados


class TestRegistroConectados(unittest.TestCase):
    """Verifica identidad única, canales y disponibilidad de operarios."""

    def setUp(self) -> None:
        self.registro = RegistroConectados()
        # Creamos sockets simulados para asociar a los usuarios
        self.sock1, self.sock1_peer = socket.socketpair()
        self.sock2, self.sock2_peer = socket.socketpair()

    def tearDown(self) -> None:
        self.sock1.close()
        self.sock1_peer.close()
        self.sock2.close()
        self.sock2_peer.close()

    def test_registro_usuario_exitoso_y_canal_general_por_defecto(self) -> None:
        exito, msg, usuario = self.registro.registrar_usuario("carlos_recepcion", self.sock1, ("127.0.0.1", 10001))
        self.assertTrue(exito)
        self.assertIsNotNone(usuario)
        assert usuario is not None
        self.assertEqual(usuario.nombre, "carlos_recepcion")
        self.assertIn(CANAL_GENERAL, usuario.canales)
        self.assertEqual(usuario.estado, EstadoDisponibilidad.ACTIVO)

    def test_rechazo_usuario_duplicado_req_01(self) -> None:
        """Verifica que no puedan existir dos sesiones con el mismo nombre (Req 01)."""
        exito1, _, _ = self.registro.registrar_usuario("sergio", self.sock1, ("127.0.0.1", 10001))
        self.assertTrue(exito1)

        # Intento con el mismo nombre
        exito2, msg2, u2 = self.registro.registrar_usuario("sergio", self.sock2, ("127.0.0.1", 10002))
        self.assertFalse(exito2)
        self.assertIsNone(u2)
        self.assertIn("Ya existe una sesión activa", msg2)

        # Intento con variación en mayúsculas/minúsculas
        exito3, msg3, u3 = self.registro.registrar_usuario("SERGIO", self.sock2, ("127.0.0.1", 10002))
        self.assertFalse(exito3)
        self.assertIsNone(u3)

    def test_gestion_canales_por_area_req_11(self) -> None:
        """Verifica que el usuario se una y salga de canales, pero no pueda salir de #general."""
        self.registro.registrar_usuario("ana_alistamiento", self.sock1, ("127.0.0.1", 10001))

        # Unirse a #recepcion
        exito_unir, msg_unir = self.registro.unir_a_canal("ana_alistamiento", "#recepcion")
        self.assertTrue(exito_unir)
        usuario = self.registro.obtener_usuario("ana_alistamiento")
        assert usuario is not None
        self.assertIn("#recepcion", usuario.canales)

        # Salir de #recepcion
        exito_salir, msg_salir = self.registro.salir_de_canal("ana_alistamiento", "#recepcion")
        self.assertTrue(exito_salir)
        self.assertNotIn("#recepcion", usuario.canales)

        # Intentar salir de #general (prohibido por Req 11)
        exito_general, msg_general = self.registro.salir_de_canal("ana_alistamiento", CANAL_GENERAL)
        self.assertFalse(exito_general)
        self.assertIn("#general", usuario.canales)

    def test_control_disponibilidad_inactividad_15s_req_08(self) -> None:
        """Verifica que tras superar el tiempo de inactividad pase a INACTIVO y se reactive."""
        self.registro.registrar_usuario("operario_turno", self.sock1, ("127.0.0.1", 10001))
        usuario = self.registro.obtener_usuario("operario_turno")
        assert usuario is not None

        # Simulamos que la última actividad fue hace 20 segundos
        usuario.ultima_actividad = time.time() - 20.0

        cambios = self.registro.verificar_disponibilidad(umbral_segundos=15.0)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0][1], EstadoDisponibilidad.INACTIVO)
        self.assertEqual(usuario.estado, EstadoDisponibilidad.INACTIVO)

        # Nueva actividad reactiva al usuario a ACTIVO
        self.registro.actualizar_actividad("operario_turno")
        self.assertEqual(usuario.estado, EstadoDisponibilidad.ACTIVO)


if __name__ == "__main__":
    unittest.main()
