import os
from time import sleep
import logging
import pytz
from PIL import Image, ImageDraw, ImageFont
from prettytable import PrettyTable
from deta import Deta
from datetime import datetime
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
from utilidades import *
import numpy as np
import matplotlib.pyplot as plt

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

from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update,
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeChat,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    Bot,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackQueryHandler,
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
# BotToken = os.getenv("BOT_TOKEN")
# bot_hostname = os.getenv("DETA_SPACE_APP_HOSTNAME")
QUINIELA, FAVORITOS, CONFIRMAR_PENALIZACION, SUBIRCOMPROBANTE, GUARDARCOMPROBANTE, VALIDARPAGO, SIGUIENTEPAGO, FINPAGOS, MENU_AYUDA, GUARDAR_PILOTOS, CONFIRMAR_PILOTOS, P1, P2, P3, P4, P5, P6, P7 = range(18)
REGLAS = 'reglas'
AYUDA = 'ayuda'
ultima_carrera = ''
siguiente_carrera = ''
dbPuntosPilotos = deta.Base('PuntosPilotos')
dbCarreras = deta.Base('Carreras')
dbfavoritos = deta.Base("Favoritos")
dbHistorico = deta.Base('Historico')
dbQuiniela = deta.Base("Quiniela")
dbPilotos = deta.Base("Pilotos")
dbPagos = deta.Base('Pagos')
dbConfiguracion= deta.Base('Configuracion')
documentos = deta.Drive('Documentos')
dias_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre','dicembre']
MARKDOWN_SPECIAL_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

