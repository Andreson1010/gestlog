"""Política de redação de PII: termos reconhecidos e marcadores de substituição."""

from __future__ import annotations

from dataclasses import dataclass

NOMES_COMUNS: frozenset[str] = frozenset(
    {
        "Alexandre",
        "Ana",
        "André",
        "Antônio",
        "Beatriz",
        "Bianca",
        "Bruno",
        "Camila",
        "Carla",
        "Carlos",
        "Carolina",
        "Cláudia",
        "Daniela",
        "Débora",
        "Diego",
        "Eduarda",
        "Eduardo",
        "Eliane",
        "Fábio",
        "Felipe",
        "Fernanda",
        "Francisco",
        "Gabriel",
        "Gabriela",
        "Gustavo",
        "Helena",
        "Henrique",
        "Igor",
        "Isabel",
        "Isabela",
        "Jéssica",
        "João",
        "Jorge",
        "José",
        "Juliana",
        "Júlio",
        "Larissa",
        "Leandro",
        "Leonardo",
        "Letícia",
        "Lucas",
        "Luciana",
        "Luís",
        "Luiz",
        "Luiza",
        "Marcelo",
        "Márcia",
        "Márcio",
        "Marcos",
        "Maria",
        "Mariana",
        "Mateus",
        "Maurício",
        "Michele",
        "Nelson",
        "Otávio",
        "Patrícia",
        "Paula",
        "Paulo",
        "Pedro",
        "Priscila",
        "Rafael",
        "Renata",
        "Renato",
        "Ricardo",
        "Roberta",
        "Roberto",
        "Rodrigo",
        "Sandra",
        "Sérgio",
        "Silvia",
        "Simone",
        "Tatiane",
        "Thiago",
        "Vanessa",
        "Verônica",
        "Vinícius",
        "Vitor",
        "Vitória",
        "William",
    }
)


@dataclass(frozen=True)
class PoliticaRedacao:
    """Termos reconhecidos e marcadores usados para redigir PII de um texto."""

    nomes: frozenset[str] = NOMES_COMUNS
    marcador_nome: str = "[NOME]"
    marcador_endereco: str = "[ENDERECO]"
    marcador_telefone: str = "[TELEFONE]"


POLITICA_PADRAO = PoliticaRedacao()

CATEGORIA_NOME = "nome"
CATEGORIA_ENDERECO = "endereco"
CATEGORIA_TELEFONE = "telefone"
