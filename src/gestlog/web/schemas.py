"""Schemas de entrada das rotas web."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Papel = Literal["admin", "operador", "gestor"]
DecisaoFeedback = Literal["aceita", "descartada"]


class ContaCreate(BaseModel):
    """Dados para criar a conta da empresa e o usuário administrador."""

    nome_empresa: str = Field(min_length=1, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=128)

    @field_validator("nome_empresa")
    @classmethod
    def _rejeitar_nome_vazio(cls, valor: str) -> str:
        """Normaliza e rejeita nome de empresa composto só por espaços."""
        nome = valor.strip()
        if not nome:
            raise ValueError("nome_empresa não pode ser vazio")
        return nome


class ConviteCreate(BaseModel):
    """Dados para convidar um usuário para a empresa da sessão."""

    email: EmailStr
    papel: Papel = "operador"
    senha: str = Field(min_length=8, max_length=128)


class PapelAtualizar(BaseModel):
    """Novo papel de um usuário da empresa (gestão pelo administrador)."""

    papel: Papel
