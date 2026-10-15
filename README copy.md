# Segundo Parcial · Lenguaje de Programación I

Un servidor de mensajería en tres niveles, individual y en máquina. **El enunciado completo está en [`parcial2/README.md`](parcial2/README.md).**

| Tramo | Qué | Tiempo | Al cierre |
| --- | --- | --- | --- |
| 1 | Niveles 1 y 2 | 40 min | commit **`niveles 1-2`** y push, antes de la **primera hora límite** |
| 2 | Nivel 3, y la sustentación en su puesto | 75 min | último push, antes de la **hora límite final** |

- **La sustentación se hace sobre el commit `niveles 1-2`.** Quien no lo haya empujado a la primera hora límite sustenta lo que tenga en ese momento.
- **El código se califica sobre el último push anterior a la hora límite final.** Los niveles 1 y 2 se pueden terminar o corregir durante el tramo 2.
- Las dos horas las anuncia el docente y las registra GitHub, no su computador.
- **Internet** solo para GitHub y la documentación de Python ([docs.python.org](https://docs.python.org/3/)). Se puede consultar el repositorio.

## Cómo se entrega (GitHub)

Se trabaja en su repositorio del curso, `<nombre>-<apellido>`, dentro de una carpeta `parcial2/`:

```bash
<nombre>-<apellido>/
└── parcial2/
    ├── ENUNCIADO.md
    ├── README.md
    ├── mensajeria/
    ├── prueba_n1.py
    ├── prueba_n2.py
    └── prueba_n3.py
```

### 1. Copiar el material

### 2. Primer commit y push (antes de empezar a resolver)

```bash
git add .
git commit -m "parcial2: inicio"
git push
```

Abra su repositorio en github.com y confirme que aparece `parcial2/`. **Si el push falla, avísele al docente en ese momento**, no al final.

### 3. Trabajar y probar

Siempre desde la carpeta `parcial2/`:

```bash
cd parcial2
python3 prueba_n1.py
python3 prueba_n2.py
```

Cada prueba termina en `NIVEL N: CORRECTO` o dice en qué paso falló y por qué. Un commit por nivel:

```bash
git add .
git commit -m "nivel 1"
git push
```

### 4. Primera hora límite: el commit `niveles 1-2`

Antes de la hora que anuncia el docente, con lo que tenga de los niveles 1 y 2, **con ese mensaje exacto**:

```bash
git add .
git commit -m "niveles 1-2"
git push
```

Ese es el commit que se sustenta.

### 5. Hora límite final

Para el Nivel 3, copie su `servidor.py` y trabaje sobre la copia:

```bash
cp mensajeria/servidor.py mensajeria/servidor_json.py
python3 prueba_n3.py
```

Haga el último `git push` **antes de la hora límite final**. Lo que se envie después no cuenta. Revise en github.com que sus archivos estén ahí, incluido `mensajeria/servidor_json.py`.

### Si el push no funciona

Comprima la carpeta `parcial2/` en `parcial2-<nombre>-<apellido>.zip`, envie por correo electronico (juan.charfuelan@uniremington.edu.co) antes de la hora límite y avísele al docente.
