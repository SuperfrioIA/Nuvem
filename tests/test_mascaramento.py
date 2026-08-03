"""Mascaramento de cliente/CNPJ antes do envio a IA (Bloco E / V1.5).
Funcao pura -- sem banco, sem monkeypatch de rede.
"""

from backend.services import mascaramento


def _perfil_arquivo():
    return {
        "colunas": [
            {"posicao": 1, "nome": "Cliente", "exemplos": ["SAPORE", "GR"]},
            {"posicao": 2, "nome": "Cliente CNPJ", "exemplos": ["67945071000159"]},
            {"posicao": 3, "nome": "Peso Bruto", "exemplos": []},
        ],
        "clientes": {
            "coluna": "Cliente",
            "origem": "catalogo",
            "distintos": 2,
            "top": [{"valor": "SAPORE", "linhas": 10}, {"valor": "GR", "linhas": 5}],
        },
        "amostra": {
            "colunas": ["Cliente", "Cliente CNPJ", "Peso Bruto"],
            "linhas": [
                ["SAPORE", "67945071000159", 100],
                ["GR", "11122233000144", 50],
                ["SAPORE", "67945071000159", 30],
            ],
        },
    }


def test_mascara_amostra_com_pseudonimo_consistente():
    perfil = _perfil_arquivo()
    mascarado = mascaramento.mascarar_perfil_arquivo(perfil)

    linhas = mascarado["amostra"]["linhas"]
    assert linhas[0] == ["CLIENTE_1", "CLIENTE_2", 100]
    assert linhas[1] == ["CLIENTE_3", "CLIENTE_4", 50]
    # mesma linha (SAPORE + mesmo CNPJ) repete o MESMO pseudonimo -- e o que
    # permite a IA raciocinar sobre agrupamento sem ver a identidade real
    assert linhas[2] == ["CLIENTE_1", "CLIENTE_2", 30]
    assert linhas[2][:2] == linhas[0][:2]  # mesmo cliente/CNPJ -- mesmo pseudonimo

    # nome real nao sobrevive em lugar nenhum da amostra mascarada
    texto = str(mascarado["amostra"])
    assert "SAPORE" not in texto
    assert "67945071000159" not in texto


def test_mascara_top_de_clientes_com_o_mesmo_mapa_da_amostra():
    mascarado = mascaramento.mascarar_perfil_arquivo(_perfil_arquivo())
    top = mascarado["clientes"]["top"]
    assert top[0]["valor"] == "CLIENTE_1"  # SAPORE -- mesmo pseudonimo da amostra
    assert top[1]["valor"] == "CLIENTE_3"  # GR
    assert top[0]["linhas"] == 10  # contagem intacta, so o nome mascara


def test_mascara_exemplos_das_colunas_sensiveis_preserva_as_demais():
    mascarado = mascaramento.mascarar_perfil_arquivo(_perfil_arquivo())
    por_nome = {c["nome"]: c for c in mascarado["colunas"]}
    assert por_nome["Cliente"]["exemplos"] == ["CLIENTE_1", "CLIENTE_3"]
    assert por_nome["Cliente CNPJ"]["exemplos"] == ["CLIENTE_2"]
    # coluna sem dado pessoal nao e tocada
    assert por_nome["Peso Bruto"]["exemplos"] == []


def test_sem_coluna_sensivel_devolve_o_mesmo_objeto():
    perfil = _perfil_arquivo()
    perfil["clientes"]["coluna"] = None
    for coluna in perfil["colunas"]:
        coluna["nome"] = coluna["nome"].replace("Cliente", "Fornecedor").replace("CNPJ", "Codigo")
    assert mascaramento.mascarar_perfil_arquivo(perfil) is perfil


def test_nao_muta_o_perfil_original():
    perfil = _perfil_arquivo()
    mascaramento.mascarar_perfil_arquivo(perfil)
    assert perfil["amostra"]["linhas"][0] == ["SAPORE", "67945071000159", 100]
    assert perfil["clientes"]["top"][0]["valor"] == "SAPORE"
    assert perfil["colunas"][0]["exemplos"] == ["SAPORE", "GR"]


def test_valor_vazio_ou_none_nao_e_mascarado():
    perfil = _perfil_arquivo()
    perfil["amostra"]["linhas"].append([None, "", 10])
    mascarado = mascaramento.mascarar_perfil_arquivo(perfil)
    assert mascarado["amostra"]["linhas"][-1] == [None, "", 10]


# --- achado da verificação independente: filtro de cliente ecoado sem máscara ----


def test_mascara_limitacao_do_filtro_de_cliente_com_o_mesmo_pseudonimo_da_amostra():
    perfil = _perfil_arquivo()
    perfil["filtro_aplicado"] = {"tipo": "cliente", "valores": ["sapore"], "linhas_antes": 3}
    perfil["limitacoes"] = [
        "Perfil calculado APÓS filtro de cliente (sapore): 2 de 3 linha(s) lida(s) "
        "passaram no filtro. Todos os números abaixo descrevem só essas linhas.",
        "Outra limitação sem nenhum nome de cliente.",
    ]

    mascarado = mascaramento.mascarar_perfil_arquivo(perfil)

    # "sapore" (digitado, minusculo) some e vira o MESMO pseudonimo que
    # "SAPORE" (maiusculo, vindo da planilha) recebe na amostra -- prova que
    # os dois usam o mesmo mapa, so normalizado por caixa
    assert "sapore" not in mascarado["limitacoes"][0].lower()
    assert "CLIENTE_1" in mascarado["limitacoes"][0]
    assert mascarado["amostra"]["linhas"][0][0] == "CLIENTE_1"
    # limitacao sem nome de cliente nao muda
    assert mascarado["limitacoes"][1] == perfil["limitacoes"][1]


def test_filtro_de_cliente_sem_limitacoes_nao_quebra():
    perfil = _perfil_arquivo()
    perfil["filtro_aplicado"] = {"tipo": "cliente", "valores": ["sapore"], "linhas_antes": 3}
    perfil["limitacoes"] = []
    mascarado = mascaramento.mascarar_perfil_arquivo(perfil)
    assert mascarado["limitacoes"] == []
