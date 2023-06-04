import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class AsyncDatabaseSession:
    def __init__(self):
        login = os.getenv("MYSQL_LOGIN")
        password = os.getenv("MYSQL_PASSWORD")
        database = os.getenv("MYSQL_DATABASE")
        host = os.getenv("MYSQL_HOST")

        self._engine = create_async_engine(
            f"mysql+aiomysql://{login}:{password}@{host}/{database}?charset=utf8mb4"
        )
        self._session = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    def __call__(self):
        return self._session()

    def __getattr__(self, name):
        return getattr(self._session, name)

    async def create_all(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await self._engine.dispose()


async_db_session = AsyncDatabaseSession()
