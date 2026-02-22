from contextlib import asynccontextmanager
from http import HTTPStatus
from fastapi import FastAPI, Request, Response
from bot import iniciar_todos_bots, set_hooks, apagar_todos_bots, procesar_actualizacion_bot
from environment import DEBUG_MODE, WEBHOOK_URL, WEBHOOK_URL_TEST
from base import INFORMACION_BOTS
from models_db_1 import Base as Base_db_1
from models_db_2 import Base as Base_db_2
from config import logger
from utilidades import actualizar_basedatos_pilotos

Base_db_1.metadata.create_all(INFORMACION_BOTS['Bot1']['engine'])
Base_db_2.metadata.create_all(INFORMACION_BOTS['Bot2']['engine'])

@asynccontextmanager
async def lifespan(_: FastAPI):
    await iniciar_todos_bots()
    if DEBUG_MODE == "ON":
        await set_hooks(WEBHOOK_URL_TEST)
        logger.info(f'url base en modo test {WEBHOOK_URL_TEST}')
    else:
        await set_hooks(WEBHOOK_URL)
    yield
    await apagar_todos_bots()

# Initialize FastAPI app (similar to Flask)
app = FastAPI(lifespan=lifespan)

@app.post("/webhook/{bot_name}")
async def manejador_webhook(bot_name:str, request: Request):
    try:
        data = await request.json()
        await procesar_actualizacion_bot(bot_name, data)
        return {"status":"ok"}
    except ValueError as e:
        return {"error": str(e)}

@app.get("/test")
async def test():
    return "esto es una prueba"

@app.get("/actualizarpilotos")
async def actualizarpilotos():
    for nombre, mi_bot in INFORMACION_BOTS.items():
        actualizar_basedatos_pilotos(mi_bot['sesion'], mi_bot['tablas']['piloto'])
    return "se actualizaron las base de datos de todos los bots"
    