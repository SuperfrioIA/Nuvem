"""Perfil deterministico (Bloco D / V1.4) -- funcao pura, sem banco e sem rede.

O que esta fixado aqui: tipo dominante com conformidade declarada, nulos,
distintos, min/max, duplicidades, chaves candidatas, cobertura temporal,
clientes, granularidade, qualidade, amostra -- e, principalmente, a regra de
que **soma so sai quando o catalogo autoriza** (e nunca por posicao quando a
estrutura do arquivo diverge do catalogo).
"""

from datetime import date, datetime

import pytest

from backend.services import perfil_dados

# tabela de unidades espelhando o seed (backend/seed_semantico.py) -- o motor
# de compatibilidade recebe dicionario, entao o teste nao precisa de banco
_TABELA = {
    "kg": {"categoria": "massa", "fator": 1, "base": True},
    "t": {"categoria": "massa", "fator": 1000, "base": False},
    "brl": {"categoria": "valor_monetario", "fator": 1, "base": True},
    "un": {"categoria": "quantidade", "fator": 1, "base": True},
    "pct": {"categoria": "percentual", "fator": 1, "base": True},
}


def _leitura(colunas: list[str], linhas: list[list], **extra) -> dict:
    base = {
        "item_id": "item-1",
        "arquivo": "ENTRADA_MERCADORIAS_016_2607.xlsx",
        "caminho": "RMSPII/ENTRADA/ENTRADA MERCADORIAS/ENTRADA_MERCADORIAS_016_2607.xlsx",
        "web_url": "https://exemplo/arquivo",
        "tamanho": 1000,
        "modificado_em": "2026-07-13T00:00:00Z",
        "familia": "ENTRADA_MERCADORIAS",
        "area": "ENTRADA",
        "estado_familia": "integrada",
        "filial": "016",
        "competencia": "2026-07",
        "aba": "SLIN",
        "abas": ["SLIN"],
        "linha_cabecalho": 1,
        "origem_linha_cabecalho": "familia",
        "colunas": [{"posicao": i + 1, "nome": nome} for i, nome in enumerate(colunas)],
        "linhas": linhas,
        "linhas_lidas": len(linhas),
        "truncado": False,
    }
    base.update(extra)
    return base


def _campo(posicao, nome, **extra) -> dict:
    # agregacao 'soma' no default espelha os campos somaveis do seed real
    # (Peso Bruto, Vlr. Total, Qtde UA...); soma exige declaracao explicita
    campo = {
        "posicao": posicao,
        "nome_original": nome,
        "conceito_chave": None,
        "unidade_canonica": None,
        "unidade_por_coluna": None,
        "categoria_unidade": None,
        "dim_cliente": False,
        "agregacao": "soma",
        "status": "aprovado",
    }
    campo.update(extra)
    return campo


def _coluna(perfil: dict, nome: str) -> dict:
    return next(c for c in perfil["colunas"] if c["nome"] == nome)


# --- tipos, nulos, distintos, min/max ------------------------------------------


def test_tipos_nulos_distintos_e_extremos():
    leitura = _leitura(
        ["Cliente", "Peso", "Data", "Vazia"],
        [
            ["SAPORE", 10, datetime(2026, 7, 1), None],
            ["SAPORE", 30.5, datetime(2026, 7, 15), None],
            [None, 20, datetime(2026, 7, 3), None],
        ],
    )
    perfil = perfil_dados.perfilar(leitura, [], _TABELA)

    cliente = _coluna(perfil, "Cliente")
    assert cliente["tipo"] == "texto"
    assert cliente["nulos"] == 1
    assert cliente["nulos_pct"] == 33.3
    assert cliente["distintos"] == 1
    assert cliente["exemplos"] == ["SAPORE"]

    peso = _coluna(perfil, "Peso")
    assert (peso["tipo"], peso["conformidade_pct"]) == ("numero", 100.0)
    assert (peso["minimo"], peso["maximo"]) == (10.0, 30.5)
    assert peso["distintos"] == 3

    data = _coluna(perfil, "Data")
    assert data["tipo"] == "data"
    assert (data["minimo"], data["maximo"]) == ("2026-07-01", "2026-07-15")

    assert _coluna(perfil, "Vazia")["tipo"] == "vazio"


