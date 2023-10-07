import os
from time import sleep
import logging
import pytz
import requests
from PIL import Image, ImageDraw, ImageFont
from prettytable import PrettyTable
from deta import Deta
from datetime import datetime
from bs4 import BeautifulSoup
from operator import itemgetter
from io import BytesIO
from telegram import __version__ as TG_VER
from collections import Counter
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
import asyncio

try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}. To view the "
        f"{TG_VER} version of this example, "
        f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
    )

# from fastapi import FastAPI, Request

from telegram import (
    Bot,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

deta = Deta()
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = 'https://' + os.getenv('DETA_SPACE_APP_HOSTNAME')
PORT = int(os.getenv('PORT'))

dbPuntosPilotos = deta.Base('PuntosPilotos')
dbCarreras = deta.Base('Carreras')
dbfavoritos = deta.Base("Favoritos")
dbHistorico = deta.Base('Historico')
dbQuiniela = deta.Base("Quiniela")
dbPilotos = deta.Base("Pilotos")
dbPagos = deta.Base('Pagos')
dbConfiguracion= deta.Base('Configuracion')

dias_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre','dicembre']
MARKDOWN_SPECIAL_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
controles = dbConfiguracion.get('controles')

def crear_tabla_puntos(obj_carrera):
    tabla_puntos_piloto = PrettyTable()
    tabla_puntos_piloto.title = obj_carrera['Nombre']
    tabla_puntos_piloto.field_names = ["Pos", "Nombre", "Equipo", "Puntos", "Intervalo"]
    tabla_puntos_piloto.sortby = "Pos"
    resultado_pilotos = dbPuntosPilotos.get(obj_carrera['key'])
    detalles_piloto = dbPilotos.get('2023')['Lista']
    for numero, resultado in resultado_pilotos['Pilotos'].items():
        tabla_puntos_piloto.add_row([resultado['posicion'], detalles_piloto[numero]['Nombre'] + ' ' + detalles_piloto[numero]['Apellido'], detalles_piloto[numero]['Equipo'], resultado['puntos'], resultado['intervalo']])
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablapilotostamano = dibujo.multiline_textbbox([0,0],str(tabla_puntos_piloto),font=letra)
    im = im.resize((tablapilotostamano[2] + 20, tablapilotostamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo.text((10, 10), str(tabla_puntos_piloto), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablapilotostamano[3] + 20), "Resultados tomados de la pagina oficial de Formula 1", font=letraabajo, fill="black")
    return im, obj_carrera['Nombre']

def crear_tabla_quinielas(carrera_en_curso, enmascarada=False):
    """Crear la tabla de las quinielas en una imagen."""
    carrera_nombre = carrera_en_curso['Nombre']
    carrera_clave = carrera_en_curso['key']
    tablaquiniela = PrettyTable()
    tablaquiniela.title = carrera_nombre
    tablaquiniela.field_names = ["Fecha/hora", "Nombre", "P1", "P2", "P3", "P4", "P5", "P6", "P7",]
    tablaquiniela.sortby = "Fecha/hora"
    datosquiniela = dbQuiniela.fetch({'Carrera':carrera_clave})
    filas = datosquiniela.items    
    datos_posiciones = {'P1': [], 'P2': [], 'P3': [], 'P4': [], 'P5': [], 'P6': [], 'P7': []}        
    for index in range(datosquiniela.count):
        fila = filas[index]
        listaquiniela = fila["Lista"].split(",")
        for pos, piloto in enumerate(listaquiniela):
            datos_posiciones['P' + str(pos + 1)].append(piloto)
        if(enmascarada):
            listaquiniela = ["XXX"] * len(listaquiniela)
        fechahoraoriginal = datetime.fromisoformat(fila["FechaHora"])
        fechahoragdl = fechahoraoriginal.astimezone(pytz.timezone('America/Mexico_City'))
        tablaquiniela.add_row([fechahoragdl.strftime('%Y-%m-%d %H:%M:%S'), fila["Nombre"], listaquiniela[0], listaquiniela[1], listaquiniela[2], listaquiniela[3], listaquiniela[4], listaquiniela[5], listaquiniela[6]])
    texto_estadisticas = ''
    if not enmascarada:
        for pos, datos in datos_posiciones.items():
            total = len(datos)
            contador = Counter(datos)
            texto_estadisticas = texto_estadisticas + pos
            contador = dict(sorted(contador.items(), key=lambda item: item[1], reverse=True))
            for piloto, repeticion in contador.items():
                texto_estadisticas = texto_estadisticas + ' ' + piloto + ' ' + str( round(100 * repeticion/total, 1) ) + '%'
            texto_estadisticas = texto_estadisticas + '\n'
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablaquinielatamano = dibujo.multiline_textbbox([0,0],str(tablaquiniela),font=letra)
    im = im.resize((tablaquinielatamano[2] + 20, tablaquinielatamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo.text((10, 10), str(tablaquiniela), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablaquinielatamano[3] + 20), "Fecha y hora con el horario de GDL", font=letraabajo, fill="black")
    return im, carrera_nombre, texto_estadisticas

def crear_tabla_general():
    tablaresultados = PrettyTable()
    tablaresultados.title = 'Tabla General Quiniela F1'
    tablaresultados.field_names = ["Nombre", "Puntos Totales", "Puntos Pilotos", "Puntos Extras", "Penalizaciones"]
    tablaresultados.sortby = "Puntos Totales"
    tablaresultados.reversesort = True

    resultados_historicos = dbHistorico.fetch()
    total_rondas = dbCarreras.fetch([{'Estado':'ARCHIVADA'}, {'Estado':'NO_ENVIADA'}]).count
    for usuario in resultados_historicos.items:
        normales = 0
        extras = 0
        penalizaciones = 0
        for carrera in usuario['Resultados']:
            normales = normales + usuario['Resultados'][carrera]['normales']
            extras = extras + usuario['Resultados'][carrera]['extras']
            penalizaciones = penalizaciones + usuario['Resultados'][carrera]['penalizaciones']
        tablaresultados.add_row([usuario["Nombre"], normales + extras + penalizaciones, normales, extras, penalizaciones])   
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablaresultados_tamano = dibujo.multiline_textbbox([0,0],str(tablaresultados),font=letra)
    im = im.resize((tablaresultados_tamano[2] + 20, tablaresultados_tamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo.text((10, 10), str(tablaresultados), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablaresultados_tamano[3] + 20), "Total de rondas incluidas: " + str(total_rondas), font=letraabajo, fill="black")
    return im, total_rondas

def crear_tabla_resultados():
    carreras = dbCarreras.fetch([{'Estado':'ARCHIVADA'}, {'Estado':'NO_ENVIADA'}])
    maximo_horario = datetime.fromisoformat('2023-01-01T00:00:00.000+00:00')
    ultima_carrera_archivada = ''
    for carrera in carreras.items:
        horario_Carrera = datetime.fromisoformat(carrera['Termino'])
        if(horario_Carrera > maximo_horario):
            maximo_horario = horario_Carrera
            ultima_carrera_archivada = carrera['key']
    
    carrera_codigo = ultima_carrera_archivada
    carrera_dict = dbCarreras.get(carrera_codigo)
    carrera_nombre = carrera_dict['Nombre']
    tablaresultados = PrettyTable()
    tablaresultados.title = carrera_nombre
    tablaresultados.field_names = ["Nombre", "Puntos Totales", "Puntos Pilotos", "Puntos Extras", "Penalizaciones"]
    datosHistoricos = dbHistorico.fetch()
    usuarios = datosHistoricos.items
    listaresultados = []

    for index in range(datosHistoricos.count):
        usuario = usuarios[index]
        puntos_totales = usuario['Resultados'][carrera_codigo]['normales'] + usuario['Resultados'][carrera_codigo]['extras'] + usuario['Resultados'][carrera_codigo]['penalizaciones']
        listaresultados.append([usuario["Nombre"], puntos_totales, usuario['Resultados'][carrera_codigo]['normales'], usuario['Resultados'][carrera_codigo]['extras'], usuario['Resultados'][carrera_codigo]['penalizaciones']])
    listaresultados.sort(key=itemgetter(4,1), reverse=True)

    linea = False
    ganador = ''
    puntos_ganador = 0
    texto_ganador = 'El ganador de la carrera ' + carrera_nombre + ' es: '
    for index in range(len(listaresultados)):
        resultado = listaresultados[index]
        siguiente_resultado = listaresultados[min(index + 1, len(listaresultados) - 1) ]
        if index == 0:
            ganador = resultado[0]
            puntos_ganador = resultado[1]
        else:
            if (resultado[1] == puntos_ganador and resultado[4] >= 0):
                ganador = ganador + ', ' + resultado[0]
                texto_ganador = 'Los ganadores de la carrera ' + carrera_nombre + ' son: '
        if(siguiente_resultado[4] < 0 and not linea):
            tablaresultados.add_row(resultado,  divider=True)
            linea = True
        else:
            tablaresultados.add_row(resultado)
    if puntos_ganador >= 90:
        texto_ganador = texto_ganador + ganador + '. Con un total de ' + str(puntos_ganador) + ' puntos.'
    else:
        texto_ganador = 'No hubo ganador para la carrera: ' + carrera_nombre + '. Nadie logro hacer mas de 90 puntos. El premio se acumula para la /proxima carrera.'
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablaresultados_tamano = dibujo.multiline_textbbox([0,0],str(tablaresultados),font=letra)
    im = im.resize((tablaresultados_tamano[2] + 20, tablaresultados_tamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo.text((10, 10), str(tablaresultados), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablaresultados_tamano[3] + 20), "Los que tienen penalizaciones no pueden ganar el premio, estan en la segunda seccion de la tabla", font=letraabajo, fill="black")
    return im, texto_ganador


async def actualizar_tablas():
    bot_quiniela = Bot(BOT_TOKEN)
    F1_API_KEY = 'qPgPPRJyGCIPxFT3el4MF7thXHyJCzAP'
    urlevent_tracker = 'https://api.formula1.com/v1/event-tracker' 
    headerapi = {'apikey':F1_API_KEY, 'locale':'en'}
    urllivetiming = 'https://livetiming.formula1.com/static/'
    controles = dbConfiguracion.get('controles')
    
    utc = pytz.utc
    hora_actual = datetime.now()
    hora_actual = hora_actual.astimezone()
    hora_actual_utc = hora_actual.astimezone(utc)

    logger.warning("Comenzo el proceso de actualizar tablas")

    carrera_no_enviada = dbCarreras.fetch([{'Estado':'NO_ENVIADA'}])
    if carrera_no_enviada.count > 0:
        logger.warning("Imprimir tabla de resultados")
        im, texto = crear_tabla_resultados()
        with BytesIO() as tablaresutados_imagen:    
            im.save(tablaresutados_imagen, "png")
            tablaresutados_imagen.seek(0)
            await bot_quiniela.send_photo(
                chat_id= float(controles['grupo']),
                photo=tablaresutados_imagen, 
                caption=texto
                )
        logger.warning("Imprimir tabla de resultados carrera")
        im, carrera = crear_tabla_puntos(carrera_no_enviada.items[0])
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
        im, total_rondas = crear_tabla_general()
        texto = "Total de rondas incluidas: " + str(total_rondas)
        with BytesIO() as tablageneral_imagen:    
            im.save(tablageneral_imagen, "png")
            tablageneral_imagen.seek(0)
            await bot_quiniela.send_photo(
                chat_id= float(controles['grupo']),
                photo=tablageneral_imagen, 
                caption=texto
                )
        dbCarreras.update(updates={'Estado':'ARCHIVADA'}, key=carrera_no_enviada.items[0]['key'])
        
    encurso_siguiente_Carrera = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    if(encurso_siguiente_Carrera.count == 0):
        response = requests.get(url=urlevent_tracker, headers=headerapi)
        response.encoding = 'utf-8-sig'
        response_dict = response.json()
        carrera_codigo_eventtracker = dbCarreras.get(response_dict['fomRaceId'])
        rondas_archivadas = dbCarreras.fetch([{'Estado':'ARCHIVADA'}, {'Estado':'CANCELADA'}]).count
        if(carrera_codigo_eventtracker is None):
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
                carrera_dict[session_row['session']] = {
                    'estado': session_row['state'],
                    'hora_empiezo': session_row['startTime'] + session_row['gmtOffset'],
                    'hora_termino': session_row['endTime'] + session_row['gmtOffset'],
                }
            dbCarreras.put(carrera_dict)
    else:
        estado_Carrera = encurso_siguiente_Carrera.items[0]['Estado']
        if(estado_Carrera == 'IDLE'):
            horaempiezo_Carrera = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['Empiezo'])
            horaempiezo_Carrera_utc = horaempiezo_Carrera.astimezone(utc)
            if(hora_actual_utc > horaempiezo_Carrera_utc):
                carrera_codigo = encurso_siguiente_Carrera.items[0]['key']
                dbCarreras.update(updates={'Estado':'EN-CURSO'}, key=carrera_codigo)
        else:
            horario_termino = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['Termino'])
            horario_termino_utc = horario_termino.astimezone(utc)

            horario_q_sesion = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['q']['hora_empiezo'])
            horario_q_sesion_utc = horario_q_sesion.astimezone(utc)
            estado_qualy = encurso_siguiente_Carrera.items[0]['q']['estado']

            if hora_actual_utc >= horario_q_sesion_utc and estado_qualy == 'upcoming':
                #mandar tabla quinielas
                im, carrera_nombre, texto_estadisticas = crear_tabla_quinielas(encurso_siguiente_Carrera.items[0], False)
                texto = "Quinielas para la carrera " + encurso_siguiente_Carrera.items[0]['Nombre']
                with BytesIO() as tablaquinielaimagen:    
                    im.save(tablaquinielaimagen, "png")
                    tablaquinielaimagen.seek(0)
                    await bot_quiniela.send_photo(
                        chat_id= float(controles['grupo']),
                        photo=tablaquinielaimagen, 
                        caption=texto + '\n' + texto_estadisticas
                        )
                carrera_codigo = encurso_siguiente_Carrera.items[0]['key']
                cambiar_estado_qualy = encurso_siguiente_Carrera.items[0]['q']
                cambiar_estado_qualy['estado'] = 'EMPEZADA'
                dbCarreras.update(updates={'q':cambiar_estado_qualy}, key=carrera_codigo)
            revisar_Pilotos = dbPilotos.fetch({'Carrera':encurso_siguiente_Carrera.items[0]['key']})
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
                    dbPilotos.update(updates={'Carrera': encurso_siguiente_Carrera.items[0]['key'], 'Sesion': sesion_carrera}, key='2023')
                    for id in response_dict:
                        piloto = dbPilotos.fetch({'Lista.' + response_dict[id]['RacingNumber'] + '.Nombre':response_dict[id]['FirstName']})
                        if(piloto.count == 0):
                            record_pilotos = dbPilotos.get('2023')      
                            listapilotos = record_pilotos['Lista']
                            listapilotos[response_dict[id]['RacingNumber']] = {
                                'codigo':response_dict[id]['Tla'],
                                'Nombre':response_dict[id]['FirstName'],
                                'Apellido':response_dict[id]['LastName'],
                                'Equipo':response_dict[id]['TeamName'],
                                'AcumuladoPuntos':0
                            }
                            dbPilotos.update(updates={'Lista':listapilotos}, key='2023')
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
                        dbPilotos.update(updates={'Carrera': encurso_siguiente_Carrera.items[0]['key'], 'Sesion': sesion_carrera}, key='2023')
                        for id in response_dict:
                            piloto = dbPilotos.fetch({'Lista.' + response_dict[id]['RacingNumber'] + '.Nombre':response_dict[id]['FirstName']})
                            if(piloto.count == 0):
                                record_pilotos = dbPilotos.get('2023')      
                                listapilotos = record_pilotos['Lista']
                                listapilotos[response_dict[id]['RacingNumber']] = {
                                    'codigo':response_dict[id]['Tla'],
                                    'Nombre':response_dict[id]['FirstName'],
                                    'Apellido':response_dict[id]['LastName'],
                                    'Equipo':response_dict[id]['TeamName'],
                                    'AcumuladoPuntos':0
                                }
                                dbPilotos.update(updates={'Lista':listapilotos}, key='2023')
                        # if(sesion_carrera == 'r'):                            
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
                        soup = BeautifulSoup(requests.get(url_results).text)
                        table = soup.find('table')
                        # header = []
                        rows = []
                        for i, row in enumerate(table.find_all('tr')):
                            if i == 0:
                                header = [el.text.strip() for el in row.find_all('th')]
                            else:
                                rows.append([el.text.strip() for el in row.find_all('td')])
                        posiciones_dict = {}
                        for row in rows:
                            if(row[1].isnumeric()):
                                posicion = int(row[1])
                                if(posicion < 11):
                                    posiciones_dict[row[2]] = {
                                        'posicion': posicion, 
                                        'intervalo': row[6],
                                        'puntos': int(row[7])
                                        }
                        datosquiniela = dbQuiniela.fetch()
                        quinielas = datosquiniela.items
                        dbPuntosPilotos.put({'key': encurso_siguiente_Carrera.items[0]['key'], 'Pilotos':posiciones_dict})
                        for i_quiniela in range(len(quinielas)):
                            quiniela = quinielas[i_quiniela]
                            historico = dbHistorico.get(quiniela['key'])
                            if historico is None:
                                dbHistorico.put({
                                    'key': quiniela['key'],
                                    'Nombre': quiniela['Nombre'],
                                    'Quinielas': {},
                                    'Resultados': {}, 
                                })
                                historico = dbHistorico.get(quiniela['key'])
                            historico_quinielas = historico['Quinielas']
                            historico_quinielas[encurso_siguiente_Carrera.items[0]['key']] = quiniela
                            historico_resultados = historico['Resultados']
                            listaquiniela = quiniela['Lista'].split(',')
                            if quiniela['Carrera'] != encurso_siguiente_Carrera.items[0]['key']:
                                resultados = {'normales':0, 'extras':0, 'penalizaciones':-5}
                            else:
                                resultados = {'normales':0, 'extras':0, 'penalizaciones':0}
                            pagosusuarios = dbPagos.fetch([{'usuario':quiniela['key'], 'estado':'guardado'},{'usuario':quiniela['key'], 'estado':'confirmado'} ])
                            rondas_pagadas = 0
                            rondas_confirmadas = 0
                            for pagousuario in pagosusuarios.items:
                                # rondas_pagadas = int(pagousuario['carreras']) + rondas_pagadas
                                # if pagousuario['estado'] == 'confirmado':
                                #     rondas_confirmadas = int(pagousuario['carreras']) + rondas_confirmadas
                                if str(pagousuario['carreras']) == 'Todas':
                                    rondas_pagadas = int(controles['rondas'])
                                else:
                                    rondas_pagadas = int(pagousuario['carreras']) + rondas_pagadas
                                if pagousuario['estado'] == 'confirmado':
                                    if pagousuario['carreras'] == 'Todas':
                                        rondas_confirmadas = int(controles['rondas'])
                                    else:
                                        rondas_confirmadas = int(pagousuario['carreras']) + rondas_confirmadas
                            logger.info('valores: ' + quiniela['key'] + str(rondas_pagadas))
                            if rondas_pagadas < int(encurso_siguiente_Carrera.items[0]['Ronda']):
                                resultados['penalizaciones'] = resultados['penalizaciones'] - 5
                            # se termino revisar pagos
                            for i_lista in range(len(listaquiniela)):
                                piloto = listaquiniela[i_lista]
                                piloto_fetch = dbPilotos.get('2023')
                                numero_piloto = ''
                                for n in piloto_fetch['Lista']:
                                    if(piloto == piloto_fetch['Lista'][n]['codigo']):
                                        numero_piloto = n
                                if( numero_piloto in posiciones_dict):
                                    resultados['normales'] = resultados['normales'] + posiciones_dict[numero_piloto]['puntos']
                                    if(i_lista + 1 == posiciones_dict[numero_piloto]['posicion']):
                                        resultados['extras'] = resultados['extras'] + 2
                            historico_resultados[encurso_siguiente_Carrera.items[0]['key']] = resultados
                            dbHistorico.update(updates={ 
                                'Quinielas': historico_quinielas, 
                                'Resultados': historico_resultados, 
                                }, key=quiniela['key'])
                        
                        dbCarreras.update(updates={'Estado':'NO_ENVIADA'}, key=encurso_siguiente_Carrera.items[0]['key'])
                        await bot_quiniela.send_message(
                            chat_id= float(controles['grupo']), 
                            text='Se guardaron los resultados de la carrera correctamente en la base de datos. En un momento mando las imagenes.'
                            )
                        logger.warning('Llego hasta el final del codigo')
    return

async def enviar_pagos():
    bot_quiniela = Bot(BOT_TOKEN)
    pagos_por_enviar = dbPagos.fetch([{'estado':'confirmado', 'enviado':False }, {'estado':'rechazado', 'enviado':False}])
    if pagos_por_enviar.count > 0:
        for pago in pagos_por_enviar.items:
            texto = 'Este pago ya fue ' + pago['estado']+ ' por el tesorero.'
            userid = pago['usuario']
            logger.info(F'este es usuario {userid}')
            await bot_quiniela.send_message(
                float(pago['usuario']), 
                text=texto,
                reply_to_message_id=pago['mensaje']
            )                
            dbPagos.update(updates={'enviado':True}, key=pago['key'])
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
        logger.info("Entro a actualizar tablas")
        await actualizar_tablas()
    if event['id'] == 'revisarpagos':
        logger.info("Entro a revisar pagos")
        await enviar_pagos()
    if event['id'] == "healthcheckBot":
        logger.info("Entro a healthcheck del bot")
        await healthcheck_bot()
    return Response()

app = Starlette(debug=True, routes=[
    Route('/__space/v0/actions', actions, methods=["POST"]),
])