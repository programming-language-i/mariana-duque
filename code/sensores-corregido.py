import threading
import time

def sensor(numero, temperatura):
    print(f"{numero} sensor")

    for i in range(5):
        print(f"{numero} - {i+1}: temperatura: {temperatura} grados centigrados")
        time.sleep(1)

    print("termino")

if __name__ == "__main__":
    threads = [
        threading.Thread(target=sensor, args=("Sensor 1", 30)),
        threading.Thread(target=sensor, args=("Sensor 2", 40)),
        threading.Thread(target=sensor, args=("Sensor 1", 50)),
        threading.Thread(target=sensor, args=("Sensor 1", 60)),
        threading.Thread(target=sensor, args=("Sensor 1", 70)),
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    print("Finalizo el proceso")

