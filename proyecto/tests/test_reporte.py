"""Pruebas unitarias para el módulo de reporte y análisis funcional (Hito 3)."""

import unittest

from mensajeria.reporte import (
    MetricasOperacion,
    es_mensaje_valido,
    extraer_emisor,
    extraer_hora,
    extraer_palabras_mensaje,
    generar_texto_reporte,
    procesar_bitacora_stream,
)


class TestReporteFuncional(unittest.TestCase):
    """Verifica las transformaciones funcionales y la reducción en streaming de la bitácora."""

    def test_funciones_puras_de_extraccion(self) -> None:
        mensaje = {
            "emisor": "carlos_recepcion",
            "canal": "#recepcion",
            "texto": "Llegaron 30 cajas de repuestos urgentes",
            "timestamp": "2026-10-18T14:35:10Z",
        }

        self.assertEqual(extraer_emisor(mensaje), "carlos_recepcion")
        self.assertEqual(extraer_hora(mensaje), 14)
        palabras = extraer_palabras_mensaje(mensaje)
        self.assertIn("llegaron", palabras)
        self.assertIn("cajas", palabras)
        self.assertIn("repuestos", palabras)
        # "de" es stopword y debe haber sido filtrada
        self.assertNotIn("de", palabras)
        self.assertTrue(es_mensaje_valido(mensaje))

    def test_reduccion_funcional_streaming(self) -> None:
        mensajes_simulados = [
            {"emisor": "juan", "canal": "#general", "texto": "iniciando turno cargamento", "timestamp": "2026-10-18T08:00:00Z"},
            {"emisor": "juan", "canal": "#general", "texto": "cargamento verificado", "timestamp": "2026-10-18T08:30:00Z"},
            {"emisor": "maria", "canal": "#recepcion", "texto": "cargamento en muelle", "timestamp": "2026-10-18T14:15:00Z"},
            {"emisor": "juan", "canal": "#general", "texto": "listo pedido despacho", "timestamp": "2026-10-18T14:45:00Z"},
        ]

        # Convertimos en generador para asegurar que procesa streaming
        stream = (m for m in mensajes_simulados)
        metricas = procesar_bitacora_stream(stream)

        self.assertEqual(metricas.total_mensajes, 4)

        # 1. Top emisores
        top_emisores = metricas.conteo_emisores.most_common()
        self.assertEqual(top_emisores[0], ("juan", 3))
        self.assertEqual(top_emisores[1], ("maria", 1))

        # 2. Distribución horaria (0 a 23)
        self.assertEqual(metricas.conteo_horas[8], 2)   # 2 mensajes a las 08:xx
        self.assertEqual(metricas.conteo_horas[14], 2)  # 2 mensajes a las 14:xx
        self.assertEqual(metricas.conteo_horas[0], 0)

        # 3. Palabras más frecuentes
        self.assertEqual(metricas.conteo_palabras["cargamento"], 3)

    def test_generar_texto_reporte_contiene_secciones_clave(self) -> None:
        mensajes = [
            {"emisor": "operario1", "canal": "#alistamiento", "texto": "caja pallet", "timestamp": "2026-10-18T10:00:00Z"}
        ]
        metricas = procesar_bitacora_stream((m for m in mensajes))
        texto = generar_texto_reporte(metricas)

        self.assertIn("REPORTE DE OPERACIÓN Y AUDITORÍA", texto)
        self.assertIn("TOP EMISORES", texto)
        self.assertIn("DISTRIBUCIÓN DE MENSAJES POR HORA DEL DÍA", texto)
        self.assertIn("PALABRAS MÁS FRECUENTES", texto)
        self.assertIn("operario1", texto)


if __name__ == "__main__":
    unittest.main()
