"""V3.0 -- as regras de dominio da V3 e o contrato de colunas.

Testes puros: nao tocam banco, nao importam `backend/`.

A regra de tipo de estoque nasceu como copia da do V2.2 e **divergiu de
proposito** em 24/ago/2026, por decisao da Maria (ver `catering/dominio/
tipo_estoque.py`). Estes testes fixam o que ELA decidiu -- nao a igualdade com
o V2 -- para que qualquer mudanca futura seja deliberada.
"""

import pytest

from catering import contrato
from catering.dominio import clientes, tipo_estoque, unidades


# ------------------------------------------------------- tipo de estoque
@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("CONGELADO", "CONGELADO"),
        ("SECO", "SECO"),
        ("HORTIFRUTI", "HORTIFRUTI"),
        ("HORT", "HORTIFRUTI"),
        ("UTENSILIOS", "UTENSILIOS"),
        ("UTENSÍLIOS", "UTENSILIOS"),          # acento normalizado
        ("  congelado  ", "CONGELADO"),        # caixa e espaco
        ("AJUSTE DE TARIFA", "NAO_CLASSIFICADO"),
        ("", "NAO_CLASSIFICADO"),
        (None, "NAO_CLASSIFICADO"),
        # nomes reais do DW, conferidos na medicao de 24/ago/2026
        ("CONGELADO_RMSPII", "CONGELADO"),
        ("SECO - 10591", "SECO"),
        ("HORTI-FRUTI - 14074", "HORTIFRUTI"),
        ("NOVO-CONGELADO", "CONGELADO"),
        ("LC UTENSILIOS - GRUPO GR - RMSPII", "UTENSILIOS"),
        ("RETAIL SECO - 14528", "SECO"),
        ("HORTIFRÚTI", "HORTIFRUTI"),
    ],
)
def test_classifica_por_palavra_chave(valor, esperado):
    assert tipo_estoque.classificar(valor) == esperado


@pytest.mark.parametrize(
    "valor,esperado,porque",
    [
        ("CONG FLV (CUCINARE)", "CONGELADO", "CONG conta como congelado"),
        ("RESFRIADO - PR", "RESFRIADO", "classe de temperatura nova"),
        ("ÁGUA / CARVÃO", "SECO", "de-para por nome exato"),
    ],
)
def test_decisoes_da_maria_de_24_ago(valor, esperado, porque):
    """As tres classificacoes que a Maria decidiu em 24/ago/2026, diante da
    medicao dos 40 nomes do DW. Juntas tiraram 6.313,2 t de NAO_CLASSIFICADO
    (de 10.317,4 t para 4.004,1 t, de 3,2% para 1,3% do peso)."""
    assert tipo_estoque.classificar(valor) == esperado, porque


def test_cong_nao_colide_com_outro_tipo():
    """`CONG` foi conferido contra os 40 nomes do DW: pega os 10 de congelado e
    nao casa com nenhum outro tipo -- `CONSOLIDADOR` tem CONS, nao CONG. Se um
    nome novo trouxer CONG junto de SECO ou HORT, cai em NAO_CLASSIFICADO em
    vez de escolher errado, e este teste documenta isso."""
    assert tipo_estoque.classificar("CONSOLIDADOR") == "NAO_CLASSIFICADO"
    assert tipo_estoque.classificar("CONG SECO") == "NAO_CLASSIFICADO"


def test_de_para_por_nome_exato_e_exato():
    """Nome exato nao e prefixo nem contem: `AGUA` sozinho nao vira SECO. Se
    virasse, qualquer nome com 'agua' seria classificado por acidente."""
    assert tipo_estoque.classificar("ÁGUA / CARVÃO") == "SECO"
    assert tipo_estoque.classificar("AGUA") == "NAO_CLASSIFICADO"
    assert tipo_estoque.classificar("ÁGUA / CARVÃO E MAIS") == "NAO_CLASSIFICADO"
    assert tipo_estoque.regra_que_casou("ÁGUA / CARVÃO") == "nome exato"


def test_ambiguidade_nao_e_desempatada_por_ordem():
    """Valor que casa com duas palavras-chave e ambiguidade real do dado, nao
    empate a resolver pela ordem da lista. Se um dia isto virar um chute
    silencioso, um numero errado passa a existir sem sinal na tela."""
    assert tipo_estoque.classificar("SECO E CONGELADO") == "NAO_CLASSIFICADO"
    assert tipo_estoque.regra_que_casou("SECO E CONGELADO") == "CONGELADO+SECO"


def test_todo_resultado_e_tipo_valido():
    for valor in ("CONGELADO", "SECO", "HORT", "UTENSILIOS", "XPTO", "", None):
        assert tipo_estoque.classificar(valor) in tipo_estoque.TIPOS_VALIDOS


