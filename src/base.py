# base.py
from sqlalchemy import URL, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from environment import DB_HOST, DB_HOST_TEST, DB_PASSWORD, DB_USER, DEBUG_MODE, INFORMACION_BOTS

db_user = DB_USER
db_password = DB_PASSWORD
db_host = ''

if DEBUG_MODE == "ON":
    db_host = DB_HOST_TEST
else :
    db_host = DB_HOST

for mi_bot in INFORMACION_BOTS.values():
    connection_string = URL.create(
        'postgresql',
        username = db_user,
        password= db_password,
        host= db_host,
        database=mi_bot["basededatos"],
    )
    mi_bot["engine"] = create_engine(connection_string, pool_pre_ping=True)
    mi_bot["sesion"] = sessionmaker(bind=mi_bot['engine'])
    