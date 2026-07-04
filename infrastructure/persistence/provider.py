"""DatabaseProvider — backend abstraction (SQLite dev / MariaDB prod).

Keeps the rest of the app independent of the concrete DBMS; see the skill's
persistence reference.
"""
from abc import ABC, abstractmethod

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DatabaseProvider(ABC):
    @abstractmethod
    def engine(self): ...


class SqliteProvider(DatabaseProvider):
    def __init__(self, url: str = "sqlite:///./musterdepot.sqlite"):
        self._engine = create_engine(url, future=True)

    def engine(self):
        return self._engine


class MariaDbProvider(DatabaseProvider):
    def __init__(self, url: str):
        self._engine = create_engine(url, pool_pre_ping=True, future=True)

    def engine(self):
        return self._engine


def build_database_provider(settings) -> DatabaseProvider:
    if settings.db_backend == "mariadb":
        return MariaDbProvider(settings.db_url)
    return SqliteProvider(settings.db_url)


def build_session_factory(provider: DatabaseProvider):
    return sessionmaker(bind=provider.engine(), future=True, expire_on_commit=False)
