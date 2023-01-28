from datetime import datetime
from sqlalchemy import ForeignKey, String, Integer, DateTime, Column, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


user_vpn_connections_association_table = Table(
    "user_vpn_connections",
    Base.metadata,
    Column("user_id", ForeignKey("users.id")),
    Column("vpn_conn_id", ForeignKey("vpn_connections.id")),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int]
    vpn_connections: Mapped[list["VPNConnection"]] = relationship(
        secondary=user_vpn_connections_association_table
    )
    active_bills: Mapped[list["ActiveBills"]] = relationship()


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))
    ip: Mapped[str] = mapped_column(String(45))
    login: Mapped[str] = mapped_column(String(50))
    password: Mapped[str] = mapped_column(String(50))
    location: Mapped[str] = mapped_column(String(100))
    vpn_connections: Mapped[list["VPNConnection"]] = relationship()


class VPNConnection(Base):
    __tablename__ = "vpn_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    available: Mapped[bool]
    local_ip: Mapped[str] = mapped_column(String(15))
    available_to: Mapped[datetime] = mapped_column(DateTime())
    free: Mapped[int] = mapped_column(Integer(), default=1)


bills_vpn_connections_association_table = Table(
    "bills_vpn_connections",
    Base.metadata,
    Column("bill_id", ForeignKey("active_bills.id")),
    Column("vpn_conn_id", ForeignKey("vpn_connections.id")),
)


class ActiveBills(Base):
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
