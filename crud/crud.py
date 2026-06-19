from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os, logging, ssl
import paho.mqtt.publish as publish
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

logging.basicConfig(format='%(asctime)s - CRUD - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config["MYSQL_USER"] = os.environ["MYSQL_USER"]
app.config["MYSQL_PASSWORD"] = os.environ["MYSQL_PASSWORD"]
app.config["MYSQL_DB"] = os.environ["MYSQL_DB"]
app.config["MYSQL_HOST"] = os.environ["MYSQL_HOST"]
app.config['PERMANENT_SESSION_LIFETIME'] = 180
mysql = MySQL(app)

# --- VARIABLES MQTT DESDE EL .ENV ---
MQTT_BROKER = os.environ.get('MQTT_BROKER')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 8883))
MQTT_USER = os.environ.get('MQTT_USER')
MQTT_PASS = os.environ.get('MQTT_PASS')

# --- AUTENTICACIÓN ---
def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        if not request.form.get("usuario") or not request.form.get("password"):
            return "Usuario y contraseña son obligatorios"
        passhash = generate_password_hash(request.form.get("password"), method='scrypt', salt_length=16)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO usuarios (usuario, hash) VALUES (%s,%s)", (request.form.get("usuario"), passhash[17:]))
        mysql.connection.commit()
        flash('Usuario registrado exitosamente', 'success')
        return redirect(url_for('login'))
    return render_template('registrar.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not request.form.get("usuario") or not request.form.get("password"):
            return "Usuario y contraseña son obligatorios"
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario LIKE %s", (request.form.get("usuario"),))
        rows = cur.fetchone()
        if rows and check_password_hash('scrypt:32768:8:1$' + rows[2], request.form.get("password")):
            session.permanent = True
            session["user_id"] = request.form.get("usuario")
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrecto', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/logout")
@require_login
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- PANEL IOT (NODOS Y MQTT) ---
@app.route('/', methods=['GET'])
@require_login
def index():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM nodos')
    datos = cur.fetchall()
    cur.close()
    return render_template('index.html', nodos=datos)

@app.route('/add_nodo', methods=['POST'])
@require_login
def add_nodo():
    mac = request.form['mac']
    descripcion = request.form['descripcion']
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO nodos (mac, descripcion) VALUES (%s,%s)", (mac, descripcion))
    mysql.connection.commit()
    flash('Placa agregada correctamente', 'success')
    return redirect(url_for('index'))

@app.route('/borrar_nodo/<id>', methods=['GET'])
@require_login
def borrar_nodo(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM nodos WHERE id = %s', (id,))
    mysql.connection.commit()
    flash('Placa eliminada', 'success')
    return redirect(url_for('index'))

@app.route('/enviar_comando', methods=['POST'])
@require_login
def enviar_comando():
    mac = request.form.get('mac_destino')
    comando = request.form.get('comando')
    setpoint_val = request.form.get('setpoint_val', '0')

    # Armamos la estructura de tópicos
    if comando == 'destello':
        topic = f"{mac}/destello"
        payload = "destello"
    elif comando == 'setpoint':
        topic = f"{mac}/setpoint"
        payload = str(setpoint_val)
    else:
        flash("Comando no reconocido.", "danger")
        return redirect(url_for('index'))

    try:
        auth_dict = {'username': MQTT_USER, 'password': MQTT_PASS}
        publish.single(
            topic=topic,
            payload=payload,
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            auth=auth_dict,
            tls={'tls_version': ssl.PROTOCOL_TLS_CLIENT, 'ca_certs': None}
        )
        flash(f'Mensaje enviado. Tópico: {topic} | Payload: {payload}', 'success')
    except Exception as e:
        flash(f'Error de conexión MQTTS: {str(e)}', 'danger')
        logging.error(f"Error MQTT: {str(e)}")

    return redirect(url_for('index'))