import os
import logging
import pytz
import requests
from deta import Deta
from datetime import datetime
from io import BytesIO
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from utilidades import *
from telegram import Bot
import numpy as np
import matplotlib.pyplot as plt

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

deta = Deta()
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = 'https://' + os.getenv('DETA_SPACE_APP_HOSTNAME')
PORT = int(os.getenv('PORT'))

dias_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre','dicembre']
MARKDOWN_SPECIAL_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

async def actualizar_tablas():
    bot_quiniela = Bot(BOT_TOKEN)
    F1_API_KEY = 'qPgPPRJyGCIPxFT3el4MF7thXHyJCzAP'
    urlevent_tracker = 'https://api.formula1.com/v1/event-tracker' 
    headerapi = {'apikey':F1_API_KEY, 'locale':'en'}
    urllivetiming = 'https://livetiming.formula1.com/static/'
    dbConfiguracion = deta.AsyncBase('Configuracion')
    controles = await dbConfiguracion.get('controles')
    await dbConfiguracion.close()
    utc = pytz.utc
    hora_actual = datetime.now()
    hora_actual = hora_actual.astimezone()
    hora_actual_utc = hora_actual.astimezone(utc)

    logger.warning("Comenzo el proceso de actualizar tablas")

    dbCarreras = deta.AsyncBase('Carreras')
    carrera_no_enviada = await dbCarreras.fetch([{'Estado':'NO_ENVIADA'}])
    if carrera_no_enviada.count > 0:
        logger.warning("Imprimir tabla de resultados")
        im, texto = await crear_tabla_resultados()
        with BytesIO() as tablaresutados_imagen:    
            im.save(tablaresutados_imagen, "png")
            tablaresutados_imagen.seek(0)
            await bot_quiniela.send_photo(
                chat_id= float(controles['grupo']),
                photo=tablaresutados_imagen, 
                caption=texto
                )
        logger.warning("Imprimir tabla de resultados carrera")
        im, carrera = await crear_tabla_puntos(carrera_no_enviada.items[0])
        texto = 'Resultados de la carrera: ' + carrera
        with BytesIO() as tabla_puntos_imagen:    
            im.save(tabla_puntos_imagen, "png")
            tabla_puntos_imagen.seek(0)
            await bot_quiniela.send_photo(
                chat_id= float(controles['grupo']),
                photo=tabla_puntos_imagen, 
                caption=texto
                )
            
        logger.warning("Imprimir tabla general")
        im, total_rondas = await crear_tabla_general()
        texto = "Total de rondas incluidas: " + str(total_rondas)
        with BytesIO() as tablageneral_imagen:    
            im.save(tablageneral_imagen, "png")
            tablageneral_imagen.seek(0)
            await bot_quiniela.send_photo(
                chat_id= float(controles['grupo']),
                photo=tablageneral_imagen, 
                caption=texto
                )
        await dbCarreras.update(updates={'Estado':'ARCHIVADA'}, key=carrera_no_enviada.items[0]['key'])
    await dbCarreras.close()

    dbCarreras = deta.AsyncBase('Carreras')
    encurso_siguiente_Carrera = await dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    if(encurso_siguiente_Carrera.count == 0):
        response = requests.get(url=urlevent_tracker, headers=headerapi)
        response.encoding = 'utf-8-sig'
        response_dict = response.json()
        carrera_codigo_eventtracker = await dbCarreras.get(response_dict['fomRaceId'])
        rondas_archivadas = await dbCarreras.fetch([{'Estado':'ARCHIVADA'}, {'Estado':'CANCELADA'}])
        rondas_archivadas = rondas_archivadas.count
        if(carrera_codigo_eventtracker is None):
            es_valida = True
            carrera_codigo = response_dict['fomRaceId']
            carrera_nombre = response_dict['race']['meetingOfficialName']
            carrera_estado = response_dict['seasonContext']['state']
            carrera_empiezo = response_dict['race']['meetingStartDate']
            carrera_empiezo = carrera_empiezo.replace('Z', '+00:00')
            carrera_termino = response_dict['race']['meetingEndDate']
            carrera_termino = carrera_termino.replace('Z','+00:00')
            
            carrera_dict = {}
            carrera_dict['key'] = carrera_codigo
            carrera_dict['Nombre'] = carrera_nombre
            carrera_dict['Estado'] = carrera_estado
            carrera_dict['Empiezo'] = carrera_empiezo
            carrera_dict['Termino'] = carrera_termino
            carrera_dict['Ronda'] = str(rondas_archivadas + 1)
            for session in range(len(response_dict['seasonContext']['timetables'])):
                session_row = response_dict['seasonContext']['timetables'][session]
                if session_row['startTime'] == 'TBC':
                    es_valida = False
                carrera_dict[session_row['session']] = {
                    'estado': session_row['state'],
                    'hora_empiezo': session_row['startTime'] + session_row['gmtOffset'],
                    'hora_termino': session_row['endTime'] + session_row['gmtOffset'],
                }
            if es_valida:
                await dbCarreras.put(carrera_dict)
            # mandar mensaje de proxima
    else:
        estado_Carrera = encurso_siguiente_Carrera.items[0]['Estado']
        if(estado_Carrera == 'IDLE'):
            horaempiezo_Carrera = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['Empiezo'])
            horaempiezo_Carrera_utc = horaempiezo_Carrera.astimezone(utc)
            if(hora_actual_utc > horaempiezo_Carrera_utc):
                carrera_codigo = encurso_siguiente_Carrera.items[0]['key']
                await dbCarreras.update(updates={'Estado':'EN-CURSO'}, key=carrera_codigo)
        else:
            horario_termino = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['Termino'])
            horario_termino_utc = horario_termino.astimezone(utc)

            horario_q_sesion = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['q']['hora_empiezo'])
            horario_q_sesion_utc = horario_q_sesion.astimezone(utc)
            estado_qualy = encurso_siguiente_Carrera.items[0]['q']['estado']

            if hora_actual_utc >= horario_q_sesion_utc and estado_qualy == 'upcoming':
                #mandar tabla quinielas
                await archivar_quinielas_participante(encurso_siguiente_Carrera.items[0]['key'])
                im, carrera_nombre, graficaPilotosPos = await crear_tabla_quinielas(encurso_siguiente_Carrera.items[0], False)
                texto = "Quinielas para la carrera " + encurso_siguiente_Carrera.items[0]['Nombre']
                with BytesIO() as tablaquinielaimagen:    
                    im.save(tablaquinielaimagen, "png")
                    tablaquinielaimagen.seek(0)
                    await bot_quiniela.send_photo(
                        chat_id= float(controles['grupo']),
                        photo=tablaquinielaimagen, 
                        caption=texto
                        )
                texto = "Grafica de los pilotos para la carrera de " + carrera_nombre
                with BytesIO() as graficaPilotosPos_imagen:    
                    graficaPilotosPos.savefig(graficaPilotosPos_imagen)
                    graficaPilotosPos_imagen.seek(0)
                    await bot_quiniela.send_photo(
                        chat_id= float(controles['grupo']),
                        photo=graficaPilotosPos_imagen, 
                        caption=texto
                        )
                carrera_codigo = encurso_siguiente_Carrera.items[0]['key']
                cambiar_estado_qualy = encurso_siguiente_Carrera.items[0]['q']
                cambiar_estado_qualy['estado'] = 'EMPEZADA'
                await dbCarreras.update(updates={'q':cambiar_estado_qualy}, key=carrera_codigo)
            dbPilotos = deta.AsyncBase('Pilotos')
            revisar_Pilotos = await dbPilotos.fetch({'Carrera':encurso_siguiente_Carrera.items[0]['key']})
            if(revisar_Pilotos.count == 0):
                response = requests.get(url=urlevent_tracker, headers=headerapi)
                response.encoding = 'utf-8-sig'
                response_dict = response.json()
                if('sessionLinkSets' in response_dict):
                    sesion_carrera = response_dict['sessionLinkSets']['replayLinks'][0]['session']
                    urllivetiming = response_dict['sessionLinkSets']['replayLinks'][0]['url']
                    driverslist = 'DriverList.json'
                    response = requests.get(url=urllivetiming + driverslist)
                    response.encoding = 'utf-8-sig'
                    response_dict = response.json()
                    await dbPilotos.update(updates={'Carrera': encurso_siguiente_Carrera.items[0]['key'], 'Sesion': sesion_carrera}, key='2024')
                    for id in response_dict:
                        piloto = await dbPilotos.fetch({'Lista.' + response_dict[id]['RacingNumber'] + '.Nombre':response_dict[id]['FirstName']})
                        if(piloto.count == 0):
                            record_pilotos = await dbPilotos.get('2024')      
                            listapilotos = record_pilotos['Lista']
                            listapilotos[response_dict[id]['RacingNumber']] = {
                                'codigo':response_dict[id]['Tla'],
                                'Nombre':response_dict[id]['FirstName'],
                                'Apellido':response_dict[id]['LastName'],
                                'Equipo':response_dict[id]['TeamName'],
                                'AcumuladoPuntos':0
                            }
                            await dbPilotos.update(updates={'Lista':listapilotos}, key='2024')
            
            else:    
                horario_sesion = datetime.fromisoformat(encurso_siguiente_Carrera.items[0][revisar_Pilotos.items[0]['Sesion']]['hora_termino']) 
                horario_siguiente_sesion = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['Termino']) 
                for sesion in encurso_siguiente_Carrera.items[0]:
                    if(isinstance(encurso_siguiente_Carrera.items[0][sesion], dict)):
                        horario_sesion_comparar = datetime.fromisoformat(encurso_siguiente_Carrera.items[0][sesion]['hora_termino'])
                        if(horario_sesion_comparar > horario_sesion):
                            if(horario_sesion_comparar < horario_siguiente_sesion):
                                horario_siguiente_sesion = horario_sesion_comparar
                horario_siguiente_sesion_utc = horario_siguiente_sesion.astimezone(utc)
                if(hora_actual_utc > horario_siguiente_sesion_utc):
                    # si el horario actual es mayor al de la siguiente session                     
                    response = requests.get(url=urlevent_tracker, headers=headerapi)
                    response.encoding = 'utf-8-sig'
                    response_dict = response.json()
                    
                    if('sessionLinkSets' in response_dict):
                        index_sesion = len(response_dict['sessionLinkSets']['replayLinks']) - 1
                        sesion_carrera = response_dict['sessionLinkSets']['replayLinks'][index_sesion]['session']
                        urllivetiming = response_dict['sessionLinkSets']['replayLinks'][index_sesion]['url']
                        
                        driverslist = 'DriverList.json'
                        response = requests.get(url=urllivetiming + driverslist)
                        response.encoding = 'utf-8-sig'
                        response_dict = response.json()
                        await dbPilotos.update(updates={'Carrera': encurso_siguiente_Carrera.items[0]['key'], 'Sesion': sesion_carrera}, key='2024')
                        for id in response_dict:
                            piloto = await dbPilotos.fetch({'Lista.' + response_dict[id]['RacingNumber'] + '.Nombre':response_dict[id]['FirstName']})
                            if(piloto.count == 0):
                                record_pilotos = dbPilotos.get('2024')      
                                listapilotos = record_pilotos['Lista']
                                listapilotos[response_dict[id]['RacingNumber']] = {
                                    'codigo':response_dict[id]['Tla'],
                                    'Nombre':response_dict[id]['FirstName'],
                                    'Apellido':response_dict[id]['LastName'],
                                    'Equipo':response_dict[id]['TeamName'],
                                    'AcumuladoPuntos':0
                                }
                                await dbPilotos.update(updates={'Lista':listapilotos}, key='2024')
                        # if(sesion_carrera == 'r'):                            
            await dbPilotos.close()
            if hora_actual_utc > horario_termino_utc:
                response = requests.get(url=urlevent_tracker, headers=headerapi)
                response.encoding = 'utf-8-sig'
                response_dict = response.json()
                # contenido_nuevo += hora_actual_utc.isoformat() + ' Respuesta de la API ' + str(response_dict) + '\n'
                links = []
                if('links' in response_dict):
                    links = response_dict['links']                                
                    url_results_index = next((index for (index, d) in enumerate(links) if d["text"] == "RESULTS"), None)
                    if(not(url_results_index is None)):
                        url_results = links[url_results_index]['url']                        
                        posiciones_dict, pilotos_con_puntos = await obtener_resultados(url_results, encurso_siguiente_Carrera.items[0]['key'])
                        if pilotos_con_puntos >= 10:
                            await archivar_puntos_participante(encurso_siguiente_Carrera.items[0]['key'], posiciones_dict)
                            await dbCarreras.update(updates={'Estado':'NO_ENVIADA'}, key=encurso_siguiente_Carrera.items[0]['key'])
                            await bot_quiniela.send_message(
                                chat_id= float(controles['grupo']), 
                                text='Se guardaron los resultados de la carrera correctamente en la base de datos. En un momento mando las imagenes.'
                                )
                            logger.warning('Llego hasta el final del codigo.')
    await dbCarreras.close()
    return

