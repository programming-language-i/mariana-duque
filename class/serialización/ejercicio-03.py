import json

mensaje = {
    "emisor": "garbanzo",
    "emisor": "Chicharron",
    "emisor": "Chunchurria",
    "emisor": "Arroz",
    "contenido": "hola clase",
    "etiquetas": ("a", "b")
}

texto = json.dumps(mensaje, ensure_ascii=False)

print(texto)

copia = json.loads(texto)
print(f"Texto cargado {copia}")

print("\n")

print(f"Son iguales? {mensaje == copia}")