"""
Nodo de un sistema distribuido de archivos (PFO 3).

Un solo archivo parametrizado: cada nodo se levanta con su propio puerto,
su carpeta y la lista de sus réplicas.

Ejemplo (tres nodos en tres terminales):
    python nodo.py --port 5000 --replicas http://localhost:5001,http://localhost:5002
    python nodo.py --port 5001 --replicas http://localhost:5000,http://localhost:5002
    python nodo.py --port 5002 --replicas http://localhost:5000,http://localhost:5001
"""

import argparse
import os
import requests
from flask import Flask, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename


def crear_app(files_dir, replicas):
    os.makedirs(files_dir, exist_ok=True)
    app = Flask(__name__)

    @app.route("/upload", methods=["POST"])
    def upload():
        """Recibe un archivo del usuario, lo guarda y lo replica en los demás nodos."""
        if "file" not in request.files:
            return jsonify({"error": "falta el campo 'file'"}), 400

        f = request.files["file"]
        filename = secure_filename(f.filename)  # evita rutas tipo ../../
        if not filename:
            return jsonify({"error": "nombre de archivo invalido"}), 400

        ruta = os.path.join(files_dir, filename)
        f.save(ruta)

        # Replicar en cada réplica. Si UNA está caída, seguimos con las demás:
        # tolerancia a fallos de verdad (la subida no se rompe por un nodo caído).
        replicado_en, replicas_caidas = [], []
        for server in replicas:
            try:
                with open(ruta, "rb") as fh:
                    requests.post(
                        f"{server}/replicate",
                        files={"file": (filename, fh)},
                        timeout=3,
                    )
                replicado_en.append(server)
            except requests.RequestException:
                replicas_caidas.append(server)

        return jsonify({
            "status": "subido",
            "archivo": filename,
            "replicado_en": replicado_en,
            "replicas_caidas": replicas_caidas,
        }), 200

    @app.route("/replicate", methods=["POST"])
    def replicate():
        """Guarda una copia que mandó otro nodo. NO vuelve a replicar (evita loops)."""
        if "file" not in request.files:
            return jsonify({"error": "falta el campo 'file'"}), 400
        f = request.files["file"]
        filename = secure_filename(f.filename)
        f.save(os.path.join(files_dir, filename))
        return jsonify({"status": "replicado", "archivo": filename}), 200

    @app.route("/download/<filename>", methods=["GET"])
    def download(filename):
        """Devuelve el archivo. Si no lo tiene local, lo busca en una réplica."""
        filename = secure_filename(filename)
        ruta = os.path.join(files_dir, filename)

        if os.path.exists(ruta):
            return send_file(ruta, as_attachment=True)

        # No está local. Si el pedido NO es reenviado, probamos las réplicas.
        # (forward=0 corta la cadena para que dos nodos no se reenvíen infinito.)
        if request.args.get("forward") != "0":
            for server in replicas:
                try:
                    r = requests.get(
                        f"{server}/download/{filename}",
                        params={"forward": "0"},
                        timeout=3,
                    )
                    if r.status_code == 200:
                        return Response(
                            r.content,
                            headers={
                                "Content-Disposition": f"attachment; filename={filename}"
                            },
                            mimetype="application/octet-stream"
                        )
                except requests.RequestException:
                    continue

        return jsonify({"error": "archivo no encontrado"}), 404

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "archivos": sorted(os.listdir(files_dir))}), 200

    return app


def main():
    parser = argparse.ArgumentParser(description="Nodo de almacenamiento distribuido")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--replicas", default="",
        help="URLs de las réplicas separadas por coma",
    )
    parser.add_argument(
        "--dir", default=None,
        help="carpeta de archivos (default: files_<port>)",
    )
    args = parser.parse_args()

    replicas = [r.strip() for r in args.replicas.split(",") if r.strip()]
    files_dir = args.dir or f"files_{args.port}"

    app = crear_app(files_dir, replicas)
    print(f"Nodo escuchando en http://localhost:{args.port}  |  dir='{files_dir}'  |  réplicas={replicas}")
    app.run(port=args.port)


if __name__ == "__main__":
    main()
