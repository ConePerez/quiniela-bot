import os
from time import sleep
import logging
import pytz
from PIL import Image, ImageDraw, ImageFont
from prettytable import PrettyTable
from datetime import datetime
from operator import itemgetter
from io import BytesIO
from telegram import __version__ as TG_VER
from collections import Counter
from utilidades import *
import numpy as np
import matplotlib.pyplot as plt
from models import Usuario, Quiniela, Resultado, Pago, Piloto, PuntosPilotosCarrrera, Carrera, SesionCarrera, Base
from base import engine, Session
from sqlalchemy import or_

from contextlib import asynccontextmanager
from http import HTTPStatus
from fastapi import FastAPI, Request, Response

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

BOT_TOKEN = os.environ.get("TOKEN")
WEBHOOK_URL = "https://parental-giulietta-conesoft-b7c0edc7.koyeb.app/"
QUINIELA, FAVORITOS, CONFIRMAR_PENALIZACION, SUBIRCOMPROBANTE, GUARDARCOMPROBANTE, PROCESARPAGO, PAGOREVISADO, PAGOCONFIRMADO, SIGUIENTEPAGOREVISAR, SIGUIENTEPAGOCONFIRMAR, FINPAGOS, MENU_AYUDA, GUARDAR_PILOTOS, CONFIRMAR_PILOTOS, P1, P2, P3, P4, P5, P6, P7 = range(21)
REGLAS = 'reglas'
AYUDA = 'ayuda'
ultima_carrera = ''
siguiente_carrera = ''
# dbPuntosPilotos = deta.Base('PuntosPilotos')
# dbCarreras = deta.Base('Carreras')
# dbfavoritos = deta.Base("Favoritos")
# dbHistorico = deta.Base('Historico')
# dbQuiniela = deta.Base("Quiniela")
# dbPilotos = deta.Base("Pilotos")
# dbPagos = deta.Base('Pagos')
# dbConfiguracion= deta.Base('Configuracion')
# documentos = deta.Drive('Documentos')
dias_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre','dicembre']
MARKDOWN_SPECIAL_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
tesorero = '5895888783'
TELEGRAM_GROUP = -4542082656
# create all tabless
Base.metadata.create_all(engine)

