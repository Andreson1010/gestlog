"""Schemas de entrada das rotas web."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Papel = Literal["admin", "operador", "gestor"]


class ContaCreate(BaseModel):
    """Dados para criar a conta da empresa e o usuário administrador."""

    nome_empresa: str = Field(min_length=1, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=128)


class ConviteCreate(BaseModel):
    """Dados para convidar um usuário para a empresa da sessão."""

    email: EmailStr
    papel: Papel = "operador"
    senha: str = Field(min_length=8, max_length=128)
