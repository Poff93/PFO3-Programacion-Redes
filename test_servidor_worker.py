"""
test_servidor_worker.py
Prueba automatica de concurrencia, framing y Pool de Hilos para servidor_worker.py (PFO 3).

Verifica:
  1) Conexiones simultaneas desde multiples clientes.
  2) Framing correcto en TCP (mensajes delimitados por \\n).
  3) Distribucion de tareas al ThreadPoolExecutor y consistencia en la seccion critica (Lock).
"""

import socket
import json
import time
import subprocess
import sys
import os

HOST = "localhost"
PORT = 6000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ok_total = True


def check(nombre, condicion):
    global ok_total
    estado = "OK  " if condicion else "FALLA"
    if not condicion:
        ok_total = False
    print(f"   [{estado}] {nombre}")


def enviar_y_recibir(sock, peticion):
    msg = json.dumps(peticion, ensure_ascii=False) + "\n"
    sock.sendall(msg.encode("utf-8"))

    buffer = ""
    while True:
        data = sock.recv(1024)
        if not data:
            return None
        buffer += data.decode("utf-8")
        if "\n" in buffer:
            linea, _ = buffer.split("\n", 1)
            return json.loads(linea.strip())


def main():
    print("Levantando servidor_worker.py...")
    p_worker = subprocess.Popen(
        [sys.executable, "servidor_worker.py"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=BASE_DIR
    )

    # Esperar a que el servidor este escuchando
    time.sleep(1.5)

    try:
        # 1) Prueba de PING
        print("1) Prueba de respuesta PING y Framing")
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.connect((HOST, PORT))
        resp_ping = enviar_y_recibir(s1, {"accion": "ping"})
        check("ping responde PONG", resp_ping and resp_ping.get("mensaje") == "PONG del servidor worker")

        # 2) Prueba de envio de tareas concurrentes con 2 clientes
        print("2) Concurrencia y Pool de Workers")
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.connect((HOST, PORT))

        resp_tarea1 = enviar_y_recibir(s1, {"accion": "analisis", "payload": "Prueba de sockets"})
        resp_tarea2 = enviar_y_recibir(s2, {"accion": "conversion", "payload": "hola mundo"})

        check("tarea 1 de analisis procesada", resp_tarea1 and "Analisis completado" in resp_tarea1.get("resultado", ""))
        check("tarea 2 de conversion procesada", resp_tarea2 and "HOLA MUNDO" in resp_tarea2.get("resultado", ""))

        # 3) Verificar estado de concurrencia y contador con Lock
        print("3) Estado del servidor y seccion critica (Lock)")
        resp_est = enviar_y_recibir(s1, {"accion": "estado"})
        check("contador de clientes activos es 2", resp_est and resp_est.get("clientes_activos") == 2)
        check("contador de tareas procesadas es 2", resp_est and resp_est.get("tareas_procesadas") == 2)
        check("pool de workers configurado en 5", resp_est and resp_est.get("workers_max") == 5)

        # Cierre limpio
        s1.sendall(b"salir\n")
        s2.sendall(b"salir\n")
        s1.close()
        s2.close()

        print()
        print("RESULTADO TEST WORKER:", "TODO OK" if ok_total else "HUBO FALLAS")

    finally:
        p_worker.terminate()
        try:
            p_worker.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p_worker.kill()

    sys.exit(0 if ok_total else 1)


if __name__ == "__main__":
    main()
