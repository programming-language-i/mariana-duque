import pickle

mensaje = {
    "emisor": "garbanzo",
    "emisor": "Chicharron",
    "emisor": "Chunchurria",
    "emisor": "Arroz",
    "contenido": "hola clase",
    "etiquetas": ("a", "b")
}

datos = pickle.dumps(mensaje)

print(datos)
print("\n")

copia = pickle.loads(datos)
print(copia)