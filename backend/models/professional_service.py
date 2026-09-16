"""Association model between service professionals and bookable services."""

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class ProfessionalService(Base):
    """Represent a professional's capability to provide a service."""

    __tablename__ = "professional_services"

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

    __table_args__ = (
        UniqueConstraint(
            "professional_id",
            "service_id",
            name="uq_professional_service",
        ),
    )
