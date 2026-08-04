"""Teste de ponta a ponta (Bloco G / G3): arquivo do DataHub -> pipeline real
de processamento -> a MESMA celula aparece consistente no cockpit e na
linhagem. Os testes unitarios de cada camada (test_cockpit.py,
test_linhagem.py, test_cockpit_router.py, test_linhagem_router.py) ja cobrem
cada endpoint isolado, semeando dado minimo direto por SQL -- o que falta e
provar que a cadeia inteira (execucao -> recebida -> medida -> cockpit e
linhagem lendo a mesma medida) se encaixa, usando o caminho real de ingestao
(processamento_datahub.processar_arquivo), nao um atalho de teste.
"""

import io

import openpyxl
import pytest

from backend.services import graph_datahub, inventario_datahub, processamento_datahub

_CABECALHO = [
    "Cliente", "Cliente CNPJ", "GEM", "Devolução", "Solicitação", "NF Entrada",
    "Código", "Descrição", "Volume", "EMB", "Fração", "EMB", "Peso Líquido",
    "Peso Bruto", "Vlr. Unitário", "Vlr. Total", "Qtde UA", "Código Estoque",
    "Nome Estoque", "Operação",
]

_SAPORE_CNPJ = "67945071000159"
_DESCONHECIDO_CNPJ = "99999999000199"


def _linha(cliente="SAPORE", cnpj=_SAPORE_CNPJ, peso_bruto=100.0, vlr_total=50.0):
    return [
        cliente, cnpj, "GEM1", "N", "SOL1", "NF001", "COD1", "DESC",
        10, "CX", 1, "CX", 90.0, peso_bruto, 5.0, vlr_total, 3,
        "EST1", "ESTOQUE 1", "ENTRADA",
    ]


