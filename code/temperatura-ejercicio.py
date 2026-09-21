import threading
import time

# En esta función se representa el trabajo que realiza cada sensor.
# Recibe el número del sensor y la temperatura que tiene.
def sensor(numero, temperatura):

# Acá el sensor va a mostrar la información 5 veces.
    for i in range(5):

        # Acá mostramos el hilo, el sensor y la temperatura (h) es hilo.
        print(f"H{numero} - Sensor {numero} - Temperatura: {temperatura}°C")
        time.sleep(1)

# El primer número es el sensor y el segundo es la temperatura.
sensores = [
    (1, 30),
    (2, 40),
    (3, 50),
    (4, 60),
    (5, 70)
]

# En esta lista se van guardando los hilos que vamos creando.
hilos = []

#Se Recorren los sensores para crear un hilo para cada uno de ellos.
for numero, temperatura in sensores:
    hilo = threading.Thread(
        target=sensor,
        args=(numero, temperatura),
        name=f"H{numero}"
    )

    hilos.append(hilo)
    hilo.start()

for hilo in hilos:
    hilo.join()

print("Todos los sensores terminaron.")