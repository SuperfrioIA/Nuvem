"""Testes da classificacao de tipo de estoque (lote V2.2), puros -- sem banco.

Os nove valores observados vem de memory/operacao-e-tipo-estoque.md (conferido
no dado em 06/ago/2026, filial 016).
"""

import pytest

from backend.services import tipo_estoque


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("SECO_RMSPII", "SECO"),
        ("SECO", "SECO"),
        ("SECO-2023", "SECO"),
        ("SECO - 2015", "SECO"),
        ("SECO FLV (CUCINARE)", "SECO"),
        ("LC SECO - GRUPO GR - RMSPII", "SECO"),
        ("HORT-FRUTTI", "HORTIFRUTI"),
        ("HORTIFRUTI", "HORTIFRUTI"),
        ("HORTI_RMSPII", "HORTIFRUTI"),
        ("CONGELADO", "CONGELADO"),
        ("LC UTENSILIOS - GRUPO GR - RMSPII", "UTENSILIOS"),
        # minusculo e com acento -- normalizacao
        ("congelado", "CONGELADO"),
        ("hortifrúti", "HORTIFRUTI"),
        ("  SECO  ", "SECO"),
    ],
)
def test_classifica_os_nove_valores_conhecidos(valor, esperado):
    assert tipo_estoque.classificar(valor) == esperado


@pytest.mark.parametrize("valor", [None, "", "   ", "ARMAZEM GERAL XYZ", "001"])
def test_valor_vazio_ou_sem_palavra_chave_e_nao_classificado(valor):
    assert tipo_estoque.classificar(valor) == tipo_estoque.NAO_CLASSIFICADO


def test_valor_com_duas_palavras_chave_e_ambiguo_nao_desempata(monkeypatch):
    """Conflito (mais de uma palavra-chave casando) e NAO_CLASSIFICADO, nunca
    resolvido por ordem da lista -- nao existe no dado real hoje, mas o
    comportamento e o guarda contra um valor futuro ambiguo."""
    assert tipo_estoque.classificar("SECO CONGELADO") == tipo_estoque.NAO_CLASSIFICADO


def test_valor_numerico_nao_quebra():
    assert tipo_estoque.classificar(12345) == tipo_estoque.NAO_CLASSIFICADO


def test_tipos_validos_inclui_o_sentinela():
    assert tipo_estoque.TIPOS_VALIDOS == {
        "CONGELADO", "SECO", "HORTIFRUTI", "UTENSILIOS", "NAO_CLASSIFICADO",
    }