def _xlsx(linhas, aba="SLIN"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    ws.append(_CABECALHO)
    for linha in linhas:
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _arquivo(nome, id_, unidade="RMSPII", web_url="https://exemplo/arquivo"):
    return {
        "nome": nome,
        "caminho": f"{unidade}/ENTRADA/ENTRADA MERCADORIAS/{nome}",
        "tamanho": 1000,
        "modificado_em": "2026-07-13T00:00:00Z",
        "id": id_,
        "web_url": web_url,
    }


@pytest.fixture(autouse=True)
def cache_limpo():
    estado_inicial = {"sincronizado_em": None, "ok": None, "mensagem_erro": None, "resumo": None}
    inventario_datahub._cache.update(estado_inicial)
    yield
    inventario_datahub._cache.update(estado_inicial)


def _preparar(monkeypatch, arquivos):
    inventario_datahub._cache.update({
        "sincronizado_em": "2026-07-29T00:00:00Z", "ok": True, "mensagem_erro": None,
        "resumo": {"arquivos": [a for a, _ in arquivos]},
    })
    conteudos = {a["id"]: conteudo for a, conteudo in arquivos}
    monkeypatch.setattr(graph_datahub, "baixar_item", lambda item_id, limite_bytes: conteudos[item_id])


def test_pipeline_ate_cockpit_e_linhagem(cliente, cursor, monkeypatch):
    """Um arquivo (2 clientes, 1 filial, 1 competencia) processado pelo
    caminho real deve aparecer, com o MESMO total, no resumo do cockpit, no
    ranking de filiais e na lista de celulas da linhagem -- e a origem da
    celula precisa resolver de volta pro arquivo/execucao semeados."""
    linhas = [
        _linha(cliente="SAPORE", cnpj=_SAPORE_CNPJ, peso_bruto=100.0, vlr_total=10.0),
        _linha(cliente="NOVO LTDA", cnpj=_DESCONHECIDO_CNPJ, peso_bruto=7.0, vlr_total=3.0),
    ]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016", web_url="https://exemplo/nf016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    processamento_datahub.processar_arquivo(cursor, "item-016")
    cursor.connection.commit()

    resumo = cliente.get(
        "/api/admin/cockpit/resumo", params={"de": "2026-07", "ate": "2026-07", "filial": "RMSPIV"}
    )
    assert resumo.status_code == 200
    kpis = {k["chave"]: k["valor"] for k in resumo.json()["kpis"]}
    assert kpis["peso_bruto_movimentado"] == 107.0

    ranking = cliente.get(
        "/api/admin/cockpit/comparacao/filiais",
        params={"metrica": "peso_bruto_movimentado", "de": "2026-07", "ate": "2026-07"},
    )
    assert ranking.status_code == 200
    por_filial = {r["rotulo"]: r for r in ranking.json()["ranking"]}
    assert por_filial["RMSPIV"]["valor"] == 107.0
    assert por_filial["RMSPIV"]["percentual"] == 100.0

    celulas = cliente.get(
        "/api/admin/linhagem/celulas",
        params={"metrica": "peso_bruto_movimentado", "competencia": "2026-07"},
    )
    assert celulas.status_code == 200
    por_cliente_nome = {c["cliente"]: c for c in celulas.json()["celulas"]}
    assert por_cliente_nome["Sapore"]["valor"] == 100.0
    assert por_cliente_nome["Sem cliente identificado"]["valor"] == 7.0

    origem = cliente.get(f"/api/admin/linhagem/celulas/{por_cliente_nome['Sapore']['medida_id']}")
    assert origem.status_code == 200
    corpo = origem.json()
    assert corpo["rastreavel"] is True
    assert corpo["recebida"]["arquivo"] == "ENTRADA_MERCADORIAS_016_2607.xlsx"
    assert corpo["arquivo"]["item_id"] == "item-016"
    assert corpo["arquivo"]["web_url"] == "https://exemplo/nf016"


def test_pipeline_duas_filiais_nao_mistura_origem(cliente, cursor, monkeypatch):
    """Dois arquivos, duas filiais, mesma competencia: o cockpit soma as duas
    no total mas discrimina o ranking por filial; a linhagem de cada celula
    aponta pro arquivo certo, sem misturar origem entre filiais."""
    arquivo_016 = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    arquivo_001 = _arquivo("ENTRADA_MERCADORIAS_001_2607.xlsx", "item-001")
    _preparar(monkeypatch, [
        (arquivo_016, _xlsx([_linha(peso_bruto=100.0, vlr_total=10.0)])),
        (arquivo_001, _xlsx([_linha(peso_bruto=40.0, vlr_total=4.0)])),
    ])

    processamento_datahub.processar_arquivo(cursor, "item-016")
    processamento_datahub.processar_arquivo(cursor, "item-001")
    cursor.connection.commit()

    ranking = cliente.get(
        "/api/admin/cockpit/comparacao/filiais",
        params={"metrica": "peso_bruto_movimentado", "de": "2026-07", "ate": "2026-07"},
    )
    assert ranking.status_code == 200
    por_filial = {r["rotulo"]: r["valor"] for r in ranking.json()["ranking"]}
    assert por_filial["RMSPIV"] == 100.0
    assert por_filial["RMSPII"] == 40.0
    assert ranking.json()["total"] == 140.0

    celulas_016 = cliente.get(
        "/api/admin/linhagem/celulas",
        params={"metrica": "peso_bruto_movimentado", "competencia": "2026-07", "filial": "RMSPIV"},
    )
    assert celulas_016.status_code == 200
    (celula_016,) = celulas_016.json()["celulas"]
    origem_016 = cliente.get(f"/api/admin/linhagem/celulas/{celula_016['medida_id']}")
    assert origem_016.json()["arquivo"]["item_id"] == "item-016"
    assert origem_016.json()["arquivo"]["filial_sigla"] == "RMSPIV"

    celulas_001 = cliente.get(
        "/api/admin/linhagem/celulas",
        params={"metrica": "peso_bruto_movimentado", "competencia": "2026-07", "filial": "RMSPII"},
    )
    assert celulas_001.status_code == 200
    (celula_001,) = celulas_001.json()["celulas"]
    origem_001 = cliente.get(f"/api/admin/linhagem/celulas/{celula_001['medida_id']}")
    assert origem_001.json()["arquivo"]["item_id"] == "item-001"
    assert origem_001.json()["arquivo"]["filial_sigla"] == "RMSPII"
