import os
import sys

path = os.path.join(os.path.dirname(__file__), './lib/sqlalchemy/lib')
sys.path.append(path)
from sqlalchemy.engine import create_engine
from sqlalchemy.types import Integer, String, DateTime
from sqlalchemy.schema import Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relation

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

class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    copy_log_id = Column(Integer, ForeignKey("copy_logs.id"))
    file_id = Column(Integer, ForeignKey("files.id"))
    file = relation("File", uselist=False)

class Destination(Base):
    __tablename__ = "destinations"

    id = Column(Integer, primary_key=True)
    copy_log_id = Column(Integer, ForeignKey("copy_logs.id"))
    file_id = Column(Integer, ForeignKey("files.id"))
    file = relation("File", uselist=False)

class CopyLog(Base):
    __tablename__ = "copy_logs"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime)

    # Define relation to File, using middle table ("Source" and "Destination")
    # example: CopyLog().source = File()
    source = relation("File", uselist=False, secondary="sources")
    destination = relation("File", uselist=False, secondary="destinations")

engine = create_engine('sqlite:///filelog.sqlite3', echo=False)
Base.metadata.create_all(engine)

session = sessionmaker(bind = engine)
