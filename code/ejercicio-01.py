import threading
import time

def imprimir_mensaje():
    for i in range(5):
        print("Hello")
        time.sleep(1)  #Se duerfme un mili segundo y vuelve a imprimer

def main():
    thread = threading.Thread(target=imprimir_mensaje)
    thread.start()
    thread.join()  # Espera a que el hilo termine antes de continuar

    print("Finalizo")

if __name__ == "__main__":
    main()
   