def test_regra_que_casou_serve_de_auditoria():
    assert tipo_estoque.regra_que_casou("CONGELADO GERAL") == "CONGELADO"
    assert tipo_estoque.regra_que_casou("AJUSTE DE TARIFA") == ""
    assert tipo_estoque.regra_que_casou("") == ""


def test_o_que_segue_sem_classificacao():
    """Depois das tres decisoes de 24/ago, sobram 10 nomes em
    NAO_CLASSIFICADO: 875 linhas, 4.004,1 t, 1,3% do peso. `CONSOLIDADOR` e
    `CONSOLIDADOR - 14025` sao 3.872,5 t disso -- 97% do que resta -- e nao
    foram decididos (segue aberto no A-6 do V3_PLANO).

    Nao classifico nenhum por conta propria: a disciplina do projeto e que
    ambiguidade vira sentinela visivel, nunca chute silencioso. Este teste fixa
    o comportamento para que mudar seja deliberado."""
    for nome in ("CONSOLIDADOR", "CONSOLIDADOR - 14025", "RETAIL",
                 "QUÍM/ DESC/ LIMP", "CROSS DOCKING", "EPI", "REAJUSTE",
                 "PAP", "MAQUINARIO", "AJUSTE DE TARIFA"):
        assert tipo_estoque.classificar(nome) == tipo_estoque.NAO_CLASSIFICADO


def test_resfriado_entrou_nos_tipos_validos():
    """Classe nova precisa estar no CHECK da migration tambem -- sem isso a
    carga insere e o banco recusa."""
    assert "RESFRIADO" in tipo_estoque.TIPOS_VALIDOS
    assert len(tipo_estoque.TIPOS_VALIDOS) == 6


# -------------------------------------------------------------- unidades
def test_sigla_e_identidade_por_padrao():
    """Unidade nova entra sozinha com a sigla que o DW mandou -- nao existe
    de-para a manter para as cinco que ja batem."""
    for s in ("RMSPII", "RMRJ", "CWBIII", "MAQ", "RPII"):
        assert unidades.sigla(s) == s
        assert not unidades.tem_excecao(s)


def test_sanca_e_a_unica_excecao():
    """Decisao da Maria em 21/ago/2026: a fonte manda RMSPV, a tela mostra
    RMSPIV."""
    assert unidades.sigla("RMSPV") == "RMSPIV"
    assert unidades.tem_excecao("RMSPV")
    assert list(unidades.SIGLA_EXIBIDA) == ["RMSPV"]


def test_sigla_tolera_espaco_e_vazio():
    assert unidades.sigla("  RMSPV  ") == "RMSPIV"
    assert unidades.sigla("") == ""
    assert unidades.sigla(None) == ""


# -------------------------------------------------------------- clientes
def test_grafia_de_maior_peso_ganha():
    escolhida, grafias = clientes.canonizar([
        ("01838723", "CONVIDA ALIMENTACAO", 100.0),
        ("01838723", "NOVITA ALIMENTACAO", 900.0),
    ])
    assert escolhida["01838723"] == "NOVITA ALIMENTACAO"
    assert grafias["01838723"][0] == ("NOVITA ALIMENTACAO", 900.0)


def test_peso_da_mesma_grafia_acumula():
    escolhida, _ = clientes.canonizar([
        ("02905110", "SAPORE S.A.", 300.0),
        ("02905110", "SAPORE S.A.", 300.0),
        ("02905110", "SAPORE SA", 500.0),
    ])
    assert escolhida["02905110"] == "SAPORE S.A."      # 600 > 500


def test_empate_desempata_alfabeticamente_e_nao_oscila():
    """Sem desempate deterministico o rotulo do cliente poderia trocar de uma
    carga para a outra sem nada mudar na fonte -- e a tela mostraria um nome
    diferente para o mesmo numero."""
    entrada = [("001", "BETA LTDA", 50.0), ("001", "ALFA LTDA", 50.0)]
    primeira, _ = clientes.canonizar(entrada)
    segunda, _ = clientes.canonizar(list(reversed(entrada)))
    assert primeira["001"] == segunda["001"] == "ALFA LTDA"


def test_grafia_vazia_nao_ganha_de_preenchida_no_empate():
    escolhida, _ = clientes.canonizar([("001", "", 50.0), ("001", "ALFA LTDA", 50.0)])
    assert escolhida["001"] == "ALFA LTDA"


def test_grafia_vazia_vence_se_for_a_unica():
    escolhida, _ = clientes.canonizar([("001", "", 50.0)])
    assert escolhida["001"] == ""