def test_numero_br_em_texto_conta_como_numero():
    leitura = _leitura(["Valor"], [["1.234,56"], ["10"], [7.5]])
    coluna = _coluna(perfil_dados.perfilar(leitura, [], _TABELA), "Valor")
    assert coluna["tipo"] == "numero"
    assert coluna["maximo"] == 1234.56


def test_tipo_dominante_declara_conformidade():
    """Uma celula suja no meio de coluna numerica nao transforma a coluna em
    texto -- o tipo continua numero e a conformidade denuncia o resto."""
    linhas = [[i] for i in range(19)] + [["N/A"]]
    coluna = _coluna(perfil_dados.perfilar(_leitura(["Qtde"], linhas), [], _TABELA), "Qtde")
    assert coluna["tipo"] == "numero"
    assert coluna["conformidade_pct"] == 95.0


def test_maioria_suja_vira_texto():
    linhas = [["a"], ["b"], [1], [2]]
    coluna = _coluna(perfil_dados.perfilar(_leitura(["Mix"], linhas), [], _TABELA), "Mix")
    assert coluna["tipo"] == "texto"


# --- soma: quem decide e o catalogo ---------------------------------------------


def test_soma_permitida_com_campo_aprovado_sai_do_motor_de_compatibilidade():
    leitura = _leitura(["Peso Bruto"], [[100], [200], [50.5]])
    campos = [
        _campo(1, "Peso Bruto", conceito_chave="peso_bruto_entrada",
               unidade_canonica="kg", categoria_unidade="massa")
    ]
    coluna = _coluna(perfil_dados.perfilar(leitura, campos, _TABELA), "Peso Bruto")

    assert coluna["soma_permitida"] is True
    assert coluna["soma"] == {
        "total": 350.5, "unidade": "kg", "itens_somados": 3, "itens_ignorados": 0,
    }
    assert coluna["conceito"] == "peso_bruto_entrada"


def test_soma_ignora_valor_nao_numerico_e_conta():
    leitura = _leitura(["Peso Bruto"], [[100]] * 19 + [["N/A"]])
    campos = [_campo(1, "Peso Bruto", unidade_canonica="kg", categoria_unidade="massa")]
    perfil = perfil_dados.perfilar(leitura, campos, _TABELA)
    coluna = _coluna(perfil, "Peso Bruto")

    assert coluna["soma"]["itens_somados"] == 19
    assert coluna["soma"]["itens_ignorados"] == 1
    assert coluna["soma"]["total"] == 1900.0
    assert any("não numérico" in l for l in perfil["limitacoes"])


def test_sem_catalogo_nenhuma_soma():
    leitura = _leitura(["Peso Bruto"], [[100], [200]], familia="GUIAS_ENTRADA")
    perfil = perfil_dados.perfilar(leitura, [], _TABELA)
    coluna = _coluna(perfil, "Peso Bruto")

    assert coluna["soma_permitida"] is False
    assert coluna["soma"] is None
    assert "sem mapeamento semantico aprovado" in coluna["soma_motivo"]
    assert any("não tem mapeamento semântico aprovado" in l for l in perfil["limitacoes"])


def test_campo_em_rascunho_nao_soma():
    leitura = _leitura(["Fração"], [[1], [2]])
    campos = [_campo(1, "Fração", unidade_canonica="un", categoria_unidade="quantidade",
                     status="rascunho")]
    coluna = _coluna(perfil_dados.perfilar(leitura, campos, _TABELA), "Fração")
    assert coluna["soma_permitida"] is False
    assert "rascunho" in coluna["soma_motivo"]


def test_unidade_por_coluna_nao_soma_o_volume():
    """O caso real do V1.2: Volume e declarado na embalagem da coluna EMB --
    total unico e proibido."""
    leitura = _leitura(["Volume", "EMB"], [[10, "CX"], [5, "KGS"]])
    campos = [
        _campo(1, "Volume", conceito_chave="volumes_declarados",
               categoria_unidade="embalagem", unidade_por_coluna=2),
        _campo(2, "EMB", categoria_unidade="embalagem"),
    ]
    coluna = _coluna(perfil_dados.perfilar(leitura, campos, _TABELA), "Volume")
    assert coluna["soma_permitida"] is False
    assert "linha a linha" in coluna["soma_motivo"]


