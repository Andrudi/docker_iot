from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os, logging, ssl
import paho.mqtt.publish as publish # <-- Esta librería faltaba importar
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

logging.basicConfig(format='%(asctime)s - CRUD - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config["MYSQL_USER"] = os.environ["MYSQL_USER"]
app.config["MYSQL_PASSWORD"] = os.environ["MYSQL_PASSWORD"]
app.config["MYSQL_DB"] = os.environ["MYSQL_DB"]
app.config["MYSQL_HOST"] = os.environ["MYSQL_HOST"]
app.config['PERMANENT_SESSION_LIFETIME']=180
mysql = MySQL(app)

# --- VARIABLES MQTT DESDE .ENV ---
MQTT_BROKER = os.environ.get('MQTT_BROKER')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 8883))
MQTT_USER = os.environ.get('MQTT_USER')
MQTT_PASS = os.environ.get('MQTT_PASS')

# --- RUTAS Y AUTENTICACIÓN ---

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
        if not request.form.get("usuario"):
            return "El campo usuario es obligatorio"
        elif not request.form.get("password"):
            return "El campo contraseña es obligatorio"

        passhash=generate_password_hash(request.form.get("password"), method='scrypt', salt_length=16)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO usuarios (usuario, hash) VALUES (%s,%s)", (request.form.get("usuario"), passhash[17:]))
        if mysql.connection.affected_rows():
            flash('Se agregó un nuevo usuario', 'success')
            logging.info("Se agregó un usuario")
        mysql.connection.commit()
        return redirect(url_for('index'))

    return render_template('registrar.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not request.form.get("usuario"):
            return "El campo usuario es obligatorio"
        elif not request.form.get("password"):
            return "El campo contraseña es obligatorio"

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario LIKE %s", (request.form.get("usuario"),))
        rows=cur.fetchone()
        if(rows):
            if (check_password_hash('scrypt:32768:8:1$' + rows[2],request.form.get("password"))):
                session.permanent = True
                session["user_id"]=request.form.get("usuario")
                logging.info("Se autenticó correctamente")
                return redirect(url_for('index'))
            else:
                flash('Usuario o contraseña incorrecto', 'danger')
                return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/logout")
@require_login
def logout():
    session.clear()
    logging.info("El usuario cerró su sesión")
    return redirect(url_for('login'))

# --- PANEL PRINCIPAL (CONTROL MQTT) ---

@app.route('/', methods=['GET', 'POST'])
@require_login
def index():
    if request.method == 'POST':
        nodo_destino_mac = request.form.get('nodo')
        comando = request.form.get('comando')
        valor_setpoint = request.form.get('setpoint_val', '0')

        # Armamos el tópico usando la estructura MAC/comandos
        topic = f"{nodo_destino_mac}/comandos"

        if comando == 'destello':
            payload = "CMD:BLINK"
        elif comando == 'setpoint':
            payload = f"CMD:SETPOINT,VAL:{valor_setpoint}"
        else:
            payload = "CMD:UNKNOWN"

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
            flash(f'Comando "{comando}" enviado a {nodo_destino_mac}.', 'success')
            
        except Exception as e:
            flash(f'Error de conexión MQTTS: {str(e)}', 'danger')
            logging.error(f"Fallo en MQTT: {str(e)}")

        return redirect(url_for('index'))

    # Ahora renderizamos index.html que será nuestro panel de control
    return render_template('index.html')