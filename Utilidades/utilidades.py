from PIL import Image, ImageDraw, ImageFont
from deta import Deta
from bs4 import BeautifulSoup
import requests
from prettytable import PrettyTable
from datetime import datetime
import pytz
from operator import itemgetter
import numpy as np
import matplotlib.pyplot as plt

deta = Deta()

def poner_fondo_gris(dibujo: ImageDraw.ImageDraw, total_filas: int, largo_fila: int) -> ImageDraw.ImageDraw:
    y = 81.5
    filas_grises = range(0, total_filas, 2)
    for fila in filas_grises:
        dibujo.rectangle([(15, y + 3.5 + 15),( largo_fila + 5, y + 3.5 + 15 + 3.5 + 14)], fill='#D3D3D3')
        y = y + 3.5 + 15 + 3.5 + 14
    return dibujo

async def obtener_resultados(url, carrera):
    dbPuntosPilotos = deta.AsyncBase('PuntosPilotos')
    dbCarreras = deta.AsyncBase('Carreras')
    soup = BeautifulSoup(requests.get(url).text)
    table = soup.find('table')
    rows = []
    for i, row in enumerate(table.find_all('tr')):
        if i == 0:
            header = [el.text.strip() for el in row.find_all('th')]
        else:
            rows.append([el.text.strip() for el in row.find_all('td')])
    posiciones_dict = {}
    pilotos_con_puntos = 0
    for row in rows:
        if(row[1].isnumeric()):
            posicion = int(row[1])
            if(posicion < 11):
                posiciones_dict[row[2]] = {
                    'posicion': posicion, 
                    'intervalo': row[6],
                    'puntos': int(row[7])
                    }
                if int(row[7]) > 0:
                    pilotos_con_puntos = pilotos_con_puntos + 1
    await dbPuntosPilotos.put({'key': carrera, 'Pilotos':posiciones_dict})
    await dbCarreras.update(updates={'url':url}, key=carrera)
    await dbPuntosPilotos.close()
    await dbCarreras.close()
    return posiciones_dict, pilotos_con_puntos

async def archivar_quinielas_participante(carrera):
    dbHistorico = deta.AsyncBase('Historico')
    dbQuiniela = deta.AsyncBase("Quiniela")
    datosquiniela = await dbQuiniela.fetch()
    await dbQuiniela.close()
    quinielas = datosquiniela.items
    for i_quiniela in range(len(quinielas)):
        quiniela = quinielas[i_quiniela]
        historico = await dbHistorico.get(quiniela['key'])
        if historico is None:
            await dbHistorico.put({
                'key': quiniela['key'],
                'Nombre': quiniela['Nombre'],
                'Quinielas': {},
                'Resultados': {}, 
            })
            historico = await dbHistorico.get(quiniela['key'])
        historico_quinielas = historico['Quinielas']
        historico_quinielas[carrera] = quiniela
        historico_resultados = historico['Resultados']
        historico_resultados[carrera] = {}
        await dbHistorico.update(updates={ 
            'Quinielas': historico_quinielas, 
            'Resultados': historico_resultados, 
            }, key=quiniela['key'])
    await dbHistorico.close()
    await dbQuiniela.close()

