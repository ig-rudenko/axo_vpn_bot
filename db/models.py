from datetime import datetime

import flag
from sqlalchemy import exc
from sqlalchemy.schema import ForeignKey, Column, Table
from sqlalchemy.types import String, DateTime, Text, Integer
from sqlalchemy.sql import select, insert, update as sqlalchemy_update
from sqlalchemy.sql.functions import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.strategy_options import load_only, selectinload
from sqlalchemy.orm.collections import InstrumentedList

from .db_connector import Base, async_db_session


class ModelAdmin:
    @classmethod
    async def create(cls, **kwargs) -> int:
        """
        # Создаем новый объект
        :param kwargs: Поля и значения для объекта
        :return: Идентификатор PK
        """

        async with async_db_session() as session:
            res = await session.execute(insert(cls).values(**kwargs))
            await session.commit()
            return res.lastrowid

    @classmethod
    async def add(cls, **kwargs) -> None:
        """
        # Добавляем новый объект
        :param kwargs: Поля и значения для объекта
        """

        async with async_db_session() as session:
            session.add(cls(**kwargs))
            await session.commit()

    async def update(self, **kwargs) -> None:
        """
        # Обновляем текущий объект
        :param kwargs: поля и значения, которые надо поменять
        """

        async with async_db_session() as session:
            await session.execute(
                sqlalchemy_update(VPNConnection), [{"id": self.id, **kwargs}]
            )
            await session.commit()

    async def delete(self) -> None:
        """
        # Удаляем объект
        """
        async with async_db_session() as session:
            await session.delete(self)
            await session.commit()

    @classmethod
    async def get(cls, **kwargs):
        """
        # Возвращаем одну запись, которая удовлетворяет введенным параметрам
        :param kwargs: поля и значения
        :return: Объект или None
        """

        params = [getattr(cls, key) == val for key, val in kwargs.items()]
        query = select(cls).where(*params)
        try:
            async with async_db_session() as session:
                results = await session.execute(query)
                (result,) = results.one()
                result: cls
                return result
        except exc.NoResultFound:
            return None

    @classmethod
    async def filter(cls, **kwargs):
        """
        # Возвращаем все записи, которые удовлетворяют фильтру
        :param kwargs: поля и значения
        :return: ScalarResult, если нашли записи и пустой tuple, если нет
        """

        params = [getattr(cls, key) == val for key, val in kwargs.items()]
        query = select(cls).where(*params)
        try:
            async with async_db_session() as session:
                results = await session.execute(query)
                return results.scalars()
        except exc.NoResultFound:
            return ()

    @classmethod
    async def all(cls, values=None):
        """
        # Получаем все записи
        :param values: Список полей, которые надо вернуть, если нет, то все (default None)
        :return: ScalarResult записей
        """

        if values and isinstance(values, list):
            # Определенные поля
            values = [getattr(cls, val) for val in values if isinstance(val, str)]
            query = select(cls).options(load_only(*values))
        else:
            # Все поля
            query = select(cls)

        async with async_db_session() as session:
            result = await session.execute(query)
            return result.scalars()


class User(Base, ModelAdmin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int]

    active_bills: Mapped[list["ActiveBills"]] = relationship()

    @classmethod
    async def get_or_create(cls, tg_id: int) -> "User":
        user: User = await User.get(tg_id=tg_id)
        if user is None:
            user: User = await User.get(id=await User.create(tg_id=tg_id))
        return user

    async def get_connections(self) -> list:
        async with async_db_session() as session:
            query = select(VPNConnection).where(
                VPNConnection.user_id == self.id,
                VPNConnection.available == True,
                VPNConnection.available_to != None,
            )
            connections = await session.execute(query)

        return [c for c in connections.scalars()]

    async def get_active_bills(self) -> InstrumentedList:
        async with async_db_session() as session:
            query = (
                select(User)
                .where(User.tg_id == self.tg_id)
                .options(
                    selectinload(User.active_bills).selectinload(
                        ActiveBills.vpn_connections
                    )
                )
            )
            user = await session.execute(query)

        return user.scalars().one().active_bills


class Server(Base, ModelAdmin):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    ip: Mapped[str] = mapped_column(String(45), unique=True)
    port: Mapped[str] = mapped_column(Integer(), default=22)
    login: Mapped[str] = mapped_column(String(50))
    password: Mapped[str] = mapped_column(String(50))
    location: Mapped[str] = mapped_column(String(100))
    country_code: Mapped[str] = mapped_column(String(6))
    vpn_connections: Mapped[list["VPNConnection"]] = relationship()

    @property
    def verbose_location(self) -> str:
        return f"{flag.flag(self.country_code)} {self.location}"


class VPNConnection(Base, ModelAdmin):
    __tablename__ = "vpn_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    available: Mapped[bool]
    local_ip: Mapped[str] = mapped_column(String(15))
    available_to: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=True
    )
    config: Mapped[str] = mapped_column(Text())
    client_name: Mapped[str] = mapped_column(String(30))

    @staticmethod
    async def get_free(server_id: int, limit: int):
        async with async_db_session() as session:
            query = (
                select(VPNConnection)
                .where(VPNConnection.server_id == server_id)
                .where(VPNConnection.user_id.is_(None))
                .options(load_only(VPNConnection.id))
                .limit(limit)
            )
            res = await session.execute(query)
            return res.scalars()


bills_vpn_connections_association_table = Table(
    "bills_vpn_connections",
    Base.metadata,
    Column("bill_id", ForeignKey("active_bills.id")),
    Column("vpn_conn_id", ForeignKey("vpn_connections.id")),
)


class ActiveBills(Base, ModelAdmin):
    __tablename__ = "active_bills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bill_id: Mapped[str] = mapped_column(String(255))
    user: Mapped[int] = mapped_column(ForeignKey("users.id"))
    vpn_connections: Mapped[list["VPNConnection"]] = relationship(
        secondary=bills_vpn_connections_association_table,
        backref="active_bills",
        cascade="save-update, merge, delete",
    )
    available_to: Mapped[datetime] = mapped_column(
        DateTime(), nullable=True, default=None
    )
    type: Mapped[str] = mapped_column(String(50))
    rent_month: Mapped[int]
    pay_url: Mapped[str] = mapped_column(String(255))
