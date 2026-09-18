"""Testes unitários da redação de PII."""

from __future__ import annotations

import pytest

from gestlog.privacy import (
    POLITICA_PADRAO,
    PoliticaRedacao,
    RedactedText,
    redact,
)


def test_texto_sem_pii_fica_intacto() -> None:
    texto = "Qual o prazo da rota sul ate o centro de distribuicao?"
    resultado = redact(texto)
    assert resultado.texto == texto
    assert resultado.categorias == ()
    assert resultado.houve_redacao is False


def test_texto_vazio() -> None:
    resultado = redact("")
    assert resultado.texto == ""
    assert resultado.categorias == ()


@pytest.mark.parametrize(
    "texto",
    [
        "(11) 98765-4321",
        "11 98765-4321",
        "11987654321",
        "(11) 3456-7890",
        "+55 11 98765-4321",
    ],
)
def test_telefones_redigidos(texto: str) -> None:
    resultado = redact(f"Ligar para {texto} antes da coleta")
    assert "[TELEFONE]" in resultado.texto
    assert "98765" not in resultado.texto
    assert "3456" not in resultado.texto
    assert "telefone" in resultado.categorias


def test_endereco_redigido() -> None:
    resultado = redact("Entregar na Rua das Flores, 123 amanha cedo")
    assert "[ENDERECO]" in resultado.texto
    assert "Flores" not in resultado.texto
    assert "endereco" in resultado.categorias


def test_cep_redigido_como_endereco() -> None:
    resultado = redact("O CEP de destino e 01310-100, confirme")
    assert "[ENDERECO]" in resultado.texto
    assert "01310" not in resultado.texto
    assert resultado.categorias == ("endereco",)


def test_nome_redigido() -> None:
    resultado = redact("Confirmar a coleta com João Silva amanha")
    assert "[NOME]" in resultado.texto
    assert "Silva" not in resultado.texto
    assert "nome" in resultado.categorias


def test_nome_com_conector() -> None:
    resultado = redact("A João de Souza pertence a carga")
    assert resultado.texto.startswith("A [NOME] pertence")
    assert "Souza" not in resultado.texto


def test_nome_sem_acentuacao_redigido() -> None:
    resultado = redact("Falar com Joao Silva amanha")
    assert resultado.texto == "Falar com [NOME] amanha"
    assert resultado.categorias == ("nome",)


def test_marcador_com_barra_invertida_e_literal() -> None:
    politica = PoliticaRedacao(nomes=frozenset({"Zeca"}), marcador_nome=r"\1")
    resultado = redact("O Zeca assume a rota", politica)
    assert resultado.texto == r"O \1 assume a rota"


def test_multiplas_categorias() -> None:
    resultado = redact("Falar com Maria Souza no (21) 99876-5432 da Av. Brasil 500")
    assert resultado.categorias == ("telefone", "endereco", "nome")
    assert "Maria" not in resultado.texto
    assert "99876" not in resultado.texto


def test_politica_personalizada_com_nome_extra() -> None:
    politica = PoliticaRedacao(nomes=frozenset({"Zeca"}), marcador_nome="<pessoa>")
    resultado = redact("O Zeca assume a rota", politica)
    assert resultado.texto == "O <pessoa> assume a rota"
    assert resultado.categorias == ("nome",)


def test_politica_padrao_nao_casa_nome_desconhecido() -> None:
    resultado = redact("O Zeca assume a rota", POLITICA_PADRAO)
    assert resultado.texto == "O Zeca assume a rota"
    assert resultado.houve_redacao is False


def test_redacted_text_e_imutavel() -> None:
    resultado = RedactedText(texto="x", categorias=("nome",))
    with pytest.raises(AttributeError):
        resultado.texto = "y"  # type: ignore[misc]
