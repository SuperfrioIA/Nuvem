"""Testes do processamento persistente da SAIDA_MERCADORIAS e da particao
(lote V2.3), contra o Postgres real. graph_datahub e inventario_datahub sao
sempre mockados -- nenhuma chamada real ao SharePoint.

O que esta fixado aqui, alem do que test_processamento_datahub.py ja fixa pra
entrada:
- particao (1..N partes) processada como unidade so, mas uma linha por parte
  em processamentos_datahub;
- isolamento entre entrada e saida: processar uma NUNCA apaga celula da outra
  (o criterio central do V2.3 -- metricas separadas + prune por produtor);
- guarda de colisao com indice_parte (duas partes com o MESMO indice colidem;
  partes DIFERENTES da mesma particao, nao);
- origem sem coluna de cliente na fonte (layout de 34) cai no balde NULL SEM
  pendencia de cliente (decisao D2);
- escopo D3: competencia anterior a 2026 fica fora, nunca processada.
"""

import io
from datetime import date

import openpyxl
import pytest

from backend.services import graph_datahub, inventario_datahub, processamento_datahub

_SAPORE_CNPJ = "67945071000159"  # raiz 67945071, no seed_clientes

_BANDAS_36 = [
    "GSM", None, None, None, None, None, None, None, None,
    "Produto", None, None, None, None,
    "Solicitado pelo Cliente", None, None, None, None, None,
    "Atendido pelo Estoque", None, None, None, None, None,
    "Separado Fisicamente", None, None, None, None, None,
    "Dados de Separação", None, None, None,
]
_ROTULOS_36 = [
    "Cliente", "Cliente CNPJ", "Estoque", "Empresa", "GSM", "Operação",
    "Data Solicitação", "Data Saída", "Status Separação", "Item", "Código",
    "Descrição", "Pedido", "Destinatário",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Corte Físico", "Início", "Final", "Separador",
]
_BANDAS_34 = [
    "GSM", None, None, None, None, None, None,
    "Produto", None, None, None, None,
    "Solicitado pelo Cliente", None, None, None, None, None,
    "Atendido pelo Estoque", None, None, None, None, None,
    "Separado Fisicamente", None, None, None, None, None,
    "Dados de Separação", None, None, None,
]
_ROTULOS_34 = [
    "Estoque", "Empresa", "GSM", "Operação", "Data Solicitação", "Data Saída",
    "Status Separação", "Item", "Código", "Descrição", "Pedido", "Destinatário",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Corte Físico", "Início", "Final", "Separador",
]


def _linha_36(cliente="SAPORE", cnpj=_SAPORE_CNPJ, estoque="CONGELADO",
              status="Concluído", peso_bruto=100.0):
    base = {
        0: cliente, 1: cnpj, 2: estoque, 3: "EMPRESA", 4: "GSM1", 5: "SAIDA NORMAL",
        6: "2026-07-01", 7: "2026-07-02", 8: status, 9: "ITEM1", 10: "COD1",
        11: "DESC", 12: "PED1", 13: "DEST1",
        14: 10, 15: "CX", 16: 1, 17: "CX", 18: 90.0, 19: 999.0,
        20: 10, 21: "CX", 22: 1, 23: "CX", 24: 90.0, 25: 999.0,
        26: 10, 27: "CX", 28: 1, 29: "CX", 30: 90.0, 31: peso_bruto,
        32: "N", 33: "08:00", 34: "09:00", 35: "SEP1",
    }
    return [base[i] for i in range(36)]


def _linha_34(estoque="CONGELADO", status="Concluído", peso_bruto=100.0):
    base = {
        0: estoque, 1: "EMPRESA", 2: "GSM1", 3: "SAIDA NORMAL",
        4: "2026-07-01", 5: "2026-07-02", 6: status, 7: "ITEM1", 8: "COD1",
        9: "DESC", 10: "PED1", 11: "DEST1",
        12: 10, 13: "CX", 14: 1, 15: "CX", 16: 90.0, 17: 999.0,
        18: 10, 19: "CX", 20: 1, 21: "CX", 22: 90.0, 23: 999.0,
        24: 10, 25: "CX", 26: 1, 27: "CX", 28: 90.0, 29: peso_bruto,
        30: "N", 31: "08:00", 32: "09:00", 33: "SEP1",
    }
    return [base[i] for i in range(34)]


