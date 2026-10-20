"""Pruebas unitarias para la bitácora auditable y concurrente (Hito 2 - Req 07)."""

import json
from pathlib import Path
import tempfile
import threading
import unittest

from mensajeria.bitacora import BitacoraAuditable


class TestBitacoraAuditable(unittest.TestCase):
    """Verifica persistencia, concurrencia y lectura en streaming de la bitácora."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ruta_bitacora = Path(self.temp_dir.name) / "test_bitacora.jsonl"
        self.bitacora = BitacoraAuditable(self.ruta_bitacora)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_registro_simple_y_formato_jsonl(self) -> None:
        mensaje = {
            "tipo": "difusion_canal",
            "emisor": "sergio",
            "canal": "#general",
            "texto": "Hola equipo",
            "timestamp": "2026-10-18T10:00:00Z",
        }
        self.bitacora.registrar_mensaje(mensaje)

        self.assertTrue(self.ruta_bitacora.exists())
        contenido = self.ruta_bitacora.read_text(encoding="utf-8")
        lineas = contenido.strip().split("\n")
        self.assertEqual(len(lineas), 1)

        datos_guardados = json.loads(lineas[0])
        self.assertEqual(datos_guardados, mensaje)

    def test_concurrencia_multihilo_sin_perdida_de_mensajes(self) -> None:
        """Verifica que múltiples hilos escribiendo simultáneamente no corrompan el archivo."""
        num_hilos = 8
        mensajes_por_hilo = 50
        total_esperado = num_hilos * mensajes_por_hilo

        def trabajador(id_hilo: int) -> None:
            for j in range(mensajes_por_hilo):
                self.bitacora.registrar_mensaje({
                    "id_hilo": id_hilo,
                    "indice": j,
                    "texto": f"Mensaje hilo {id_hilo} iter {j}",
                })

        hilos = [threading.Thread(target=trabajador, args=(h,)) for h in range(num_hilos)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        # Comprobar que se leen exactamente todos los mensajes
        mensajes_recuperados = list(self.bitacora.iterar_mensajes())
        self.assertEqual(len(mensajes_recuperados), total_esperado)
        self.assertEqual(self.bitacora.contar_mensajes(), total_esperado)

    def test_lectura_streaming_descarta_lineas_danadas(self) -> None:
        """Verifica que líneas corruptas en el archivo se descarten sin fallar."""
        with open(self.ruta_bitacora, "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": 1, "texto": "valido"}) + "\n")
            f.write("ESTO ES UNA LINEA CORRUPTA {NO JSON\n")
            f.write(json.dumps({"id": 2, "texto": "segundo valido"}) + "\n")

        mensajes = list(self.bitacora.iterar_mensajes())
        self.assertEqual(len(mensajes), 2)
        self.assertEqual(mensajes[0]["id"], 1)
        self.assertEqual(mensajes[1]["id"], 2)


if __name__ == "__main__":
    unittest.main()
