# Segundo Parcial · Enunciado

Lenguaje de Programación I

## 1. Qué se construye

Una versión reducida del **servidor de mensajería del proyecto**: los mismos módulos y el mismo enunciado de la fase inicial del proyecto, en tres niveles. Lo que cada uno escriba hoy se puede llevar al repositorio de su equipo: el Nivel 3 es el arranque del Hito 2.

| Parte | Qué es |
| --- | --- | --- |
| Nivel 1 · Framing | `protocolo.py` |
| Nivel 2 · Servidor concurrente | `registro.py` y `servidor.py` |
| Nivel 3 · Mensajes JSON | `servidor_json.py` |
| Sustentación individual | 5 minutos, en el puesto, sobre el código propio |

## 2. Reglas

- **Individual.** Internet permitido para GitHub y la documentación oficial de Python. **Se puede consultar el repositorio del propio equipo.** Sin IA y sin chats.
- **Todo en `localhost`**, Python 3.10 o superior, solo biblioteca estándar.
- **Se entrega por `git push`** al repositorio `<nombre>-<apellido>`, en la carpeta `parcial2/`.
- **No se cambian** los nombres de archivos, funciones ni clases, ni los archivos `prueba_n*.py`, `cliente.py` y `cliente_json.py`: la calificación corre las pruebas tal como se entregaron.
- **Código que no ejecuta se califica sobre el 50%** del nivel.

## 3. Tiempos

| Tramo | Duración | Qué se hace |
| --- | --- | --- |
| 1 | 40 min | Niveles 1 y 2. Al cierre, **commit con el mensaje `niveles 1-2` y push** |
| 2 | 75 min | Nivel 3. Durante este tramo el docente pasa por cada puesto para la sustentación |

- **La sustentación se hace sobre el commit `niveles 1-2`.** Quien no lo haya empujado a la hora límite sustenta lo que tenga en ese momento.
- Los niveles 1 y 2 se pueden terminar o corregir durante el tramo 2: **el código se califica sobre el último push anterior a la hora límite final.**

## 4. Material entregado

```bash
parcial2/
├── README.md
├── ENUNCIADO.md
├── mensajeria/
│   ├── __init__.py
│   ├── protocolo.py        Nivel 1 · esqueleto con TODO
│   ├── registro.py         Nivel 2 · solo las firmas
│   ├── servidor.py         Nivel 2 · acepta conexiones; falta el hilo y la atención del cliente
│   ├── cliente.py          completo · cliente de consola para el Nivel 2
│   └── cliente_json.py     completo · cliente de consola para el Nivel 3
├── prueba_n1.py
├── prueba_n2.py
└── prueba_n3.py
```

Desde la carpeta `parcial2/`:

```bash
python3 prueba_n1.py                    # cada prueba arranca lo que necesita e imprime una salida fija
python3 -m mensajeria.servidor          # para probar a mano, en una terminal
python3 -m mensajeria.cliente camilo       # y en otras dos o tres
```

- Cada prueba termina con `NIVEL N: CORRECTO`, o se detiene en el primer paso que falla y dice qué pasó. El docstring de cada una trae la salida esperada.
- Las pruebas arrancan el servidor ellas mismas, en un puerto libre, y lo detienen al terminar: **no hay que tener nada corriendo.** Para eso el servidor recibe el puerto como argumento *(`python3 -m mensajeria.servidor 8050`; sin argumento, el 8000)*. Esa parte ya viene escrita en `main()` y no se cambia.
- Las pruebas de los niveles 2 y 3 hablan con el servidor usando **su** `protocolo.py`: el Nivel 1 va primero.
- En Windows, `python` en lugar de `python3`.

## 5. Nivel 1 · Framing

**TCP es un flujo de bytes, no de mensajes.** Completar `mensajeria/protocolo.py`:

```python
def recibir_exacto(sock: socket.socket, n: int) -> bytes | None:
    """Lee exactamente n bytes. Devuelve None si la conexión se cerró antes."""

def enviar_mensaje(sock: socket.socket, texto: str) -> None:
    """Envía texto en UTF-8 precedido de su longitud en 4 bytes big-endian."""

def recibir_mensaje(sock: socket.socket) -> str | None:
    """Lee un mensaje completo. Devuelve None si el otro extremo cerró."""
```

1. El prefijo es `struct.pack("!I", n)`, donde `n` es la longitud **en bytes** del cuerpo ya codificado.
2. `recibir_exacto` llama a `recv()` **en bucle** hasta completar los `n` bytes.
3. UTF-8 explícito al codificar y al decodificar.
4. Si `recv()` devuelve bytes vacíos, la conexión se cerró: se devuelve `None`.

**`prueba_n1.py` comprueba:** una ráfaga de 1.000 mensajes cortos sin pausa, un mensaje de 3 MB, un mensaje con `ñ` y un emoji *(byte por byte: el prefijo y el cuerpo)*, y el cierre limpio.

## 6. Nivel 2 · Servidor concurrente (20 pts)

Completar `mensajeria/registro.py` y `mensajeria/servidor.py`, usando el `protocolo.py` del Nivel 1.

### `registro.py`

```python
class RegistroClientes:
    def insertar(self, nombre: str, conexion: socket.socket) -> bool: ...
    def buscar(self, nombre: str) -> socket.socket | None: ...
    def borrar(self, nombre: str) -> None: ...
    def destinatarios(self, excepto: str) -> list[tuple[str, socket.socket]]: ...
```