async def archivar_puntos_participante(carrera_codigo, posiciones_dict):
    dbCarreras = deta.AsyncBase('Carreras')
    dbHistorico = deta.AsyncBase('Historico')
    dbPilotos = deta.AsyncBase("Pilotos")
    dbPagos = deta.AsyncBase('Pagos')
    dbConfiguracion= deta.AsyncBase('Configuracion')
    controles = await dbConfiguracion.get('controles')
    await dbConfiguracion.close()
    carrera = await dbCarreras.get(carrera_codigo)
    await dbCarreras.close()
    piloto_fetch = await dbPilotos.get('2023')
    await dbPilotos.close()
    historico_participantes = await dbHistorico.fetch()
    for historico_participante in historico_participantes.items:
        historico_quinielas = historico_participante['Quinielas']
        quiniela = historico_participante['Quinielas'][carrera['key']]
        historico_resultados = historico_participante['Resultados']
        listaquiniela = quiniela['Lista'].split(',')
        if quiniela['Carrera'] != carrera['key']:
            resultados = {'normales':0, 'extras':0, 'penalizaciones':-5}
        else:
            resultados = {'normales':0, 'extras':0, 'penalizaciones':0}
        pagosusuarios = await dbPagos.fetch([{'usuario':quiniela['key'], 'estado':'guardado'},{'usuario':quiniela['key'], 'estado':'confirmado'} ])
        rondas_pagadas = 0
        rondas_confirmadas = 0
        for pagousuario in pagosusuarios.items:
            if str(pagousuario['carreras']) == 'Todas':
                rondas_pagadas = int(controles['rondas'])
            else:
                rondas_pagadas = int(pagousuario['carreras']) + rondas_pagadas
            if pagousuario['estado'] == 'confirmado':
                if pagousuario['carreras'] == 'Todas':
                    rondas_confirmadas = int(controles['rondas'])
                else:
                    rondas_confirmadas = int(pagousuario['carreras']) + rondas_confirmadas
        if rondas_pagadas < int(carrera['Ronda']):
            resultados['penalizaciones'] = resultados['penalizaciones'] - 5
        # se termino revisar pagos
        for i_lista in range(len(listaquiniela)):
            piloto = listaquiniela[i_lista]
            numero_piloto = ''
            for n in piloto_fetch['Lista']:
                if(piloto == piloto_fetch['Lista'][n]['codigo']):
                    numero_piloto = n
            if( numero_piloto in posiciones_dict):
                resultados['normales'] = resultados['normales'] + posiciones_dict[numero_piloto]['puntos']
                if(i_lista + 1 == posiciones_dict[numero_piloto]['posicion']):
                    resultados['extras'] = resultados['extras'] + 2
        historico_resultados[carrera['key']] = resultados
        await dbHistorico.update(updates={ 
            'Quinielas': historico_quinielas, 
            'Resultados': historico_resultados, 
            }, key=quiniela['key'])
    await dbHistorico.close()
    await dbPagos.close()
    
