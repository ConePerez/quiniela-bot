import os
from io import BytesIO
import logging
import json
import asyncio
import base64
import math
from html import escape
from uuid import uuid4
from PIL import Image, ImageDraw, ImageFont
from prettytable import PrettyTable
from deta import Deta
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pytz
import requests
from dataclasses import dataclass
from operator import itemgetter


deta = Deta()

from telegram import __version__ as TG_VER

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

from fastapi import FastAPI, Request

from telegram import (
    KeyboardButton,
    KeyboardButtonPollType,
    Poll,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update,
    BotCommand,
    WebAppInfo,
    InlineQueryResultArticle, 
    InputTextMessageContent,
    BotCommandScopeAllGroupChats,
    BotCommandScopeChat,
    BotCommandScopeAllPrivateChats,
    Bot,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PollAnswerHandler,
    ConversationHandler,
    PollHandler,
    filters,
    InlineQueryHandler,
    CallbackQueryHandler,
    CallbackContext,
    ExtBot,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
chandles = logging.StreamHandler()
chandles.setLevel(logging.INFO)
logger.addHandler(chandles)

BotToken = os.getenv("BOT_TOKEN")
bot_hostname = os.getenv("DETA_SPACE_APP_HOSTNAME")
QUINIELA, FAVORITOS, CONFIRMAR_PENALIZACION, SUBIRCOMPROBANTE, GUARDARCOMPROBANTE, VALIDARPAGO, SIGUIENTEPAGO, FINPAGOS, MENU_AYUDA, ELEGIR_PILOTOS, CONFIRMAR_PILOTOS = range(11)
REGLAS = 'reglas'
AYUDA = 'ayuda'
ultima_carrera = ''
siguiente_carrera = ''
dbPuntosPilotos = deta.Base('PuntosPilotos')
dbCarreras = deta.Base('Carreras')
dbfavoritos = deta.Base("Favoritos")
dbHistorico = deta.Base('Historico')
dbquiniela = deta.Base("Quiniela")
dbPilotos = deta.Base("Pilotos")
dbPagos = deta.Base('Pagos')
dbConfiguracion= deta.Base('Configuracion')
documentos = deta.Drive('Documentos')
# documentos.put('hello.txt', 'Hello world')
dias_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre','dicembre']
MARKDOWN_SPECIAL_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

def crear_tabla_quinielas(carrera_en_curso, enmascarada=False):
    carrera_nombre = carrera_en_curso['Nombre']
    carrera_ronda = carrera_en_curso['Ronda']
    carrera_clave = carrera_en_curso['key']
    tablaquiniela = PrettyTable()
    tablaquiniela.title = carrera_nombre
    tablaquiniela.field_names = ["Fecha/hora", "Nombre", "P1", "P2", "P3", "P4", "P5", "P6", "P7",]
    tablaquiniela.sortby = "Fecha/hora"
    dbquiniela = deta.Base("Quiniela")
    datosquiniela = dbquiniela.fetch({'Carrera':carrera_clave})
    filas = datosquiniela.items            
    for index in range(datosquiniela.count):
    # for index in range(3):
        fila = filas[index]
        listaquiniela = fila["Lista"].split(",")
        if(enmascarada):
            listaquiniela = ["XXX"] * len(listaquiniela)
        fechahoraoriginal = datetime.fromisoformat(fila["FechaHora"])
        fechahoragdl = fechahoraoriginal.astimezone(pytz.timezone('America/Mexico_City'))
        tablaquiniela.add_row([fechahoragdl.strftime('%Y-%m-%d %H:%M:%S'), fila["Nombre"], listaquiniela[0], listaquiniela[1], listaquiniela[2], listaquiniela[3], listaquiniela[4], listaquiniela[5], listaquiniela[6]])
        # tablaquiniela.add_row(["2023-03-02T23:34:00-06:00", filas, "PER", "SAI", "VER", "ALO", "MAG", "VER", "HAM",])    
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablaquinielatamano = dibujo.multiline_textbbox([0,0],str(tablaquiniela),font=letra)
    im = im.resize((tablaquinielatamano[2] + 20, tablaquinielatamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo.text((10, 10), str(tablaquiniela), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablaquinielatamano[3] + 20), "Fecha y hora con el horario de GDL", font=letraabajo, fill="black")
    return im, carrera_ronda

def crear_tabla_general():
    tablaresultados = PrettyTable()
    tablaresultados.title = 'Tabla General Quiniela F1'
    tablaresultados.field_names = ["Nombre", "Puntos Totales", "Puntos Pilotos", "Puntos Extras", "Penalizaciones"]
    tablaresultados.sortby = "Puntos Totales"
    tablaresultados.reversesort = True

    resultados_historicos = dbHistorico.fetch()
    total_rondas = dbCarreras.fetch({'Estado':'ARCHIVADA'}).count
    for usuario in resultados_historicos.items:
        normales = 0
        extras = 0
        penalizaciones = 0
        print(usuario['key'])
        for carrera in usuario['Resultados']:
            print(usuario['Resultados'][carrera])
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
    carreras = dbCarreras.fetch({'Estado':'ARCHIVADA'})
    maximo_horario = datetime.fromisoformat('2023-01-01T00:00:00.000+00:00')
    ultima_carrera_archivada = ''
    for carrera in carreras.items:
        print(carrera['key'], carrera['Termino'])
        horario_Carrera = datetime.fromisoformat(carrera['Termino'])
        if(horario_Carrera > maximo_horario):
            maximo_horario = horario_Carrera
            ultima_carrera_archivada = carrera['key']
    
    carrera_codigo = ultima_carrera_archivada
    carrera_dict = dbCarreras.get(carrera_codigo)
    carrera_nombre = carrera_dict['Nombre']
    carrera_ronda = carrera_dict['Ronda']

    tablaresultados = PrettyTable()
    tablaresultados.title = carrera_nombre
    tablaresultados.field_names = ["Nombre", "Puntos Totales", "Puntos Pilotos", "Puntos Extras", "Penalizaciones"]
    # tablaresultados.sortby = "Puntos Totales"
    # tablaresultados.reversesort = True
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
    # print(tablaresultados.get_string())
    texto_ganador = texto_ganador + ganador + '. Con un total de ' + str(puntos_ganador) + ' puntos.'
    # for index in range(datosHistoricos.count):
    #     usuario = usuarios[index]
    #     puntos_totales = usuario['Resultados'][carrera_codigo]['normales'] + usuario['Resultados'][carrera_codigo]['extras'] + usuario['Resultados'][carrera_codigo]['penalizaciones']
    #     tablaresultados.add_row([usuario["Nombre"], puntos_totales, usuario['Resultados'][carrera_codigo]['normales'], usuario['Resultados'][carrera_codigo]['extras'], usuario['Resultados'][carrera_codigo]['penalizaciones']])
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablaresultados_tamano = dibujo.multiline_textbbox([0,0],str(tablaresultados),font=letra)
    im = im.resize((tablaresultados_tamano[2] + 20, tablaresultados_tamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo.text((10, 10), str(tablaresultados), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablaresultados_tamano[3] + 20), "Los que tienen penalizaciones no pueden ganar el premio, estan en la segunda seccion de la tabla", font=letraabajo, fill="black")
    return im, carrera_ronda, texto_ganador

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inform user about what this bot can do"""
    print("entro start", update)
    texto =  "Bienvenido a la quiniela de F1 usa /quiniela para seleccionar a los pilotos del 1-7, /mipago para subir un comprobante de pago y /help para ver la ayuda. En cualquier momento puedes usar /cancelar para cancelar cualquier comando."
    await update.message.reply_text(
        texto, 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# async def general(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     """Inform user about what this bot can do"""
#     print("entro start", update)
#     await update.message.reply_text(
#         "Todavia no esta implementada", 
#         reply_markup=ReplyKeyboardRemove()
#     )
#     return ConversationHandler.END

async def pagos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display a help message"""
    carreras = dbCarreras.fetch()
    total_carreras = str(carreras.count)
    configuracion = dbConfiguracion.get('controles')
    tablapagos = PrettyTable()
    tablapagos.title = 'Tabal de pagos'
    tablapagos.field_names = ["Nombre", "Total Rondas", "Rondas Pagadas", "Rondas Confirmadas"]
    tablapagos.sortby = "Nombre"
    dbquiniela = deta.Base("Quiniela")
    datosquiniela = dbquiniela.fetch()
    for usuarioquiniela in datosquiniela.items:
        pagosusuarios = dbPagos.fetch([{'usuario':usuarioquiniela['key'], 'estado':'guardado'},{'usuario':usuarioquiniela['key'], 'estado':'confirmado'} ])
        rondas_pagadas = 0
        rondas_confirmadas = 0
        for pagousuario in pagosusuarios.items:
            rondas_pagadas = int(pagousuario['carreras']) + rondas_pagadas
            if pagousuario['estado'] == 'confirmado':
                rondas_confirmadas = int(pagousuario['carreras']) + rondas_confirmadas
            
        tablapagos.add_row([usuarioquiniela['Nombre'], configuracion['rondas'], str(rondas_pagadas), str(rondas_confirmadas)]) 
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablapagostamano = dibujo.multiline_textbbox([0,0],str(tablapagos),font=letra)
    im = im.resize((tablapagostamano[2] + 20, tablapagostamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo.text((10, 10), str(tablapagos), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablapagostamano[3] + 20), "Ronda actual: " + total_carreras, font=letraabajo, fill="black")

    with BytesIO() as tablapagos_imagen:    
        im.save(tablapagos_imagen, "png")
        tablapagos_imagen.seek(0)
        await update.message.reply_photo(tablapagos_imagen, caption='Tabla de pagos al momento, la ronda actual es: ' + total_carreras )
    
    return ConversationHandler.END

async def proxima(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display a help message"""
    proxima_Carrera = dbCarreras.fetch([{'Estado':'IDLE'},{'Estado':'EN-CURSO'}])
    if(proxima_Carrera.count == 0):
        await update.message.replay_text(
            'Todavia no se actualiza mi base de datos con la proxima carrera. Por lo general se actualiza un dia despues de que termino la ultima carrera.'
        )
        return ConversationHandler.END
    proxima_nombre = proxima_Carrera.items[0]['Nombre']
    for char in MARKDOWN_SPECIAL_CHARS:
        if char in proxima_nombre:
            proxima_nombre = proxima_nombre.replace(char, "\\" + char)
    # proxima_nombre = 'Imola'
    # respuesta = "*Carrera:* " + proxima_nombre.replace("-", "\-")
    respuesta = "*Carrera:* " + proxima_nombre
    orden_horarios = ['p1', 'p2', 'p3', 'q', 'r']
    if('s' in proxima_Carrera.items[0]):
        orden_horarios = ['p1', 'q', 'p2', 's', 'r']
    for sesion in orden_horarios:
        horario_sesion = datetime.fromisoformat(proxima_Carrera.items[0][sesion]['hora_empiezo'])
        horario_sesion = horario_sesion.astimezone(pytz.timezone('America/Mexico_City'))
        dia_semana = dias_semana[horario_sesion.weekday()]
        mes = meses[horario_sesion.month - 1] 
        hora = horario_sesion.strftime('%H:%M')
        dia_numero = horario_sesion.strftime('%d')
        respuesta = respuesta + "\n" + "*Sesion " + sesion + " horario:* " + dia_semana + ", " + dia_numero + " de " + mes + " a las " +  hora + "hrs"
    # respuesta = "*Carrera:* " + proxima_nombre.replace("'", " ")
    await update.message.reply_markdown_v2(
        respuesta,
        reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END    

# async def quiniela(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     """Starts the conversation and asks the user about their gender."""
#     carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
#     if(carrera_quiniela.count > 0):
#         if(carrera_quiniela.items[0]['Estado'] == 'EN-CURSO'):
#             horario_qualy = datetime.fromisoformat(carrera_quiniela.items[0]['q']['hora_empiezo'])
#             ahora = datetime.now()
#             ahora = ahora.astimezone()
#             if(ahora > horario_qualy):
#                 await update.message.reply_text(
#                     'Meter o modificar tu quiniela ahora causara una penalizacion, porque la calificacion ya empezo.', 
#                     reply_markup=ReplyKeyboardMarkup(
#                         [['Si', 'No']], 
#                         one_time_keyboard=True, 
#                         input_field_placeholder="¿Estas seguro de continuar?")
#                     )
#                 return CONFIRMAR_PENALIZACION
#         user = update.message.from_user
#         leerfavoritos = dbfavoritos.get(str(user.id))
#         listafavoritos = ""
#         if(leerfavoritos is None):
#             puntospilotos = dbPuntosPilotos.fetch()
#             pilotoslista = dbPilotos.get('2023')['Lista']
#             for carrera in puntospilotos.items:
#                 for piloto in carrera['Pilotos']:
#                     # print(piloto, carrer['Pilotos'][piloto]['puntos'])
#                     pilotoslista[piloto]['AcumuladoPuntos'] = pilotoslista[piloto]['AcumuladoPuntos'] + carrera['Pilotos'][piloto]['puntos']
#             pilotoslista = sorted(pilotoslista.items(), key=lambda item: item[1]['AcumuladoPuntos'], reverse=True)
#             listacodigosenorden = ''
#             for pilotonumer in pilotoslista:
#                 if(listacodigosenorden == ''):
#                     listacodigosenorden = pilotonumer[1]['codigo']
#                 else:
#                     listacodigosenorden = listacodigosenorden + ',' + pilotonumer[1]['codigo']
#             #print(pilotoslista.items())
#             print(listacodigosenorden)
#             listafavoritos = listacodigosenorden
#         else:
#             listafavoritos = leerfavoritos['Lista']
#         carrera_nombre = carrera_quiniela.items[0]['Nombre'].replace(' ', '_')
        
#         webappurl="https://" + bot_hostname + "/quiniela/?lista=" + listafavoritos + "&carrera=" + carrera_nombre
#         await update.message.reply_text(
#             "Presiona el boton para abrir la forma",
#             reply_markup=ReplyKeyboardMarkup.from_button(
#                 KeyboardButton(
#                     text="Abrir quiniela",
#                     web_app=WebAppInfo(url=webappurl),
#                 )
#             ),
#         )
#         return QUINIELA
#     else:
#         await update.message.reply_text(
#             'Todavia no hay informacion de la siguiente carrera. Por favor intenta un dia despues de la carrera',
#             reply_markup=ReplyKeyboardRemove()
#             )
#         return ConversationHandler.END 


# async def confirmar_penalizacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     respuesta = update.message.text 
#     if(respuesta == 'Si'):
#         carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
#         user = update.message.from_user
#         leerfavoritos = dbfavoritos.get(str(user.id))
#         listafavoritos = ""
#         if(leerfavoritos is None):
#             puntospilotos = dbPuntosPilotos.fetch()
#             pilotoslista = dbPilotos.get('2023')['Lista']
#             for carrera in puntospilotos.items:
#                 for piloto in carrera['Pilotos']:
#                     # print(piloto, carrer['Pilotos'][piloto]['puntos'])
#                     pilotoslista[piloto]['AcumuladoPuntos'] = pilotoslista[piloto]['AcumuladoPuntos'] + carrera['Pilotos'][piloto]['puntos']
#             pilotoslista = sorted(pilotoslista.items(), key=lambda item: item[1]['AcumuladoPuntos'], reverse=True)
#             listacodigosenorden = ''
#             for pilotonumer in pilotoslista:
#                 if(listacodigosenorden == ''):
#                     listacodigosenorden = pilotonumer[1]['codigo']
#                 else:
#                     listacodigosenorden = listacodigosenorden + ',' + pilotonumer[1]['codigo']
#             #print(pilotoslista.items())
#             print(listacodigosenorden)
#             listafavoritos = listacodigosenorden
#         else:
#             listafavoritos = leerfavoritos['Lista']
#         carrera_nombre = carrera_quiniela.items[0]['Nombre'].replace(' ', '_')
#         webappurl="https://" + bot_hostname + "/quiniela/?lista=" + listafavoritos + "&carrera=" + carrera_nombre
#         await update.message.reply_text(
#             "Presiona el boton para abrir la forma",
#             reply_markup=ReplyKeyboardMarkup.from_button(
#                 KeyboardButton(
#                     text="Abrir quiniela",
#                     web_app=WebAppInfo(url=webappurl),
#                 )
#             ),
#         )
#         return QUINIELA
#     await update.message.reply_text(
#         'Cancelado, puedes iniciar otra conversacion con el comando /start',
#         reply_markup=ReplyKeyboardRemove()
#         )
#     return ConversationHandler.END

    #  reply_keyboard = [["ALB", "ALO", "BOT", "DEV", "GAS"], ["HAM", "HUL", "LEC", "MAG", "NOR"], ["OCO", "PIA", "PER",]]
 
    #  await update.message.reply_text(
    #      "Hola! aqui seleccionaras los pilotos del primero al septiomo lugar"
    #      "\n\n"
    #      "Presiona el boton del piloto que quedara en primer lugar: ",
    #      reply_markup=ReplyKeyboardMarkup(
    #          reply_keyboard, one_time_keyboard=True, input_field_placeholder="Primer lugar"
    #      ),
    #  )

# async def segundo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#      """Starts the conversation and asks the user about their gender."""
#      reply_keyboard = [["ALO", "BOT", "DEV", "GAS"], ["HAM", "HUL", "LEC", "MAG", "NOR"], ["OCO", "PIA", "PER",]]
#      user = update.message.from_user
#      piloto = update.message.text
#      context.user_data["P1"] = piloto
#      print(user.first_name, piloto)
#      await update.message.reply_text(
#          "Presiona el boton del piloto que quedara en SEGUNDO lugar: ",
#         #  reply_markup=ReplyKeyboardRemove(),
#          reply_markup=ReplyKeyboardMarkup(
#              reply_keyboard, one_time_keyboard=True, input_field_placeholder="Segundo lugar"
#          ),
#      )
 
#      return TERCERO

# async def tercero(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#      """Starts the conversation and asks the user about their gender."""
#      reply_keyboard = [["ALB", "ALO", "BOT", "DEV", "GAS"], ["HAM", "HUL", "LEC", "MAG", "NOR"], ["OCO", "PIA", "PER"]]
#      user = update.message.from_user
#      piloto = update.message.text
#      print(user.first_name, piloto)
#      context.user_data["P2"] = piloto
#      await update.message.reply_text(
#          "Presiona el boton del piloto que quedara en TERCER lugar: ",
#          reply_markup=ReplyKeyboardMarkup(
#              reply_keyboard, one_time_keyboard=True, input_field_placeholder="Tercer lugar"
#          ),
#      )

#      return FIN

# async def fin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     user = update.message.from_user
#     piloto = update.message.text
#     print(user.first_name, piloto)
#     context.user_data["P3"] = piloto
#     print(context.user_data)
#     listpilots = ""
#     for x, y in context.user_data.items():
#         print(x, y)
#         listpilots += x + ": " + y + "\n"
#     await update.message.reply_text( 
#         "Tu quiniela quedo asi:\n" + listpilots, reply_markup=ReplyKeyboardRemove()
#     )
#     return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    # dbprueba = deta.Base('simple_db')
    # dbprueba.put({'prueba':str(user)})
    # dbprueba.put({'update':str(update)})
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Comando cancelado, puedes empezar de nuevo con el comando /start", 
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

# async def favoritos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     """Send a message with a button that opens a the web app."""
#     user = update.message.from_user
#     puntospilotos = dbPuntosPilotos.fetch()
#     pilotoslista = dbPilotos.get('2023')['Lista']
#     for carrera in puntospilotos.items:
#         for piloto in carrera['Pilotos']:
#             # print(piloto, carrer['Pilotos'][piloto]['puntos'])
#             pilotoslista[piloto]['AcumuladoPuntos'] = pilotoslista[piloto]['AcumuladoPuntos'] + carrera['Pilotos'][piloto]['puntos']
#     pilotoslista = sorted(pilotoslista.items(), key=lambda item: item[1]['AcumuladoPuntos'], reverse=True)
#     listacodigosenorden = ''
#     for pilotonumer in pilotoslista:
#         if(listacodigosenorden == ''):
#             # listacodigosenorden = pilotonumer[1]['codigo'] + '_' + pilotonumer[1]['Nombre'] + '_' + pilotonumer[1]['Apellido'] 
#             listacodigosenorden = pilotonumer[1]['codigo']
#         else:
#             # listacodigosenorden = listacodigosenorden + ',' + pilotonumer[1]['codigo'] + '_' + pilotonumer[1]['Nombre'] + '_' + pilotonumer[1]['Apellido'] 
#             listacodigosenorden = listacodigosenorden + ',' + pilotonumer[1]['codigo']
#     #print(pilotoslista.items())
#     print(listacodigosenorden)
#     leerfavoritos = dbfavoritos.get(str(user.id))
#     usuariofavoritos = ''
#     if(leerfavoritos is None):
#         usuariofavoritos = 'nohay'
#     else:
#         usuariofavoritos = leerfavoritos['Lista']

#     await update.message.reply_text(
#         "Presiona el boton de abajo para abrir la forma",
#         reply_markup=ReplyKeyboardMarkup.from_button(
#             KeyboardButton(
#                 text="Abrir lista de pilotos favoritos",
#                 web_app=WebAppInfo(url="https://" + bot_hostname + "/favoritos/?lista=" + listacodigosenorden + "&favoritos=" + usuariofavoritos),
#             )
#         ),
#     )
#     return FAVORITOS

async def help(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # await update.message.reply_photo(
    #     'AgACAgEAAxkBAAIIT2QkP7i2-OltRtYockIEzTv7e22kAAK5qzEb70cgRU6I4NOmmE7AAQADAgADeAADLwQ'
    # )
    # im, ronda = crear_tabla_resultados()
    # with BytesIO() as tablaresutados_imagen:    
    #     im.save(tablaresutados_imagen, "png")
    #     tablaresutados_imagen.seek(0)
    #     #await update.message.reply_photo(tablaresutados_imagen, caption='Resultados de la ronda: ' + ronda)
    # guia_usuario = documentos.get('Quiniela Formula 1.pdf')
    # contenido = guia_usuario.read()
    # guia_usuario.close()
    # await update.message.reply_document(
    #     contenido,
    #     caption='Documento de ayuda al participante',
    #     filename='Ayuda General Quinieala.pdf',
    #     reply_markup=ReplyKeyboardRemove()
    # )
    # return ConversationHandler.END

    keyboard = [
        [
            InlineKeyboardButton("Reglas Quiniela", callback_data=REGLAS),
            InlineKeyboardButton("Ayuda Quiniela", callback_data=AYUDA),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Send message with text and appended InlineKeyboard
    await update.message.reply_text("Elige que documento de ayuda necesitas: ", reply_markup=reply_markup)
    # Tell ConversationHandler that we're in state `FIRST` now
    return MENU_AYUDA

async def reglas(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    guia_usuario = documentos.get('Reglamento Quiniela fórmula 1.pdf')
    contenido = guia_usuario.read()
    guia_usuario.close()
    # await update.message.reply_document(
    #     contenido,
    #     caption='Documento con las reglas de la Quiniela',
    #     filename='Reglas Generales Quinieala.pdf',
    #     reply_markup=ReplyKeyboardRemove()
    # )
    # keyboard = [
    #     [
    #         InlineKeyboardButton("Reglas Quiniela", callback_data=REGLAS),
    #         InlineKeyboardButton("\U00002714 Ayuda Quiniela", callback_data=AYUDA),
    #     ]
    # ]
    # reply_markup = InlineKeyboardMarkup(keyboard)
    # await query.edit_message_text(
    #     text="Fourth CallbackQueryHandler, Choose a route", reply_markup=reply_markup
    # )
    await query.edit_message_text(text="Ok, en un nuevo mensaje te envio el documento")
    await application.bot.send_document(
        chat_id= query.from_user.id,
        document=contenido, 
        filename="Reglas Quiniela.pdf",
        caption="Aqui esta el documento con las relgas",
    )
    return ConversationHandler.END

async def ayuda(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    guia_usuario = documentos.get('Quiniela Formula 1.pdf')
    contenido = guia_usuario.read()
    guia_usuario.close()
    # await update.message.reply_document(
    #     contenido,
    #     caption='Documento de ayuda al participante',
    #     filename='Ayuda General Quinieala.pdf',
    #     reply_markup=ReplyKeyboardRemove()
    # )
    await query.edit_message_text(text="Ok, en un nuevo mensaje te envio el documento")
    await application.bot.send_document(
        chat_id= query.from_user.id,
        document=contenido, 
        filename="Ayuda General Quiniela.pdf",
        caption="Aqui esta el documento de ayuda general",
    )
    
    return ConversationHandler.END

async def guardar_comprobante(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_id = update.message.photo[-1].file_id
    mensaje = update.effective_message.id
    user = update.message.from_user
    dbPagos.update(updates={'foto':photo_id, 'estado':'guardado', 'mensaje':mensaje}, key=context.user_data["fecha"])
    
    # await photo_file.download_to_drive("user_photo.jpg")
    # logger.info("Photo of %s: %s", user.first_name, "user_photo.jpg")
    await update.message.reply_text(
        "Tu pago se ha guardado por " + context.user_data["pago_carreras"] + " carreras" +  ". El tesorero va a revisar la foto del comprobante para confirmarlo",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def subir_comprobante(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # photo_id = update.message.photo[-1].file_id
    # await photo_file.download_to_drive("user_photo.jpg")
    # logger.info("Photo of %s: %s", user.first_name, "user_photo.jpg")
    user = update.message.from_user
    pago_carreras = update.message.text
    context.user_data["pago_carreras"] = pago_carreras
    dbPagos.update(updates={'carreras':context.user_data["pago_carreras"], 'estado':'sinfoto'}, key=context.user_data["fecha"])
    await update.message.reply_text(
        "Sube la foto del comprobante de pago de las " + context.user_data["pago_carreras"] + ' carreras',
        reply_markup=ReplyKeyboardRemove()
    )
    return GUARDARCOMPROBANTE

async def mipago(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    ahora = datetime.now()
    ahora = ahora.astimezone()
    ahora_gdl = ahora.astimezone(pytz.timezone('America/Mexico_City'))
    context.user_data["fecha"] = ahora_gdl.isoformat()
    dbPagos.put({'key': context.user_data["fecha"], 'usuario':str(user.id) , 'carreras':'' , 'foto':'' , 'estado':'creado', 'enviado':False})
    await update.message.reply_text(
        '¿Cuantas carreras vas a cubrir con el comprobante de pago?', 
        reply_markup=ReplyKeyboardMarkup(
            [['1', '2','3','4','5'], ['6', '7','8','9','10'], ['11', '12','13','14','15'], ['Todas']], 
            one_time_keyboard=True, 
            input_field_placeholder="Numero de carreras:")
        )
    return SUBIRCOMPROBANTE

async def revisarpagos(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pagos_guardados = dbPagos.fetch({'estado':'guardado'})
    pagos_por_confirmar = str(pagos_guardados.count)
    context.user_data['procesados'] = 0
    if pagos_guardados.count == 0:
        await update.message.reply_text(
        "No hay pagos por confirmar.", 
        reply_markup=ReplyKeyboardRemove()
    )
        return ConversationHandler.END
    await update.message.reply_text(
        'Hay ' + pagos_por_confirmar + ' pagos por confirmar, ¿quieres empezar a confirmarlos?', 
        reply_markup=ReplyKeyboardMarkup(
            [['Si', 'No']], 
            one_time_keyboard=True, 
            )
        )
    return VALIDARPAGO

async def validarpago(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pagos_guardados = dbPagos.fetch({'estado':'guardado'})
    if pagos_guardados.count == 0:
        pagos_procesados = str(context.user_data['procesados'])
        await update.message.reply_text(
            'Validaste ' + pagos_procesados + ' pagos, ya no quedan mas pagos por validar.',
            reply_markup=ReplyKeyboardRemove()
            )
        return ConversationHandler.END
    else:
        pago_confirmar = pagos_guardados.items[0]
        numero_carreras = pago_confirmar['carreras']
        usuario = dbquiniela.get(pago_confirmar['usuario'])['Nombre']
        context.user_data["pago"] = pago_confirmar['key']
        await update.message.reply_photo(
            pago_confirmar['foto'], 
            caption='Confirmas este pago por ' + numero_carreras + ' carreras, enviado por ' + usuario,
            reply_markup=ReplyKeyboardMarkup(
                [['Si', 'No']], 
                one_time_keyboard=True, 
                )
            )
        return SIGUIENTEPAGO

async def pagovalidado(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # user = update.message.from_user
    dbPagos.update(updates={'estado':'confirmado'}, key=context.user_data['pago'])
    # pagoprocesado = dbPagos.get(context.user_data['pago'])
    # responder = None
    # if pagoprocesado['mensaje'] != 0:
    #     responder = pagoprocesado['mensaje']
    context.user_data['procesados'] = context.user_data['procesados'] + 1
    # revisar si hay pagos pendientes, si no hay terminar. si hay preguntar
    await update.message.reply_text(
            'Pago validado ¿quieres confirmar el siguiente pago?', 
            reply_markup=ReplyKeyboardMarkup(
                [['Si', 'No']], 
                one_time_keyboard=True, 
                )
            )
    # await application.bot.send_message(
    #     chat_id= float(user.id),
    #     message_id= responder, 
    #     text='Este pago ya fue validado por el tesorero.')
    return VALIDARPAGO
    
async def pagorechazado(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # user = update.message.from_user
    dbPagos.update(updates={'estado':'rechazado'}, key=context.user_data['pago'])
    # pagoprocesado = dbPagos.get(context.user_data['pago'])
    # responder = None
    # if pagoprocesado['mensaje'] != 0:
    #     responder = pagoprocesado['mensaje']
    context.user_data['procesados'] = context.user_data['procesados'] + 1
    # revisar si hay pagos pendientes, si no hay terminar. si hay preguntar
    await update.message.reply_text(
            'Pago rechazado ¿quieres confirmar el siguiente pago?', 
            reply_markup=ReplyKeyboardMarkup(
                [['Si', 'No']], 
                one_time_keyboard=True, 
                )
            )
    # await application.bot.send_message(
    #     chat_id= float(user.id),
    #     message_id= responder, 
    #     text='Este pago fue rechazado por el tesorero.')
    return VALIDARPAGO

# async def siguientepago(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     # pago validado por X numero de carreras, quieres ver otro pago pendiente si o no
#     return

async def finpagos(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    #validaste x numeros de pagos, quedan pendientes x numeros de pagos. Puedes volver 
    #a validar con /revisarpagos
    pagos_pendientes = str(dbPagos.fetch({'estado':'guardado'}).count)
    pagos_procesados = str(context.user_data['procesados'])
    await update.message.reply_text(
        'Validaste ' + pagos_procesados + ' pagos, quedan pendientes ' + pagos_pendientes + 'pagos. Puedes volver a validar con /revisarpagos', 
        reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END

async def quinielas(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a picture"""
    carreras = dbCarreras.fetch([{'Estado':'EN-CURSO'}, {'Estado':'IDLE'}])
    if(carreras.count > 0):
        horario_qualy = datetime.fromisoformat(carreras.items[0]['q']['hora_empiezo'])
        ahora = datetime.now()
        ahora = ahora.astimezone()
        enmascarar = True
        mensaje = "Aun no es hora de qualy, aqui esta la lista con los que han puesto quiniela para la ronda: "
        if(ahora > horario_qualy):
            enmascarar = False
            mensaje = "Quinielas para ronda: "
        im, carrera_ronda = crear_tabla_quinielas(carreras.items[0], enmascarar)
        with BytesIO() as tablaquinielaimagen:    
            im.save(tablaquinielaimagen, "png")
            tablaquinielaimagen.seek(0)
            await update.message.reply_photo(tablaquinielaimagen, caption= mensaje + carrera_ronda)
        return ConversationHandler.END
        # await update.message.reply_text(
        #     'Aun no pasa la hora de la qualy, no puedo mandar las quinielas.'
        #     )
        # return ConversationHandler.END
    await update.message.reply_text(
        'Aun no pasa un dia despues de la ultima carrera, no hay quinielas por mostrar.'
        )
    return ConversationHandler.END

async def general(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    # agregar if para revisar si hay carrera en curso, esperar a que se termine para generar la tabla.
    im, total_rondas = crear_tabla_general()
    with BytesIO() as tablaresutados_imagen:    
        im.save(tablaresutados_imagen, "png")
        tablaresutados_imagen.seek(0)
        await update.message.reply_photo(tablaresutados_imagen, caption="Total de rondas incluidas: " + str(total_rondas) )
    return ConversationHandler.END



async def resultados(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a picture"""
    # aggregar un if, si hay carrera en curso mandar mensaje de espera
    im, ronda, texto = crear_tabla_resultados()
    with BytesIO() as tablaresutados_imagen:    
        im.save(tablaresutados_imagen, "png")
        tablaresutados_imagen.seek(0)
        await update.message.reply_photo(tablaresutados_imagen, caption=texto)
    return ConversationHandler.END



# async def web_app_data_favoritos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     """Print the received data and remove the button."""
#     user = update.message.from_user
#     data = json.loads(update.effective_message.web_app_data.data)
#     now = datetime.now()
#     now = now.astimezone()
#     dbfavoritos.put({"Lista": data["prueba"], "FechaHora":now.isoformat(), "key": str(user.id)})
#     await update.message.reply_html(
#         text="Tu lista es la siguiente: " + data["prueba"],
#         reply_markup=ReplyKeyboardRemove(),
#     )
#     return ConversationHandler.END

# async def web_app_data_quiniela(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     """Print the received data and remove the button."""
#     carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
#     user = update.message.from_user
#     data = json.loads(update.effective_message.web_app_data.data)
#     now = datetime.now()
#     now = now.astimezone()
#     apellido = ''
#     if(user.last_name is not None):
#         apellido = ' ' + user.last_name
#     dbquiniela.put({"Carrera": carrera_quiniela.items[0]['key'], "Lista": data["prueba"], "FechaHora":now.isoformat(), "Nombre":user.first_name + apellido, "key": str(user.id)})
#     await update.message.reply_html(
#         text="Tu quiniela quedo asi: " + data["prueba"],
#         reply_markup=ReplyKeyboardRemove(),
#     )
#     return ConversationHandler.END

async def inicio_pilotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['Lista'] = []
    puntospilotos = dbPuntosPilotos.fetch()
    pilotoslista = dbPilotos.get('2023')['Lista']
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    horario_qualy = datetime.fromisoformat(carrera_quiniela.items[0]['q']['hora_empiezo'])
    ahora = datetime.now()
    ahora = ahora.astimezone()
    if(ahora > horario_qualy):
        await update.message.reply_text(
            'Ya no se puede modificar o ingresar una quiniela porque la qualy ya empezo. Si no metiste quiniela, se te penalizara con base a las reglas. Usa /help para ver las reglas.'
            )
        return ConversationHandler.END
    for carrera in puntospilotos.items:
        for piloto in carrera['Pilotos']:
            # print(piloto, carrer['Pilotos'][piloto]['puntos'])
            pilotoslista[piloto]['AcumuladoPuntos'] = pilotoslista[piloto]['AcumuladoPuntos'] + carrera['Pilotos'][piloto]['puntos']
    pilotoslista = sorted(pilotoslista.items(), key=lambda item: item[1]['AcumuladoPuntos'], reverse=True)
    context.user_data['ListaPilotosOrdenada'] = pilotoslista
    COLUMNAS = 5
    # numero_filas = math.ceil(len(pilotoslista) / COLUMNAS)
    keyboard = []
    # fila = numero_filas
    cuenta_columnas = COLUMNAS
    for pilotonumer in pilotoslista:
        if COLUMNAS == cuenta_columnas:
            keyboard.append([])
            cuenta_columnas = 0
        # keyboard[len(keyboard) - 1].append(pilotonumer[1]['codigo'])
        keyboard[len(keyboard) - 1].append(InlineKeyboardButton(pilotonumer[1]['codigo'], callback_data=pilotonumer[1]['codigo']))
        cuenta_columnas = cuenta_columnas + 1
    if len(keyboard[len(keyboard) - 1]) < COLUMNAS:
        for i in range(COLUMNAS - len(keyboard[len(keyboard) - 1])):
            keyboard[len(keyboard) - 1].append('')
    print(keyboard)
    # keyboard = [
    #     [
    #         InlineKeyboardButton("VER", callback_data='VER'),
    #         InlineKeyboardButton("PER", callback_data='PER'),
    #         InlineKeyboardButton("ALO", callback_data='ALO'),
    #         InlineKeyboardButton("HAM", callback_data='HAM'),
    #         InlineKeyboardButton("SAI", callback_data='SAI'),
    #     ],
    #     [
    #         InlineKeyboardButton("RUS", callback_data='RUS'),
    #         InlineKeyboardButton("LEC", callback_data='LEC'),
    #         InlineKeyboardButton("STR", callback_data='STR'),
    #         InlineKeyboardButton("NOR", callback_data='NOR'),
    #         InlineKeyboardButton("GAS", callback_data='GAS'),
    #     ],
    #     [
    #         InlineKeyboardButton("TSU", callback_data='TSU'),
    #         InlineKeyboardButton("HUL", callback_data='HUL'),
    #         InlineKeyboardButton("OCO", callback_data='OCO'),
    #         InlineKeyboardButton("BOT", callback_data='BOT'),
    #         InlineKeyboardButton("PIA", callback_data='PIA'),
    #     ],
    #     [
    #         InlineKeyboardButton("MAG", callback_data='MAG'),
    #         InlineKeyboardButton("ZHO", callback_data='ZHO'),
    #         InlineKeyboardButton("ALB", callback_data='ALB'),
    #         InlineKeyboardButton("SAR", callback_data='SAR'),
    #         InlineKeyboardButton("DEV", callback_data='DEV'),
    #     ],
    # ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Send message with text and appended InlineKeyboard
    nombre_carrera = carrera_quiniela.items[0]['Nombre']
    
    await update.message.reply_text("Usando los botones de abajo, ve escogiendo los pilotos del P1 a P7 para la carrera: " + nombre_carrera, reply_markup=reply_markup)
    
    return ELEGIR_PILOTOS

async def elegir_pilotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cuenta_pilotos = len(context.user_data['Lista'])
    codigo_eliminado = ''
    
    if query.data == 'ATRAS':
        if cuenta_pilotos > 0:
            codigo_eliminado = context.user_data['Lista'].pop()
    else:
        if cuenta_pilotos < 7:
            if not query.data in context.user_data['Lista']:
                context.user_data['Lista'].append(query.data)
    
    # puntospilotos = dbPuntosPilotos.fetch()
    # pilotoslista = dbPilotos.get('2023')['Lista']
    # for carrera in puntospilotos.items:
    #     for piloto in carrera['Pilotos']:
    #         # print(piloto, carrer['Pilotos'][piloto]['puntos'])
    #         pilotoslista[piloto]['AcumuladoPuntos'] = pilotoslista[piloto]['AcumuladoPuntos'] + carrera['Pilotos'][piloto]['puntos']
    # pilotoslista = sorted(pilotoslista.items(), key=lambda item: item[1]['AcumuladoPuntos'], reverse=True)
    
    pilotoslista = context.user_data['ListaPilotosOrdenada']
    
    COLUMNAS = 5
    # numero_filas = math.ceil(len(pilotoslista) / COLUMNAS)
    keyboard = []
    # fila = numero_filas
    cuenta_columnas = COLUMNAS
    for pilotonumer in pilotoslista:
        pos = ''
        if COLUMNAS == cuenta_columnas:
            keyboard.append([])
            cuenta_columnas = 0
        # keyboard[len(keyboard) - 1].append(pilotonumer[1]['codigo'])
        if pilotonumer[1]['codigo'] in context.user_data['Lista']:
            p = context.user_data['Lista'].index(pilotonumer[1]['codigo']) + 1
            pos = 'P' + str(p) + ' '
        keyboard[len(keyboard) - 1].append(InlineKeyboardButton(pos + pilotonumer[1]['codigo'], callback_data=pilotonumer[1]['codigo']))
        cuenta_columnas = cuenta_columnas + 1
    if len(keyboard[len(keyboard) - 1]) < COLUMNAS:
        for i in range(COLUMNAS - len(keyboard[len(keyboard) - 1])):
            keyboard[len(keyboard) - 1].append('')
    print(keyboard)
    # keyboard = [
    #     [
    #         InlineKeyboardButton("VER", callback_data='VER'),
    #         InlineKeyboardButton("P1 PER", callback_data='PER'),
    #         InlineKeyboardButton("ALO", callback_data='ALO'),
    #         InlineKeyboardButton("HAM", callback_data='HAM'),
    #         InlineKeyboardButton("SAI", callback_data='SAI'),
    #     ],
    #     [
    #         InlineKeyboardButton("RUS", callback_data='RUS'),
    #         InlineKeyboardButton("LEC", callback_data='LEC'),
    #         InlineKeyboardButton("STR", callback_data='STR'),
    #         InlineKeyboardButton("NOR", callback_data='NOR'),
    #         InlineKeyboardButton("GAS", callback_data='GAS'),
    #     ],
    #     [
    #         InlineKeyboardButton("TSU", callback_data='TSU'),
    #         InlineKeyboardButton("HUL", callback_data='HUL'),
    #         InlineKeyboardButton("OCO", callback_data='OCO'),
    #         InlineKeyboardButton("BOT", callback_data='BOT'),
    #         InlineKeyboardButton("PIA", callback_data='PIA'),
    #     ],
    #     [
    #         InlineKeyboardButton("MAG", callback_data='MAG'),
    #         InlineKeyboardButton("ZHO", callback_data='ZHO'),
    #         InlineKeyboardButton("P2 ALB", callback_data='ALB'),
    #         InlineKeyboardButton("SAR", callback_data='SAR'),
    #         InlineKeyboardButton("DEV", callback_data='DEV'),
    #     ],
    # ]

    cuenta_pilotos = len(context.user_data['Lista'])
    if cuenta_pilotos > 0:
        keyboard.append([
            InlineKeyboardButton("Atras", callback_data='ATRAS'),
        ])
    if cuenta_pilotos == 7:
        keyboard.append([
            InlineKeyboardButton("CONFIRMAR", callback_data='CONFIRMAR'),
        ])
    # \U00002714
    reply_markup = InlineKeyboardMarkup(keyboard)
    texto = 'Asi va tu lista de piltos (de P1 a P7):\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)
    return ELEGIR_PILOTOS

async def confirmar_pilotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    user = query.from_user
    data = ",".join(context.user_data['Lista'])
    now = datetime.now()
    now = now.astimezone()
    apellido = ''
    if(user.last_name is not None):
        apellido = ' ' + user.last_name
    dbquiniela.put({"Carrera": carrera_quiniela.items[0]['key'], "Lista": data, "FechaHora":now.isoformat(), "Nombre":user.first_name + apellido, "key": str(user.id)})
    texto = "Tu lista se ha guardado en la base de datos. Quedo de la siguiente manera:\n"
    for index, codigo in enumerate(context.user_data['Lista']):
        texto = texto + 'P' + str(index + 1) + ' ' + codigo + '\n'
    await query.edit_message_text(text=texto)
    return ConversationHandler.END

def get_application():
    # filtropilotos = "^(VER|PER|ALO|HAM|RUS|LEC|STR|SAI|NOR|GAS|TSU|HUL|OCO|BOT|PIA|MAG|ZHO|ALB|SAR|DEV|ATRAS)$"
    pilotoslista = dbPilotos.get('2023')['Lista']
    filtropilotos = 'ATRAS'
    for pilotonumer in pilotoslista:
        filtropilotos = filtropilotos + '|' + pilotoslista[pilotonumer]['codigo']
    # print('^(' + filtropilotos + ')$')
    filtropilotos = '^(' + filtropilotos + ')$'
    application = Application.builder().token(BotToken).build()
    # add handlers
    # application.add_handler(CommandHandler("start", start))
    # application.add_handler(CommandHandler("quiniela", quiniela))
    # application.add_handler(CommandHandler("favoritos", poll))
    # application.add_handler(CommandHandler("help", help_handler))
    # application.add_handler(MessageHandler(filters.POLL, receive_poll))
    # application.add_handler(MessageHandler(filters.Regex(pilotos), segundo))
    # application.add_handler(PollAnswerHandler(receive_poll_answer))
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("quiniela", inicio_pilotos), 
            # CommandHandler("quiniela", quiniela), 
            CommandHandler("start", start),
            # CommandHandler("favoritos", favoritos),
            # CommandHandler("favoritos", inicio_pilotos),
            CommandHandler("help", help),
            CommandHandler("quinielas", quinielas),
            CommandHandler("general", general),
            CommandHandler("resultados", resultados),
            CommandHandler("cancelar", cancelar),
            CommandHandler("proxima", proxima),
            CommandHandler("mipago", mipago),
            CommandHandler("pagos", pagos),
            CommandHandler("revisarpagos", revisarpagos),
            
            # InlineQueryHandler(inline_query),
            # CallbackQueryHandler(inline_query),
            ],
        states={
            # SEGUNDO: [MessageHandler(filters.Regex(pilotos), segundo)],
            # TERCERO: [MessageHandler(filters.Regex(pilotos), tercero)],
            ELEGIR_PILOTOS:[CallbackQueryHandler(elegir_pilotos, pattern=filtropilotos), CallbackQueryHandler(confirmar_pilotos, pattern="^CONFIRMAR$")], 
            MENU_AYUDA: [CallbackQueryHandler(reglas, pattern="^" + REGLAS + "$"), CallbackQueryHandler(ayuda, pattern="^" + AYUDA + "$")],
            VALIDARPAGO: [MessageHandler(filters.Regex('^Si$'), validarpago), MessageHandler(filters.Regex('^No$'), finpagos)], 
            SIGUIENTEPAGO: [MessageHandler(filters.Regex('^Si$'), pagovalidado), MessageHandler(filters.Regex('^No$'), pagorechazado)], 
            FINPAGOS: [MessageHandler(filters.Regex('^No$'), finpagos)],
            GUARDARCOMPROBANTE: [MessageHandler(filters.PHOTO, guardar_comprobante)], 
            SUBIRCOMPROBANTE: [MessageHandler(filters.Regex('^(1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|Todas)$'), subir_comprobante)],
            # CONFIRMAR_PENALIZACION: [MessageHandler(filters.Regex('^(Si|No)$'), confirmar_penalizacion)],
            # QUINIELA: [MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_quiniela)],
            # # FIN: [MessageHandler(filters.Regex(pilotos), fin)],
            # FAVORITOS: [MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_favoritos)]
            },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    application.add_handler(conv_handler)
      
    # application.add_handler(InlineQueryHandler(inline_query))
    return application

application = get_application()

async def pruebapilotos():

    F1_API_KEY = 'qPgPPRJyGCIPxFT3el4MF7thXHyJCzAP'
    urlevent_tracker = 'https://api.formula1.com/v1/event-tracker' 
    headerapi = {'apikey':F1_API_KEY, 'locale':'en'}
    urllivetiming = 'https://livetiming.formula1.com/static/'
    controles = dbConfiguracion.get('controles')
    
    carrera_no_enviada = dbCarreras.fetch([{'Estado':'NO_ENVIADA'}])
    if carrera_no_enviada.count > 0:
        print("imprimir tabla resultados")
        im, ronda, texto = crear_tabla_resultados()
        with BytesIO() as tablaresutados_imagen:    
            im.save(tablaresutados_imagen, "png")
            tablaresutados_imagen.seek(0)
            await application.bot.send_photo(
                chat_id= float(controles['grupo']),
                photo=tablaresutados_imagen, 
                caption=texto
                )

        print("imprimir tabla general")
        im, total_rondas = crear_tabla_general()
        texto = "Total de rondas incluidas: " + str(total_rondas)
        with BytesIO() as tablageneral_imagen:    
            im.save(tablageneral_imagen, "png")
            tablageneral_imagen.seek(0)
            await application.bot.send_photo(
                chat_id= float(controles['grupo']),
                photo=tablageneral_imagen, 
                caption=texto
                )
        dbCarreras.update(updates={'Estado':'ARCHIVADA'}, key=carrera_no_enviada.items[0]['key'])

    # await asyncio.gather(
    #     application.bot.send_photo(chat_id= float(controles['grupo']),photo=tablaresutados_imagen, caption=texto),
    #     application.bot.send_photo(chat_id= float(controles['grupo']),photo=tablageneral_imagen, caption=texto)
    # )

    encurso_siguiente_Carrera = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    if(encurso_siguiente_Carrera.count == 0):
        response = requests.get(url=urlevent_tracker, headers=headerapi)
        response.encoding = 'utf-8-sig'
        # print(response.json())
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
                #print(session_row)
                carrera_dict[session_row['session']] = {
                    'estado': session_row['state'],
                    'hora_empiezo': session_row['startTime'] + session_row['gmtOffset'],
                    'hora_termino': session_row['endTime'] + session_row['gmtOffset'],
                }
            dbCarreras.put(carrera_dict)
    else:
        estado_Carrera = encurso_siguiente_Carrera.items[0]['Estado']
        if(estado_Carrera == 'IDLE'):
            ahora = datetime.now()
            ahora = ahora.astimezone()            
            horaempiezo_Carrera = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['Empiezo'])
            if(ahora > horaempiezo_Carrera):
                carrera_codigo = encurso_siguiente_Carrera.items[0]['key']
                dbCarreras.update(updates={'Estado':'EN-CURSO'}, key=carrera_codigo)
        else:
            horario_actual = datetime.now()
            horario_actual = horario_actual.astimezone()
            horario_q_sesion = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['q']['hora_empiezo'])
            estado_qualy = encurso_siguiente_Carrera.items[0]['q']['estado']
            # horario_q_sesion_4min = horario_q_sesion + timedelta(minutes=4, seconds=49)
            print(horario_actual, horario_q_sesion, estado_qualy)
            if horario_actual >= horario_q_sesion and estado_qualy == 'upcoming':
                #mandar tabla quinielas
                print('entro a crear tabla quiniela')
                im, carrera_ronda = crear_tabla_quinielas(encurso_siguiente_Carrera.items[0], False)
                texto = "Quinielas para la carrera " + encurso_siguiente_Carrera.items[0]['Nombre']
                with BytesIO() as tablaquinielaimagen:    
                    im.save(tablaquinielaimagen, "png")
                    tablaquinielaimagen.seek(0)
                    await application.bot.send_photo(
                        chat_id= float(controles['grupo']),
                        photo=tablaquinielaimagen, 
                        caption=texto
                        )
                carrera_codigo = encurso_siguiente_Carrera.items[0]['key']
                cambiar_estado_qualy = encurso_siguiente_Carrera.items[0]['q']
                cambiar_estado_qualy['estado'] = 'EMPEZADA'
                dbCarreras.update(updates={'q':cambiar_estado_qualy}, key=carrera_codigo)
            revisar_Pilotos = dbPilotos.fetch({'Carrera':encurso_siguiente_Carrera.items[0]['key']})
            print('revisar_pilotos', revisar_Pilotos.count)
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
                        print('pilotocount', piloto.count)
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
                            print('racingnumer', response_dict[id]['RacingNumber'])
                            dbPilotos.update(updates={'Lista':listapilotos}, key='2023')
            else:    
                horario_sesion = datetime.fromisoformat(encurso_siguiente_Carrera.items[0][revisar_Pilotos.items[0]['Sesion']]['hora_termino']) 
                horario_siguiente_sesion = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['Termino']) 
                siguiente_sesion = 'r'
                # print(horario_sesion)
                for sesion in encurso_siguiente_Carrera.items[0]:
                    if(isinstance(encurso_siguiente_Carrera.items[0][sesion], dict)):
                        horario_sesion_comparar = datetime.fromisoformat(encurso_siguiente_Carrera.items[0][sesion]['hora_termino'])
                        if(horario_sesion_comparar > horario_sesion):
                            if(horario_sesion_comparar < horario_siguiente_sesion):
                                horario_siguiente_sesion = horario_sesion_comparar
                                siguiente_sesion = sesion
                                # guardar tambien el empiezo de la siguiente sesion
                print(siguiente_sesion, horario_siguiente_sesion)
                horario_actual = datetime.now()
                horario_actual = horario_actual.astimezone()
                if(horario_actual > horario_siguiente_sesion):
                    print('leo api')
                    # si el horario actual es mayor al de la siguiente session                     
                    response = requests.get(url=urlevent_tracker, headers=headerapi)
                    response.encoding = 'utf-8-sig'
                    response_dict = response.json()
                    if('sessionLinkSets' in response_dict):
                        index_sesion = len(response_dict['sessionLinkSets']['replayLinks']) - 1
                        sesion_carrera = response_dict['sessionLinkSets']['replayLinks'][index_sesion]['session']
                        urllivetiming = response_dict['sessionLinkSets']['replayLinks'][index_sesion]['url']
                        links = []
                        if('links' in response_dict and sesion_carrera == 'r'):
                            links = response_dict['links']
                        driverslist = 'DriverList.json'
                        response = requests.get(url=urllivetiming + driverslist)
                        response.encoding = 'utf-8-sig'
                        response_dict = response.json()
                        dbPilotos.update(updates={'Carrera': encurso_siguiente_Carrera.items[0]['key'], 'Sesion': sesion_carrera}, key='2023')
                        for id in response_dict:
                            piloto = dbPilotos.fetch({'Lista.' + response_dict[id]['RacingNumber'] + '.Nombre':response_dict[id]['FirstName']})
                            print('pilotocount', piloto.count)
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
                                print('racingnumer', response_dict[id]['RacingNumber'])
                                dbPilotos.update(updates={'Lista':listapilotos}, key='2023')
                        if(sesion_carrera == 'r'):
                            print('hacer tabla resultados')
                            url_results_index = next((index for (index, d) in enumerate(links) if d["text"] == "RESULTS"), None)
                            if(not(url_results_index is None)):
                                url_results = links[url_results_index]['url']
                                soup = BeautifulSoup(requests.get(url_results).text)
                                table = soup.find('table')
                                header = []
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
                                # print(posiciones_dict)
                                datosquiniela = dbquiniela.fetch()
                                quinielas = datosquiniela.items
                                dbPuntosPilotos.put({'key': encurso_siguiente_Carrera.items[0]['key'], 'Pilotos':posiciones_dict})
                                #agregar caso cuando es la primera quinieal, debe ser con put
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
                                    
                                    horario_qualy = datetime.fromisoformat(encurso_siguiente_Carrera.items[0]['q']['hora_empiezo'])
                                    hora_quiniela = datetime.fromisoformat(quiniela['FechaHora'])

                                    historico_resultados = historico['Resultados']
                                    listaquiniela = quiniela['Lista'].split(',')
                                    # checar hora para penalizar
                                    if hora_quiniela > horario_qualy:
                                        resultados = {'normales':0, 'extras':0, 'penalizaciones':-5}    
                                    else:
                                        if quiniela['Carrera'] != encurso_siguiente_Carrera.items[0]['key']:
                                            resultados = {'normales':0, 'extras':0, 'penalizaciones':-5}
                                        else:
                                            resultados = {'normales':0, 'extras':0, 'penalizaciones':0}
                                        # resultados = {'normales':0, 'extras':0, 'penalizaciones':0}
                                    # revisar si esta al corriente con los pagos
                                    pagosusuarios = dbPagos.fetch([{'usuario':quiniela['key'], 'estado':'guardado'},{'usuario':quiniela['key'], 'estado':'confirmado'} ])
                                    rondas_pagadas = 0
                                    rondas_confirmadas = 0
                                    for pagousuario in pagosusuarios.items:
                                        rondas_pagadas = int(pagousuario['carreras']) + rondas_pagadas
                                        if pagousuario['estado'] == 'confirmado':
                                            rondas_confirmadas = int(pagousuario['carreras']) + rondas_confirmadas
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
                                
                                await application.bot.send_message(
                                    chat_id= float(controles['grupo']), 
                                    text='prueba mensaje automatico'
                                    )

                                # await application.bot.send_message(
                                #     chat_id= float(controles['grupo']), 
                                #     text='/resultados'
                                #     )
    
                                # await application.bot.send_message(
                                #     chat_id= float(controles['grupo']), 
                                #     text='/general'
                                #     )

                                # print("imprimir tabla resultados")
                                # im, ronda, texto = crear_tabla_resultados()
                                # with BytesIO() as tablaresutados_imagen:    
                                #     im.save(tablaresutados_imagen, "png")
                                #     tablaresutados_imagen.seek(0)
                                #     await application.bot.send_photo(
                                #         chat_id= float(controles['grupo']),
                                #         photo=tablaresutados_imagen, 
                                #         caption=texto
                                #         )

                                # print("imprimir tabla general")
                                # im, total_rondas = crear_tabla_general()
                                # texto = "Total de rondas incluidas: " + str(total_rondas)
                                # with BytesIO() as tablageneral_imagen:    
                                #     im.save(tablageneral_imagen, "png")
                                #     tablageneral_imagen.seek(0)
                                #     await application.bot.send_photo(
                                #         chat_id= float(controles['grupo']),
                                #         photo=tablageneral_imagen, 
                                #         caption=texto
                                #         )                                    
                                
    pagos_por_enviar = dbPagos.fetch([{'estado':'confirmado', 'enviado':False }, {'estado':'rechazado', 'enviado':False}])
    # await application.bot.send_message(
    #             float(pagos_por_enviar[0]['usuario']), 
    #             text='Este pago ya fue validado por el tesorero.',
    #             reply_to_message_id=pagos_por_enviar[0]['mensaje']
    #         )
    if pagos_por_enviar.count > 0:
        for pago in pagos_por_enviar.items:
            texto = 'Este pago ya fue ' + pago['estado']+ ' por el tesorero.'
            await application.bot.send_message(
                float(pago['usuario']), 
                text=texto,
                reply_to_message_id=pago['mensaje']
            )
            dbPagos.update(updates={'enviado':True}, key=pago['key'])
    return

app = FastAPI()

@app.post("/webhook")
async def webhook_handler(req: Request):
    controles = dbConfiguracion.get('controles')
    data = await req.json()
    print("entro webhook", data)
    async with application:
        print("entro webhook application", data)
        # set bot commands menu
        ## BotCommand("command", "description")
        await application.bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats)  
        await application.bot.set_my_commands(
            [
                BotCommand("start", "empezar el bot"),
                BotCommand("quiniela", "llenar la quiniela"),
                # BotCommand("favoritos", "escoger lista de pilotos favoritos"),
                BotCommand("mipago", "mandar comprobante pago"),
                BotCommand("help", "mostrar reglas quiniela"),
                BotCommand("cancelar", "cancelar una accion"),
            ]
        )
        await application.bot.set_my_commands(
            [
                BotCommand("quinielas", "quinielas al momento"),
                BotCommand("resultados", "resultados ultima carrera"),
                BotCommand("general", "tabla general"),
                BotCommand("proxima", "cual es la proxima carrera"),
                BotCommand("pagos", "tabla de pagos"),
            ], 
            scope=BotCommandScopeAllGroupChats()
        )
        await application.bot.set_my_commands(
            [
                BotCommand("start", "empezar el bot"),
                BotCommand("quiniela", "llenar la quiniela"),
                # BotCommand("favoritos", "escoger lista de pilotos favoritos"),
                BotCommand("mipago", "mandar comprobante pago"),
                BotCommand("revisarpagos", "revisar pagos pendientes"),
                BotCommand("help", "mostrar reglas quiniela"),
                BotCommand("cancelar", "cancelar una accion"),
            ],
            scope=BotCommandScopeChat(controles['tesorero'])
        )
        await application.start()
        await application.process_update(Update.de_json(data=data, bot=application.bot))
        await application.stop()

@app.post('/__space/v0/actions')
# @app.post("/quinieladb")
async def actions(req: Request):
  data = await req.json()
  event = data['event']
  if event['id'] == 'actualizartablas':
    await pruebapilotos()

# @app.post("/quinieladb")
# async def getpilotos(req: Request):
#     data = await req.json()
#     codigos = data['Lista']
#     pilotos = dbPilotos.get('2023')
#     pilotos = pilotos['Lista']
#     nombres = {}
#     for codigo in codigos.split(','):
#         result=[new_k for new_k in pilotos.items() if new_k[1]['codigo'] == codigo][0][0]
#         nombres[codigo] = pilotos[result]['Nombre'] + ' ' + pilotos[result]['Apellido']
#     return nombres
