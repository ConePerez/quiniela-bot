# models.py
import enum
from base import Base
from sqlalchemy import Column, String, Enum, ForeignKey, Float, BigInteger, Integer, TIMESTAMP, Double, Boolean
from sqlalchemy.orm import relationship, backref

class EstadoCarrera(enum.Enum):
    IDLE = 'IDLE'
    EN_CURSO = 'EN-CURSO'
    NO_ENVIADA = 'NO_ENVIADA'
    ARCHIVADA = 'ARCHIVADA'

class Usuario(Base):
    __tablename__ = 'usuarios'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger)
    nombre = Column(String)
    apellido = Column(String)
    nombre_usuario = Column(String)
    quinielas = relationship("Quiniela", backref=backref("usuarios"))
    resultados = relationship("Resultado", backref=backref("usuarios"))
    pagos = relationship("Pago", backref=backref("usuarios"))
    
    def __init__(self, telegram_id, nombre, apellido, nombre_usuario):
        self.telegram_id = telegram_id,
        self.nombre = nombre,
        self.apellido = apellido,
        self.nombre_usuario = nombre_usuario

    @staticmethod
    def obtener_usuario_por_telegram_id(session, telegram_id):
        return session.query(Usuario).filter_by(telegram_id = telegram_id).first()
    
class Quiniela(Base):
    __tablename__ = 'quinielas'

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    carrera_id = Column(Integer, ForeignKey("carreras.id"))
    fecha_hora = Column(TIMESTAMP(timezone=True))
    lista = Column(String)

    def __init__(self, usuario_id, carrera_id, fecha_hora, lista):
        self.usuario_id = usuario_id
        self.carrera_id = carrera_id
        self.fecha_hora = fecha_hora
        self.lista = lista

class Piloto(Base):
    __tablename__ = 'pilotos'

    id = Column(Integer, primary_key=True)
    numero = Column(Integer)
    nombre = Column(String)
    apellido = Column(String)
    codigo = Column(String)
    equipo = Column(String)
    acumulado_puntos = Column(Double)
    puntospiloto = relationship("PuntosPilotosCarrrera", backref=backref("pilotos"))

    @staticmethod
    def obtener_pilotos(session):
        return session.query(Piloto).all()

class PuntosPilotosCarrrera(Base):
    __tablename__ = 'puntospilotoscarrera'

    id = Column(Integer, primary_key=True)
    carrera_id = Column(Integer, ForeignKey("carreras.id"))
    piloto_id = Column(Integer, ForeignKey("pilotos.id"))
    posicion = Column(Integer)
    puntos = Column(Double)
    intervalo = Column(String)

class Carrera(Base):
    __tablename__ = 'carreras'

    id = Column(Integer, primary_key=True)
    codigo = Column(Integer)
    nombre = Column(String)
    hora_empiezo = Column(TIMESTAMP(timezone=True))
    hora_termino = Column(TIMESTAMP(timezone=True))
    estado = Column(String)
    ronda = Column(Integer)
    url = Column(String)
    quinielas = relationship("Quiniela", backref=backref("carreras"))
    puntospilotocarrreras = relationship("PuntosPilotosCarrrera", backref=backref("carreras"))
    sesionescarrera = relationship("SesionCarrera", backref=backref("carreras"))
    resultados = relationship("Resultado", backref=backref("carreras"))

    def __init__(self, codigo, nombre, hora_empiezo, hora_termino, estado, ronda, url):
        self.codigo = codigo
        self.nombre = nombre
        self.hora_empiezo = hora_empiezo
        self.hora_empiezo = hora_termino
        self.estado = estado
        self.ronda = ronda
        self.url = url

class SesionCarrera(Base):
    __tablename__ = 'sesioncarreras'

    id = Column(Integer, primary_key=True)
    codigo = Column(String)
    carrera_id = Column(Integer, ForeignKey("carreras.id"))
    estado = Column(String)
    hora_empiezo = Column(TIMESTAMP(timezone=True))
    hora_termino = Column(TIMESTAMP(timezone=True))

    def __init__(self, codigo, carrera_id, estado, hora_empiezo, hora_termino):
        self.codigo = codigo
        self.carrera_id = carrera_id
        self.estado = estado
        self.hora_empiezo = hora_empiezo
        self.hora_termino = hora_termino

class Resultado(Base):
    __tablename__ = 'resultados'

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    carrera_id = Column(Integer, ForeignKey("carreras.id"))
    puntos_extras = Column(Double)
    puntos_normales = Column(Double)
    penalizaciones = Column(Double)

class Pago(Base):
    __tablename__ = 'pagos'

    id = Column(Integer, primary_key=True)
    fecha_hora = Column(TIMESTAMP(timezone=True))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    carreras = Column(Integer)
    enviado = Column(Boolean)
    estado = Column(String)
    foto = Column(String)
    mensaje = Column(String)
    texto = Column(String)

    def __init__(self, fecha_hora, usuario_id, carreras, enviado, estado, foto, mensaje, texto):
        self.fecha_hora = fecha_hora
        self.usuario_id = usuario_id
        self.carreras = carreras
        self.enviado = enviado
        self.estado = estado
        self.foto = foto
        self.mensaje = mensaje
        self.texto = texto