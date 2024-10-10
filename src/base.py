# base.py
from sqlalchemy import URL, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

db_user = os.environ.get("DB_USER")
db_password = os.environ.get("DB_PASSWORD")
db_host = os.environ.get("DB_HOST")

connection_string = URL.create(
    'postgresql',
    username = db_user,
    password= db_password,
    host=db_host,
    database='quinielaF1',
)

engine = create_engine(connection_string, pool_pre_ping=True)
Session = sessionmaker(bind=engine, expire_on_commit=False)
# Base = declarative_base()