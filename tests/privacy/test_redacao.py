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


def test_telefone_sem_mascara_de_onze_digitos_vira_documento() -> None:
    """Telefone sem máscara e CPF compartilham 11 dígitos; documento vem antes.

    A ordem fixa do design (documento antes de telefone) redige o run de
    dígitos como ``[DOCUMENTO]`` — a redação nunca é perdida, só a categoria
    do caso ambíguo sem máscara.
    """
    resultado = redact("Ligar para 11987654321 antes da coleta")
    assert "11987654321" not in resultado.texto
    assert resultado.categorias == ("documento",)


@pytest.mark.parametrize(
    "email",
    ["ana.silva@empresa.com.br", "joão@empresa.com"],
)
def test_email_redigido(email: str) -> None:
    resultado = redact(f"Confirmar com {email} o recebimento")
    assert "[EMAIL]" in resultado.texto
    assert email not in resultado.texto
    assert "@" not in resultado.texto
    assert resultado.categorias == ("email",)


@pytest.mark.parametrize(
    "documento",
    ["12.345.678/0001-99", "12345678000199"],
)
def test_cnpj_redigido_como_documento(documento: str) -> None:
    resultado = redact(f"CNPJ do fornecedor: {documento} na nota")
    assert "[DOCUMENTO]" in resultado.texto
    assert "0001" not in resultado.texto
    assert resultado.categorias == ("documento",)


@pytest.mark.parametrize(
    "documento",
    ["123.456.789-01", "12345678901"],
)
def test_cpf_redigido_como_documento(documento: str) -> None:
    resultado = redact(f"CPF do contato: {documento} na nota")
    assert "[DOCUMENTO]" in resultado.texto
    assert "789" not in resultado.texto
    assert resultado.categorias == ("documento",)


def test_cpf_nao_e_capturado_como_telefone() -> None:
    resultado = redact("Documento do motorista: 123.456.789-01 na coleta")
    assert resultado.texto.count("[DOCUMENTO]") == 1
    assert "[TELEFONE]" not in resultado.texto
    assert resultado.categorias == ("documento",)


def test_cnpj_nao_e_capturado_como_cpf() -> None:
    resultado = redact("CNPJ do parceiro: 12.345.678/0001-99 na nota")
    assert resultado.texto.count("[DOCUMENTO]") == 1
    assert "[EMAIL]" not in resultado.texto
    assert resultado.categorias == ("documento",)


def test_email_cpf_e_cnpj_sao_redigidos_juntos() -> None:
    texto = "Enviar para ana@x.com, CPF 123.456.789-01, CNPJ 12.345.678/0001-99"
    resultado = redact(texto)
    assert resultado.categorias == ("email", "documento")
    assert "@" not in resultado.texto
    assert "123.456" not in resultado.texto
    assert "12345678000199" not in resultado.texto


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
