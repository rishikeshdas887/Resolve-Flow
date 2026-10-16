"""SQLAlchemy ORM model for the ``students`` table."""

from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    course: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enrollment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
