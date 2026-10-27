"""
cliente.py
Cliente interactivo para conectarse al servidor worker por sockets TCP (PFO 3).

Maneja framing TCP delimitado por salto de linea (\\n) para evitar truncamientos en mensajes JSON.
"""

import socket
import json

HOST = "localhost"
PORT = 6000


def enviar_y_recibir(sock, peticion):
    """Envia una peticion JSON con '\\n' y recibe la respuesta con acumulador de buffer."""
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
    print("=== Cliente interactivo para Servidor Worker (PFO 3) ===")
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((HOST, PORT))
            print(f"Conectado exitosamente al worker en {HOST}:{PORT}\n")
        except ConnectionRefusedError:
            print(f"Error: No se pudo conectar a {HOST}:{PORT}. Asegurate de ejecutar 'python servidor_worker.py' primero.")
            return

        print("Opciones disponibles:")
        print(" 1. Enviar tarea de analisis de texto")
        print(" 2. Enviar tarea de conversion a mayusculas")
        print(" 3. Ver estado del servidor (contador de tareas/clientes)")
        print(" 4. Enviar PING")
        print(" 5. Salir\n")

        while True:
            opcion = input("Elegi una opcion (1-5): ").strip()

            if opcion == "1":
                texto = input("Ingresa el texto a analizar: ").strip()
                peticion = {"accion": "analisis", "payload": texto}
            elif opcion == "2":
                texto = input("Ingresa el texto a convertir: ").strip()
                peticion = {"accion": "conversion", "payload": texto}
            elif opcion == "3":
                peticion = {"accion": "estado"}
            elif opcion == "4":
                peticion = {"accion": "ping"}
            elif opcion == "5" or opcion.lower() in ("salir", "exit"):
                s.sendall(b"salir\n")
                print("Desconectando del servidor...")
                break
            else:
                print("Opcion invalida, intenta de nuevo.\n")
                continue

            resp = enviar_y_recibir(s, peticion)
            if resp is None:
                print("El servidor cerro la conexion.")
                break

            print(f"-> Respuesta del Servidor: {json.dumps(resp, indent=2, ensure_ascii=False)}\n")


if __name__ == "__main__":
    main()