1. Un `dict` con el nombre como clave, protegido con **un** `threading.Lock`.
2. `insertar` devuelve `False` si el nombre ya está en uso. **Verificar e insertar ocurren bajo el mismo lock.**
3. `buscar` devuelve `None` si el nombre no está. `borrar` un nombre que ya no está no es un error.
4. `destinatarios` devuelve **una copia**, hecha dentro del lock: la lista de `(nombre, conexion)` de todos menos `excepto`.

### `servidor.py`

1. **Un hilo por conexión.** El hilo principal solo acepta.
2. **La primera trama del cliente es su nombre.** El servidor responde `OK` y lo registra, o responde `ERROR: nombre en uso` y cierra la conexión.
3. Cada trama siguiente se **retransmite a todos los demás** como `emisor: contenido`.
4. **El envío va fuera del lock:** se copia la lista de destinatarios bajo el lock y se envía después.
5. **Una desconexión no tumba nada:** si un cliente se va, con aviso o a la fuerza, su entrada se borra del registro y los demás siguen. Un destinatario al que ya no se puede enviar también se retira.
6. `SO_REUSEADDR` y `with` para los sockets.

**`prueba_n2.py` comprueba:** el registro por sí solo *(las cuatro operaciones, y dos hilos que insertan el mismo nombre a la vez)*, varios clientes conectados a la vez, dos que piden el mismo nombre al mismo tiempo *(solo uno recibe `OK`)*, la retransmisión a los demás y no al emisor, y un cliente cerrado a la fuerza sin que los otros dejen de recibir.

## 7. Nivel 3 · Mensajes JSON

**Copiar `servidor.py` a `mensajeria/servidor_json.py` y trabajar sobre la copia.** El Nivel 2 queda intacto y las tres pruebas siguen pasando.

```bash
python3 -m mensajeria.servidor_json         # para probar a mano
python3 -m mensajeria.cliente_json ana      # texto, o  /privado luis texto
```

El saludo con el nombre no cambia. Después, **cada trama es un objeto JSON** con un campo `tipo`, dentro del mismo framing:

| Dirección | `tipo` | Ejemplo |
| --- | --- | --- |
| Cliente → servidor | `mensaje` | `{"tipo": "mensaje", "contenido": "camión 3 listo"}` |
| Cliente → servidor | `privado` | `{"tipo": "privado", "destino": "luis", "contenido": "pasa por el muelle 2"}` |
| Servidor → los demás | `mensaje` | `{"tipo": "mensaje", "emisor": "ana", "canal": "general", "contenido": "camión 3 listo", "timestamp": "2026-10-20T18:42:07"}` |
| Servidor → destino | `privado` | `{"tipo": "privado", "emisor": "ana", "destino": "luis", "contenido": "pasa por el muelle 2", "timestamp": "2026-10-20T18:43:10"}` |
| Servidor → quien pidió | `error` | `{"tipo": "error", "detalle": "luis no está conectado"}` |

1. **`emisor` y `timestamp` los pone el servidor**, con el nombre del registro y `datetime.now().isoformat(timespec="seconds")`. Si el cliente envía un `emisor`, se ignora.
2. **`mensaje`** llega a todos los demás, con `"canal": "general"` *(los demás canales son del Hito 2)*.
3. **`privado`** llega **solo** al destino.
4. **Un pedido inválido recibe un `error`** y no se reenvía: destino que no está conectado, privado a uno mismo, `tipo` desconocido o falta el `contenido`. El texto del `detalle` es libre.
5. **Un JSON dañado no tumba al servidor:** se descarta esa trama y la conexión sigue.
6. Nunca `pickle`.

**`prueba_n3.py` comprueba:** un `mensaje` que llega a los demás con `emisor` y `timestamp`, un `privado` que el tercer cliente no ve, un `emisor` falsificado que llega firmado por quien lo envió, los cuatro errores y una trama con JSON roto seguida de una válida.

## 8. Calificación del código

| Criterio | Peso | Qué se evalúa |
| --- | --- | --- |
| Funciona | 50% | La prueba del nivel termina en `CORRECTO` |
| Corrección técnica | 30% | `recv` en bucle y longitud en bytes; verificación dentro del lock, copia y envío fuera; `emisor` del servidor y JSON dañado tolerado |
| Claridad | 20% | Nombres claros, sin cambios fuera de lo pedido, sockets cerrados con `with` |

## 9. Sustentación

Cinco minutos, en el puesto, sobre el commit `niveles 1-2`:

| Parte | Puntos | Qué se pide |
| --- | --- | --- |
| Demostración | 10 | Correr la prueba del nivel más alto que se tenga |
| Trazado | 15 | Seguir un mensaje sobre el código propio: del `sendall` del cliente al `recv` del servidor, y de ahí al registro |
| Tarjeta | 15 | Se saca una al azar: predecir o hacer en vivo un cambio sobre el código, o responder un concepto de las Clases 5–8 |

- **Entran como concepto** los temas que el código no toca: UDP, `pickle` frente a `json`, y RMI.
- **Regla de tope:** con menos de 16 puntos en la sustentación *(40%)*, el código se califica sobre el 60%. No se puede obtener nota por un código que no se sabe explicar.

Los comandos, paso a paso, están en el [README principal](../README.md).
