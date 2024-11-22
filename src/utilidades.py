from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup
import requests
from prettytable import PrettyTable
from datetime import datetime
import pytz
from operator import itemgetter
import numpy as np
import matplotlib.pyplot as plt
from models import Usuario, Quiniela, Resultado, Pago, Piloto, PuntosPilotosCarrrera, Carrera, SesionCarrera, Base, HistoricoQuiniela


def poner_fondo_gris(dibujo: ImageDraw.ImageDraw, total_filas: int, largo_fila: int) -> ImageDraw.ImageDraw:
    y = 81.5
    filas_grises = range(0, total_filas, 2)
    for fila in filas_grises:
        dibujo.rectangle([(15, y + 3.5 + 15),( largo_fila + 5, y + 3.5 + 15 + 3.5 + 14)], fill='#D3D3D3')
        y = y + 3.5 + 15 + 3.5 + 14
    return dibujo

def obtener_resultados(sesion, carrera, soup):
    # soup = BeautifulSoup(requests.get(url).content, features="html.parser")
    table = soup.find('table')
    rows = []
    for i, row in enumerate(table.find_all('tr')):
        if i == 0:
            header = [el.text.strip() for el in row.find_all('th')]
        else:
            rows.append([el.text.strip() for el in row.find_all('td')])
    posiciones_dict = {}
    pilotos_con_puntos = 0
    pilotos_top10 = []
    for row in rows:
        if(row[0].isnumeric()):
            posicion = int(row[0])
            if(posicion < 11):
                posiciones_dict[row[1]] = {
                    'posicion': posicion, 
                    'intervalo': row[5],
                    'puntos': int(row[6])
                    }
                piloto = sesion.query(Piloto).filter(Piloto.numero == int(row[1])).first()
                pilotos_top10.append(PuntosPilotosCarrrera(carrera_id=carrera.id, piloto_id=piloto.id, posicion=posicion, puntos=int(row[6]), intervalo=row[5]))
                if int(row[6]) > 0:
                    pilotos_con_puntos = pilotos_con_puntos + 1
    if pilotos_con_puntos >= 10:
        sesion.add_all(pilotos_top10)
        sesion.flush()
    return posiciones_dict, pilotos_con_puntos

def archivar_quinielas_participante(sesion, carrera):
    historicos = []
    quinielas = sesion.query(Quiniela).all()
    for quiniela in quinielas:
        historicos.append(HistoricoQuiniela(usuario_id=quiniela.usuario_id, carrera_id=carrera.id , quiniela_carrera_id=quiniela.carrera_id, quiniela_fechahora=quiniela.fecha_hora, 
                                            quiniela_lista=quiniela.lista))
    sesion.add_all(historicos)
    sesion.commit()

def archivar_puntos_participante(sesion, carrera:Carrera, posiciones_dict):
    restulados_carrera = []
    for historico_quiniela in carrera.historicoquinielas_carrera:
        penalizacion = 0
        normales = 0
        extras = 0
        if carrera.id != historico_quiniela.quiniela_carrera_id:
            penalizacion = penalizacion - 5
        pagos_guardados, pagos_confirmados = pagos_usuario(historico_quiniela.usuario.pagos)
        carreras_pagadas =  pagos_confirmados + pagos_guardados
        if carreras_pagadas < carrera.ronda:
            penalizacion = penalizacion - 5
        lista_quiniela = historico_quiniela.quiniela_lista.split(",")
        for idx, codigo in enumerate(lista_quiniela):
            piloto = sesion.query(Piloto).filter(Piloto.codigo == codigo).first()
            numero_piloto = str(piloto.numero)
            if numero_piloto in posiciones_dict:
                normales = normales + posiciones_dict[numero_piloto]["puntos"]
                if idx + 1 == posiciones_dict[numero_piloto]['posicion']:
                    extras = extras + 2
        restulados_carrera.append(Resultado(usuario_id=historico_quiniela.usuario_id, carrera_id=carrera.id, puntos_normales=normales, puntos_extras=extras, penalizaciones=penalizacion))
    sesion.add_all(restulados_carrera)
    sesion.flush()
    
