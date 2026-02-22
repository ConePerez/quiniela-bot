from telegram import Update
from telegram.ext import (
    ContextTypes,
)
from base import INFORMACION_BOTS
from utilidades import archivar_quinielas_participante, archivar_puntos_participante, crear_tabla_quinielas, crear_tabla_puntos, obtener_resultados, crear_tabla_resultados, crear_tabla_general
from io import BytesIO
from config import logger
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from environment import DEBUG_MODE, F1_API_KEY
from sqlalchemy import or_

async def enviar_pagos(context: ContextTypes.DEFAULT_TYPE):
    pagos_por_enviar = None
    Pago = INFORMACION_BOTS[context.bot_data['nombre']]['tablas']['pago']
    Usuario = INFORMACION_BOTS[context.bot_data['nombre']]['tablas']['usuario']
    with INFORMACION_BOTS[context.bot_data['nombre']]['sesion']() as sesion:
        pagos_por_enviar = sesion.query(Pago).filter((Pago.estado == 'confirmado') & (Pago.enviado == False)).all()
        if len(pagos_por_enviar) > 0:
            for pago in pagos_por_enviar:
                usuario = sesion.get(Usuario, pago.usuario_id)
                texto = 'Este pago ya fue ' + pago.estado + ' por el tesorero. Puedes revisar cuantas carreras tienes pagadas con el comando de /misaldo'
                await context.bot.send_message(
                    usuario.telegram_id, 
                    text=texto,
                    reply_to_message_id=pago.mensaje
                )                
                pago.enviado = True
            sesion.commit()
    return

async def mandar_quinielas(context: ContextTypes.DEFAULT_TYPE):
    Carrera = INFORMACION_BOTS[context.bot_data['nombre']]['tablas']['carrera']
    TELEGRAM_GROUP = INFORMACION_BOTS[context.bot_data['nombre']]['telegramgroup']

    with INFORMACION_BOTS[context.bot_data['nombre']]['sesion']() as sesion:
        encurso_siguiente_Carrera = sesion.query(Carrera).filter((Carrera.estado == 'IDLE') | (Carrera.estado == 'EN-CURSO')).first()
        archivar_quinielas_participante(sesion=sesion, carrera=encurso_siguiente_Carrera, bot_nombre=context.bot_data['nombre'])
        im, graficaPilotos = crear_tabla_quinielas(encurso_siguiente_Carrera, False)
        texto = "Quinielas para la carrera" + encurso_siguiente_Carrera.nombre
        with BytesIO() as tablaquinielaimagen:
            im.save(tablaquinielaimagen, "png")
            tablaquinielaimagen.seek(0)
            await context.bot.send_photo(
                chat_id= TELEGRAM_GROUP,
                photo=tablaquinielaimagen,
                caption =texto,
            )
        texto = 'Grafica de los pilotos para la carrera de ' + encurso_siguiente_Carrera.nombre
        with BytesIO() as graficaPilotos_imagen:
            graficaPilotos.savefig(graficaPilotos_imagen)
            graficaPilotos_imagen.seek(0)
            await context.bot.send_photo(
                chat_id=TELEGRAM_GROUP,
                photo=graficaPilotos_imagen,
                caption=texto
            )

