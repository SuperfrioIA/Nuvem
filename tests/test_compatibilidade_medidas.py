"""Testes do motor de compatibilidade de medidas (Bloco B / V1.2). Funcoes
puras -- a tabela de unidades entra como dicionario, sem banco."""

import pytest

from backend.services import compatibilidade_medidas as cm

# espelho reduzido do seed real (backend/seed_semantico.py)
_TABELA = {
    "kg": {"categoria": "massa", "fator": 1, "base": True},
    "t": {"categoria": "massa", "fator": 1000, "base": False},
    "g": {"categoria": "massa", "fator": 0.001, "base": False},
    "lb": {"categoria": "massa", "fator": 0.45359237, "base": False},
    "brl": {"categoria": "valor_monetario", "fator": 1, "base": True},
    "posicao": {"categoria": "estrutura_logistica", "fator": None, "base": False},
    "ua": {"categoria": "estrutura_logistica", "fator": None, "base": False},
    "pct": {"categoria": "percentual", "fator": 1, "base": True},
}


# --- converter ---------------------------------------------------------------


def test_conversoes_seguras_de_massa():
    assert cm.converter(2, "t", "kg", _TABELA) == 2000.0
    assert cm.converter(500, "g", "kg", _TABELA) == 0.5
    assert cm.converter(10, "lb", "kg", _TABELA) == pytest.approx(4.5359237)
    assert cm.converter(2500, "kg", "t", _TABELA) == 2.5


def test_mesma_unidade_nao_converte():
    assert cm.converter(7.5, "kg", "kg", _TABELA) == 7.5
    # mesma unidade vale ate pra unidade fora do catalogo
    assert cm.converter(3, "CXS", "CXS", _TABELA) == 3.0


def test_conversao_entre_categorias_e_proibida():
    with pytest.raises(cm.ConversaoInvalidaError, match="categorias diferentes"):
        cm.converter(1, "kg", "brl", _TABELA)


def test_conversao_com_unidade_desconhecida_e_proibida():
    with pytest.raises(cm.ConversaoInvalidaError, match="fora do catálogo"):
        cm.converter(1, "CXS", "kg", _TABELA)


def test_conversao_sem_fator_registrado_e_proibida():
    # posicao e ua sao da mesma categoria, mas nao ha conversao entre elas
    with pytest.raises(cm.ConversaoInvalidaError, match="sem fator"):
        cm.converter(1, "posicao", "ua", _TABELA)


def test_percentual_identidade_passa_mas_conversao_entre_percentuais_nao():
    # mesma unidade e identidade (nenhuma conta feita) -- permitido
    assert cm.converter(50, "pct", "pct", _TABELA) == 50.0
    # entre unidades percentuais DIFERENTES nao ha conversao valida
    tabela = {**_TABELA, "pontos_base": {"categoria": "percentual", "fator": 1, "base": False}}
    with pytest.raises(cm.ConversaoInvalidaError, match="[Pp]ercentuais"):
        cm.converter(50, "pct", "pontos_base", tabela)


# --- podem_consolidar --------------------------------------------------------


def test_podem_consolidar_mesma_unidade_e_mesma_categoria_com_fator():
    assert cm.podem_consolidar("kg", "kg", _TABELA)[0] is True
    assert cm.podem_consolidar("kg", "t", _TABELA)[0] is True
    assert cm.podem_consolidar("CXS", "CXS", _TABELA)[0] is True


def test_bloqueios_do_direcionamento():
    # caixa + kg / unidade + palete / caixa + unidade / volume sem unidade
    assert cm.podem_consolidar("CXS", "kg", _TABELA)[0] is False
    assert cm.podem_consolidar("UND", "palete", _TABELA)[0] is False
    assert cm.podem_consolidar("CXS", "UND", _TABELA)[0] is False
    assert cm.podem_consolidar("posicao", "ua", _TABELA)[0] is False
    ok, motivo = cm.podem_consolidar("kg", "brl", _TABELA)
    assert ok is False
    assert "categorias diferentes" in motivo