def _xlsx(linhas_de_dado, bandas=_BANDAS_36, rotulos=_ROTULOS_36):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SLIN"
    for _ in range(4):
        ws.append([None] * len(rotulos))
    ws.append(bandas)
    ws.append(rotulos)
    for linha in linhas_de_dado:
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _arquivo(nome, id_, modificado_em="2026-08-06T00:00:00Z", unidade="RMSPII"):
    return {
        "nome": nome,
        "caminho": f"{unidade}/SAIDA/SAIDA MERCADORIAS/{nome}",
        "tamanho": 2000,
        "modificado_em": modificado_em,
        "id": id_,
        "web_url": "https://exemplo/arquivo",
    }


@pytest.fixture(autouse=True)
def cache_limpo():
    estado_inicial = {"sincronizado_em": None, "ok": None, "mensagem_erro": None, "resumo": None}
    inventario_datahub._cache.update(estado_inicial)
    yield
    inventario_datahub._cache.update(estado_inicial)


def _preparar(monkeypatch, arquivos):
    """arquivos: lista de (dict do inventario, bytes do xlsx)."""
    inventario_datahub._cache.update(
        {
            "sincronizado_em": "2026-08-06T00:00:00Z",
            "ok": True,
            "mensagem_erro": None,
            "resumo": {"arquivos": [a for a, _ in arquivos]},
        }
    )
    conteudos = {a["id"]: conteudo for a, conteudo in arquivos}
    monkeypatch.setattr(
        graph_datahub, "baixar_item", lambda item_id, limite_bytes: conteudos[item_id]
    )


def _medidas(cur, metrica):
    cur.execute(
        """
        SELECT c.nk_erp, m.valor::float
        FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        LEFT JOIN clientes c ON c.id = m.cliente_id
        WHERE mt.nome = %s
        ORDER BY c.nk_erp NULLS LAST
        """,
        (metrica,),
    )
    return cur.fetchall()


# --- particao: 1, 2 e N partes -------------------------------------------------


def test_processa_particao_de_uma_parte_36_colunas(cursor, monkeypatch):
    arquivo = _arquivo("SAIDA_MERCADORIAS_016_2607.xlsx", "item-saida-1")
    _preparar(monkeypatch, [(arquivo, _xlsx([_linha_36(peso_bruto=100.0)]))])

    relatorio = processamento_datahub.processar_particao_saida(cursor, ["item-saida-1"])

    assert relatorio["status"] == "ok"
    assert relatorio["filial"] == "016"
    assert relatorio["competencia"] == "2026-07"
    assert relatorio["clientes"] == 1
    assert relatorio["sem_cliente"] == 0
    assert _medidas(cursor, "peso_bruto_saida") == [("67945071", 100.0)]
    assert _medidas(cursor, "registros_saida") == [("67945071", 1.0)]
    # nao existe valor_mercadoria_saida -- nao ha o que buscar
    cursor.execute("SELECT COUNT(*) FROM metricas WHERE nome = 'valor_mercadoria_saida'")
    assert cursor.fetchone()[0] == 0

    cursor.execute(
        "SELECT arquivo, filial, competencia, status, layout_lido FROM processamentos_datahub"
    )
    assert cursor.fetchall() == [
        (arquivo["nome"], "016", date(2026, 7, 1), "ok", "36_colunas")
    ]


