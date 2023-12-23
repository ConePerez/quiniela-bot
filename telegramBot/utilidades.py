from PIL import ImageDraw

def poner_fondo_gris(dibujo: ImageDraw.ImageDraw, total_filas: int, largo_fila: int) -> ImageDraw.ImageDraw:
    y = 81.5
    filas_grises = range(0, total_filas, 2)
    for fila in filas_grises:
        dibujo.rectangle([(15, y + 3.5 + 15),( largo_fila + 5, y + 3.5 + 15 + 3.5 + 14)], fill='#D3D3D3')
        y = y + 3.5 + 15 + 3.5 + 14
    return dibujo