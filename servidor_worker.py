"""
servidor_worker.py
Servidor worker basado en sockets TCP con Pool de Hilos (ThreadPoolExecutor) para la PFO 3.

- Acepta conexiones concurrentes en el puerto 6000.
- Distribuye las tareas a un Pool de Workers (ThreadPoolExecutor).
- Implementa delimitador por salto de linea (\n) para evitar problemas de framing en TCP.
- Mantiene estado compartido seguro mediante un candado de exclusion mutua (Lock).
"""

import socket
import threading
import json
import time
from concurrent.futures import ThreadPoolExecutor

HOST = "localhost"
PORT = 6000
MAX_WORKERS = 5

# Pool de hilos dedicado al procesamiento de tareas (Workers)
worker_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Estado compartido protegido por candado
candado = threading.Lock()
tareas_procesadas = 0
clientes_activos = 0


def tarea_procesar(tipo_tarea, payload):
    """Ejecutada por un worker del ThreadPoolExecutor."""
    time.sleep(0.5)  # simula trabajo pesado I/O o CPU
    if tipo_tarea == "analisis":
        res = f"Analisis completado para: '{payload}'. Total caracteres: {len(payload)}"
    elif tipo_tarea == "conversion":
        res = f"Conversion completada: {payload.upper()}"
    else:
        res = f"Tarea '{tipo_tarea}' procesada con exito para: {payload}"
    return res


def leer_mensaje(conn):
    """Lee del socket TCP acumulando datos hasta encontrar el delimitador '\\n' (Framing TCP)."""
    buffer = ""
    while True:
        data = conn.recv(1024)
        if not data:
            return None  # socket cerrado
        buffer += data.decode("utf-8")
        if "\n" in buffer:
            linea, _ = buffer.split("\n", 1)
            return linea.strip()


def enviar_mensaje(conn, obj):
    """Envia un objeto JSON terminado en '\\n' para garantizar el framing."""
    msg = json.dumps(obj, ensure_ascii=False) + "\n"
    conn.sendall(msg.encode("utf-8"))


def atender_cliente(conn, addr):
    """Atiende el socket del cliente y envia las tareas pesadas al Pool de Workers."""
    global tareas_procesadas, clientes_activos

    with candado:
        clientes_activos += 1
        n_cli = clientes_activos
    print(f"[+] Cliente conectado desde {addr} | Activos: {n_cli}")

    with conn:
        while True:
            try:
                mensaje = leer_mensaje(conn)
                if mensaje is None:
                    break

                if not mensaje or mensaje.lower() in ("salir", "exit", "chau"):
                    break

                # Parseo la peticion
                try:
                    peticion = json.loads(mensaje)
                    accion = peticion.get("accion", "desconocida")
                    payload = peticion.get("payload", "")
                except json.JSONDecodeError:
                    accion = "conversion"
                    payload = mensaje

                if accion == "ping":
                    enviar_mensaje(conn, {"status": "ok", "mensaje": "PONG del servidor worker"})
                elif accion == "estado":
                    with candado:
                        resp = {
                            "status": "ok",
                            "tareas_procesadas": tareas_procesadas,
                            "clientes_activos": clientes_activos,
                            "workers_max": MAX_WORKERS
                        }
                    enviar_mensaje(conn, resp)
                else:
                    # Distribuyo la tarea al Pool de Workers (ThreadPoolExecutor)
                    future = worker_pool.submit(tarea_procesar, accion, payload)
                    resultado = future.result()  # espera el resultado del worker

                    with candado:
                        tareas_procesadas += 1
                        total = tareas_procesadas

                    enviar_mensaje(conn, {
                        "status": "ok",
                        "resultado": resultado,
                        "tarea_numero": total
                    })

            except ConnectionResetError:
                break
            except Exception as e:
                try:
                    enviar_mensaje(conn, {"status": "error", "mensaje": str(e)})
                except Exception:
                    pass

    with candado:
        clientes_activos -= 1
    print(f"[-] Cliente {addr} desconectado")


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"=== Servidor Worker con ThreadPoolExecutor ({MAX_WORKERS} workers) en {HOST}:{PORT} ===")
        print("Listo para recibir conexiones (Ctrl+C para salir)\n")

        try:
            while True:
                conn, addr = s.accept()
                hilo = threading.Thread(target=atender_cliente, args=(conn, addr), daemon=True)
                hilo.start()
        except KeyboardInterrupt:
            print("\nDeteniendo el servidor worker...")
            worker_pool.shutdown(wait=False)


if __name__ == "__main__":
    main()
