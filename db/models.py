from datetime import datetime

from sqlalchemy import update as sqlalchemy_update, insert
from sqlalchemy import (
    ForeignKey,
    String,
    Integer,
    DateTime,
    Column,
    Table,
    select,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, load_only
from sqlalchemy import exc
from .db_connector import Base, async_db_session


class ModelAdmin:
    @classmethod
    async def create(cls, **kwargs) -> int:
        async with async_db_session() as session:
            res = await session.execute(insert(cls).values(**kwargs))
            await session.commit()
            return res.lastrowid

    @classmethod
    async def add(cls, **kwargs):
        async with async_db_session() as session:
            session.add(cls(**kwargs))
            await session.commit()

    @classmethod
    async def update(cls, id_, **kwargs):
        query = sqlalchemy_update(User).where(User.id == id_).values(**kwargs)
        async with async_db_session() as session:
            await session.execute(query)
            await session.commit()

    @classmethod
    async def get(cls, **kwargs):
        params = [getattr(cls, key) == val for key, val in kwargs.items()]
        query = select(cls).where(*params)
        try:
            async with async_db_session() as session:
                results = await session.execute(query)
                (result,) = results.one()
                return result
        except exc.NoResultFound:
            return None

    @classmethod
    async def all(cls, values=None):
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


user_vpn_connections_association_table = Table(
    "user_vpn_connections",
    Base.metadata,
    Column("user_id", ForeignKey("users.id")),
    Column("vpn_conn_id", ForeignKey("vpn_connections.id")),
)


class User(Base, ModelAdmin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int]
    vpn_connections: Mapped[list["VPNConnection"]] = relationship(
        secondary=user_vpn_connections_association_table
    )
    active_bills: Mapped[list["ActiveBills"]] = relationship()

    @classmethod
    async def get_by_tg(cls, tg_id: int):
        query = select(cls).where(cls.tg_id == tg_id)
        try:
            async with async_db_session() as session:
                results = await session.execute(query)
                (result,) = results.one()
                return result
        except exc.NoResultFound:
            return None


class Server(Base, ModelAdmin):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))
    ip: Mapped[str] = mapped_column(String(45))
    login: Mapped[str] = mapped_column(String(50))
    password: Mapped[str] = mapped_column(String(50))
    location: Mapped[str] = mapped_column(String(100))
    country_code: Mapped[str] = mapped_column(String(6))
    vpn_connections: Mapped[list["VPNConnection"]] = relationship()


class VPNConnection(Base, ModelAdmin):
    __tablename__ = "vpn_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    available: Mapped[bool]
    local_ip: Mapped[str] = mapped_column(String(15))
    available_to: Mapped[datetime] = mapped_column(server_default=func.now())
    free: Mapped[int] = mapped_column(Integer(), default=1)
    config: Mapped[str] = mapped_column(Text())

    @staticmethod
    async def get_free(server_id: int, limit: int):
        async with async_db_session() as session:
            query = (
                select(VPNConnection)
                .where(VPNConnection.server_id == server_id)
                .where(VPNConnection.free == 1)
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
        secondary=bills_vpn_connections_association_table
    )
    available_to: Mapped[datetime] = mapped_column(DateTime())
    type: Mapped[str] = mapped_column(String(50))
    rent_month: Mapped[int]
    pay_url: Mapped[str] = mapped_column(String(255))