async def misaldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    usuario = str(update.message.from_user.id)
    pagos_usuario = dbPagos.fetch([{'usuario':usuario, 'estado':'guardado'},{'usuario':usuario, 'estado':'confirmado'}])
    pagos_guardados = 0
    pagos_confirmados = 0
    for pago in pagos_usuario.items:
        pagos_guardados += int(pago['carreras'])
        if pago['estado'] == 'confirmado':
            pagos_confirmados += int(pago['carreras'])
    carreras = dbCarreras.fetch().count
    texto_mensaje = f'Hasta el momento llevas {pagos_guardados} pagadas ({pagos_confirmados} estan confirmados), para entrar a la /proxima carrera debes tener al menos {carreras} pagadas.'
    await update.message.reply_text(
        texto_mensaje, 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Informar al usuario que es lo que puede hacer"""
    logger.warning('Entro a start')
    texto =  "Bienvenido a la quiniela de F1 usa /quiniela para seleccionar a los pilotos del 1-7, /mipago para subir un comprobante de pago y /help para ver la ayuda. En cualquier momento puedes usar /cancelar para cancelar cualquier comando."
    await update.message.reply_text(
        texto, 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def mihistorico(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Crear tabla con detalle de puntos por carrera de un participante"""
    im, mensaje = await detalle_individual_historico(str(update.message.from_user.id))
    with BytesIO() as tablaindividualhistoricoimagen:
        im.save(tablaindividualhistoricoimagen, "png")
        tablaindividualhistoricoimagen.seek(0)
        await update.message.reply_photo(tablaindividualhistoricoimagen, caption= mensaje)
    return ConversationHandler.END

async def mispuntos(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Crear tabla con detalle de puntos por participante"""
    im, mensaje = await detalle_individual_puntos(str(update.message.from_user.id))
    with BytesIO() as tablaindividualpuntosimagen:    
            im.save(tablaindividualpuntosimagen, "png")
            tablaindividualpuntosimagen.seek(0)
            await update.message.reply_photo(tablaindividualpuntosimagen, caption= mensaje)
    return ConversationHandler.END

async def pagos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando para desplegar la tabla de pagos"""
    carreras = dbCarreras.fetch()
    total_carreras = str(carreras.count)
    configuracion = dbConfiguracion.get('controles')
    tablapagos = PrettyTable()
    tablapagos.title = 'Tabal de pagos'
    tablapagos.field_names = ["Nombre", "Total Rondas", "Rondas Pagadas", "Rondas Confirmadas"]
    tablapagos.sortby = "Nombre"
    datosquiniela = dbQuiniela.fetch()
    for usuarioquiniela in datosquiniela.items:
        pagosusuarios = dbPagos.fetch([{'usuario':usuarioquiniela['key'], 'estado':'guardado'},{'usuario':usuarioquiniela['key'], 'estado':'confirmado'} ])
        rondas_pagadas = 0
        rondas_confirmadas = 0
        for pagousuario in pagosusuarios.items:
            if str(pagousuario['carreras']) == 'Todas':
                rondas_pagadas = configuracion['rondas']
            else:
                rondas_pagadas = int(pagousuario['carreras']) + rondas_pagadas
            if pagousuario['estado'] == 'confirmado':
                if pagousuario['carreras'] == 'Todas':
                    rondas_confirmadas = configuracion['rondas']
                else:
                    rondas_confirmadas = int(pagousuario['carreras']) + rondas_confirmadas
        tablapagos.add_row([usuarioquiniela['Nombre'], configuracion['rondas'], str(rondas_pagadas), str(rondas_confirmadas)]) 
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablapagostamano = dibujo.multiline_textbbox([0,0],str(tablapagos),font=letra)
    im = im.resize((tablapagostamano[2] + 20, tablapagostamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    poner_fondo_gris(dibujo=dibujo, total_filas=datosquiniela.count, largo_fila=tablapagostamano[2])
    dibujo.text((10, 10), str(tablapagos), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablapagostamano[3] + 20), "Ronda actual: " + total_carreras, font=letraabajo, fill="black")

    with BytesIO() as tablapagos_imagen:    
        im.save(tablapagos_imagen, "png")
        tablapagos_imagen.seek(0)
        await update.message.reply_photo(tablapagos_imagen, caption='Tabla de pagos al momento, asegurate de tener ' + total_carreras + ' carreras pagadas para poder entrar sin penalizacion a la /proxima carrera.')
    
    return ConversationHandler.END

async def proxima(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando para desplegar la informacion de la siguiente carrera"""
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
    respuesta = "*" + proxima_nombre + "* \n"
    orden_horarios = ['p1', 'p2', 'p3', 'q', 'r']
    texto_sesion = {'p1':'P1', 'p2':'P2', 'p3':'P3', 'q':'Qualy', 'r':'Carrera','ss':'Sprint Qualy', 's': 'Sprint'}
    if('s' in proxima_Carrera.items[0]):
        orden_horarios = ['p1', 'q', 'ss', 's', 'r']
    for sesion in orden_horarios:
        horario_sesion = datetime.fromisoformat(proxima_Carrera.items[0][sesion]['hora_empiezo'])
        horario_sesion = horario_sesion.astimezone(pytz.timezone('America/Mexico_City'))
        dia_semana = dias_semana[horario_sesion.weekday()]
        mes = meses[horario_sesion.month - 1] 
        hora = horario_sesion.strftime('%H:%M')
        dia_numero = horario_sesion.strftime('%d')
        respuesta = respuesta + "\n" + "*" + texto_sesion[sesion] + ":* " + dia_semana + ", " + dia_numero + " de " + mes + " a las " +  hora + "hrs"
    await update.message.reply_markdown_v2(
        respuesta,
        reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END    

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.warning("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Comando cancelado, puedes empezar de nuevo con el comando /start", 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def help(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("Reglas Quiniela", callback_data=REGLAS),
            InlineKeyboardButton("Ayuda Quiniela", callback_data=AYUDA),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Elige que documento de ayuda necesitas: ", reply_markup=reply_markup)
    return MENU_AYUDA

async def reglas(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    guia_usuario = documentos.get('Reglamento Quiniela fórmula 1.pdf')
    contenido = guia_usuario.read()
    guia_usuario.close()
    await query.edit_message_text(text="Ok, en un nuevo mensaje te envio el documento")
    await context.bot.send_document(
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
    await query.edit_message_text(text="Ok, en un nuevo mensaje te envio el documento")
    await context.bot.send_document(
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
    await update.message.reply_text(
        "Tu pago se ha guardado por " + context.user_data["pago_carreras"] + " carreras" +  ". El tesorero va a revisar la foto del comprobante para confirmarlo",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def subir_comprobante(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    context.user_data["pago_carreras"] = update.message.text
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
    pagos_guardados, pagos_confirmados = await pagos_usuario(str(user.id))
    controles = dbConfiguracion.get('controles')
    resto = int(controles['rondas']) - pagos_guardados
    if resto == 0:
        await update.message.reply_text(
            'Ya cubriste todas las carresas. Puedes meter tu /quiniela sin problema.',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    COLUMNAS = 5
    keyboard = []
    cuenta_columnas = COLUMNAS
    for boton in range(resto):
        if COLUMNAS == cuenta_columnas:
            keyboard.append([])
            cuenta_columnas = 0
        keyboard[len(keyboard) - 1].append(str(boton + 1))
        cuenta_columnas = cuenta_columnas + 1
    # if len(keyboard[len(keyboard) - 1]) < COLUMNAS:
    #     for i in range(COLUMNAS - len(keyboard[len(keyboard) - 1])):
    #         keyboard[len(keyboard) - 1].append('')

    context.user_data["fecha"] = ahora_gdl.isoformat()
    dbPagos.put({'key': context.user_data["fecha"], 'usuario':str(user.id) , 'carreras':'' , 'foto':'' , 'estado':'creado', 'enviado':False})
    await update.message.reply_text(
        '¿Cuantas carreras vas a cubrir con el comprobante de pago?', 
        reply_markup=ReplyKeyboardMarkup(
            keyboard, 
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
        usuario = dbQuiniela.get(pago_confirmar['usuario'])['Nombre']
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
    dbPagos.update(updates={'estado':'confirmado'}, key=context.user_data['pago'])
    context.user_data['procesados'] = context.user_data['procesados'] + 1
    await update.message.reply_text(
            'Pago validado ¿quieres confirmar el siguiente pago?', 
            reply_markup=ReplyKeyboardMarkup(
                [['Si', 'No']], 
                one_time_keyboard=True, 
                )
            )
    return VALIDARPAGO
    
async def pagorechazado(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    dbPagos.update(updates={'estado':'rechazado'}, key=context.user_data['pago'])
    context.user_data['procesados'] = context.user_data['procesados'] + 1
    await update.message.reply_text(
            'Pago rechazado ¿quieres confirmar el siguiente pago?', 
            reply_markup=ReplyKeyboardMarkup(
                [['Si', 'No']], 
                one_time_keyboard=True, 
                )
            )
    return VALIDARPAGO

async def finpagos(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        mensaje = "Aun no es hora de qualy, aqui esta la lista con los que han puesto quiniela para la carrera: "
        if(ahora > horario_qualy):
            enmascarar = False
            mensaje = "Quinielas para ronda: "
        im, carrera_nombre, graficaPilotosPos = await crear_tabla_quinielas(carreras.items[0], enmascarar)
        with BytesIO() as tablaquinielaimagen:    
            im.save(tablaquinielaimagen, "png")
            tablaquinielaimagen.seek(0)
            await update.message.reply_photo(tablaquinielaimagen, caption= mensaje + carrera_nombre)
        if not enmascarar:
            texto = "Grafica de los pilotos para la carrera de " + carrera_nombre
            with BytesIO() as graficaPilotosPos_imagen:    
                graficaPilotosPos.savefig(graficaPilotosPos_imagen)
                graficaPilotosPos_imagen.seek(0)
                await context.bot.send_photo(
                    chat_id = update.message.chat.id,
                    photo=graficaPilotosPos_imagen, 
                    caption=texto
                    )
        return ConversationHandler.END
    await update.message.reply_text(
        'Aun no pasa un dia despues de la ultima carrera, no hay quinielas por mostrar.'
        )
    return ConversationHandler.END

async def general(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    im, total_rondas = await crear_tabla_general()
    with BytesIO() as tablaresutados_imagen:    
        im.save(tablaresutados_imagen, "png")
        tablaresutados_imagen.seek(0)
        await update.message.reply_photo(tablaresutados_imagen, caption="Total de rondas incluidas: " + str(total_rondas) )
    return ConversationHandler.END

async def resultados(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a picture"""
    # aggregar un if, si hay carrera en curso mandar mensaje de espera
    im, texto = await crear_tabla_resultados()
    with BytesIO() as tablaresutados_imagen:    
        im.save(tablaresutados_imagen, "png")
        tablaresutados_imagen.seek(0)
        await update.message.reply_photo(tablaresutados_imagen, caption=texto)
    return ConversationHandler.END

async def inicio_pilotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['Lista'] = []
    puntospilotos = dbPuntosPilotos.fetch()
    pilotoslista = dbPilotos.get('2023')['Lista']
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    if carrera_quiniela.count == 0:
        await update.message.reply_text(
                'Aun no tengo los datos para la siguiente carrera, espera un dia despues que termino la ultima carrera, para mandar la quiniela de la proxima.'
                )
        return ConversationHandler.END
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
            pilotoslista[piloto]['AcumuladoPuntos'] = pilotoslista[piloto]['AcumuladoPuntos'] + carrera['Pilotos'][piloto]['puntos']
    pilotoslista = sorted(pilotoslista.items(), key=lambda item: item[1]['AcumuladoPuntos'], reverse=True)
    # context.user_data['ListaPilotosOrdenada'] = pilotoslista
    COLUMNAS = 5
    keyboard = []
    cuenta_columnas = COLUMNAS
    for pilotonumer in pilotoslista:
        if COLUMNAS == cuenta_columnas:
            keyboard.append([])
            cuenta_columnas = 0
        keyboard[len(keyboard) - 1].append(InlineKeyboardButton(pilotonumer[1]['codigo'], callback_data=pilotonumer[1]['codigo']))
        cuenta_columnas = cuenta_columnas + 1
    if len(keyboard[len(keyboard) - 1]) < COLUMNAS:
        for i in range(COLUMNAS - len(keyboard[len(keyboard) - 1])):
            keyboard[len(keyboard) - 1].append(InlineKeyboardButton(' ', callback_data='NADA'))
    reply_markup = InlineKeyboardMarkup(keyboard)
    nombre_carrera = carrera_quiniela.items[0]['Nombre']
    await update.message.reply_text("Usando los botones de abajo, ve escogiendo los pilotos del P1 a P7 para la carrera: " + nombre_carrera, reply_markup=reply_markup)
    return P1

async def p1(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    hay_boton_atras = False
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    query = update.callback_query
    await query.answer()
    if query.data == 'NADA':
        return None
    if query.data in context.user_data['Lista']:
        return None
    if query.data == 'ATRAS':
        codigo_eliminado = context.user_data['Lista'].pop()
    else:
        context.user_data['Lista'].append(query.data)
    teclado = []
    for fila in update.effective_message.reply_markup.inline_keyboard:
        teclado.append([])
        if len(fila) == 5:
            for boton in fila:
                texto = boton.text
                if len(texto) > 3:
                    texto = boton.text[3:]
                if texto in context.user_data['Lista']:
                    posicion = str(context.user_data['Lista'].index(texto) + 1)
                    texto = 'P' + posicion + ' ' + texto
                teclado[len(teclado) - 1].append(InlineKeyboardButton(text= texto, callback_data=boton.callback_data))
    teclado.append([InlineKeyboardButton("Atras", callback_data='ATRAS')])
    reply_markup = InlineKeyboardMarkup(teclado)
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela.items[0]['Nombre'] + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        await query.edit_message_text(text='Vuelve a empezar con el comando /quiniela')
        return ConversationHandler.END
    return P2

async def p2(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    query = update.callback_query
    await query.answer()
    if query.data == 'NADA':
        return None
    if query.data in context.user_data['Lista']:
        return None
    if query.data == 'ATRAS':
        codigo_eliminado = context.user_data['Lista'].pop()
    else:
        context.user_data['Lista'].append(query.data)
    teclado = []
    for fila in update.effective_message.reply_markup.inline_keyboard:
        teclado.append([])
        if len(fila) == 5:
            for boton in fila:
                texto = boton.text
                if len(texto) > 3 and not texto == 'ATRAS':
                    texto = boton.text[3:]
                if texto in context.user_data['Lista']:
                    posicion = str(context.user_data['Lista'].index(texto) + 1)
                    texto = 'P' + posicion + ' ' + texto
                teclado[len(teclado) - 1].append(InlineKeyboardButton(text= texto, callback_data=boton.callback_data))    
    teclado.append([InlineKeyboardButton("Atras", callback_data='ATRAS')])
    reply_markup = InlineKeyboardMarkup(teclado)
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela.items[0]['Nombre'] + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P1
    return P3

async def p3(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    query = update.callback_query
    await query.answer()
    if query.data == 'NADA':
        return None
    if query.data in context.user_data['Lista']:
        return None
    if query.data == 'ATRAS':
        codigo_eliminado = context.user_data['Lista'].pop()
    else:
        context.user_data['Lista'].append(query.data)
    teclado = []
    for fila in update.effective_message.reply_markup.inline_keyboard:
        teclado.append([])
        if len(fila) == 5:
            for boton in fila:
                texto = boton.text
                if len(texto) > 3:
                    texto = boton.text[3:]
                if texto in context.user_data['Lista']:
                    posicion = str(context.user_data['Lista'].index(texto) + 1)
                    texto = 'P' + posicion + ' ' + texto
                teclado[len(teclado) - 1].append(InlineKeyboardButton(text= texto, callback_data=boton.callback_data))    
    teclado.append([InlineKeyboardButton("Atras", callback_data='ATRAS')])
    reply_markup = InlineKeyboardMarkup(teclado)
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela.items[0]['Nombre'] + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P2
    return P4

async def p4(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    query = update.callback_query
    await query.answer()
    if query.data == 'NADA':
        return None
    if query.data in context.user_data['Lista']:
        return None
    if query.data == 'ATRAS':
        codigo_eliminado = context.user_data['Lista'].pop()
    else:
        context.user_data['Lista'].append(query.data)
    teclado = []
    for fila in update.effective_message.reply_markup.inline_keyboard:
        teclado.append([])
        if len(fila) == 5:
            for boton in fila:
                texto = boton.text
                if len(texto) > 3:
                    texto = boton.text[3:]
                if texto in context.user_data['Lista']:
                    posicion = str(context.user_data['Lista'].index(texto) + 1)
                    texto = 'P' + posicion + ' ' + texto
                teclado[len(teclado) - 1].append(InlineKeyboardButton(text= texto, callback_data=boton.callback_data))
    teclado.append([InlineKeyboardButton("Atras", callback_data='ATRAS')])
    reply_markup = InlineKeyboardMarkup(teclado)
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela.items[0]['Nombre'] + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P3
    return P5

async def p5(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    query = update.callback_query
    await query.answer()
    if query.data == 'NADA':
        return None
    if query.data in context.user_data['Lista']:
        return None
    if query.data == 'ATRAS':
        codigo_eliminado = context.user_data['Lista'].pop()
    else:
        context.user_data['Lista'].append(query.data)
    teclado = []
    for fila in update.effective_message.reply_markup.inline_keyboard:
        teclado.append([])
        if len(fila) == 5:
            for boton in fila:
                texto = boton.text
                if len(texto) > 3:
                    texto = boton.text[3:]
                if texto in context.user_data['Lista']:
                    posicion = str(context.user_data['Lista'].index(texto) + 1)
                    texto = 'P' + posicion + ' ' + texto
                teclado[len(teclado) - 1].append(InlineKeyboardButton(text= texto, callback_data=boton.callback_data))
    teclado.append([InlineKeyboardButton("Atras", callback_data='ATRAS')])
    reply_markup = InlineKeyboardMarkup(teclado)
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela.items[0]['Nombre'] + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P4
    return P6

async def p6(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    query = update.callback_query
    await query.answer()
    if query.data == 'NADA':
        return None
    if query.data in context.user_data['Lista']:
        return None
    if query.data == 'ATRAS':
        codigo_eliminado = context.user_data['Lista'].pop()
    else:
        context.user_data['Lista'].append(query.data)
    teclado = []
    for fila in update.effective_message.reply_markup.inline_keyboard:
        teclado.append([])
        if len(fila) == 5:
            for boton in fila:
                texto = boton.text
                if len(texto) > 3:
                    texto = boton.text[3:]
                if texto in context.user_data['Lista']:
                    posicion = str(context.user_data['Lista'].index(texto) + 1)
                    texto = 'P' + posicion + ' ' + texto
                teclado[len(teclado) - 1].append(InlineKeyboardButton(text= texto, callback_data=boton.callback_data))
    teclado.append([InlineKeyboardButton("Atras", callback_data='ATRAS')])
    reply_markup = InlineKeyboardMarkup(teclado)
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela.items[0]['Nombre'] + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P5
    return P7

async def p7(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    query = update.callback_query
    await query.answer()
    if query.data == 'NADA':
        return None
    if query.data in context.user_data['Lista']:
        return None
    if query.data == 'ATRAS':
        codigo_eliminado = context.user_data['Lista'].pop()
    else:
        context.user_data['Lista'].append(query.data)
    teclado = []
    for fila in update.effective_message.reply_markup.inline_keyboard:
        teclado.append([])
        if len(fila) == 5:
            for boton in fila:
                texto = boton.text
                if len(texto) > 3:
                    texto = boton.text[3:]
                if texto in context.user_data['Lista']:
                    posicion = str(context.user_data['Lista'].index(texto) + 1)
                    texto = 'P' + posicion + ' ' + texto
                teclado[len(teclado) - 1].append(InlineKeyboardButton(text= texto, callback_data=boton.callback_data))
    teclado.append([InlineKeyboardButton("Atras", callback_data='ATRAS')])
    if not query.data == 'ATRAS':
        teclado.append([InlineKeyboardButton("Confirmar", callback_data='CONFIRMAR')])
    reply_markup = InlineKeyboardMarkup(teclado)
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela.items[0]['Nombre'] + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P6
    return GUARDAR_PILOTOS

async def guardar_pilotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    if query.data == 'ATRAS':
        codigo_eliminado = context.user_data['Lista'].pop()
        teclado = []
        for fila in update.effective_message.reply_markup.inline_keyboard:
            teclado.append([])
            if len(fila) == 5:
                for boton in fila:
                    texto = boton.text
                    if len(texto) > 3:
                        texto = boton.text[3:]
                    if texto in context.user_data['Lista']:
                        posicion = str(context.user_data['Lista'].index(texto) + 1)
                        texto = 'P' + posicion + ' ' + texto
                    teclado[len(teclado) - 1].append(InlineKeyboardButton(text= texto, callback_data=boton.callback_data))
        teclado.append([InlineKeyboardButton("Atras", callback_data='ATRAS')])
        reply_markup = InlineKeyboardMarkup(teclado)
        texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela.items[0]['Nombre'] + ':\n' + ",".join(context.user_data['Lista'])
        await query.edit_message_text(text=texto, reply_markup=reply_markup)
        return P7
    user = query.from_user
    data = ",".join(context.user_data['Lista'])
    now = datetime.now()
    now = now.astimezone()
    apellido = ''
    if(user.last_name is not None):
        apellido = ' ' + user.last_name
    dbQuiniela.put({"Carrera": carrera_quiniela.items[0]['key'], "Lista": data, "FechaHora":now.isoformat(), "Nombre":user.first_name + apellido, "key": str(user.id)})
    texto = "Tu lista para la carrera " + carrera_quiniela.items[0]['Nombre'] + " se ha guardado en la base de datos. Quedo de la siguiente manera:\n"
    for index, codigo in enumerate(context.user_data['Lista']):
        texto = texto + 'P' + str(index + 1) + ' ' + codigo + '\n'
    if len(context.user_data['Lista']) > 7:
        texto = 'Hubo un error en la captura, mas de 7 pilotos entraron en tu quiniela. Por favor vuelve con el comando /quiniela a meter una captura.'
    await query.edit_message_text(text=texto)
    return ConversationHandler.END

controles = dbConfiguracion.get('controles')

async def main() -> None:
    """Set up the application and a custom webserver."""
    url = WEBHOOK_URL
    port = PORT
    pilotoslista = dbPilotos.get('2023')['Lista']
    filtropilotos = 'NADA|ATRAS|'
    for pilotonumer in pilotoslista:
        filtropilotos = filtropilotos + '|' + pilotoslista[pilotonumer]['codigo']
    filtropilotos = '^(' + filtropilotos + ')$'
    application = (
        Application.builder().token(BOT_TOKEN).updater(None).build()
    )

    # register handlers
    conv_teclado = ConversationHandler(
        entry_points=[
            CommandHandler("quiniela", inicio_pilotos), 
            CommandHandler("start", start),
            CommandHandler("help", help),
            CommandHandler("quinielas", quinielas),
            CommandHandler("general", general),
            CommandHandler("resultados", resultados),
            CommandHandler("cancelar", cancelar),
            CommandHandler("proxima", proxima),
            CommandHandler("mipago", mipago),
            CommandHandler("pagos", pagos),
            CommandHandler("revisarpagos", revisarpagos),
            CommandHandler("mispuntos", mispuntos),
            CommandHandler("mihistorico", mihistorico),
            CommandHandler("misaldo", misaldo),
            ],
        states={
            # ELEGIR_PILOTOS:[CallbackQueryHandler(elegir_pilotos, pattern=filtropilotos), CallbackQueryHandler(confirmar_pilotos, pattern="^CONFIRMAR$")], 
            P1:[CallbackQueryHandler(p1, pattern=filtropilotos)],
            P2:[CallbackQueryHandler(p2, pattern=filtropilotos) ],
            P3:[CallbackQueryHandler(p3, pattern=filtropilotos) ],
            P4:[CallbackQueryHandler(p4, pattern=filtropilotos) ],
            P5:[CallbackQueryHandler(p5, pattern=filtropilotos) ],
            P6:[CallbackQueryHandler(p6, pattern=filtropilotos) ],
            P7:[CallbackQueryHandler(p7, pattern=filtropilotos) ],
            # CONFIRMAR_PILOTOS:[CallbackQueryHandler(confirmar_pilotos, pattern=filtropilotos), CallbackQueryHandler(p7, pattern='^ATRAS$')],
            GUARDAR_PILOTOS:[CallbackQueryHandler(guardar_pilotos, pattern='^(CONFIRMAR|ATRAS)$')],
            MENU_AYUDA: [CallbackQueryHandler(reglas, pattern="^" + REGLAS + "$"), CallbackQueryHandler(ayuda, pattern="^" + AYUDA + "$")],
            VALIDARPAGO: [MessageHandler(filters.Regex('^Si$'), validarpago), MessageHandler(filters.Regex('^No$'), finpagos)], 
            SIGUIENTEPAGO: [MessageHandler(filters.Regex('^Si$'), pagovalidado), MessageHandler(filters.Regex('^No$'), pagorechazado)], 
            FINPAGOS: [MessageHandler(filters.Regex('^No$'), finpagos)],
            GUARDARCOMPROBANTE: [MessageHandler(filters.PHOTO, guardar_comprobante)], 
            SUBIRCOMPROBANTE: [MessageHandler(filters.Regex('^(1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|Todas)$'), subir_comprobante)],
            },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        # fallbacks=[CallbackQueryHandler(cancelar, pattern="cancelar$")],
        # per_message=True,
        # name="my_conversation",
        # persistent=True,
        # block=False,
    )
    application.add_handler(conv_teclado)

    # Pass webhook settings to telegram
    await application.bot.delete_webhook()
    sleep(3)
    await application.bot.set_webhook(url=f"{url}/telegram", allowed_updates=Update.ALL_TYPES)
    await application.bot.set_my_commands(
        [
            BotCommand("start", "empezar el bot"),
            BotCommand("quiniela", "llenar la quiniela"),
            BotCommand("mipago", "mandar comprobante pago"),
            BotCommand("help", "mostrar reglas quiniela"),
            BotCommand("cancelar", "cancelar una accion"),
            BotCommand("mispuntos", "enviar detalle puntos ultima carrera"),
            BotCommand("mihistorico", "enviar mis puntos por carrera"),
            BotCommand("misaldo", "saber cuantas carreras pagadas tengo"),
        ],
        scope=BotCommandScopeAllPrivateChats()
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
            BotCommand("mipago", "mandar comprobante pago"),
            BotCommand("revisarpagos", "revisar pagos pendientes"),
            BotCommand("help", "mostrar reglas quiniela"),
            BotCommand("cancelar", "cancelar una accion"),
            BotCommand("mispuntos", "detalle puntos ultima carrera"),
            BotCommand("mihistorico", "puntos por carrera"),
            BotCommand("misaldo", "saber cuantas carreras pagadas tengo"),
        ],
        scope=BotCommandScopeChat(controles['tesorero'])
    )
    # Set up webserver
    async def telegram(request: Request) -> Response:
        """Handle incoming Telegram updates by putting them into the `update_queue`"""
        # await application.update_queue.put(
        #     Update.de_json(data=await request.json(), bot=application.bot)
        # )
        logger.warning(str(await request.json()))
        await application.process_update(Update.de_json(data=await request.json(), bot=application.bot))
        return Response()

    async def health(_: Request) -> PlainTextResponse:
        """For the health endpoint, reply with a simple plain text message."""
        return PlainTextResponse(content="The bot is still running fine :)")

    starlette_app = Starlette(
        routes=[
            Route("/telegram", telegram, methods=["POST"]),
            Route("/healthcheck", health, methods=["GET"]),
        ],
    )
    webserver = uvicorn.Server(
        config=uvicorn.Config(
            app=starlette_app,
            port=port,
            use_colors=False,
            host="127.0.0.1",
            # log_level='debug',
        )
    )

    # Run application and webserver together
    async with application:
        await application.start()
        await webserver.serve()
        await application.stop()


if __name__ == "__main__":
    asyncio.run(main())