from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class User(Base):
    __tablename__ = "users"

    # username - Primary Key
    username: Mapped[str] = mapped_column(String, primary_key=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
    last_seen: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    public_key: Mapped[str] = mapped_column(String, nullable=True)