@pytest.mark.parametrize("agregacao", ["nenhuma", "media", "ultimo", "contagem_distinta", None])
def test_soma_exige_agregacao_soma_declarada(agregacao):
    """Allowlist, nao blocklist: so 'soma' autoriza somar. Vlr. Unitário e o
    caso real ('nenhuma'); media/ultimo tambem nunca viram soma -- a mesma
    regra que a consulta da serie aplica (direcionamento, secao 7)."""
    leitura = _leitura(["Vlr. Unitário"], [[5.0], [7.0]])
    campos = [_campo(1, "Vlr. Unitário", unidade_canonica="brl",
                     categoria_unidade="valor_monetario", agregacao=agregacao)]
    coluna = _coluna(perfil_dados.perfilar(leitura, campos, _TABELA), "Vlr. Unitário")
    assert coluna["soma_permitida"] is False
    assert "agregacao" in coluna["soma_motivo"]


def test_percentual_nunca_soma():
    leitura = _leitura(["Ocupação"], [[50], [30]])
    campos = [_campo(1, "Ocupação", unidade_canonica="pct", categoria_unidade="percentual")]
    coluna = _coluna(perfil_dados.perfilar(leitura, campos, _TABELA), "Ocupação")
    assert coluna["soma_permitida"] is False
    assert "percentual" in coluna["soma_motivo"].lower()


def test_coluna_de_texto_nao_soma_mesmo_com_catalogo():
    leitura = _leitura(["Cliente"], [["SAPORE"], ["GR"]])
    campos = [_campo(1, "Cliente", unidade_canonica="un", categoria_unidade="quantidade")]
    coluna = _coluna(perfil_dados.perfilar(leitura, campos, _TABELA), "Cliente")
    assert coluna["soma_permitida"] is False
    assert "nao numerica" in coluna["soma_motivo"]


# --- guarda estrutural (reestruturacao de 31/jul/2026) ---------------------------


def test_estrutura_divergente_descarta_o_catalogo_inteiro():
    """Variante da mesma familia com outra estrutura (o caso da unidade RJ, com
    18 colunas e sem Cliente): o catalogo casa por POSICAO, entao aplicar aqui
    trocaria conceito/unidade de coluna. Melhor perfil estrutural puro."""
    leitura = _leitura(["Cliente", "Peso Bruto"], [["SAPORE", 100]])
    campos = [
        _campo(1, "Cliente", dim_cliente=True),
        _campo(2, "Volume", unidade_canonica="un", categoria_unidade="quantidade"),
    ]
    perfil = perfil_dados.perfilar(leitura, campos, _TABELA)

    assert all(c["conceito"] is None for c in perfil["colunas"])
    assert all(c["soma_permitida"] is False for c in perfil["colunas"])
    divergencia = next(l for l in perfil["limitacoes"] if "ESTRUTURA DIVERGENTE" in l)
    assert "posição 2" in divergencia
    assert "catálogo semântico NÃO foi aplicado" in divergencia
    # nao acumula a mensagem de "familia sem mapeamento" (ela TEM mapeamento)
    assert not any("não tem mapeamento semântico" in l for l in perfil["limitacoes"])


def test_catalogo_com_posicao_alem_do_arquivo_tambem_diverge():
    leitura = _leitura(["Cliente"], [["SAPORE"]])
    campos = [_campo(1, "Cliente"), _campo(2, "Peso Bruto")]
    perfil = perfil_dados.perfilar(leitura, campos, _TABELA)
    assert any("não existe neste arquivo" in l for l in perfil["limitacoes"])


def test_rotulo_com_espaco_a_mais_ainda_casa():
    leitura = _leitura(["Peso  Bruto "], [[10]])
    campos = [_campo(1, "Peso Bruto", unidade_canonica="kg", categoria_unidade="massa")]
    perfil = perfil_dados.perfilar(leitura, campos, _TABELA)
    assert perfil["colunas"][0]["soma_permitida"] is True


