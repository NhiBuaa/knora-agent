from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from knora.infrastructure.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