async def mandar_resultados(context: ContextTypes.DEFAULT_TYPE):
    Carrera = INFORMACION_BOTS[context.bot_data['nombre']]['tablas']['carrera']
    TELEGRAM_GROUP = INFORMACION_BOTS[context.bot_data['nombre']]['telegramgroup']
    fila_trabajos = INFORMACION_BOTS[context.bot_data['nombre']]['filatrabajos']

    with INFORMACION_BOTS[context.bot_data['nombre']]['sesion']() as sesion:
        with requests.Session() as s:
            urlevent_tracker = 'https://api.formula1.com/v1/event-tracker' 
            headerapi = {'apikey':F1_API_KEY, 'locale':'en'}
            encurso_siguiente_Carrera = sesion.query(Carrera).filter((Carrera.estado == 'IDLE') | (Carrera.estado == 'EN-CURSO')).first()
            response = s.get(url=urlevent_tracker, headers=headerapi)
            response.encoding = 'utf-8-sig'
            response_dict = response.json()
            links = []
            if('links' in response_dict):
                links = response_dict['links']
                if DEBUG_MODE == 'ON':
                    links = [{"text":"RESULTS", "url":"https://www.formula1.com/en/results/2025/races/1254/australia/race-result"}]                                
                url_results_index = next((index for (index, d) in enumerate(links) if d["text"] == "RESULTS"), None)
                logger.info(url_results_index)
                if(not(url_results_index is None)):
                    url_results = links[url_results_index]['url'] 
                    response = s.get(url_results)
                    if DEBUG_MODE == 'ON':
                        response = s.get("https://www.formula1.com/en/results/2025/races/1254/australia/race-result")
                    soup = BeautifulSoup(response.content, features="html.parser")                     
                    posiciones_dict, pilotos_con_puntos = obtener_resultados(sesion, encurso_siguiente_Carrera, soup, context.bot_data['nombre'])
                    if pilotos_con_puntos >= 10:
                        archivar_puntos_participante(sesion, encurso_siguiente_Carrera, posiciones_dict, context.bot_data['nombre'])
                        encurso_siguiente_Carrera.estado = 'ARCHIVADA'
                        sesion.flush()
                        im, texto = crear_tabla_resultados(sesion, encurso_siguiente_Carrera, context.bot_data['nombre'])
                        with BytesIO() as tablaresutados_imagen:    
                            im.save(tablaresutados_imagen, "png")
                            tablaresutados_imagen.seek(0)
                            await context.bot.send_photo(
                                chat_id= TELEGRAM_GROUP,
                                photo=tablaresutados_imagen, 
                                caption=texto
                                )
                        im = crear_tabla_puntos(sesion, encurso_siguiente_Carrera)
                        texto = 'Resultados de la carrera: ' + encurso_siguiente_Carrera.nombre
                        with BytesIO() as tabla_puntos_imagen:    
                            im.save(tabla_puntos_imagen, "png")
                            tabla_puntos_imagen.seek(0)
                            await context.bot.send_photo(
                                chat_id= TELEGRAM_GROUP,
                                photo=tabla_puntos_imagen, 
                                caption=texto
                                )
                        im, total_rondas = crear_tabla_general(sesion=sesion, bot_nombre=context.bot_data['nombre'])
                        texto = "Total de rondas incluidas: " + str(total_rondas)
                        with BytesIO() as tablageneral_imagen:    
                            im.save(tablageneral_imagen, "png")
                            tablageneral_imagen.seek(0)
                            await context.bot.send_photo(
                                chat_id= TELEGRAM_GROUP,
                                photo=tablageneral_imagen, 
                                caption=texto
                                )
                        trabajo_qualy = fila_trabajos.get_jobs_by_name("mandar_quinielas")
                        if trabajo_qualy:
                            for trabajo in trabajo_qualy:
                                trabajo.schedule_removal()
                        trabajo_carrera = fila_trabajos.get_jobs_by_name("mandar_resultados")
                        if trabajo_carrera:
                            for trabajo in trabajo_carrera:
                                trabajo.schedule_removal()
                    sesion.commit()