# --- duplicidades, chaves, cobertura, clientes, granularidade --------------------


def test_duplicidades_conta_linhas_identicas():
    leitura = _leitura(["A", "B"], [["x", 1], ["x", 1], ["y", 2], ["x", 1]])
    duplicidades = perfil_dados.perfilar(leitura, [], _TABELA)["duplicidades"]
    assert duplicidades == {"linhas_identicas": 2, "grupos_repetidos": 1}


def test_chave_candidata_simples():
    leitura = _leitura(["GEM", "Cliente"], [["G1", "A"], ["G2", "A"], ["G3", "B"]])
    perfil = perfil_dados.perfilar(leitura, [], _TABELA)
    assert perfil["chaves_candidatas"] == [
        {"colunas": ["GEM"], "posicoes": [1], "tipo": "simples"}
    ]
    assert perfil["granularidade_provavel"].startswith("1 linha por GEM")


def test_chave_candidata_composta_quando_nenhuma_coluna_sozinha_serve():
    leitura = _leitura(
        ["Pedido", "Item"],
        [["P1", "1"], ["P1", "2"], ["P2", "1"], ["P2", "2"]],
    )
    chaves = perfil_dados.perfilar(leitura, [], _TABELA)["chaves_candidatas"]
    assert chaves == [{"colunas": ["Pedido", "Item"], "posicoes": [1, 2], "tipo": "composta"}]


def test_sem_chave_candidata_declara_risco_de_dupla_contagem():
    leitura = _leitura(["Cliente"], [["A"], ["A"], ["B"], ["B"]])
    perfil = perfil_dados.perfilar(leitura, [], _TABELA)
    assert perfil["chaves_candidatas"] == []
    assert "Nenhuma chave única" in " ".join(perfil["limitacoes"])
    assert "nenhuma chave única" in perfil["granularidade_provavel"]


def test_cobertura_temporal_e_competencia_do_arquivo():
    leitura = _leitura(
        ["Solicitação"], [[date(2026, 7, 2)], [date(2026, 7, 28)]]
    )
    cobertura = perfil_dados.perfilar(leitura, [], _TABELA)["cobertura_temporal"]
    assert cobertura["competencia_do_arquivo"] == "2026-07"
    assert cobertura["colunas_de_data"] == [
        {"coluna": "Solicitação", "posicao": 1, "de": "2026-07-02", "ate": "2026-07-28"}
    ]


def test_clientes_pelo_catalogo_com_top_de_frequencia():
    leitura = _leitura(
        ["Cliente"], [["SAPORE"], ["SAPORE"], ["GR"], ["SAPORE"], ["GR"], ["NOVITA"]]
    )
    campos = [_campo(1, "Cliente", dim_cliente=True)]
    clientes = perfil_dados.perfilar(leitura, campos, _TABELA)["clientes"]

    assert clientes["origem"] == "catalogo"
    assert clientes["distintos"] == 3
    assert clientes["top"][:2] == [
        {"valor": "SAPORE", "linhas": 3}, {"valor": "GR", "linhas": 2}
    ]


def test_cliente_por_heuristica_declara_limitacao():
    leitura = _leitura(["Cliente"], [["SAPORE"]], familia="GUIAS_SAIDA")
    perfil = perfil_dados.perfilar(leitura, [], _TABELA)
    assert perfil["clientes"]["origem"] == "heuristica"
    assert any("HEURÍSTICA" in l for l in perfil["limitacoes"])


def test_sem_coluna_de_cliente():
    leitura = _leitura(["Produto"], [["X"]])
    clientes = perfil_dados.perfilar(leitura, [], _TABELA)["clientes"]
    assert (clientes["coluna"], clientes["distintos"], clientes["origem"]) == (None, 0, "nenhuma")


# --- qualidade, limitacoes e amostra ---------------------------------------------


def test_qualidade_resume_o_arquivo():
    leitura = _leitura(
        ["A", "Vazia"], [["x", None], ["y", None], [None, None]]
    )
    qualidade = perfil_dados.perfilar(leitura, [], _TABELA)["qualidade"]
    assert qualidade["linhas_perfiladas"] == 3
    assert qualidade["colunas"] == 2
    assert qualidade["colunas_totalmente_vazias"] == ["Vazia"]
    assert qualidade["celulas_preenchidas_pct"] == 33.3
    assert qualidade["truncado"] is False


