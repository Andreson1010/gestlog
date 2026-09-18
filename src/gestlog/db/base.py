"""Base declarativa compartilhada pelos modelos do sistema."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Classe base declarativa do SQLAlchemy 2.x."""
