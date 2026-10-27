"""
Prueba automatica del sistema distribuido de archivos (PFO 3).

Levanta 3 nodos, sube un archivo y verifica los 4 comportamientos clave:
  1) Replicacion        - el archivo llega a los otros nodos al subirlo.
  2) Fallback           - un nodo que NO tiene el archivo lo busca en una replica.
  3) Tolerancia a fallos - si un nodo se cae, el archivo sigue disponible en otro.
  4) Subida degradada    - se puede subir aunque haya replicas caidas.

Uso: python test_sistema.py (100% multiplataforma: Windows, Linux, Mac)
"""

import os
import shutil
import subprocess
import sys
import time
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

NODOS = [
    {"port": 5000, "replicas": "http://localhost:5001,http://localhost:5002", "dir": "files_5000"},
    {"port": 5001, "replicas": "http://localhost:5000,http://localhost:5002", "dir": "files_5001"},
    {"port": 5002, "replicas": "http://localhost:5000,http://localhost:5001", "dir": "files_5002"},
]

procesos = {}
ok_total = True


def check(nombre, condicion):
    global ok_total
    estado = "OK  " if condicion else "FALLA"
    if not condicion:
        ok_total = False
    print(f"   [{estado}] {nombre}")


def esperar_nodo(port, timeout=10):
    limite = time.time() + timeout
    while time.time() < limite:
        try:
            if requests.get(f"http://localhost:{port}/health", timeout=1).status_code == 200:
                return True
        except requests.RequestException:
            time.sleep(0.2)
    return False


def levantar(nodo):
    nodo_dir = os.path.join(BASE_DIR, nodo["dir"])
    p = subprocess.Popen(
        [sys.executable, "nodo.py",
         "--port", str(nodo["port"]),
         "--replicas", nodo["replicas"],
         "--dir", nodo_dir],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=BASE_DIR
    )
    procesos[nodo["port"]] = p


def limpiar():
    for p in procesos.values():
        p.terminate()
    for p in procesos.values():
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill()
    for nodo in NODOS:
        shutil.rmtree(os.path.join(BASE_DIR, nodo["dir"]), ignore_errors=True)


def main():
    # Arranque limpio
    for nodo in NODOS:
        shutil.rmtree(os.path.join(BASE_DIR, nodo["dir"]), ignore_errors=True)

    print("Levantando 3 nodos distribuidos...")
    for nodo in NODOS:
        levantar(nodo)
    for nodo in NODOS:
        if not esperar_nodo(nodo["port"]):
            print(f"El nodo {nodo['port']} no arranco. Abortando.")
            limpiar()
            sys.exit(1)
    print("Los 3 nodos estan arriba.\n")

    contenido = b"Hola, soy un archivo distribuido.\n" * 3
    test_path = os.path.join(BASE_DIR, "test.txt")
    test2_path = os.path.join(BASE_DIR, "test2.txt")

    with open(test_path, "wb") as f:
        f.write(contenido)

    # 1) REPLICACION: subir a :5000 y ver que aparece en :5001 y :5002
    print("1) Replicacion al subir")
    with open(test_path, "rb") as f:
        r = requests.post("http://localhost:5000/upload",
                          files={"file": ("test.txt", f)})
    datos = r.json()
    check("la subida responde 200", r.status_code == 200)
    check("replico en las 2 replicas", len(datos.get("replicado_en", [])) == 2)
    check("copia fisica en files_5001", os.path.exists(os.path.join(BASE_DIR, "files_5001", "test.txt")))
    check("copia fisica en files_5002", os.path.exists(os.path.join(BASE_DIR, "files_5002", "test.txt")))

    # 2) FALLBACK: borro la copia local de :5002 y le pido el archivo a :5002
    print("2) Fallback a una replica cuando falta local")
    os.remove(os.path.join(BASE_DIR, "files_5002", "test.txt"))
    r = requests.get("http://localhost:5002/download/test.txt")
    check("recupera el archivo desde otra replica", r.status_code == 200 and r.content == contenido)

    # 3) TOLERANCIA A FALLOS: mato :5000 y descargo de :5001
    print("3) Tolerancia a fallos (nodo caido)")
    procesos[5000].terminate(); procesos[5000].wait()
    time.sleep(0.5)
    r = requests.get("http://localhost:5001/download/test.txt")
    check("el archivo sigue disponible tras caer :5000", r.status_code == 200 and r.content == contenido)

    # 4) SUBIDA DEGRADADA: con :5000 y :5002 caidos, subir a :5001 igual funciona
    print("4) Subida degradada (replicas caidas)")
    procesos[5002].terminate(); procesos[5002].wait()
    time.sleep(0.5)
    with open(test2_path, "wb") as f:
        f.write(b"segundo archivo\n")
    with open(test2_path, "rb") as f:
        r = requests.post("http://localhost:5001/upload",
                          files={"file": ("test2.txt", f)})
    datos = r.json()
    check("la subida responde 200 aunque haya nodos caidos", r.status_code == 200)
    check("reporta las replicas caidas", len(datos.get("replicas_caidas", [])) == 2)
    check("guardo el archivo localmente", os.path.exists(os.path.join(BASE_DIR, "files_5001", "test2.txt")))

    print()
    print("RESULTADO TEST NODOS:", "TODO OK" if ok_total else "HUBO FALLAS")
    for extra in (test_path, test2_path):
        if os.path.exists(extra):
            os.remove(extra)
    limpiar()
    sys.exit(0 if ok_total else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Error en el test:", e)
        limpiar()
        sys.exit(1)