def crear_tabla_puntos(sesion, carrera:Carrera):
    tabla_puntos_piloto = PrettyTable()
    tabla_puntos_piloto.title = carrera.nombre
    tabla_puntos_piloto.field_names = ["Pos", "Nombre", "Equipo", "Puntos", "Intervalo"]
    tabla_puntos_piloto.sortby = "Pos"
    resultado_pilotos = carrera.puntospilotoscarreras
    for puntos_piloto in resultado_pilotos:
        tabla_puntos_piloto.add_row([puntos_piloto.posicion, puntos_piloto.piloto.nombre + ' ' + puntos_piloto.piloto.apellido, puntos_piloto.piloto.equipo, puntos_piloto.puntos, puntos_piloto.intervalo])
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("./src/Menlo.ttc", 15)
    tablapilotostamano = dibujo.multiline_textbbox([0,0],str(tabla_puntos_piloto),font=letra)
    im = im.resize((tablapilotostamano[2] + 20, tablapilotostamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo = poner_fondo_gris(dibujo, len(resultado_pilotos), tablapilotostamano[2])
    dibujo.text((10, 10), str(tabla_puntos_piloto), font=letra, fill="black")
    letraabajo = ImageFont.truetype("./src/Menlo.ttc", 10)
    dibujo.text((20, tablapilotostamano[3] + 20), "Resultados tomados de la pagina oficial de Formula 1", font=letraabajo, fill="black")
    return im

def crear_tabla_quinielas(carrera_en_curso, enmascarada=False):
    """Crear la tabla de las quinielas en una imagen."""
    tablaquiniela = PrettyTable()
    tablaquiniela.title = carrera_en_curso.nombre
    tablaquiniela.field_names = ["Fecha/hora", "Nombre", "P1", "P2", "P3", "P4", "P5", "P6", "P7",]
    tablaquiniela.sortby = "Fecha/hora"
    quinielas = carrera_en_curso.quinielas
    im = Image.new("RGB", (200, 200), "white")
    fig = 'No hay carreras archivadas.'
    if len(quinielas) > 0:
        fig = 'Si hay quinielas'
        pilotos_posiciones_conteo = {'P1': [], 'P2': [], 'P3': [], 'P4': [], 'P5': [], 'P6': [], 'P7': []}
        pilotos_en_quiniela = []
        indice_piloto = 0
        for quiniela in quinielas:
            listaquiniela = quiniela.lista.split(",")
            for pos, piloto in enumerate(listaquiniela):
                if piloto in pilotos_en_quiniela:
                    indice_piloto = pilotos_en_quiniela.index(piloto)
                else:
                    pilotos_en_quiniela.append(piloto)
                    indice_piloto = len(pilotos_en_quiniela) - 1
                if len(pilotos_posiciones_conteo['P' + str(pos + 1)]) > indice_piloto:
                    pilotos_posiciones_conteo['P' + str(pos +1)][indice_piloto] = pilotos_posiciones_conteo['P' + str(pos +1)][indice_piloto] + 1
                else:
                    for i in range(1 + indice_piloto - len(pilotos_posiciones_conteo['P' + str(pos +1)])):
                        pilotos_posiciones_conteo['P' + str(pos +1)].append(0)
                    pilotos_posiciones_conteo['P' + str(pos +1)][indice_piloto] = 1
            if(enmascarada):
                listaquiniela = ["XXX"] * len(listaquiniela)
            fechahoraoriginal = quiniela.fecha_hora
            fechahoragdl = fechahoraoriginal.astimezone(pytz.timezone('America/Mexico_City'))
            tablaquiniela.add_row([fechahoragdl.strftime('%Y-%m-%d %H:%M:%S'), quiniela.usuario.obtener_nombre_completo(), listaquiniela[0], listaquiniela[1], listaquiniela[2], listaquiniela[3], listaquiniela[4], listaquiniela[5], listaquiniela[6]])
        indice_piloto = 0
        for pos, conteo in pilotos_posiciones_conteo.items():
            if len(conteo) != len(pilotos_en_quiniela):
                for i in range(len(pilotos_en_quiniela) - len(conteo)):
                    pilotos_posiciones_conteo[pos].append(0)
        if not enmascarada:
            fig, ax = plotBarHorizontal(pilotos_posiciones_conteo, pilotos_en_quiniela)
                
        dibujo = ImageDraw.Draw(im)
        letra = ImageFont.truetype("Menlo.ttc", 15)
        tablaquinielatamano = dibujo.multiline_textbbox([0,0],str(tablaquiniela),font=letra)
        im = im.resize((tablaquinielatamano[2] + 20, tablaquinielatamano[3] + 40))
        dibujo = ImageDraw.Draw(im)
        dibujo = poner_fondo_gris(dibujo, len(quinielas), tablaquinielatamano[2])
        dibujo.text((10, 10), str(tablaquiniela), font=letra, fill="black")
        letraabajo = ImageFont.truetype("Menlo.ttc", 10)
        dibujo.text((20, tablaquinielatamano[3] + 20), "Fecha y hora con el horario de GDL", font=letraabajo, fill="black")
    return im, fig

def plotBarHorizontal(results, category_names):
    labels = list(results.keys())
    data = np.array(list(results.values()))
    data_cum = data.cumsum(axis=1)
    category_colors = plt.colormaps['RdYlGn'](
        np.linspace(0.15, 0.85, data.shape[1]))
    fig, ax = plt.subplots(figsize=(9.2, 5))
    ax.invert_yaxis()
    ax.xaxis.set_visible(False)
    ax.set_xlim(0, np.sum(data, axis=1).max())
    ax.set_title("Porcentaje de pilotos por posicion")
    for i, (colname, color) in enumerate(zip(category_names, category_colors)):
        widths = data[:, i]
        starts = data_cum[:, i] - widths
        rects = ax.barh(labels, widths, left=starts, height=0.5,
                        label=colname, color=color)
        r, g, b, _ = color
        text_color = 'white' if r * g * b < 0.5 else 'darkgrey'
        ax.bar_label(rects, label_type='center', color=text_color, fmt=lambda x: f'{category_names[i]}' if x>0 else f'')

    return fig, ax

def crear_tabla_general(sesion):
    tablaresultados = PrettyTable()
    tablaresultados.title = 'Tabla General Quiniela F1'
    tablaresultados.field_names = ["Nombre", "Puntos Totales", "Puntos Pilotos", "Puntos Extras", "Penalizaciones"]
    tablaresultados.sortby = "Puntos Totales"
    tablaresultados.reversesort = True
    usuarios = sesion.query(Usuario).all()
    carreras_archivadas = sesion.query(Carrera).filter(Carrera.estado == "ARCHIVADA").all()
    total_rondas = len(carreras_archivadas)
    im = Image.new("RGB", (200, 200), "white")
    if total_rondas > 0:
        for usuario in usuarios:
            normales = 0
            extras = 0
            penalizaciones = 0
            for resultado in usuario.resultados:
                normales = normales + resultado.puntos_normales
                extras = extras + resultado.puntos_extras
                penalizaciones = penalizaciones + resultado.penalizaciones
            tablaresultados.add_row([usuario.obtener_nombre_completo(), normales + extras + penalizaciones, normales, extras, penalizaciones])   
        dibujo = ImageDraw.Draw(im)
        letra = ImageFont.truetype("./src/Menlo.ttc", 15)
        tablaresultados_tamano = dibujo.multiline_textbbox([0,0],str(tablaresultados),font=letra)
        im = im.resize((tablaresultados_tamano[2] + 20, tablaresultados_tamano[3] + 40))
        dibujo = ImageDraw.Draw(im)
        dibujo = poner_fondo_gris(dibujo, len(usuarios), tablaresultados_tamano[2])
        dibujo.text((10, 10), str(tablaresultados), font=letra, fill="black")
        letraabajo = ImageFont.truetype("./src/Menlo.ttc", 10)
        dibujo.text((20, tablaresultados_tamano[3] + 20), "Total de rondas incluidas: " + str(total_rondas), font=letraabajo, fill="black")
    return im, total_rondas

def crear_tabla_resultados(sesion, carrera:Carrera|None):
    carreras_archivadas = []
    im = Image.new("RGB", (200, 200), "white")
    texto_ganador = 'No hay carreras archivadas.'
    if carrera is None:
        carreras_archivadas = sesion.query(Carrera).filter((Carrera.estado == "ARCHIVADA") | (Carrera.estado == "NO_ENVIADA")).all()
        carreras_archivadas.sort(key=lambda x: x.hora_empiezo, reverse = True)
        if len(carreras_archivadas) > 0:
            carrera = carreras_archivadas[0]
        else:
            return im, texto_ganador
    tablaresultados = PrettyTable()
    tablaresultados.title = carrera.nombre
    tablaresultados.field_names = ["Nombre", "Puntos Totales", "Puntos Pilotos", "Puntos Extras", "Penalizaciones"]
    listaresultados = []
    for resultado in carrera.resultados:
        puntos_totales = resultado.puntos_normales + resultado.puntos_extras + resultado.penalizaciones
        listaresultados.append([resultado.usuario.obtener_nombre_completo(), puntos_totales, resultado.puntos_normales, resultado.puntos_extras, resultado.penalizaciones])
    listaresultados.sort(key=itemgetter(4,1), reverse=True)
    linea = False
    ganador = ''
    puntos_ganador = 0
    texto_ganador = 'El ganador de la carrera ' + carrera.nombre + ' es: '
    for index in range(len(listaresultados)):
        resultado = listaresultados[index]
        siguiente_resultado = listaresultados[min(index + 1, len(listaresultados) - 1) ]
        if index == 0:
            ganador = resultado[0]
            puntos_ganador = resultado[1]
        else:
            if (resultado[1] == puntos_ganador and resultado[4] >= 0):
                ganador = ganador + ', ' + resultado[0]
                texto_ganador = 'Los ganadores de la carrera ' + carrera.nombre + ' son: '
        if(siguiente_resultado[4] < 0 and not linea):
            tablaresultados.add_row(resultado,  divider=True)
            linea = True
        else:
            tablaresultados.add_row(resultado)
    if puntos_ganador >= 90:
        texto_ganador = texto_ganador + ganador + '. Con un total de ' + str(puntos_ganador) + ' puntos.'
    else:
        texto_ganador = 'No hubo ganador para la carrera: ' + carrera.nombre + '. Nadie logro hacer 90 puntos o mas. El premio se acumula para la /proxima carrera.'
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("./src/Menlo.ttc", 15)
    tablaresultados_tamano = dibujo.multiline_textbbox([0,0],str(tablaresultados),font=letra)
    im = im.resize((tablaresultados_tamano[2] + 20, tablaresultados_tamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo = poner_fondo_gris(dibujo, len(carrera.resultados), tablaresultados_tamano[2])
    dibujo.text((10, 10), str(tablaresultados), font=letra, fill="black")
    letraabajo = ImageFont.truetype("./src/Menlo.ttc", 10)
    dibujo.text((20, tablaresultados_tamano[3] + 20), "Los que tienen penalizaciones no pueden ganar el premio, estan en la segunda seccion de la tabla", font=letraabajo, fill="black")
    return im, texto_ganador

def detalle_individual_historico(sesion, telegram_id):
    usuario = sesion.query(Usuario).filter(Usuario.telegram_id == telegram_id).first()
    mis_resultados = usuario.resultados
    im = Image.new("RGB", (200, 200), "white")
    texto_mensaje = 'No hay carreras archivadas.'
    if len(mis_resultados)> 0:
        tabla_historico_puntos = PrettyTable()
        tabla_historico_puntos.title = 'Tabla de puntos obtenidos por carrera'
        tabla_historico_puntos.field_names = ["Ronda", "Nombre", "Puntos Totales", "Puntos Piloto","Puntos Extras", "Penaizaciones"]
        tabla_historico_puntos.sortby = "Ronda"
        puntos_totales = 0
        for mi_resultado in mis_resultados:
            puntos_carrera = mi_resultado.puntos_normales + mi_resultado.puntos_extras + mi_resultado.penalizaciones
            puntos_totales += puntos_carrera
            tabla_historico_puntos.add_row([ int(mi_resultado.carrera.ronda), mi_resultado.carrera.nombre, puntos_carrera, mi_resultado.puntos_normales , mi_resultado.puntos_extras, mi_resultado.penalizaciones])
        texto_abajo = f'Total de puntos: {puntos_totales}'
        texto_mensaje = f'Este es el detalle de los puntos por carrera que has obtenido hasta el momento'
        im = Image.new("RGB", (200, 200), "white")
        dibujo = ImageDraw.Draw(im)
        letra = ImageFont.truetype("Menlo.ttc", 15)
        tabladetalletamano = dibujo.multiline_textbbox([0,0],str(tabla_historico_puntos),font=letra)
        im = im.resize((tabladetalletamano[2] + 20, tabladetalletamano[3] + 40))
        dibujo = ImageDraw.Draw(im)
        dibujo = poner_fondo_gris(dibujo, len(mis_resultados), tabladetalletamano[2])
        dibujo.text((10, 10), str(tabla_historico_puntos), font=letra, fill="black")
        letraabajo = ImageFont.truetype("Menlo.ttc", 10)
        dibujo.text((20, tabladetalletamano[3] + 20), texto_abajo, font=letra, fill="black")
    return im, texto_mensaje

def detalle_individual_puntos(sesion, telegram_id):
    usuario = None
    ultimo_resultado = None
    ultima_quiniela = None
    resultado_pilotos = None
    usuario = sesion.query(Usuario).filter(Usuario.telegram_id == telegram_id).first()
    usuario.resultados.sort(key=lambda x: x.carrera.hora_empiezo, reverse = True)
    ultimo_resultado = usuario.resultados[0]
    ultima_quiniela = sesion.query(HistoricoQuiniela).filter(HistoricoQuiniela.usuario_id == usuario.id, HistoricoQuiniela.carrera_id == ultimo_resultado.carrera_id).first()
    resultado_pilotos = sesion.query(PuntosPilotosCarrrera).filter(PuntosPilotosCarrrera.carrera_id == ultimo_resultado.carrera_id).all()
    im = Image.new("RGB", (200, 200), "white")
    texto_mensaje = 'No hay carreras archivadas.'
    if len(usuario.resultados) > 0:
        tabla_detalle_puntos = PrettyTable()
        tabla_detalle_puntos.title = ultimo_resultado.carrera.nombre
        tabla_detalle_puntos.field_names = ["Pos", "Piloto", "Puntos", "Tus Puntos", "Tus Extras"]
        tabla_detalle_puntos.sortby = "Pos"
        mi_lista = ultima_quiniela.quiniela_lista
        mi_quiniela_carrera = ultima_quiniela.carrera.nombre
        mis_puntos_totales = ultimo_resultado.puntos_normales + ultimo_resultado.puntos_extras + ultimo_resultado.penalizaciones
        mis_penalizaciones = ultimo_resultado.penalizaciones
        mi_quiniela = ultima_quiniela.quiniela_lista.split(',')
        texto_abajo = f'Tu quiniela: {mi_lista}'
        texto_mensaje = f'Tus puntos totales fueron: {mis_puntos_totales}, en la imagen puedes ver como los obtuviste. Tambien puedes revisar el documento de las reglas con el comando /ayuda para mas detalles'
        if mis_penalizaciones < 0:
            texto_mensaje = f'Tus puntos totales fueron: {mis_puntos_totales}, en la imagen puedes ver como obtuviste los puntos por pilotos y los puntos extras. Estuviste penalizado con {mis_penalizaciones} estos los debes de restar de los puntos de la imagen. Recuerda que puedes revisar las reglas con el comando /ayuda'
        for resultado_piloto in resultado_pilotos:
            mis_puntos_pilotos = 0
            mis_puntos_extras = 0
            if resultado_piloto.piloto.codigo in mi_quiniela:
                mis_puntos_pilotos = resultado_piloto.puntos
                mi_posicion = mi_quiniela.index(resultado_piloto.piloto.codigo) + 1
                if mi_posicion == resultado_piloto.posicion:
                    mis_puntos_extras = 2
            tabla_detalle_puntos.add_row([resultado_piloto.posicion, resultado_piloto.piloto.codigo , resultado_piloto.puntos, mis_puntos_pilotos , mis_puntos_extras])
    
        dibujo = ImageDraw.Draw(im)
        letra = ImageFont.truetype("Menlo.ttc", 15)
        tabladetalletamano = dibujo.multiline_textbbox([0,0],str(tabla_detalle_puntos),font=letra)
        im = im.resize((tabladetalletamano[2] + 20, tabladetalletamano[3] + 40))
        dibujo = ImageDraw.Draw(im)
        dibujo = poner_fondo_gris(dibujo, len(resultado_pilotos), tabladetalletamano[2])
        dibujo.text((10, 10), str(tabla_detalle_puntos), font=letra, fill="black")
        letraabajo = ImageFont.truetype("Menlo.ttc", 10)
        dibujo.text((20, tabladetalletamano[3] + 20), texto_abajo, font=letra, fill="black")    
    return im, texto_mensaje

def pagos_usuario(usuario_pagos):
    # dbPagos = deta.AsyncBase('Pagos')
    # pagos_usuario = await dbPagos.fetch([{'usuario':usuario, 'estado':'guardado'},{'usuario':usuario, 'estado':'confirmado'}])
    # await dbPagos.close()
    pagos_guardados = 0
    pagos_confirmados = 0
    for pago in usuario_pagos:
        if pago.estado == 'guardado' or pago.estado == 'revision':
            pagos_guardados += pago.carreras
        if pago.estado == 'confirmado':
            pagos_confirmados += pago.carreras
    return pagos_guardados, pagos_confirmados