async def enviar_pagos():
    dbPagos = deta.AsyncBase('Pagos')
    bot_quiniela = Bot(BOT_TOKEN)
    pagos_por_enviar = await dbPagos.fetch([{'estado':'confirmado', 'enviado':False }, {'estado':'rechazado', 'enviado':False}])
    if pagos_por_enviar.count > 0:
        for pago in pagos_por_enviar.items:
            texto = 'Este pago ya fue ' + pago['estado']+ ' por el tesorero. Puedes revisar cuantas carreras tienes pagadas con el comando de /misaldo'
            userid = pago['usuario']
            logger.info(F'este es usuario {userid}')
            await bot_quiniela.send_message(
                float(pago['usuario']), 
                text=texto,
                reply_to_message_id=pago['mensaje']
            )                
            await dbPagos.update(updates={'enviado':True}, key=pago['key'])
    await dbPagos.close()
    return

async def healthcheck_bot():
    BOT_URL_HEALTHCHECK = 'https://' + os.getenv('DETA_SPACE_APP_HOSTNAME') + '/healthcheck'
    response = requests.get(url=BOT_URL_HEALTHCHECK)
    logger.info(response.text)
    return

async def actions(req: Request):
    data = await req.json()   
    event = data['event']
    if event['id'] == 'actualizartablas':
        logger.warning("Entro a actualizar tablas")
        await actualizar_tablas()
    if event['id'] == 'revisarpagos':
        logger.warning("Entro a revisar pagos")
        await enviar_pagos()
    if event['id'] == "healthcheckBot":
        logger.warning("Entro a healthcheck del bot")
        await healthcheck_bot()
    return Response()

app = Starlette(debug=True, routes=[
    Route('/__space/v0/actions', actions, methods=["POST"]),
])