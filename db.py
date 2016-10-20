import os
import sys

path = os.path.join(os.path.dirname(__file__), './sqlalchemy/lib')
sys.path.append(path)
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    inode = Column(Integer)
    name = Column(String)
    path = Column(String)
    uid = Column(Integer)
    gid = Column(Integer)
    atime = Column(DateTime)
    mtime = Column(DateTime)
    ctime = Column(DateTime)
    size = Column(Integer)
    hash_value = Column(String)

engine = create_engine('sqlite:///filelog.sqlite3', echo=True)
Base.metadata.create_all(engine)

session = sessionmaker(bind = engine)