ptb = (
    Application.builder()
    .updater(None)
    .token(BOT_TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

fila_trabajos = ptb.job_queue

@asynccontextmanager
async def lifespan(_: FastAPI):
    await ptb.bot.setWebhook("https://parental-giulietta-conesoft-b7c0edc7.koyeb.app/") # replace <your-webhook-url>
    await ptb.bot.set_my_commands(
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
    await ptb.bot.set_my_commands(
        [
            BotCommand("quinielas", "quinielas al momento"),
            BotCommand("resultados", "resultados ultima carrera"),
            BotCommand("general", "tabla general"),
            BotCommand("proxima", "cual es la proxima carrera"),
            BotCommand("pagos", "tabla de pagos"),
        ], 
        scope=BotCommandScopeAllGroupChats()
    )
    await ptb.bot.set_my_commands(
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
        scope=BotCommandScopeChat(tesorero)
    )    
    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()

# Initialize FastAPI app (similar to Flask)
app = FastAPI(lifespan=lifespan)

@app.post("/")
async def process_update(request: Request):
    req = await request.json()
    update = Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=HTTPStatus.OK)

@app.get("/test")
async def test():
    return "esto es una prueba"

async def misaldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_usuario = update.message.from_user
    pagos_guardados = 0
    pagos_confirmados = 0
    carreras = 0
    with Session() as sesion:
        usuario = Usuario.obtener_usuario_por_telegram_id(telegram_id=telegram_usuario.id, session=sesion)
        pagos_guardados, pagos_confirmados = pagos_usuario(usuario_pagos=usuario.pagos)
        carreras = len(sesion.query(Carrera).all())
    # pagos_usuario = dbPagos.fetch([{'usuario':usuario, 'estado':'guardado'},{'usuario':usuario, 'estado':'confirmado'}])
    
    # carreras = 0
    # for pago in pagos_usuario.items:
    #     pagos_guardados += int(pago['carreras'])
    #     if pago['estado'] == 'confirmado':
    #         pagos_confirmados += int(pago['carreras'])
    # carreras = dbCarreras.fetch().count
    texto_mensaje = f'Hasta el momento llevas {pagos_guardados + pagos_confirmados} pagadas ({pagos_confirmados} estan confirmados), para entrar a la /proxima carrera debes tener al menos {carreras} pagadas.'
    await update.message.reply_text(
        texto_mensaje, 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Informar al usuario que es lo que puede hacer"""
    with Session() as sesion:
        telegram_id = update.message.from_user.id
        usuario = Usuario.obtener_usuario_por_telegram_id(sesion, telegram_id)
        if not usuario:
            telegram_usuario = update.message.from_user
            usuario_nuevo = Usuario(telegram_id= telegram_usuario.id, nombre=telegram_usuario.first_name, apellido=telegram_usuario.last_name, 
                                    nombre_usuario= telegram_usuario.username)
            sesion.add(usuario_nuevo) 
            sesion.commit()
        texto =  "Bienvenido a la quiniela de F1 usa /quiniela para seleccionar a los pilotos del 1-7, /mipago para subir un comprobante de pago y /help para ver la ayuda. En cualquier momento puedes usar /cancelar para cancelar cualquier comando."
        await update.message.reply_text(
            texto, 
            reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END

async def mihistorico(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Crear tabla con detalle de puntos por carrera de un participante"""
    with Session() as sesion:
        im, mensaje = detalle_individual_historico(sesion=sesion, telegram_id=update.message.from_user.id)
    if mensaje == 'No hay carreras archivadas.':
        await update.message.reply_text(mensaje)
        return ConversationHandler.END
    with BytesIO() as tablaindividualhistoricoimagen:
        im.save(tablaindividualhistoricoimagen, "png")
        tablaindividualhistoricoimagen.seek(0)
        await update.message.reply_photo(tablaindividualhistoricoimagen, caption= mensaje)
    return ConversationHandler.END

async def mispuntos(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Crear tabla con detalle de puntos por participante"""
    with Session() as sesion:
        im, mensaje = detalle_individual_puntos(sesion=sesion, telegram_id=update.message.from_user.id)
    if mensaje == 'No hay carreras archivadas.':
        await update.message.reply_text(mensaje)
        return ConversationHandler.END
    with BytesIO() as tablaindividualpuntosimagen:    
            im.save(tablaindividualpuntosimagen, "png")
            tablaindividualpuntosimagen.seek(0)
            await update.message.reply_photo(tablaindividualpuntosimagen, caption= mensaje)
    return ConversationHandler.END

async def pagos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando para desplegar la tabla de pagos"""
    # carreras = dbCarreras.fetch()
    # total_carreras = str(carreras.count)
    total_carreras = 0
    # configuracion = dbConfiguracion.get('controles')
    tablapagos = PrettyTable()
    tablapagos.title = 'Tabal de pagos'
    tablapagos.field_names = ["Nombre", "Total Rondas", "Rondas Pagadas", "Rondas Confirmadas"]
    tablapagos.sortby = "Nombre"
    # datosquiniela = dbQuiniela.fetch()
    # for usuarioquiniela in datosquiniela.items:
    #     pagosusuarios = dbPagos.fetch([{'usuario':usuarioquiniela['key'], 'estado':'guardado'},{'usuario':usuarioquiniela['key'], 'estado':'confirmado'} ])
    #     rondas_pagadas = 0
    #     rondas_confirmadas = 0
    #     for pagousuario in pagosusuarios.items:
    #         if str(pagousuario['carreras']) == 'Todas':
    #             rondas_pagadas = configuracion['rondas']
    #         else:
    #             rondas_pagadas = int(pagousuario['carreras']) + rondas_pagadas
    #         if pagousuario['estado'] == 'confirmado':
    #             if pagousuario['carreras'] == 'Todas':
    #                 rondas_confirmadas = configuracion['rondas']
    #             else:
    #                 rondas_confirmadas = int(pagousuario['carreras']) + rondas_confirmadas
    #     tablapagos.add_row([usuarioquiniela['Nombre'], configuracion['rondas'], str(rondas_pagadas), str(rondas_confirmadas)]) 
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablapagostamano = dibujo.multiline_textbbox([0,0],str(tablapagos),font=letra)
    im = im.resize((tablapagostamano[2] + 20, tablapagostamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    # poner_fondo_gris(dibujo=dibujo, total_filas=datosquiniela.count, largo_fila=tablapagostamano[2])
    dibujo.text((10, 10), str(tablapagos), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablapagostamano[3] + 20), "Ronda actual: " + str(total_carreras), font=letraabajo, fill="black")

    with BytesIO() as tablapagos_imagen:    
        im.save(tablapagos_imagen, "png")
        tablapagos_imagen.seek(0)
        await update.message.reply_photo(tablapagos_imagen, caption='Tabla de pagos al momento, asegurate de tener ' + str(total_carreras) + ' carreras pagadas para poder entrar sin penalizacion a la /proxima carrera.')
    
    return ConversationHandler.END

async def proxima(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando para desplegar la informacion de la siguiente carrera"""
    # proxima_Carrera = dbCarreras.fetch([{'Estado':'IDLE'},{'Estado':'EN-CURSO'}])
    proxima_carrera = None
    sesiones_carrera_quiniela = None
    with Session() as sesion:
        proxima_carrera = sesion.query(Carrera).filter(or_(Carrera.estado == "IDLE", Carrera.estado == "EN-CURSO")).first()
        if proxima_carrera:
            sesiones_carrera_quiniela = proxima_carrera.sesioncarreras
    if not proxima_carrera:
        await update.message.reply_text(
            'Todavia no se actualiza mi base de datos con la proxima carrera. Por lo general se actualiza un dia despues de que termino la ultima carrera.'
        )
        return ConversationHandler.END
    proxima_nombre = proxima_carrera.nombre
    for char in MARKDOWN_SPECIAL_CHARS:
        if char in proxima_nombre:
            proxima_nombre = proxima_nombre.replace(char, "\\" + char)
    respuesta = "*" + proxima_nombre + "* \n"
    texto_sesion = {'p1':'P1', 'p2':'P2', 'p3':'P3', 'q':'Qualy', 'r':'Carrera','ss':'Sprint Qualy', 's': 'Sprint'}
    sesiones_carrera_quiniela.sort(key=lambda x: x.hora_empiezo)
    for sesion_carrera in sesiones_carrera_quiniela:
        horario_sesion = sesion_carrera.hora_empiezo
        horario_sesion = horario_sesion.astimezone(pytz.timezone('America/Mexico_City'))
        dia_semana = dias_semana[horario_sesion.weekday()]
        mes = meses[horario_sesion.month - 1] 
        hora = horario_sesion.strftime('%H:%M')
        dia_numero = horario_sesion.strftime('%d')
        respuesta = respuesta + "\n" + "*" + texto_sesion[sesion_carrera.codigo] + ":* " + dia_semana + ", " + dia_numero + " de " + mes + " a las " +  hora + "hrs"
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
    mensaje_texto = ''
    pago_id = context.user_data["pago_id"]
    if update.effective_message.caption is None:
        mensaje_texto = 'Sin mensaje'
    else:
        mensaje_texto = update.effective_message.caption
    usuario = update.message.from_user.first_name
    with Session() as sesion:
        pago = sesion.get(Pago, pago_id)
        pago.foto = photo_id
        pago.estado = 'guardado'
        pago.mensaje = mensaje
        pago.texto = mensaje_texto
        sesion.commit()
    # dbPagos.update(updates={'foto':photo_id, 'estado':'guardado', 'mensaje':mensaje, 'texto':mensaje_texto, 'nombre':usuario}, key=context.user_data["fecha"])
        await update.message.reply_text(
            "Tu pago se ha guardado por " + context.user_data["pago_carreras"] + " carreras" +  ". El tesorero va a revisar la foto del comprobante para confirmarlo",
            reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END

async def subir_comprobante(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    context.user_data["pago_carreras"] = update.message.text
    # dbPagos.update(updates={'carreras':context.user_data["pago_carreras"], 'estado':'sinfoto'}, key=context.user_data["fecha"])
    pago_id = context.user_data["pago_id"]
    with Session() as sesion:
        pago = sesion.get(Pago, pago_id)
        pago.carreras = int(context.user_data["pago_carreras"])
        pago.estado = 'sinfoto'
        sesion.commit()
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
    usuario_pagos = None
    with Session() as sesion:
        usuario = Usuario.obtener_usuario_por_telegram_id(session=sesion, telegram_id=user.id)
        usuario_pagos = usuario.pagos
        pagos_guardados, pagos_confirmados = pagos_usuario(usuario_pagos)
        # controles = dbConfiguracion.get('controles')
        resto = 24 - (pagos_guardados + pagos_confirmados)
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

        
        nuevo_pago = Pago(fecha_hora=ahora, usuario_id=usuario.id, carreras=0, enviado=False, estado='creado', foto='', mensaje='', texto='0')
        sesion.add(nuevo_pago)
        sesion.commit()
        context.user_data["pago_id"] = nuevo_pago.id
        await update.message.reply_text(
            '¿Cuantas carreras vas a cubrir con el comprobante de pago?', 
            reply_markup=ReplyKeyboardMarkup(
                keyboard, 
                one_time_keyboard=True, 
                input_field_placeholder="Numero de carreras:")
            )
    return SUBIRCOMPROBANTE

async def revisarpagos(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_usuario = update.message.from_user
    # pagos_guardados = dbPagos.fetch({'estado':'guardado'})
    # pagos_en_revision = dbPagos.fetch({'estado':'revision'})
    pagos_guardados = 0
    pagos_en_revision = 0
    with Session() as sesion:
        pagos_guardados = len(sesion.query(Pago).filter(Pago.estado == 'guardado').all() )
        pagos_en_revision = len(sesion.query(Pago).filter(Pago.estado == 'revision').all() )
    # pagos_por_revisar = str(pagos_guardados.count)
    # pagos_por_confirmar = str(pagos_en_revision.count)
    context.user_data['procesados'] = 0
    if pagos_guardados == 0 and pagos_en_revision == 0:
        await update.message.reply_text(
        "No hay pagos por revisar o confirmar", 
        reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    await update.message.reply_text(
        'Hay ' + str(pagos_guardados) + ' pagos por revisar y hay ' + str(pagos_en_revision) + ' pagos por confirmar ¿Que quieres hacer?', 
        reply_markup=ReplyKeyboardMarkup(
            [['Revisar', 'Confirmar', 'Cancelar']], 
            one_time_keyboard=True, 
            )
        )
    return PROCESARPAGO

async def revisarpago(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pago_revisar = None
    usuario = None
    with Session() as sesion:
        pago_revisar = sesion.query(Pago).filter(Pago.estado == 'guardado').first()
        if pago_revisar:
            usuario = sesion.get(Usuario, pago_revisar.usuario_id)
    if not pago_revisar:
        pagos_procesados = str(context.user_data['procesados'])
        await update.message.reply_text(
            'Revisaste ' + pagos_procesados + ' pagos, ya no quedan mas pagos por revisar.',
            reply_markup=ReplyKeyboardRemove()
            )
        return ConversationHandler.END
    else:
        # pago_revisar = pagos_guardados[0]
        numero_carreras = pago_revisar.carreras
        texto = pago_revisar.texto
        # usuario = pago_revisar.nombre
        context.user_data["pago"] = pago_revisar.id
        await update.message.reply_photo(
            pago_revisar.foto, 
            caption='Marcar como revisado este pago por ' + str(numero_carreras) + ' carreras, enviado por ' + usuario.nombre + ' con el siguiente mensaje: "' + texto + '"',
            reply_markup=ReplyKeyboardMarkup(
                [['Si', 'No']], 
                one_time_keyboard=True, 
                )
            )
        return PAGOREVISADO

async def confirmarpago(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # pagos_guardados = dbPagos.fetch({'estado':'revision'})
    pago_confirmar = None
    usuario = None
    with Session() as sesion:
        pago_confirmar = sesion.query(Pago).filter(Pago.estado == 'revision').first()
        if pago_confirmar:
            usuario = sesion.get(Usuario, pago_confirmar.usuario_id)
    if not pago_confirmar:
        pagos_procesados = str(context.user_data['procesados'])
        await update.message.reply_text(
            'Validaste ' + pagos_procesados + ' pagos, ya no quedan mas pagos por validar.',
            reply_markup=ReplyKeyboardRemove()
            )
        return ConversationHandler.END
    else:
        # pago_confirmar = pagos_guardados.items[0]
        numero_carreras = pago_confirmar.carreras
        texto = pago_confirmar.texto
        # usuario = pago_confirmar['nombre']
        context.user_data["pago"] = pago_confirmar.id
        await update.message.reply_photo(
            pago_confirmar.foto, 
            caption='Confirmas este pago por ' + str(numero_carreras) + ' carreras, enviado por ' + usuario.nombre + ' con el siguiente mensaje: "' + texto + '"',
            reply_markup=ReplyKeyboardMarkup(
                [['Si', 'No']], 
                one_time_keyboard=True, 
                )
            )
        return PAGOCONFIRMADO

async def pagorevisado(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # dbPagos.update(updates={'estado':'revision'}, key=context.user_data['pago'])
    with Session() as sesion:
        pago_revisado = sesion.get(Pago, context.user_data['pago'])
        pago_revisado.estado = 'revision'
        sesion.commit()
        context.user_data['procesados'] = context.user_data['procesados'] + 1
        await update.message.reply_text(
                'Pago revisado ¿quieres procesar otro pago?', 
                reply_markup=ReplyKeyboardMarkup(
                    [['Si', 'No']], 
                    one_time_keyboard=True, 
                    )
                )
    return SIGUIENTEPAGOREVISAR

async def pagovalidado(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # dbPagos.update(updates={'estado':'confirmado'}, key=context.user_data['pago'])
    with Session() as sesion:
        pago_validado = sesion.get(Pago, context.user_data['pago'])
        pago_validado.estado = 'confirmado'
        sesion.commit()
        context.user_data['procesados'] = context.user_data['procesados'] + 1
        await update.message.reply_text(
                'Pago validado ¿quieres procesar otro pago?', 
                reply_markup=ReplyKeyboardMarkup(
                    [['Si', 'No']], 
                    one_time_keyboard=True, 
                    )
                )
    return SIGUIENTEPAGOCONFIRMAR
    
async def pagorechazado(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # dbPagos.update(updates={'estado':'rechazado'}, key=context.user_data['pago'])
    with Session() as sesion:
        pago_rechazado = sesion.get(Pago, context.user_data['pago'])
        context.user_data['procesados'] = context.user_data['procesados'] + 1
        await update.message.reply_text(
                'Pago rechazado ¿quieres procesar otro pago?', 
                reply_markup=ReplyKeyboardMarkup(
                    [['Si', 'No']], 
                    one_time_keyboard=True, 
                    )
                )
    return SIGUIENTEPAGOCONFIRMAR

async def finpagos(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # pagos_pendientes_por_revisar = str(dbPagos.fetch({'estado':'guardado'}).count)
    # pagos_pendientes_por_validar = str(dbPagos.fetch({'estado':'revision'}).count)
    pagos_pendientes_por_revisar = 0
    pagos_pendientes_por_validar = 0
    with Session() as sesion:
        pagos_pendientes_por_revisar = len(sesion.query(Pago).filter(Pago.estado == 'guardado').all() )
        pagos_pendientes_por_validar = len(sesion.query(Pago).filter(Pago.estado == 'revision').all() )
    pagos_procesados = str(context.user_data['procesados'])
    await update.message.reply_text(
        'Revisaste o validaste ' + pagos_procesados + ' pagos, quedan pendientes ' + str(pagos_pendientes_por_revisar) + ' por revisar y ' + str(pagos_pendientes_por_validar) + ' por validar. Puedes volver a validar con /revisarpagos', 
        reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END

async def quinielas(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a picture"""   
    carrera = None
    with Session() as sesion:
        carrera = sesion.query(Carrera).filter(Carrera.estado == 'EN-CURSO' | Carrera.estado == 'IDLE').first()
    if len(carrera) > 0:
        horario_qualy = datetime.fromisoformat(carrera.hora_empiezo)
        ahora = datetime.now()
        ahora = ahora.astimezone()
        enmascarar = True
        mensaje = "Aun no es hora de qualy, aqui esta la lista con los que han puesto quiniela para la carrera: "
        if(ahora > horario_qualy):
            enmascarar = False
            mensaje = "Quinielas para ronda: "
        im, graficaPilotosPos = await crear_tabla_quinielas(carrera_en_curso=carrera, enmascarada=enmascarar)
        if graficaPilotosPos == 'No hay carreras archivadas.':
            await update.message.reply_text(graficaPilotosPos)
            return ConversationHandler.END
        with BytesIO() as tablaquinielaimagen:    
            im.save(tablaquinielaimagen, "png")
            tablaquinielaimagen.seek(0)
            await update.message.reply_photo(tablaquinielaimagen, caption= mensaje + carrera.nombre)
        if not enmascarar:
            texto = "Grafica de los pilotos para la carrera de " + carrera.nombre
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
    with Session() as sesion:
        im, total_rondas = crear_tabla_general(sesion=sesion)
    if total_rondas == 0:
        await update.message.reply_text('No hay carreras archivadas.')
        return ConversationHandler.END
    with BytesIO() as tablaresutados_imagen:    
        im.save(tablaresutados_imagen, "png")
        tablaresutados_imagen.seek(0)
        await update.message.reply_photo(tablaresutados_imagen, caption="Total de rondas incluidas: " + str(total_rondas) )
    return ConversationHandler.END

async def resultados(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a picture"""
    # aggregar un if, si hay carrera en curso mandar mensaje de espera
    with Session() as sesion:
        im, texto = crear_tabla_resultados(carrera=None, sesion=sesion)
    if texto == 'No hay carreras archivadas.':
        await update.message.reply_text(texto)
        return ConversationHandler.END
    with BytesIO() as tablaresutados_imagen:    
        im.save(tablaresutados_imagen, "png")
        tablaresutados_imagen.seek(0)
        await update.message.reply_photo(tablaresutados_imagen, caption=texto)
    return ConversationHandler.END

async def inicio_pilotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['Lista'] = []
    pilotos = None
    carrera_quiniela = None
    sesiones_carrera_quiniela = None
    with Session() as sesion:
        pilotos = Piloto.obtener_pilotos(sesion)
        carrera_quiniela =  sesion.query(Carrera).filter(or_(Carrera.estado == 'IDLE', Carrera.estado == 'EN-CURSO')).first()
        if carrera_quiniela:
            sesiones_carrera_quiniela = carrera_quiniela.sesioncarreras    
    # puntospilotos = dbPuntosPilotos.fetch()
    # pilotoslista = dbPilotos.get('2024')['Lista']
    # carrera_quiniela = dbCarreras.fetch([{'Estado':'IDLE'}, {'Estado':'EN-CURSO'}])
    if not carrera_quiniela:
        await update.message.reply_text(
                'Aun no tengo los datos para la siguiente carrera, espera un dia despues que termino la ultima carrera, para mandar la quiniela de la proxima.'
                )
        return ConversationHandler.END
    # horario_qualy = datetime.fromisoformat(carrera_quiniela.items[0]['q']['hora_empiezo'])
    horario_qualy = None
    for sesion_carrera in sesiones_carrera_quiniela:
            if sesion_carrera.codigo == 'q':
                horario_qualy = sesion_carrera.hora_empiezo
    ahora = datetime.now()
    ahora = ahora.astimezone()
    if(ahora > horario_qualy):
        await update.message.reply_text(
            'Ya no se puede modificar o ingresar una quiniela porque la qualy ya empezo. Si no metiste quiniela, se te penalizara con base a las reglas. Usa /help para ver las reglas.'
            )
        return ConversationHandler.END
    # for carrera in puntospilotos.items:
    #     for piloto in carrera['Pilotos']:
    #         pilotoslista[piloto]['AcumuladoPuntos'] = pilotoslista[piloto]['AcumuladoPuntos'] + carrera['Pilotos'][piloto]['puntos']
    # pilotoslista = sorted(pilotoslista.items(), key=lambda item: item[1]['AcumuladoPuntos'], reverse=True)
    # context.user_data['ListaPilotosOrdenada'] = pilotoslista
    pilotos.sort(key=lambda x: x.codigo, reverse=True)
    COLUMNAS = 5
    keyboard = []
    cuenta_columnas = COLUMNAS
    for piloto in pilotos:
        if COLUMNAS == cuenta_columnas:
            keyboard.append([])
            cuenta_columnas = 0
        keyboard[len(keyboard) - 1].append(InlineKeyboardButton(piloto.codigo, callback_data=piloto.codigo))
        cuenta_columnas = cuenta_columnas + 1
    if len(keyboard[len(keyboard) - 1]) < COLUMNAS:
        for i in range(COLUMNAS - len(keyboard[len(keyboard) - 1])):
            keyboard[len(keyboard) - 1].append(InlineKeyboardButton(' ', callback_data='NADA'))
    reply_markup = InlineKeyboardMarkup(keyboard)
    nombre_carrera = carrera_quiniela.nombre
    context.user_data['NombreCarrera'] = nombre_carrera
    context.user_data['ID_Carrera'] = carrera_quiniela.id
    await update.message.reply_text("Usando los botones de abajo, ve escogiendo los pilotos del P1 a P7 para la carrera: " + nombre_carrera, reply_markup=reply_markup)
    return P1

async def p1(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    hay_boton_atras = False
    carrera_quiniela = context.user_data['NombreCarrera']
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
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        await query.edit_message_text(text='Vuelve a empezar con el comando /quiniela')
        return ConversationHandler.END
    return P2

async def p2(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = context.user_data['NombreCarrera']
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
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P1
    return P3

async def p3(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = context.user_data['NombreCarrera']
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
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P2
    return P4

async def p4(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = context.user_data['NombreCarrera']
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
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P3
    return P5

async def p5(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = context.user_data['NombreCarrera']
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
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P4
    return P6

async def p6(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = context.user_data['NombreCarrera']
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
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P5
    return P7

async def p7(update:Update, context:ContextTypes.DEFAULT_TYPE) -> int:
    carrera_quiniela = context.user_data['NombreCarrera']
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
    texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela + ':\n' + ",".join(context.user_data['Lista'])
    await query.edit_message_text(text=texto, reply_markup=reply_markup)       
    if query.data == 'ATRAS':
        return P6
    return GUARDAR_PILOTOS

async def guardar_pilotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with Session() as sesion:
        query = update.callback_query
        await query.answer()
        carrera_quiniela = context.user_data['NombreCarrera']
        carrera_quiniela_id = context.user_data['ID_Carrera']
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
            texto = 'Asi va tu lista de pilotos (de P1 a P7) para la carrera ' + carrera_quiniela + ':\n' + ",".join(context.user_data['Lista'])
            await query.edit_message_text(text=texto, reply_markup=reply_markup)
            return P7
        user = query.from_user
        data = ",".join(context.user_data['Lista'])
        now = datetime.now()
        now = now.astimezone()
        apellido = ''
        if(user.last_name is not None):
            apellido = ' ' + user.last_name
    
        usuario = Usuario.obtener_usuario_por_telegram_id(sesion, user.id)
        quiniela = sesion.query(Quiniela).filter(Quiniela.usuario_id == usuario.id).first()
        if not quiniela:
            nueva_quiniela = Quiniela(usuario_id=usuario.id, carrera_id= carrera_quiniela_id, fecha_hora=now, lista=data)
            sesion.add(nueva_quiniela)
        else:
            quiniela.carrera_id = carrera_quiniela_id
            quiniela.fecha_hora = now
            quiniela.lista = data
        sesion.commit()
        texto = "Tu lista para la carrera " + carrera_quiniela + " se ha guardado en la base de datos. Quedo de la siguiente manera:\n"
        for index, codigo in enumerate(context.user_data['Lista']):
            texto = texto + 'P' + str(index + 1) + ' ' + codigo + '\n'
        if len(context.user_data['Lista']) > 7:
            texto = 'Hubo un error en la captura, mas de 7 pilotos entraron en tu quiniela. Por favor vuelve con el comando /quiniela a meter una captura.'
        await query.edit_message_text(text=texto)
    return ConversationHandler.END

    # register handlers

filtropilotos = 'NADA|ATRAS'
with Session() as sesion:
    pilotos = sesion.query(Piloto).all()
    for piloto in pilotos:
        filtropilotos = filtropilotos + "|" + piloto.codigo
filtropilotos = '^(' + filtropilotos + ')$'
logger.info(filtropilotos)
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
        PROCESARPAGO: [MessageHandler(filters.Regex('^Revisar$'), revisarpago), MessageHandler(filters.Regex('^Confirmar$'), confirmarpago), MessageHandler(filters.Regex('^Cancelar$'), finpagos)], 
        PAGOREVISADO: [MessageHandler(filters.Regex('^Si$'), pagorevisado), MessageHandler(filters.Regex('^No$'), revisarpagos)],
        PAGOCONFIRMADO: [MessageHandler(filters.Regex('^Si$'), pagovalidado), MessageHandler(filters.Regex('^No$'), pagorechazado)],
        SIGUIENTEPAGOREVISAR: [MessageHandler(filters.Regex('^Si$'), revisarpago), MessageHandler(filters.Regex('^No$'), finpagos)],
        SIGUIENTEPAGOCONFIRMAR: [MessageHandler(filters.Regex('^Si$'), confirmarpago), MessageHandler(filters.Regex('^No$'), finpagos)],  
        FINPAGOS: [MessageHandler(filters.Regex('^No$'), finpagos)],
        GUARDARCOMPROBANTE: [MessageHandler(filters.PHOTO, guardar_comprobante)], 
        SUBIRCOMPROBANTE: [MessageHandler(filters.Regex('^(1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24)$'), subir_comprobante)],
        },
    fallbacks=[CommandHandler("cancelar", cancelar)],
    # fallbacks=[CallbackQueryHandler(cancelar, pattern="cancelar$")],
    # per_message=True,
    # name="my_conversation",
    # persistent=True,
    # block=False,
)
ptb.add_handler(conv_teclado)

async def enviar_pagos(context: ContextTypes.DEFAULT_TYPE):
    pagos_por_enviar = None
    with Session() as sesion:
        pagos_por_enviar = sesion.query(Pago).filter(Pago.estado == 'confirmado' & Pago.enviado == False).all()
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

async def actualizar_tablas(context: ContextTypes.DEFAULT_TYPE):
    F1_API_KEY = 'qPgPPRJyGCIPxFT3el4MF7thXHyJCzAP'
    urlevent_tracker = 'https://api.formula1.com/v1/event-tracker' 
    headerapi = {'apikey':F1_API_KEY, 'locale':'en'}
    urllivetiming = 'https://livetiming.formula1.com/static/'
    hora_actual = datetime.now()
    hora_actual = hora_actual.astimezone()
    encurso_siguiente_Carrera = None
    with Session() as sesion:
        encurso_siguiente_Carrera = sesion.query(Carrera).filter(or_(Carrera.estado == 'IDLE', Carrera.estado == 'EN-CURSO')).first()
        if not encurso_siguiente_Carrera:
            response = requests.get(url=urlevent_tracker, headers=headerapi)
            response.encoding = 'utf-8-sig'
            response_dict = response.json()
            carrera_codigo_eventtracker = sesion.query(Carrera).filter(Carrera.codigo == response_dict['fomRaceId']).first()
            rondas_archivadas = len(sesion.query(Carrera).filter(or_(Carrera.estado == "ARCHIVADA", Carrera.estado == 'CANCELADA')).all())
            if not carrera_codigo_eventtracker:
                es_valida = True
                carrera_codigo = response_dict['fomRaceId']
                carrera_nombre = response_dict['race']['meetingOfficialName']
                carrera_estado = response_dict['seasonContext']['state']
                carrera_empiezo = response_dict['race']['meetingStartDate']
                carrera_empiezo = carrera_empiezo.replace('Z', '+00:00')
                carrera_termino = response_dict['race']['meetingEndDate']
                carrera_termino = carrera_termino.replace('Z','+00:00')
                nueva_carrera = Carrera(codigo=carrera_codigo, nombre=carrera_nombre, hora_empiezo=carrera_empiezo, hora_termino=carrera_termino, estado=carrera_estado, url='', ronda=rondas_archivadas+1)
                sesion.add(nueva_carrera)
                sesion.flush()
                logger.info(str(nueva_carrera.id))
                nuevas_sesiones = []
                for session in range(len(response_dict['seasonContext']['timetables'])):
                    session_row = response_dict['seasonContext']['timetables'][session]
                    if session_row['startTime'] == 'TBC':
                        es_valida = False
                    nuevas_sesiones.append( SesionCarrera(codigo=session_row['session'], carrera_id=nueva_carrera.id, estado=session_row['state'], 
                                                 hora_empiezo=session_row['startTime']+session_row['gmtOffset'], hora_termino=session_row['endTime']+session_row['gmtOffset']))
                if es_valida:
                    sesion.add_all(nuevas_sesiones)
                    sesion.commit()
        else:
            if encurso_siguiente_Carrera.estado == 'IDLE':
                if hora_actual > encurso_siguiente_Carrera.hora_empiezo:
                    encurso_siguiente_Carrera.estado = "EN-CURSO"
                    sesion.commit()
            else:
                sesion_qualy = None
                for sesion_carrera in encurso_siguiente_Carrera.sesioncarreras:
                    if sesion_carrera.codigo == 'q':
                        sesion_qualy = sesion_carrera
                if hora_actual >= sesion_qualy.hora_empiezo and sesion_qualy.estado == 'upcoming':
                    archivar_quinielas_participante(sesion, encurso_siguiente_Carrera)
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
                    sesion_qualy.estado = 'EMPEZADA'
                    sesion.commit()
                if hora_actual > encurso_siguiente_Carrera.hora_termino:
                    response = requests.get(url=urlevent_tracker, headers=headerapi)
                    response.encoding = 'utf-8-sig'
                    response_dict = response.json()
                    links = []
                    if('links' in response_dict):
                        links = response_dict['links']                                
                        url_results_index = next((index for (index, d) in enumerate(links) if d["text"] == "RESULTS"), None)
                        if(not(url_results_index is None)):
                            url_results = links[url_results_index]['url']                        
                            posiciones_dict, pilotos_con_puntos = obtener_resultados(sesion, url_results, encurso_siguiente_Carrera)
                            if pilotos_con_puntos >= 10:
                                archivar_puntos_participante(sesion, encurso_siguiente_Carrera, posiciones_dict)
                                im, texto = crear_tabla_resultados(sesion, encurso_siguiente_Carrera)
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
                                im, total_rondas = crear_tabla_general()
                                texto = "Total de rondas incluidas: " + str(total_rondas)
                                with BytesIO() as tablageneral_imagen:    
                                    im.save(tablageneral_imagen, "png")
                                    tablageneral_imagen.seek(0)
                                    await context.bot.send_photo(
                                        chat_id= TELEGRAM_GROUP,
                                        photo=tablageneral_imagen, 
                                        caption=texto
                                        )
                                encurso_siguiente_Carrera.estado = 'ARCHIVADA'
                                sesion.flush()
                            sesion.commit()
    return

fila_trabajos.run_repeating(enviar_pagos, interval=600)
fila_trabajos.run_repeating(actualizar_tablas, interval=600)