def test_particao_duas_partes_f1_f2_agrega_e_grava_uma_vez(cursor, monkeypatch):
    f1 = _arquivo("SAIDA_MERCADORIAS_016_2607_f1.xlsx", "item-f1")
    f2 = _arquivo("SAIDA_MERCADORIAS_016_2607_f2.xlsx", "item-f2")
    _preparar(
        monkeypatch,
        [
            (f1, _xlsx([_linha_36(peso_bruto=100.0)])),
            (f2, _xlsx([_linha_36(peso_bruto=50.0)])),
        ],
    )

    relatorio = processamento_datahub.processar_particao_saida(cursor, ["item-f1", "item-f2"])

    assert relatorio["status"] == "ok"
    # as duas partes agregam na MESMA celula -- uma gravacao so
    assert _medidas(cursor, "peso_bruto_saida") == [("67945071", 150.0)]
    assert _medidas(cursor, "registros_saida") == [("67945071", 2.0)]

    # mas CADA parte tem sua PROPRIA linha em processamentos_datahub
    cursor.execute("SELECT arquivo FROM processamentos_datahub ORDER BY arquivo")
    assert cursor.fetchall() == [(f1["nome"],), (f2["nome"],)]
    cursor.execute("SELECT COUNT(DISTINCT execucao_id) FROM processamentos_datahub")
    assert cursor.fetchone()[0] == 1  # mesma execucao pras duas partes


def test_particao_sem_sufixo_fn_processa_como_parte_unica(cursor, monkeypatch):
    """A CWB3 publica sem sufixo -- ainda assim e uma particao valida."""
    arquivo = _arquivo("SAIDA_MERCADORIAS_001_2607.xlsx", "item-cwb3", unidade="CWB3")
    _preparar(monkeypatch, [(arquivo, _xlsx([_linha_36(peso_bruto=70.0)]))])

    relatorio = processamento_datahub.processar_particao_saida(cursor, ["item-cwb3"])

    assert relatorio["status"] == "ok"
    assert relatorio["unidade"] == "CWB3"
    cursor.execute(
        "SELECT a.sigla, m.valor::float FROM medidas m "
        "JOIN metricas mt ON mt.id = m.metrica_id "
        "JOIN armazens a ON a.id = m.armazem_id WHERE mt.nome = 'peso_bruto_saida'"
    )
    assert cursor.fetchall() == [("CWBIII", 70.0)]


# --- layout de 34 colunas (SANCA) -- sem coluna de cliente, sem pendencia ------


def test_layout_34_colunas_cai_no_balde_sem_cliente_sem_pendencia(cursor, monkeypatch):
    """Decisao D2 do V2.3: origem sem coluna de cliente na fonte cai no balde
    NULL, mas NAO registra pendencia de cliente (nao ha CNPJ pra cadastrar --
    pendencia ali seria tarefa impossivel, o erro que o V2.1.1 corrigiu)."""
    arquivo = _arquivo("SAIDA_MERCADORIAS_025_2607_f1.xlsx", "item-sanca", unidade="SANCA")
    _preparar(
        monkeypatch,
        [(arquivo, _xlsx([_linha_34(peso_bruto=200.0)], bandas=_BANDAS_34, rotulos=_ROTULOS_34))],
    )

    relatorio = processamento_datahub.processar_particao_saida(cursor, ["item-sanca"])

    assert relatorio["status"] == "ok"
    assert relatorio["clientes"] == 0
    assert relatorio["sem_cliente"] == 1
    assert _medidas(cursor, "peso_bruto_saida") == [(None, 200.0)]
    assert processamento_datahub.listar_pendencias_cliente(cursor) == []

    cursor.execute("SELECT layout_lido FROM processamentos_datahub WHERE item_id = 'item-sanca'")
    assert cursor.fetchone()[0] == "34_colunas"


# --- isolamento entre entrada e saida (o criterio central do lote) ------------


