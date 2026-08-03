"""Testes da linhagem do cockpit (Bloco F / V1.7), contra o Postgres real.

Semeia pelo caminho de producao (processamento_datahub.processar_arquivo, com
graph/inventario mockados -- mesmo padrao de test_processamento_datahub.py):
assim a cadeia recebida -> execucao -> arquivo fica exatamente como o
processamento real grava, sem inventar estrutura.
"""

import io

import openpyxl
import pytest

from backend.services import graph_datahub, inventario_datahub, linhagem, processamento_datahub, serie_datahub

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


def _arquivo(nome, id_, modificado_em="2026-07-13T00:00:00Z", unidade="RMSPII", web_url="https://exemplo/arquivo"):
    return {
        "nome": nome,
        "caminho": f"{unidade}/ENTRADA/ENTRADA MERCADORIAS/{nome}",
        "tamanho": 1000,
        "modificado_em": modificado_em,
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


def _id(cur, sql, *params):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _medida_id_por_cliente(cur, metrica, cliente_nome):
    cur.execute(
        """
        SELECT m.id FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        LEFT JOIN clientes c ON c.id = m.cliente_id
        WHERE mt.nome = %s AND COALESCE(c.nome, 'Sem cliente identificado') = %s
        """,
        (metrica, cliente_nome),
    )
    return cur.fetchone()[0]


def test_celulas_lista_filtrada_por_metrica_e_competencia(cursor, monkeypatch):
    linhas = [
        _linha(peso_bruto=100.0, vlr_total=10.0),
        _linha(cliente="NOVO LTDA", cnpj=_DESCONHECIDO_CNPJ, peso_bruto=7.0, vlr_total=3.0),
    ]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])
    processamento_datahub.processar_arquivo(cursor, "item-016")

    resultado = linhagem.celulas(cursor, "peso_bruto_movimentado", "2026-07")
    assert resultado["filtros"]["competencia"] == "2026-07"
    por_cliente = {c["cliente"]: c for c in resultado["celulas"]}
    assert por_cliente["Sapore"]["valor"] == 100.0
    assert por_cliente["Sapore"]["filial"] == "RMSPIV"
    assert por_cliente["Sapore"]["tem_origem_rastreavel"] is True
    assert por_cliente["Sem cliente identificado"]["valor"] == 7.0


def test_celulas_filtra_por_filial_e_cliente(cursor, monkeypatch):
    linhas = [_linha(peso_bruto=100.0, vlr_total=10.0)]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])
    processamento_datahub.processar_arquivo(cursor, "item-016")

    so_sapore = linhagem.celulas(cursor, "peso_bruto_movimentado", "2026-07", cliente="67945071")
    assert len(so_sapore["celulas"]) == 1

    outra_filial = linhagem.celulas(cursor, "peso_bruto_movimentado", "2026-07", filial="RMSPII")
    assert outra_filial["celulas"] == []


def test_celulas_metrica_inexistente_da_erro_claro(cursor):
    with pytest.raises(serie_datahub.SerieDatahubError, match="nao cadastrada"):
        linhagem.celulas(cursor, "metrica_fantasma", "2026-07")


def test_origem_da_celula_cadeia_completa(cursor, monkeypatch):
    linhas = [_linha(peso_bruto=100.0, vlr_total=10.0)]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016", web_url="https://exemplo/nf016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])
    processamento_datahub.processar_arquivo(cursor, "item-016")

    medida_id = _medida_id_por_cliente(cursor, "peso_bruto_movimentado", "Sapore")
    origem = linhagem.origem_da_celula(cursor, medida_id)

    assert origem["rastreavel"] is True
    assert origem["recebida"]["arquivo"] == "ENTRADA_MERCADORIAS_016_2607.xlsx"
    assert origem["recebida"]["valor"] == 100.0
    assert origem["execucao"]["status"] == "ok"
    assert origem["execucao"]["caminho"] == arquivo["caminho"]
    assert origem["arquivo"]["item_id"] == "item-016"
    assert origem["arquivo"]["web_url"] == "https://exemplo/nf016"
    assert origem["arquivo"]["filial_sigla"] == "RMSPIV"


def test_origem_da_celula_legado_declara_limitacao(cursor):
    cur = cursor
    metrica_id = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_movimentado'")
    armazem_id = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    cur.execute(
        """
        INSERT INTO medidas (metrica_id, armazem_id, competencia, valor, origem_tipo)
        VALUES (%s, %s, '2026-01-01', 999, 'legado') RETURNING id
        """,
        (metrica_id, armazem_id),
    )
    medida_id = cur.fetchone()[0]

    origem = linhagem.origem_da_celula(cur, medida_id)
    assert origem["rastreavel"] is False
    assert "legado" in origem["limitacao"] or "nao reconstruivel" in origem["limitacao"]


def test_origem_da_celula_nao_encontrada(cursor):
    with pytest.raises(linhagem.LinhagemError, match="nao encontrada"):
        linhagem.origem_da_celula(cursor, 999999)
