from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Boolean,
    DateTime,
    Sequence,
    UniqueConstraint,
    text,
    func,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from os import getenv

Base = declarative_base()

load_dotenv()
host = getenv("DB_HOST")
user = getenv("DB_USER")
port = getenv("DB_PORT")
database = getenv("DATABASE")
password = getenv("PASSWORD")


connection_params = {
    "host": host,
    "port": port,
    "database": database,
    "user": user,
    "password": password,
    "sslmode": "require",
}


class GameData(Base):
    __tablename__ = "game_data"

    id = Column(
        Integer,
        Sequence("game_data_id_seq", start=1, increment=1),
        primary_key=True,
        nullable=False,
        server_default=text("nextval('game_data_id_seq'::regclass)"),
    )
    game = Column(String, nullable=False)
    announced = Column(Date, nullable=False)
    pid1 = Column(String, nullable=True)
    pid2 = Column(String, nullable=True)
    pid3 = Column(String, nullable=True)
    pid4 = Column(String, nullable=True)
    pid5 = Column(String, nullable=True)
    added = Column(Date, nullable=True)
    removed = Column(Date, nullable=True)
    release = Column(Date, nullable=True)
    indie = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    f2p = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    first_party = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    igdb = Column(Integer, nullable=True)
    steam = Column(Integer, nullable=True)
    opencritic = Column(Integer, nullable=True)
    date_created = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    date_edited = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (UniqueConstraint("game", "added", name="uq_game_added"),)

    def __repr__(self):
        return f"<GameData(id={self.id}, game='{self.game}')>"


def get_engine(connection_params):
    url = (
        f"postgresql+psycopg2://{connection_params['user']}:{connection_params['password']}"
        f"@{connection_params['host']}:{connection_params['port']}/{connection_params['database']}"
        f"?sslmode={connection_params['sslmode']}"
    )
    return create_engine(url)


def get_session(connection_params):
    engine = get_engine(connection_params)
    Session = sessionmaker(bind=engine)
    return Session()
