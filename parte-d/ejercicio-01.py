##Para cada programa, elegir **hilos** o **procesos** y justificar en una línea *(¿espera o calcula?)*.
##1. Consultar el precio de 30 productos en 30 APIs distintas.

"""
Hilos, porque se espera la respuesta de las APIs. Esta consulta las 30 APIs y mientras espera las respuestas, puede atender otras solicitudes.
"""