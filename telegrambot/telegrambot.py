from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import logging, os, asyncio, aiomysql, traceback
import matplotlib.pyplot as plt
from io import BytesIO
import aiomqtt
import ssl

# --- Configuración Inicial ---
token = os.environ["TB_TOKEN"]
id_dispositivo = os.environ["ID_DISPOSITIVO"] # La MAC RB Pico W

logging.basicConfig(format='%(asctime)s - TelegramBot - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def enviar_comando_mqtt(topico_final: str, payload: str):
    """Se conecta al broker con credenciales, publica un comando para la Pico W y se desconecta."""
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = False 
    tls_context.load_default_certs()
    
    try:
        async with aiomqtt.Client(
            hostname=os.environ['SERVIDOR'],
            port=int(os.environ['PUERTO_MQTTS']), 
            username=os.environ['MQTT_USR'],      
            password=os.environ['MQTT_PASS'],     
            tls_context=tls_context
        ) as client:
            # Obtiene el ID del .env para armar la ruta
            id_disp = os.environ.get("ID_DISPOSITIVO", "DESCONOCIDO")
            topico_completo = f"{id_disp}/{topico_final}"
            
            await client.publish(topico_completo, payload)
            logging.info(f"MQTT Publicado: {topico_completo} -> {payload}")
            
    except Exception as e:
        logging.error(f"Error al enviar comando MQTT: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.from_user.first_name if update.message.from_user.first_name else ""
    
    # Teclado ampliado con los controles de la Pico W
    kb = [
        ["temperatura", "humedad"],
        ["gráfico temperatura", "gráfico humedad"],
        ["Modo Auto", "Modo Manual"],
        ["Relé ON", "Relé OFF", "Destello"]
    ]
    await update.message.reply_text(
        text=f"¡Bienvenido al Panel de Control IoT, {nombre}!",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def acercade(update: Update, context):
    await update.message.reply_text("Este bot fue creado para el curso de IoT de la FIO.")

# --- Funciones de Control de la Pico W ---
async def control_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = update.message.text
    payload = "auto" if mensaje == "Modo Auto" else "manual"
    await enviar_comando_mqtt("modo", payload)
    await update.message.reply_text(f"Comando enviado: Cambiando a {mensaje}.")

async def control_rele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = update.message.text
    payload = "1" if mensaje == "Relé ON" else "0"
    await enviar_comando_mqtt("rele", payload) # Asumiendo que corrigieron la tilde en la Pico W
    await update.message.reply_text(f"Comando enviado: {mensaje}.")

async def control_destello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar_comando_mqtt("destello", "destello")
    await update.message.reply_text("¡Enviando orden de destello al LED de la placa!")

async def comando_setpoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite enviar el setpoint escribiendo: /setpoint 24.5"""
    if not context.args:
        await update.message.reply_text("Uso correcto: /setpoint <valor>")
        return
    valor = context.args[0]
    await enviar_comando_mqtt("setpoint", valor)
    await update.message.reply_text(f"Nuevo setpoint enviado: {valor}ºC")

# --- Funciones de Base de Datos (del ejemplo original) ---
async def medicion(update: Update, context):
    sql = f"SELECT timestamp, {update.message.text} FROM mediciones ORDER BY timestamp DESC LIMIT 1"
    try:
        conn = await aiomysql.connect(host=os.environ["MARIADB_SERVER"], port=3306,
                                        user=os.environ["MARIADB_USER"],
                                        password=os.environ["MARIADB_USER_PASS"],
                                        db=os.environ["MARIADB_DB"])
        async with conn.cursor() as cur:
            await cur.execute(sql)
            r = await cur.fetchone()
            if r:
                unidad = 'ºC' if update.message.text == 'temperatura' else '%'
                valor = str(r[1]).replace('.',',')
                await update.message.reply_text(f"La última {update.message.text} es de {valor} {unidad},\nregistrada a las {r[0]:%H:%M:%S %d/%m/%Y}")
            else:
                await update.message.reply_text("Aún no hay mediciones en la base de datos.")
        conn.close()
    except Exception as e:
        await update.message.reply_text("Error al consultar la base de datos.")
        logging.error(f"Error DB: {e}")

async def graficos(update: Update, context):
    # Toma la palabra "temperatura" o "humedad" de "gráfico temperatura"
    variable = update.message.text.split()[1] 
    sql = f"""SELECT timestamp, {variable}
            FROM (
                SELECT timestamp, {variable}, ROW_NUMBER() OVER (ORDER BY id) AS rn
                FROM mediciones
                WHERE timestamp >= NOW() - INTERVAL 1 DAY
                AND sensor_id LIKE 'sensor_1'
            ) AS t
            WHERE rn % 2 = 0
            ORDER BY timestamp;"""
    try:
        conn = await aiomysql.connect(host=os.environ["MARIADB_SERVER"], port=3306,
                                        user=os.environ["MARIADB_USER"],
                                        password=os.environ["MARIADB_USER_PASS"],
                                        db=os.environ["MARIADB_DB"])
        async with conn.cursor() as cur:
            await cur.execute(sql)
            filas = await cur.fetchall()

            if not filas:
                await update.message.reply_text("No hay datos suficientes para el gráfico.")
                return

            fig, ax = plt.subplots(figsize=(7, 4))
            fecha, var = zip(*filas)
            ax.plot(fecha, var)
            ax.grid(True, which='both')
            ax.set_title(update.message.text.capitalize(), fontsize=14, verticalalignment='bottom')
            ax.set_xlabel('Fecha')
            ax.set_ylabel('Unidad')

            buffer = BytesIO()
            fig.tight_layout()
            fig.savefig(buffer, format='png')
            plt.close()
            buffer.seek(0)
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=buffer)
            buffer.close()
        conn.close()
    except Exception as e:
        await update.message.reply_text("Error al generar el gráfico.")
        logging.error(f"Error Gráfico: {e}")

def main():
    application = Application.builder().token(token).build()
    
    # Comandos básicos
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('acercade', acercade))
    application.add_handler(CommandHandler('setpoint', comando_setpoint))
    
    # Expresiones regulares para los botones de texto
    application.add_handler(MessageHandler(filters.Regex("^(temperatura|humedad)$"), medicion))
    application.add_handler(MessageHandler(filters.Regex("^(gráfico temperatura|gráfico humedad)$"), graficos))
    application.add_handler(MessageHandler(filters.Regex("^(Modo Auto|Modo Manual)$"), control_modo))
    application.add_handler(MessageHandler(filters.Regex("^(Relé ON|Relé OFF)$"), control_rele))
    application.add_handler(MessageHandler(filters.Regex("^(Destello)$"), control_destello))
    
    application.run_polling()

if __name__ == '__main__':
    main()