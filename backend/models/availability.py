"""Availability windows for service professionals."""

from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class Availability(Base):
    """Represent a professional's available time window for a service."""

    __tablename__ = "availabilities"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
