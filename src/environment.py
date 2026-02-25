import os
from pyngrok import ngrok
import models_db_1
import models_db_2

DEPAGO, GRATIS = range(2)
DEBUG_MODE = os.environ.get("DEBUG_MODE")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_HOST_TEST = os.environ.get("DB_HOST_TEST")
WEBHOOK_URL = "https://parental-giulietta-conesoft-b7c0edc7.koyeb.app/"
WEBHOOK_URL_TEST = ""
if DEBUG_MODE == "ON":
    NGROK_PORT = 8000
    NGROK_TOKEN = os.environ.get("NGROK_TOKEN")
    ngrok.set_auth_token(NGROK_TOKEN)
    http_tunnel = ngrok.connect(NGROK_PORT, bind_tls=True)
    public_url = http_tunnel.public_url
    WEBHOOK_URL_TEST = public_url
F1_API_KEY = 'fCUCjWrKPu9ylJwRAv8BpGLEgiAuThx7'

INFORMACION_BOTS = {
    "Bot1":{"token": os.environ.get("BOT1_TOKEN"), "basededatos":os.environ.get("BOT1_BASEDATOS"), "tipo":DEPAGO, "filatrabajos":"", "telegramgroup": int(os.environ.get("BOT1_GROUP")), "tesorero": int(os.environ.get("BOT1_TESORERO")), "documentos":{"ayuda": "Quiniela Formula 1.pdf", "reglas":"Reglas Quiniela.pdf"}, "sesion":"", "engine":"", "modelo":"","tablas":{"usuario":models_db_1.Usuario, "quiniela":models_db_1.Quiniela, "resultado":models_db_1.Resultado, "pago":models_db_1.Pago, "piloto":models_db_1.Piloto, "puntospilotocarrera":models_db_1.PuntosPilotosCarrrera, "carrera":models_db_1.Carrera, "sesioncarrera":models_db_1.SesionCarrera, "base":models_db_1.Base, "historicoquiniela":models_db_1.HistoricoQuiniela}, "textostart":"Bienvenido a la quiniela de F1 usa /quiniela para seleccionar a los pilotos del 1-7, /mipago para subir un comprobante de pago, /misaldo para saber cuantas carreras tienes pagadas, /mispuntos para ver como se calculo la puntuacion de la ultima carrera, /mihistorico para ver los puntos que has obtenido en todas las carreras y /help para ver la ayuda. En cualquier momento puedes usar /cancelar para cancelar cualquier comando."}, 
    "Bot2":{"token": os.environ.get("BOT2_TOKEN"), "basededatos":os.environ.get("BOT2_BASEDATOS"), "tipo":GRATIS, "filatrabajos":"", "telegramgroup": int(os.environ.get("BOT2_GROUP")), "documentos":{"ayuda": "quinielaformulera.pdf", "reglas": "reglasquiniela.pdf"}, "sesion":"", "engine":"", "modelo":"","tablas":{"usuario":models_db_2.Usuario, "quiniela":models_db_2.Quiniela, "resultado":models_db_2.Resultado, "piloto":models_db_2.Piloto, "puntospilotocarrera":models_db_2.PuntosPilotosCarrrera, "carrera":models_db_2.Carrera, "sesioncarrera":models_db_2.SesionCarrera, "base":models_db_2.Base, "historicoquiniela":models_db_2.HistoricoQuiniela}, "textostart":"Bienvenido a la quiniela de F1 usa /quiniela para seleccionar a los pilotos del 1-7, /mispuntos para saber como se calcularon tus puntos de la ultima carrera, /mihistorico para ver tus puntos por carrera y /help para ver la ayuda. En cualquier momento puedes usar /cancelar para cancelar cualquier comando."}
    }
