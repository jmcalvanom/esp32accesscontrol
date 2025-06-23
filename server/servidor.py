from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, abort
from flask_httpauth import HTTPBasicAuth
import sqlite3
import datetime
import os


#Puerto donde se ejecutara la API y la web
PUERTO = 5000

app = Flask(__name__)
auth = HTTPBasicAuth()

users = {
    "uma": "tfg2025"
}


@auth.verify_password
def verify_password(username, password):
    if username in users and users[username] == password:
        return username


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(BASE_DIR, "accesos.db")
LOG_FILE = os.path.join(BASE_DIR, "accesos.log")
PERMITED_FILE = os.path.join(BASE_DIR, "permitidos.log")
FILTERED_FILE = os.path.join(BASE_DIR, "filtrados.log")

# Funcion para inicializar la base de datos
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uids_autorizados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE,
            activo INTEGER DEFAULT 1,
            alias TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Funcion para verificar si la uid esta permitida
@app.route("/verificar", methods=["POST"])
def verificar_uid():
    data = request.json
    uid = data.get("uid")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Timestamp para los log
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Verificar si la uid esta permitida
    cursor.execute("SELECT uid FROM uids_autorizados WHERE uid=? AND activo=1", (uid,))
    autorizado = cursor.fetchone() is not None
    
    if autorizado:
        cursor.execute("INSERT INTO historial (uid, timestamp) VALUES (?, ?)", (uid, timestamp))
        with open(PERMITED_FILE, "a") as log2:
            log2.write(f"{timestamp} - UID: {uid}\n")
        with open(LOG_FILE, "a") as log:
            log.write(f"{timestamp} - PERMITIDO - UID: {uid}\n")
    else:
        with open(LOG_FILE, "a") as log:
            log.write(f"{timestamp} - DENEGADO - UID: {uid}\n")

    conn.commit()
    conn.close()

    respuesta = {"acceso": "PERMITIDO" if autorizado else "DENEGADO"}
    return jsonify(respuesta)

# Funcion de la página web para gestionar los accesos
@app.route("/")
@auth.login_required
def index():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, uid, alias, activo FROM uids_autorizados")
    uids_autorizados = cursor.fetchall()

    cursor.execute("SELECT * FROM historial ORDER BY id DESC LIMIT 20")
    historial = cursor.fetchall()

    conn.close()
    return render_template("index.html", uids_autorizados=uids_autorizados, historial=historial)

# API para registrar llaves
@app.route("/agregar_uid", methods=["POST"])
def agregar_uid():
    uid = request.form.get("uid")
    alias = request.form.get("alias")
    if uid:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO uids_autorizados (uid, alias) VALUES (?, ?)", (uid, alias))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # No puede haber uids duplicados
        conn.close()
    return redirect(url_for("index"))

# API para eliminar un UID de la base de datos
@app.route("/eliminar_uid/<uid>")
def eliminar_uid(uid):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM uids_autorizados WHERE uid=?", (uid,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

#API para suspender una llave temporalmente
@app.route("/suspend/<uid>")
def suspend(uid):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT activo FROM uids_autorizados WHERE uid=?", (uid,))
    resultado = cursor.fetchone()

    if resultado is not None:
        nuevo_estado = 0 if resultado[0] == 1 else 1
        cursor.execute("UPDATE uids_autorizados SET activo=? WHERE uid=?", (nuevo_estado, uid))
        conn.commit()

    conn.close()
    return redirect(url_for("index"))


# Funcion para filtrar accesos segun parametros
@app.route("/descargar_informe", methods=["GET"])
def descargar_informe():
    uid = request.args.get("uid")
    fecha_inicio = request.args.get("fecha_inicio")
    fecha_fin = request.args.get("fecha_fin")
    hora_inicio = request.args.get("hora_inicio")
    hora_fin = request.args.get("hora_fin")


    with open(FILTERED_FILE, "w") as f:
        with open(PERMITED_FILE, "r") as permitedLog:
            for line in permitedLog:
                # Separa la informacion contenida en el log
                timestamp, logged_uid = line.strip().split(" - UID: ")
                fecha, hora = timestamp.split(" ")

                # Filtrado segun los parametros introducidos
                if (not fecha_inicio or fecha >= fecha_inicio) and \
                    (not fecha_fin or fecha <= fecha_fin) and \
                    (not hora_inicio or hora >= hora_inicio) and \
                    (not hora_fin or hora <= hora_fin) and \
                    (not uid or logged_uid == uid):
                    f.write(f"{timestamp} - UID: {logged_uid}\n")

    return send_file(FILTERED_FILE, as_attachment=True)

# Funcion para descargar el log completo de accesos
@app.route("/descargar_log")
def descargar_log():
    if not os.path.isfile(LOG_FILE):
        return abort(404, description="El archivo de log no existe.")
    
    return send_file(LOG_FILE, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PUERTO, debug=True)