def test_percentual_nunca_soma_nem_com_percentual():
    ok, motivo = cm.podem_consolidar("pct", "pct", _TABELA)
    assert ok is False
    assert "percentuais" in motivo.lower()


# --- somar_medidas -----------------------------------------------------------


def test_soma_converte_pra_base_da_categoria():
    resultado = cm.somar_medidas([(2, "t"), (500, "kg"), (500, "g")], _TABELA)
    assert len(resultado["grupos"]) == 1
    grupo = resultado["grupos"][0]
    assert grupo["unidade"] == "kg"
    assert grupo["total"] == pytest.approx(2500.5)
    assert grupo["itens"] == 3
    assert grupo["convertidos"] == 2
    assert resultado["limitacoes"] == []


def test_soma_separa_unidades_sem_compatibilidade():
    resultado = cm.somar_medidas(
        [(10, "CXS"), (5, "CXS"), (3, "PCT"), (1, "KGS")], _TABELA
    )
    por_unidade = {g["unidade"]: g for g in resultado["grupos"]}
    assert por_unidade["CXS"]["total"] == 15.0
    assert por_unidade["PCT"]["total"] == 3.0
    assert por_unidade["KGS"]["total"] == 1.0
    assert len(resultado["grupos"]) == 3
    assert any("separadas" in m for m in resultado["limitacoes"])


def test_soma_nao_mistura_categorias_e_declara():
    resultado = cm.somar_medidas([(1000, "kg"), (10, "CXS")], _TABELA)
    assert {g["unidade"] for g in resultado["grupos"]} == {"kg", "CXS"}
    assert any("não existe um total geral" in m for m in resultado["limitacoes"])


def test_percentual_fica_fora_de_qualquer_soma():
    resultado = cm.somar_medidas([(50, "pct"), (30, "pct")], _TABELA)
    assert resultado["grupos"] == []
    assert any("percentuais" in m.lower() for m in resultado["limitacoes"])
    assert all(a["grupo"] is None for a in resultado["auditoria"])


def test_auditoria_registra_cada_item():
    resultado = cm.somar_medidas([(2, "t"), (10, "CXS")], _TABELA)
    assert len(resultado["auditoria"]) == 2
    por_unidade = {a["unidade_original"]: a for a in resultado["auditoria"]}
    assert por_unidade["t"]["grupo"] == "kg"
    assert por_unidade["t"]["convertido"] is True
    assert por_unidade["CXS"]["grupo"] == "CXS"
    assert por_unidade["CXS"]["convertido"] is False


def test_grupos_ordenados_do_maior_pro_menor():
    resultado = cm.somar_medidas([(3, "PCT"), (15, "CXS"), (7, "UND")], _TABELA)
    assert [g["unidade"] for g in resultado["grupos"]] == ["CXS", "UND", "PCT"]


def test_lista_vazia_nao_quebra():
    resultado = cm.somar_medidas([], _TABELA)
    assert resultado == {"grupos": [], "limitacoes": [], "auditoria": []}


def test_unidade_com_espacos_ou_ausente_e_normalizada():
    # "CXS " e "CXS" sao o mesmo grupo; None/vazio ganham rotulo explicito
    resultado = cm.somar_medidas([(1, "CXS "), (2, "CXS"), (3, None), (4, "  ")], _TABELA)
    por_unidade = {g["unidade"]: g["total"] for g in resultado["grupos"]}
    assert por_unidade["CXS"] == 3.0
    assert por_unidade["(sem unidade)"] == 7.0


def test_valor_nao_numerico_da_erro_do_motor_nao_de_baixo_nivel():
    with pytest.raises(cm.ConversaoInvalidaError, match="não numérico"):
        cm.converter("2,5", "t", "kg", _TABELA)