async def crear_tabla_puntos(obj_carrera):
    dbPuntosPilotos = deta.AsyncBase("PuntosPilotos")
    dbPilotos = deta.AsyncBase("Pilotos")
    tabla_puntos_piloto = PrettyTable()
    tabla_puntos_piloto.title = obj_carrera['Nombre']
    tabla_puntos_piloto.field_names = ["Pos", "Nombre", "Equipo", "Puntos", "Intervalo"]
    tabla_puntos_piloto.sortby = "Pos"
    resultado_pilotos = await dbPuntosPilotos.get(obj_carrera['key'])
    await dbPuntosPilotos.close()
    detalles_piloto = await dbPilotos.get('2023')
    await dbPilotos.close()
    detalles_piloto = detalles_piloto['Lista']
    for numero, resultado in resultado_pilotos['Pilotos'].items():
        tabla_puntos_piloto.add_row([resultado['posicion'], detalles_piloto[numero]['Nombre'] + ' ' + detalles_piloto[numero]['Apellido'], detalles_piloto[numero]['Equipo'], resultado['puntos'], resultado['intervalo']])
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablapilotostamano = dibujo.multiline_textbbox([0,0],str(tabla_puntos_piloto),font=letra)
    im = im.resize((tablapilotostamano[2] + 20, tablapilotostamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo = poner_fondo_gris(dibujo, len(resultado_pilotos['Pilotos']), tablapilotostamano[2])
    dibujo.text((10, 10), str(tabla_puntos_piloto), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablapilotostamano[3] + 20), "Resultados tomados de la pagina oficial de Formula 1", font=letraabajo, fill="black")
    return im, obj_carrera['Nombre']

async def crear_tabla_quinielas(carrera_en_curso, enmascarada=False):
    """Crear la tabla de las quinielas en una imagen."""
    carrera_nombre = carrera_en_curso['Nombre']
    carrera_clave = carrera_en_curso['key']
    
    tablaquiniela = PrettyTable()
    tablaquiniela.title = carrera_nombre
    tablaquiniela.field_names = ["Fecha/hora", "Nombre", "P1", "P2", "P3", "P4", "P5", "P6", "P7",]
    tablaquiniela.sortby = "Fecha/hora"
    dbQuiniela = deta.AsyncBase('Quiniela')
    datosquiniela = await dbQuiniela.fetch({'Carrera':carrera_clave})
    filas = datosquiniela.items    
    
    pilotos_posiciones_conteo = {'P1': [], 'P2': [], 'P3': [], 'P4': [], 'P5': [], 'P6': [], 'P7': []}
    pilotos_en_quiniela = []
    indice_piloto = 0
    for index in range(datosquiniela.count):
        fila = filas[index]
        listaquiniela = fila["Lista"].split(",")
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
        fechahoraoriginal = datetime.fromisoformat(fila["FechaHora"])
        fechahoragdl = fechahoraoriginal.astimezone(pytz.timezone('America/Mexico_City'))
        tablaquiniela.add_row([fechahoragdl.strftime('%Y-%m-%d %H:%M:%S'), fila["Nombre"], listaquiniela[0], listaquiniela[1], listaquiniela[2], listaquiniela[3], listaquiniela[4], listaquiniela[5], listaquiniela[6]])
    indice_piloto = 0
    for pos, conteo in pilotos_posiciones_conteo.items():
        if len(conteo) != len(pilotos_en_quiniela):
            for i in range(len(pilotos_en_quiniela) - len(conteo)):
                pilotos_posiciones_conteo[pos].append(0)
    if not enmascarada:
        fig, ax = plotBarHorizontal(pilotos_posiciones_conteo, pilotos_en_quiniela)
    
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablaquinielatamano = dibujo.multiline_textbbox([0,0],str(tablaquiniela),font=letra)
    im = im.resize((tablaquinielatamano[2] + 20, tablaquinielatamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo = poner_fondo_gris(dibujo, datosquiniela.count, tablaquinielatamano[2])
    dibujo.text((10, 10), str(tablaquiniela), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablaquinielatamano[3] + 20), "Fecha y hora con el horario de GDL", font=letraabajo, fill="black")
    await dbQuiniela.close()
    
    return im, carrera_nombre, fig

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

async def crear_tabla_general():
    tablaresultados = PrettyTable()
    tablaresultados.title = 'Tabla General Quiniela F1'
    tablaresultados.field_names = ["Nombre", "Puntos Totales", "Puntos Pilotos", "Puntos Extras", "Penalizaciones"]
    tablaresultados.sortby = "Puntos Totales"
    tablaresultados.reversesort = True
    dbHistorico = deta.AsyncBase('Historico')
    dbCarreras = deta.AsyncBase('Carreras')
    resultados_historicos = await dbHistorico.fetch()
    total_rondas = await dbCarreras.fetch([{'Estado':'ARCHIVADA'}, {'Estado':'NO_ENVIADA'}])
    total_rondas = total_rondas.count
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
    dibujo = poner_fondo_gris(dibujo, resultados_historicos.count, tablaresultados_tamano[2])
    dibujo.text((10, 10), str(tablaresultados), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablaresultados_tamano[3] + 20), "Total de rondas incluidas: " + str(total_rondas), font=letraabajo, fill="black")
    await dbHistorico.close()
    await dbCarreras.close()
    return im, total_rondas

async def crear_tabla_resultados():
    dbCarreras = deta.AsyncBase('Carreras')
    dbHistorico = deta.AsyncBase('Historico')
    carreras = await dbCarreras.fetch([{'Estado':'ARCHIVADA'}, {'Estado':'NO_ENVIADA'}])
    maximo_horario = datetime.fromisoformat('2023-01-01T00:00:00.000+00:00')
    ultima_carrera_archivada = ''
    for carrera in carreras.items:
        horario_Carrera = datetime.fromisoformat(carrera['Termino'])
        if(horario_Carrera > maximo_horario):
            maximo_horario = horario_Carrera
            ultima_carrera_archivada = carrera['key']
    
    carrera_codigo = ultima_carrera_archivada
    carrera_dict = await dbCarreras.get(carrera_codigo)
    carrera_nombre = carrera_dict['Nombre']
    tablaresultados = PrettyTable()
    tablaresultados.title = carrera_nombre
    tablaresultados.field_names = ["Nombre", "Puntos Totales", "Puntos Pilotos", "Puntos Extras", "Penalizaciones"]
    datosHistoricos = await dbHistorico.fetch()
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
        texto_ganador = 'No hubo ganador para la carrera: ' + carrera_nombre + '. Nadie logro hacer 90 puntos o mas. El premio se acumula para la /proxima carrera.'
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tablaresultados_tamano = dibujo.multiline_textbbox([0,0],str(tablaresultados),font=letra)
    im = im.resize((tablaresultados_tamano[2] + 20, tablaresultados_tamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo = poner_fondo_gris(dibujo, datosHistoricos.count, tablaresultados_tamano[2])
    dibujo.text((10, 10), str(tablaresultados), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tablaresultados_tamano[3] + 20), "Los que tienen penalizaciones no pueden ganar el premio, estan en la segunda seccion de la tabla", font=letraabajo, fill="black")
    await dbCarreras.close()
    await dbHistorico.close()
    return im, texto_ganador

async def detalle_individual_historico(usuario):
    dbHistorico = deta.AsyncBase('Historico')
    dbCarreras = deta.AsyncBase('Carreras')
    mi_historico = await dbHistorico.get(usuario)
    tabla_historico_puntos = PrettyTable()
    tabla_historico_puntos.title = 'Tabla de puntos obtenidos por carrera'
    tabla_historico_puntos.field_names = ["Ronda", "Nombre", "Puntos Totales", "Puntos Piloto","Puntos Extras", "Penaizaciones"]
    tabla_historico_puntos.sortby = "Ronda"
    puntos_totales = 0
    for codigo_carrera, puntos in mi_historico['Resultados'].items():
        carrera = await dbCarreras.get(codigo_carrera)
        puntos_carrera = puntos['normales'] + puntos['extras'] + puntos['penalizaciones']
        puntos_totales += puntos_carrera
        tabla_historico_puntos.add_row([ int(carrera['Ronda']), carrera['Nombre'], puntos_carrera, puntos['normales'] , puntos['extras'], puntos['penalizaciones']])
    texto_abajo = f'Total de puntos: {puntos_totales}'
    texto_mensaje = f'Este es el detalle de los puntos por carrera que has obtenido hasta el momento'
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tabladetalletamano = dibujo.multiline_textbbox([0,0],str(tabla_historico_puntos),font=letra)
    im = im.resize((tabladetalletamano[2] + 20, tabladetalletamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo = poner_fondo_gris(dibujo, len(mi_historico['Resultados']), tabladetalletamano[2])
    dibujo.text((10, 10), str(tabla_historico_puntos), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tabladetalletamano[3] + 20), texto_abajo, font=letra, fill="black")
    await dbCarreras.close()
    await dbHistorico.close()
    return im, texto_mensaje

async def detalle_individual_puntos(usuario):
    dbHistorico = deta.AsyncBase('Historico')
    dbCarreras = deta.AsyncBase('Carreras')
    dbPuntosPilotos = deta.AsyncBase("PuntosPilotos")
    dbPilotos = deta.AsyncBase("Pilotos")
    carreras = await dbCarreras.fetch([{'Estado':'ARCHIVADA'}, {'Estado':'NO_ENVIADA'}])
    maximo_horario = datetime.fromisoformat('2023-01-01T00:00:00.000+00:00')
    ultima_carrera_archivada = {}
    for carrera in carreras.items:
        horario_Carrera = datetime.fromisoformat(carrera['Termino'])
        if(horario_Carrera > maximo_horario):
            maximo_horario = horario_Carrera
            ultima_carrera_archivada = carrera
    tabla_detalle_puntos = PrettyTable()
    tabla_detalle_puntos.title = ultima_carrera_archivada['Nombre']
    tabla_detalle_puntos.field_names = ["Pos", "Piloto", "Puntos", "Tus Puntos", "Tus Extras"]
    tabla_detalle_puntos.sortby = "Pos"
    resultado_pilotos = await dbPuntosPilotos.get(ultima_carrera_archivada['key'])
    detalles_piloto = await dbPilotos.get('2023')
    detalles_piloto = detalles_piloto['Lista']
    mi_historico = await dbHistorico.get(usuario)
    mi_lista = mi_historico['Quinielas'][ultima_carrera_archivada['key']]['Lista']
    mi_quiniela_carrera = mi_historico['Quinielas'][ultima_carrera_archivada['key']]['Carrera']
    mis_puntos_totales = mi_historico['Resultados'][ultima_carrera_archivada['key']]['extras'] + mi_historico['Resultados'][ultima_carrera_archivada['key']]['normales'] + mi_historico['Resultados'][ultima_carrera_archivada['key']]['penalizaciones']
    mis_penalizaciones = mi_historico['Resultados'][ultima_carrera_archivada['key']]['penalizaciones']
    mi_quiniela = mi_historico['Quinielas'][ultima_carrera_archivada['key']]['Lista'].split(',')
    texto_abajo = f'Tu quiniela: {mi_lista}'
    texto_mensaje = f'Tus puntos totales fueron: {mis_puntos_totales}, en la imagen puedes ver como los obtuviste. Tambien puedes revisar el documento de las reglas con el comando /ayuda para mas detalles'
    if mis_penalizaciones < 0:
        texto_mensaje = f'Tus puntos totales fueron: {mis_puntos_totales}, en la imagen puedes ver como obtuviste los puntos por pilotos y los puntos extras. Estuviste penalizado con {mis_penalizaciones} estos los debes de restar de los puntos de la imagen. Recuerda que puedes revisar las reglas con el comando /ayuda'
    for numero, resultado in resultado_pilotos['Pilotos'].items():
        mis_puntos_pilotos = 0
        mis_puntos_extras = 0
        if detalles_piloto[numero]['codigo'] in mi_quiniela:
            mis_puntos_pilotos = resultado['puntos']
            mi_posicion = mi_quiniela.index(detalles_piloto[numero]['codigo']) + 1
            if mi_posicion == resultado['posicion']:
                mis_puntos_extras = 2
        tabla_detalle_puntos.add_row([resultado['posicion'], detalles_piloto[numero]['codigo'] , resultado['puntos'], mis_puntos_pilotos , mis_puntos_extras])
    im = Image.new("RGB", (200, 200), "white")
    dibujo = ImageDraw.Draw(im)
    letra = ImageFont.truetype("Menlo.ttc", 15)
    tabladetalletamano = dibujo.multiline_textbbox([0,0],str(tabla_detalle_puntos),font=letra)
    im = im.resize((tabladetalletamano[2] + 20, tabladetalletamano[3] + 40))
    dibujo = ImageDraw.Draw(im)
    dibujo = poner_fondo_gris(dibujo, len(resultado_pilotos['Pilotos']), tabladetalletamano[2])
    dibujo.text((10, 10), str(tabla_detalle_puntos), font=letra, fill="black")
    letraabajo = ImageFont.truetype("Menlo.ttc", 10)
    dibujo.text((20, tabladetalletamano[3] + 20), texto_abajo, font=letra, fill="black")    
    await dbCarreras.close()
    await dbHistorico.close()
    await dbPilotos.close()
    await dbPuntosPilotos.close()
    return im, texto_mensaje

async def pagos_usuario(usuario):
    dbPagos = deta.AsyncBase('Pagos')
    pagos_usuario = await dbPagos.fetch([{'usuario':usuario, 'estado':'guardado'},{'usuario':usuario, 'estado':'confirmado'}])
    await dbPagos.close()
    pagos_guardados = 0
    pagos_confirmados = 0
    for pago in pagos_usuario.items:
        pagos_guardados += int(pago['carreras'])
        if pago['estado'] == 'confirmado':
            pagos_confirmados += int(pago['carreras'])
    return pagos_guardados, pagos_confirmados