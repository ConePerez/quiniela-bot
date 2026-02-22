from datetime import datetime, timedelta, time
import time as delay
from environment import INFORMACION_BOTS, DEBUG_MODE, DEPAGO, GRATIS
from telegram import (
    Update,
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,

)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackQueryHandler,
)
from handler import inicio_pilotos, start, help, quinielas, general, resultados, cancelar, proxima, mipago, pagos, revisarpagos, mispuntos, mihistorico, misaldo, p1, p2, p3, p4, p5, p6, p7, guardar_pilotos, reglas, ayuda, revisarpago, confirmarpago, pagorechazado, pagorevisado, pagovalidado, finpagos, subir_comprobante, guardar_comprobante
from job import agregar_nueva_carrera, agregar_qualy_carrera, mandar_resultados, mandar_quinielas
from environment import INFORMACION_BOTS
from config import logger

bot_apps: dict[str, Application] = {}

async def iniciar_todos_bots():
    """Iniciar y encender todos los bots"""
    filtropilotos = '^(NADA|ATRAS|[A-Z]{3})$'
    QUINIELA, FAVORITOS, CONFIRMAR_PENALIZACION, SUBIRCOMPROBANTE, GUARDARCOMPROBANTE, PROCESARPAGO, PAGOREVISADO, PAGOCONFIRMADO, SIGUIENTEPAGOREVISAR, SIGUIENTEPAGOCONFIRMAR, FINPAGOS, MENU_AYUDA, GUARDAR_PILOTOS, CONFIRMAR_PILOTOS, P1, P2, P3, P4, P5, P6, P7 = range(21)
    REGLAS = 'reglas'
    AYUDA = 'ayuda'
    for name, mi_bot in INFORMACION_BOTS.items():
        app = (Application.builder()
               .updater(None)
               .token(mi_bot['token'])
               .build()
               )

        if mi_bot['tipo'] == DEPAGO:
            logger.info("iniciando " + name)
            await app.bot.set_my_commands(
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
            await app.bot.set_my_commands(
                [
                    BotCommand("quinielas", "quinielas al momento"),
                    BotCommand("resultados", "resultados ultima carrera"),
                    BotCommand("general", "tabla general"),
                    BotCommand("proxima", "cual es la proxima carrera"),
                    BotCommand("pagos", "tabla de pagos"),
                ], 
                scope=BotCommandScopeAllGroupChats()
            )
            conversacion_bot = ConversationHandler(
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
                    P1:[CallbackQueryHandler(p1, pattern=filtropilotos)],
                    P2:[CallbackQueryHandler(p2, pattern=filtropilotos) ],
                    P3:[CallbackQueryHandler(p3, pattern=filtropilotos) ],
                    P4:[CallbackQueryHandler(p4, pattern=filtropilotos) ],
                    P5:[CallbackQueryHandler(p5, pattern=filtropilotos) ],
                    P6:[CallbackQueryHandler(p6, pattern=filtropilotos) ],
                    P7:[CallbackQueryHandler(p7, pattern=filtropilotos) ],
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
            )
            app.add_handler(conversacion_bot)
            HORA_ACTUALIZAR = time(hour=14, minute=0, second=0)
            DIAS_SEMANA = (1,2,3)
            if DEBUG_MODE == 'ON':
                HORA_ACTUALIZAR = time(hour=4, minute=45, second=0)
                DIAS_SEMANA = (1,2,3,4,5,6)
            hora_actual = datetime.now()
            hora_actual = hora_actual.astimezone()
            app.bot_data["nombre"] = name
            app.job_queue.run_daily(callback=agregar_nueva_carrera, time=HORA_ACTUALIZAR, days=DIAS_SEMANA, name="AgregarNuevaCarrera")
            app.job_queue.run_repeating(callback=agregar_qualy_carrera, first=hora_actual, last=hora_actual + timedelta(minutes=1.5), interval=60, name="AgregarQualyCarrera")
            INFORMACION_BOTS[name]['filatrabajos'] = app.job_queue
        if mi_bot['tipo'] == GRATIS:
            logger.info("iniciando : " + name)
            await app.bot.set_my_commands(
                [
                    BotCommand("start", "empezar el bot"),
                    BotCommand("quiniela", "llenar la quiniela"),
                    BotCommand("help", "mostrar reglas quiniela"),
                    BotCommand("cancelar", "cancelar una accion"),
                    BotCommand("mispuntos", "enviar detalle puntos ultima carrera"),
                    BotCommand("mihistorico", "enviar mis puntos por carrera"),
                ],
                scope=BotCommandScopeAllPrivateChats()
            )
            conversacion_bot = ConversationHandler(
                entry_points=[
                    CommandHandler("quiniela", inicio_pilotos), 
                    CommandHandler("start", start),
                    CommandHandler("help", help),
                    CommandHandler("quinielas", quinielas),
                    CommandHandler("cancelar", cancelar),
                    CommandHandler("mispuntos", mandar_quinielas),
                    CommandHandler("mihistorico", mandar_resultados),
                    ],
                states={
                    P1:[CallbackQueryHandler(p1, pattern=filtropilotos)],
                    P2:[CallbackQueryHandler(p2, pattern=filtropilotos) ],
                    P3:[CallbackQueryHandler(p3, pattern=filtropilotos) ],
                    P4:[CallbackQueryHandler(p4, pattern=filtropilotos) ],
                    P5:[CallbackQueryHandler(p5, pattern=filtropilotos) ],
                    P6:[CallbackQueryHandler(p6, pattern=filtropilotos) ],
                    P7:[CallbackQueryHandler(p7, pattern=filtropilotos) ],
                    GUARDAR_PILOTOS:[CallbackQueryHandler(guardar_pilotos, pattern='^(CONFIRMAR|ATRAS)$')],
                    MENU_AYUDA: [CallbackQueryHandler(reglas, pattern="^" + REGLAS + "$"), CallbackQueryHandler(ayuda, pattern="^" + AYUDA + "$")],
                    },
                fallbacks=[CommandHandler("cancelar", cancelar)],
            )
            app.add_handler(conversacion_bot)
            HORA_ACTUALIZAR = time(hour=14, minute=0, second=0)
            DIAS_SEMANA = (1,2,3)
            if DEBUG_MODE == 'ON':
                HORA_ACTUALIZAR = time(hour=5, minute=2, second=0)
                DIAS_SEMANA = (1,2,3,4,5,6)
            hora_actual = datetime.now()
            hora_actual = hora_actual.astimezone()
            app.bot_data["nombre"] = name
            app.job_queue.run_daily(callback=agregar_nueva_carrera, time=HORA_ACTUALIZAR, days=DIAS_SEMANA, name="AgregarNuevaCarrera")
            app.job_queue.run_repeating(callback=agregar_qualy_carrera, first=hora_actual, last=hora_actual + timedelta(minutes=1.5), interval=60, name="AgregarQualyCarrera")
            INFORMACION_BOTS[name]['filatrabajos'] = app.job_queue
        await app.initialize()
        await app.start()
        logger.info(f'bot {app.bot.name} iniciado')
        bot_apps[name] = app

async def apagar_todos_bots():
    """Apagar y limpiar todos los bots"""
    for app in bot_apps.values():
        await app.stop()
        await app.shutdown()

async def set_hooks(url):
    """Configurar los bots"""
    for name, mi_bot in INFORMACION_BOTS.items():

        await bot_apps[name].bot.set_webhook(url + "/webhook/" + name)
        logger.info(bot_apps[name].bot.id)
        
async def   procesar_actualizacion_bot(bot_name: str, data: dict):
    """Procesador de actualizaciones modificado"""
    if bot_name not in bot_apps:
        raise ValueError(f"Bot '{bot_name}' no registrado.")
    update = Update.de_json(data, bot_apps[bot_name].bot)
    # bot_apps[bot_name].bot_data["nombre"] = bot_name
    await bot_apps[bot_name].process_update(update)