def test_truncamento_fala_da_LEITURA_nao_do_filtro():
    """A mensagem de truncamento descreve quantas linhas entraram em memória —
    nunca o resultado de um filtro posterior (senão afirmaria 'as primeiras N'
    sobre linhas que não são as primeiras)."""
    leitura = _leitura(
        ["Cliente"], [["SAPORE"]], linhas_lidas=90000, truncado=True,
        linhas_em_memoria=50000,
    )
    filtro = {"tipo": "cliente", "valores": ["SAPORE"], "linhas_antes": 50000}
    limitacoes = perfil_dados.perfilar(leitura, [], _TABELA, filtro=filtro)["limitacoes"]

    truncamento = next(l for l in limitacoes if "Leitura limitada" in l)
    assert "primeiras 50.000 de 90.000 linhas" in truncamento
    # e o filtro e declarado separado, com os proprios numeros
    assert limitacoes[0].startswith("Perfil calculado APÓS filtro de cliente")
    assert "1 de 50.000 linha(s) lida(s) passaram no filtro" in limitacoes[0]


def test_filtro_declarado_por_arquivo_e_registrado_no_perfil():
    leitura = _leitura(["Cliente"], [["SAPORE"], ["SAPORE"]])
    filtro = {"tipo": "cliente", "valores": ["sapore"], "linhas_antes": 5}
    perfil = perfil_dados.perfilar(leitura, [], _TABELA, filtro=filtro)

    assert perfil["filtro_aplicado"] == filtro
    assert perfil["limitacoes"][0].startswith("Perfil calculado APÓS filtro de cliente")


def test_amostra_crua_e_declarada_no_proprio_perfil():
    """A decisão de gravar amostra sem mascaramento está nos docs; quem lê a
    sessão (e o Bloco E) tem que ver isso no artefato também."""
    leitura = _leitura(["Cliente"], [["SAPORE"]], amostra_sem_mascaramento=True)
    limitacoes = perfil_dados.perfilar(leitura, [], _TABELA)["limitacoes"]
    assert any("CRUA" in l and "Mascarar" in l for l in limitacoes)


def test_coluna_vazia_com_catalogo_nao_diz_que_nao_e_numerica():
    leitura = _leitura(["Peso Bruto"], [[None], [None]])
    campos = [_campo(1, "Peso Bruto", unidade_canonica="kg", categoria_unidade="massa")]
    coluna = _coluna(perfil_dados.perfilar(leitura, campos, _TABELA), "Peso Bruto")
    assert coluna["soma_permitida"] is False
    assert coluna["soma_motivo"] == "coluna sem nenhum valor preenchido -- nada a somar"


def test_cabecalho_detectado_vira_limitacao():
    leitura = _leitura(["A"], [["x"]], origem_linha_cabecalho="detectada",
                       linha_cabecalho=4, familia="Outros")
    perfil = perfil_dados.perfilar(leitura, [], _TABELA)
    assert any("DETECTADA" in l and "4" in l for l in perfil["limitacoes"])


def test_amostra_respeita_o_limite_e_serializa_data():
    leitura = _leitura(
        ["Data"], [[datetime(2026, 7, 1, 8, 30)] for _ in range(30)]
    )
    amostra = perfil_dados.perfilar(leitura, [], _TABELA, max_amostra=5)["amostra"]
    assert amostra["colunas"] == ["Data"]
    assert len(amostra["linhas"]) == 5
    assert amostra["linhas"][0] == ["2026-07-01 08:30:00"]


def test_arquivo_sem_linhas_nao_quebra():
    perfil = perfil_dados.perfilar(_leitura(["A", "B"], []), [], _TABELA)
    assert perfil["qualidade"]["linhas_perfiladas"] == 0
    assert perfil["chaves_candidatas"] == []
    assert perfil["amostra"]["linhas"] == []
    assert perfil["colunas"][0]["tipo"] == "vazio"
