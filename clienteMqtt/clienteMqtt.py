import asyncio, ssl, certifi, logging, os
import aiomqtt

logging.basicConfig(format='%(asctime)s - cliente mqtt - [%(funcName)s] -%(levelname)s:%(message)s', level=logging.INFO, datefmt='%d/%m/%Y %H:%M:%S %z')

async def incrementar_contador(estado: dict):
    while True:
        await asyncio.sleep(3)
        estado["contador"] += 1

async def publicar_contador(client: aiomqtt.Client, topico_para_publicar: str, estado: dict):
    while True:
        await asyncio.sleep(5)
        await client.publish(topico_para_publicar, payload=str(estado["contador"]))
        logging.info(f"Valor Publicado:{estado['contador']} en el tópico: {topico_para_publicar}")


async def leer_topico1 (mensaje):
    logging.info(f"Mensaje recibido en el tópico 1: {mensaje.payload.decode('utf-8')}")

async def leer_topico2 (mensaje):
    logging.info(f"Mensaje recibido en el tópico 2: {mensaje.payload.decode('utf-8')}")

async def main():
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    tls_context.load_default_certs()

    estado_app = {"contador": 0}

    async with aiomqtt.Client(
        os.environ['SERVIDOR'],
        port=8883,
        tls_context=tls_context,
    ) as client:
        await client.subscribe(os.environ['TOPICO1'])
        await client.subscribe(os.environ['TOPICO2'])
        asyncio.create_task(incrementar_contador(estado_app))
        asyncio.create_task(publicar_contador(client, os.environ['TOPICO_PARA_PUBLICAR'], estado_app))
        async for message in client.messages:
            if str(message.topic) == os.environ['TOPICO1']:
                await leer_topico1(message)
            elif str(message.topic) == os.environ['TOPICO2']:
                await leer_topico2(message)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Aplicación interrumpida por el usuario")