def test_raiz_vazia_e_ignorada():
    escolhida, grafias = clientes.canonizar([("", "ALFA", 10.0), ("001", "BETA", 5.0)])
    assert list(escolhida) == ["001"]
    assert "" not in grafias


def test_raiz_preserva_zero_a_esquerda():
    escolhida, _ = clientes.canonizar([("01838723", "ALFA", 1.0)])
    assert "01838723" in escolhida            # nao virou 1838723


def test_divergentes_lista_so_quem_tem_mais_de_uma_grafia():
    _, grafias = clientes.canonizar([
        ("001", "ALFA", 10.0), ("001", "ALPHA", 5.0), ("002", "BETA", 7.0),
    ])
    d = clientes.divergentes(grafias)
    assert list(d) == ["001"]
    assert [g for g, _ in d["001"]] == ["ALFA", "ALPHA"]


def test_raiz_nao_e_unida_a_outra():
    """O Power BI mantem as raizes separadas; inventar uniao aqui afastaria os
    dois lados."""
    escolhida, _ = clientes.canonizar([
        ("01838723", "GRUPO X FILIAL A", 100.0),
        ("02905110", "GRUPO X FILIAL B", 100.0),
    ])
    assert len(escolhida) == 2


# -------------------------------------------------------------- contrato
def test_nome_da_coluna_e_o_do_dw_em_minusculas():
    """A invariante que dispensa tabela de traducao no carregador."""
    for movimento in contrato.MOVIMENTOS:
        for nome, _tipo, _nulo in contrato.colunas(movimento):
            if nome in contrato.RENOMEADAS:
                continue
            assert contrato.coluna_dw(nome, movimento) == nome.upper()
            assert nome == nome.lower()


def test_pk_do_dw_e_a_unica_renomeada():
    assert list(contrato.RENOMEADAS) == ["pk_dw"]
    assert contrato.coluna_dw("pk_dw", "rec") == "PK_FATO_VOL_REC_CAT"
    assert contrato.coluna_dw("pk_dw", "exp") == "PK_FATO_VOL_EXP_CAT"


def test_chave_natural_e_toda_de_colunas_que_existem_nos_dois_fatos():
    for movimento in contrato.MOVIMENTOS:
        nomes = {n for n, _t, _nl in contrato.colunas(movimento)}
        assert set(contrato.CHAVE_NATURAL) <= nomes
        assert set(contrato.CHAVE_ARMAZEM) <= nomes


def test_identificador_com_zero_a_esquerda_e_texto():
    """Convertido para inteiro, `num_gem` '0000000001' deixa de casar com a
    fonte. Nao e preferencia de estilo: e o que quebra o de-para."""
    for movimento in contrato.MOVIMENTOS:
        for nome, tipo, _nulo in contrato.colunas(movimento):
            if nome in contrato.IDENTIFICADORES_TEXTO:
                assert tipo == "TEXT", nome


def test_pallet_nao_existe_na_expedicao():
    """Nenhuma das tres faixas tem pallet. A tela declara isso; o contrato
    precisa dizer o mesmo, senao alguem cria a coluna e ela vem vazia."""
    for faixa in contrato.FAIXAS:
        assert contrato.coluna_exp("pal", faixa) is None
    nomes_exp = {n for n, _t, _nl in contrato.COLUNAS_EXP}
    assert not [n for n in nomes_exp if "pallet" in n]


def test_coluna_da_expedicao_por_lente_e_faixa_existe_no_contrato():
    nomes_exp = {n for n, _t, _nl in contrato.COLUNAS_EXP}
    for lente in contrato.LENTES:
        for faixa in contrato.FAIXAS:
            coluna = contrato.coluna_exp(lente, faixa)
            if coluna is not None:
                assert coluna in nomes_exp, coluna


def test_lente_do_recebimento_existe_no_contrato():
    nomes_rec = {n for n, _t, _nl in contrato.COLUNAS_REC}
    for lente, cfg in contrato.LENTES.items():
        assert cfg["rec"] in nomes_rec, lente


def test_movimento_desconhecido_falha_alto():
    with pytest.raises(KeyError):
        contrato.colunas("xpto")
    with pytest.raises(KeyError):
        contrato.coluna_dw("num_gem", "xpto")
    with pytest.raises(KeyError):
        contrato.coluna_exp("liq", "xpto")
    with pytest.raises(KeyError):
        contrato.coluna_exp("xpto", "solicitado")


def test_dthr_confirm_e_nulavel_de_proposito():
    """0% vazio no medido, mas guia cancelada nao tem confirmacao -- o dia que
    ela entrar na fonte nao pode derrubar a carga."""
    for movimento in contrato.MOVIMENTOS:
        nulo = {n: nl for n, _t, nl in contrato.colunas(movimento)}
        assert nulo["dthr_confirm"] is True