def test_processar_saida_nao_apaga_celula_de_entrada_e_vice_versa(cursor, monkeypatch):
    """O criterio central do V2.3: metricas separadas tornam os escopos do
    prune disjuntos -- mas so o codigo (passar so os metrica_id do produtor
    certo pro prune) e que garante isso de fato."""
    import openpyxl as _oxl

    def _xlsx_entrada(linhas):
        wb = _oxl.Workbook()
        ws = wb.active
        ws.title = "SLIN"
        cabecalho = [
            "Cliente", "Cliente CNPJ", "GEM", "Devolução", "Solicitação", "NF Entrada",
            "Código", "Descrição", "Volume", "EMB", "Fração", "EMB", "Peso Líquido",
            "Peso Bruto", "Vlr. Unitário", "Vlr. Total", "Qtde UA", "Código Estoque",
            "Nome Estoque", "Operação",
        ]
        ws.append(cabecalho)
        for linha in linhas:
            ws.append(linha)
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def _linha_entrada(peso_bruto=999.0):
        return [
            "SAPORE", _SAPORE_CNPJ, "GEM1", "N", "SOL1", "NF001", "COD1", "DESC",
            10, "CX", 1, "CX", 90.0, peso_bruto, 5.0, 50.0, 3, "EST1", "CONGELADO", "ENTRADA",
        ]

    entrada = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-entrada")
    saida = _arquivo("SAIDA_MERCADORIAS_016_2607.xlsx", "item-saida-iso")
    inventario_datahub._cache.update(
        {
            "sincronizado_em": "2026-08-06T00:00:00Z",
            "ok": True,
            "mensagem_erro": None,
            "resumo": {"arquivos": [entrada, saida]},
        }
    )
    conteudos = {
        "item-entrada": _xlsx_entrada([_linha_entrada(peso_bruto=999.0)]),
        "item-saida-iso": _xlsx([_linha_36(peso_bruto=100.0)]),
    }
    monkeypatch.setattr(
        graph_datahub, "baixar_item", lambda item_id, limite_bytes: conteudos[item_id]
    )

    processamento_datahub.processar_arquivo(cursor, "item-entrada")
    processamento_datahub.processar_particao_saida(cursor, ["item-saida-iso"])

    # as duas celulas convivem -- nem uma apagou a outra
    assert _medidas(cursor, "peso_bruto_entrada") == [("67945071", 999.0)]
    assert _medidas(cursor, "peso_bruto_saida") == [("67945071", 100.0)]

    # reprocessar a saida de novo nao apaga a entrada, e vice-versa
    processamento_datahub.processar_particao_saida(cursor, ["item-saida-iso"])
    assert _medidas(cursor, "peso_bruto_entrada") == [("67945071", 999.0)]
    processamento_datahub.processar_arquivo(cursor, "item-entrada")
    assert _medidas(cursor, "peso_bruto_saida") == [("67945071", 100.0)]


# --- guarda de colisao: familia e indice_parte --------------------------------


def test_duas_partes_com_mesmo_indice_colidem(cursor, monkeypatch):
    original = _arquivo("SAIDA_MERCADORIAS_016_2607_f1.xlsx", "item-a")
    copia = _arquivo("SAIDA_MERCADORIAS_016_2607_f1.xlsx", "item-b")
    copia["caminho"] = "RMSPII/SAIDA/SAIDA MERCADORIAS/backup/" + copia["nome"]
    _preparar(monkeypatch, [(original, _xlsx([_linha_36()])), (copia, _xlsx([_linha_36()]))])

    with pytest.raises(processamento_datahub.ProcessamentoDatahubError, match="colisao de origem"):
        processamento_datahub.processar_todos_saida(cursor)