async def agregar_nueva_carrera(context: ContextTypes.DEFAULT_TYPE):
    Carrera = INFORMACION_BOTS[context.bot_data['nombre']]['tablas']['carrera']
    SesionCarrera = INFORMACION_BOTS[context.bot_data['nombre']]['tablas']['sesioncarrera']
    fila_trabajos = INFORMACION_BOTS[context.bot_data['nombre']]['filatrabajos']

    with INFORMACION_BOTS[context.bot_data['nombre']]['sesion']() as sesion:
        urlevent_tracker = 'https://api.formula1.com/v1/event-tracker' 
        headerapi = {'apikey':F1_API_KEY, 'locale':'en'}
        urllivetiming = 'https://livetiming.formula1.com/static/'
        hora_actual = datetime.now()
        hora_actual = hora_actual.astimezone()
        encurso_siguiente_Carrera = None
        encurso_siguiente_Carrera = sesion.query(Carrera).filter((Carrera.estado == 'IDLE') | (Carrera.estado == 'EN-CURSO')).first()
        if not encurso_siguiente_Carrera:
            response = requests.get(url=urlevent_tracker, headers=headerapi)
            response.encoding = 'utf-8-sig'
            response_dict = response.json()
            carrera_codigo_eventtracker = sesion.query(Carrera).filter(Carrera.codigo == response_dict['fomRaceId']).first()
            rondas_archivadas = len(sesion.query(Carrera).filter(or_(Carrera.estado == "ARCHIVADA", Carrera.estado == 'CANCELADA')).all())
            hora_qualy = None
            hora_termino_carrera = None
            if not carrera_codigo_eventtracker:
                es_valida = True
                carrera_codigo = response_dict['fomRaceId']
                carrera_nombre = response_dict['race']['meetingOfficialName']
                carrera_estado = response_dict['seasonContext']['state']
                carrera_empiezo = response_dict['race']['meetingStartDate']
                carrera_empiezo = carrera_empiezo.replace('Z', '+00:00')
                carrera_termino = response_dict['race']['meetingEndDate']
                carrera_termino = carrera_termino.replace('Z','+00:00')
                hora_termino_carrera = datetime.fromisoformat(carrera_termino)
                nueva_carrera = Carrera(codigo=carrera_codigo, nombre=carrera_nombre, hora_empiezo=carrera_empiezo, hora_termino=carrera_termino, estado=carrera_estado, url='', ronda=rondas_archivadas+1)
                sesion.add(nueva_carrera)
                sesion.flush()
                nuevas_sesiones = []
                for session in range(len(response_dict['seasonContext']['timetables'])):
                    session_row = response_dict['seasonContext']['timetables'][session]
                    if session_row['startTime'] == 'TBC':
                        es_valida = False
                    nuevas_sesiones.append( SesionCarrera(codigo=session_row['session'], carrera_id=nueva_carrera.id, estado=session_row['state'], 
                                                    hora_empiezo=session_row['startTime']+session_row['gmtOffset'], hora_termino=session_row['endTime']+session_row['gmtOffset']))
                    if session_row['session'] == 'q':
                        hora_qualy = datetime.fromisoformat(session_row['startTime']+session_row['gmtOffset'])
                if es_valida:
                    sesion.add_all(nuevas_sesiones)
                    sesion.commit()
                    orden_trabajo_qualy = fila_trabajos.run_once( callback=mandar_quinielas, when=hora_qualy, name="mandar_quinielas")
                    orden_trabajo_carrera = fila_trabajos.run_repeating(callback=mandar_resultados, interval=300, first=hora_termino_carrera, last=hora_termino_carrera + timedelta(hours=2), name="mandar_resultados")
                    logger.info('qualy: ' + str(orden_trabajo_qualy.next_t))
                    logger.info('carrera: ' + str(orden_trabajo_carrera.next_t))
                    logger.info('carrera fin: ' + str(hora_termino_carrera + timedelta(hours=2)))

async def agregar_qualy_carrera(context: ContextTypes.DEFAULT_TYPE):
    Carrera = INFORMACION_BOTS[context.bot_data['nombre']]['tablas']['carrera']
    fila_trabajos = INFORMACION_BOTS[context.bot_data['nombre']]['filatrabajos']
    with INFORMACION_BOTS[context.bot_data['nombre']]['sesion']() as sesion:
        encurso_siguiente_Carrera = sesion.query(Carrera).filter((Carrera.estado == 'IDLE') | (Carrera.estado == 'EN-CURSO')).first()
        if encurso_siguiente_Carrera:
            sesion_qualy = None
            for sesion_carrera in encurso_siguiente_Carrera.sesioncarreras:
                if sesion_carrera.codigo == 'q':
                    sesion_qualy = sesion_carrera
            trabajos = fila_trabajos.jobs()
            if len(trabajos) <= 2:
                orden_trabajo_qualy = fila_trabajos.run_once( callback=mandar_quinielas, when=sesion_qualy.hora_empiezo, name="mandar_quinielas")
                orden_trabajo_carrera = fila_trabajos.run_repeating(callback=mandar_resultados, interval=300, first=encurso_siguiente_Carrera.hora_termino, last=encurso_siguiente_Carrera.hora_termino + timedelta(hours=2), name="mandar_resultados")
                logger.info('qualy: ' + str(orden_trabajo_qualy.next_t))
                logger.info('carrera: ' + str(orden_trabajo_carrera.next_t))