def test_particao_mista_sem_sufixo_junto_com_fn_e_erro_nao_soma():
    """Achado da revisao independente do V2.3: `indice_parte=None` (parte
    unica) e `1`/`2` (partida) sao indices DIFERENTES, entao a guarda de
    colisao (que so pega indice duplicado) deixa passar -- mas agrupar os
    dois na mesma particao os somaria em silencio. Teste puro: nao precisa de
    banco, so exercita `_agrupar_particoes_saida` direto."""
    sem_sufixo = _arquivo("SAIDA_MERCADORIAS_016_2607.xlsx", "item-a")
    parte_1 = _arquivo("SAIDA_MERCADORIAS_016_2607_f1.xlsx", "item-b")

    with pytest.raises(processamento_datahub.ProcessamentoDatahubError, match="particao mista"):
        processamento_datahub._agrupar_particoes_saida([sem_sufixo, parte_1])


# --- escopo D3: so 2026 ---------------------------------------------------------


def test_arquivo_anterior_a_2026_fica_fora_de_escopo_e_nao_processa(cursor, monkeypatch):
    antigo = _arquivo("SAIDA_MERCADORIAS_016_2512.xlsx", "item-2512")
    novo = _arquivo("SAIDA_MERCADORIAS_016_2601.xlsx", "item-2601")
    _preparar(monkeypatch, [(antigo, _xlsx([_linha_36()])), (novo, _xlsx([_linha_36()]))])

    relatorio = processamento_datahub.processar_todos_saida(cursor)

    assert relatorio["total_fora_de_escopo"] == 1
    assert relatorio["arquivos_fora_de_escopo"] == [antigo["nome"]]
    assert [p["arquivos"] for p in relatorio["processados"]] == [[novo["nome"]]]
    cursor.execute("SELECT COUNT(*) FROM processamentos_datahub WHERE item_id = 'item-2512'")
    assert cursor.fetchone()[0] == 0


# --- pendencia de de-para e sem_dado -------------------------------------------


def test_particao_sem_depara_registra_pendencia_em_todas_as_partes_sem_baixar(cursor, monkeypatch):
    baixados = []
    f1 = _arquivo("SAIDA_MERCADORIAS_004-001_2607_f1.xlsx", "item-f1-pend", unidade="RJ")
    f2 = _arquivo("SAIDA_MERCADORIAS_004-001_2607_f2.xlsx", "item-f2-pend", unidade="RJ")
    _preparar(monkeypatch, [(f1, _xlsx([_linha_36()])), (f2, _xlsx([_linha_36()]))])
    monkeypatch.setattr(
        graph_datahub, "baixar_item",
        lambda item_id, limite_bytes: baixados.append(item_id) or b"",
    )

    relatorio = processamento_datahub.processar_particao_saida(cursor, ["item-f1-pend", "item-f2-pend"])

    assert relatorio["status"] == "pendencia_depara"
    assert baixados == []
    cursor.execute("SELECT status FROM processamentos_datahub ORDER BY item_id")
    assert cursor.fetchall() == [("pendencia_depara",), ("pendencia_depara",)]


def test_particao_so_com_cabecalho_vira_sem_dado(cursor, monkeypatch):
    arquivo = _arquivo("SAIDA_MERCADORIAS_016_2607.xlsx", "item-vazio-saida")
    _preparar(monkeypatch, [(arquivo, _xlsx([]))])

    relatorio = processamento_datahub.processar_particao_saida(cursor, ["item-vazio-saida"])

    assert relatorio["status"] == "sem_dado"
    cursor.execute("SELECT COUNT(*) FROM medidas")
    assert cursor.fetchone()[0] == 0


# --- pular particao inalterada -------------------------------------------------


def test_listar_particoes_saida_pula_particao_inalterada(cursor, monkeypatch):
    arquivo = _arquivo("SAIDA_MERCADORIAS_016_2607.xlsx", "item-repete")
    _preparar(monkeypatch, [(arquivo, _xlsx([_linha_36()]))])

    processamento_datahub.processar_todos_saida(cursor)
    plano = processamento_datahub.listar_particoes_saida(cursor)

    assert plano["particoes_pendentes"] == []
    assert plano["pulados"] == 1

    plano_forcado = processamento_datahub.listar_particoes_saida(cursor, forcar=True)
    assert len(plano_forcado["particoes_pendentes"]) == 1
