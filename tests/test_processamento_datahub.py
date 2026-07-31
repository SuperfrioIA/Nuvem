"""Testes do processamento persistente do DataHub (Bloco C / V1.3), contra o
Postgres real. graph_datahub e inventario_datahub sao sempre mockados --
nenhuma chamada real ao SharePoint.

O que esta fixado aqui:
- grao unico por metrica (cliente; NULL = sem cliente identificado) e total da
  filial por soma -- nunca duas granularidades da mesma metrica;
- idempotencia (2x nao muda nada) e reprocessamento (execucao nova, celulas
  atualizadas, orfas removidas);
- pendencias de de-para (filial 002) e de cliente (sem auto-cadastro --
  decisao da Maria, 31/jul/2026);
- raiz do CNPJ tolerante a celula numerica do Excel (zeros a esquerda).
"""

import io
from datetime import date

import openpyxl
import pytest

from backend.services import graph_datahub, inventario_datahub, processamento_datahub

_CABECALHO = [
    "Cliente", "Cliente CNPJ", "GEM", "Devolução", "Solicitação", "NF Entrada",
    "Código", "Descrição", "Volume", "EMB", "Fração", "EMB", "Peso Líquido",
    "Peso Bruto", "Vlr. Unitário", "Vlr. Total", "Qtde UA", "Código Estoque",
    "Nome Estoque", "Operação",
]

# clientes do seed (backend/seed_clientes.py): nk_erp = raiz do CNPJ
_SAPORE_CNPJ = "67945071000159"   # raiz 67945071
_GR_CNPJ = "02.905.110/0001-23"   # raiz 02905110, formatado de proposito
_DESCONHECIDO_CNPJ = "99999999000199"  # raiz 99999999, fora do cadastro


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


def _arquivo(nome, id_, modificado_em="2026-07-13T00:00:00Z"):
    return {
        "nome": nome,
        "caminho": f"ENTRADA/ENTRADA MERCADORIAS/{nome}",
        "tamanho": 1000,
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
    """arquivos: lista de (dict do inventario, bytes do xlsx). Preenche o cache
    e mocka o download por item_id."""
    inventario_datahub._cache.update(
        {
            "sincronizado_em": "2026-07-29T00:00:00Z",
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
    """[(nk_erp ou None, valor float)] das celulas canonicas da metrica."""
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


# --- raiz do CNPJ (puro) -------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("67945071000159", "67945071"),
        ("67.945.071/0001-59", "67945071"),
        ("67945071", "67945071"),          # ja e uma raiz
        (2905110000123, "02905110"),        # celula numerica: zeros a esquerda perdidos
        (2905110000123.0, "02905110"),      # idem, lida como float
        ("123", None),                       # curto demais pra identificar
        ("123456789012345", None),           # longo demais (nao e CNPJ)
        ("", None),
        (None, None),
    ],
)
def test_raiz_cnpj(valor, esperado):
    assert processamento_datahub.raiz_cnpj(valor) == esperado


# --- processamento de um arquivo ------------------------------------------------


def test_processa_grava_celulas_por_cliente(cursor, monkeypatch):
    linhas = [
        _linha(peso_bruto=100.0, vlr_total=10.0),
        _linha(peso_bruto=200.0, vlr_total=20.0),
        _linha(cliente="GR SA", cnpj=_GR_CNPJ, peso_bruto=50.0, vlr_total=5.0),
        _linha(cliente="NOVO LTDA", cnpj=_DESCONHECIDO_CNPJ, peso_bruto=7.0, vlr_total=3.0),
    ]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-016")

    assert relatorio["status"] == "ok"
    assert relatorio["filial"] == "016"
    assert relatorio["competencia"] == "2026-07"
    assert relatorio["clientes"] == 2
    assert relatorio["sem_cliente"] == 1
    assert relatorio["medidas_gravadas"] == 9  # 3 metricas x 3 baldes

    # celulas canonicas no grao cliente; total da filial = soma das linhas
    assert _medidas(cursor, "peso_bruto_movimentado") == [
        ("02905110", 50.0), ("67945071", 300.0), (None, 7.0),
    ]
    assert _medidas(cursor, "valor_mercadoria_movimentada") == [
        ("02905110", 5.0), ("67945071", 30.0), (None, 3.0),
    ]
    assert _medidas(cursor, "registros_movimentacao") == [
        ("02905110", 1.0), ("67945071", 2.0), (None, 1.0),
    ]

    # execucao do conector novo, com o caminho do SharePoint como arquivo_path
    cursor.execute(
        """
        SELECT e.origem, e.status, e.linhas_lidas, e.linhas_gravadas, e.arquivo_path, c.tipo
        FROM execucoes e JOIN conectores c ON c.id = e.conector_id
        """
    )
    assert cursor.fetchall() == [
        ("datahub", "ok", 4, 9, arquivo["caminho"], "sharepoint_datahub")
    ]

    # recebidas: append-only, com unidade canonica do conceito e arquivo de origem
    cursor.execute(
        """
        SELECT DISTINCT mt.nome, mr.unidade, mr.arquivo_origem
        FROM medidas_recebidas mr JOIN metricas mt ON mt.id = mr.metrica_id
        ORDER BY mt.nome
        """
    )
    assert cursor.fetchall() == [
        ("peso_bruto_movimentado", "kg", arquivo["nome"]),
        ("registros_movimentacao", "un", arquivo["nome"]),
        ("valor_mercadoria_movimentada", "brl", arquivo["nome"]),
    ]
    cursor.execute("SELECT COUNT(*) FROM medidas_recebidas")
    assert cursor.fetchone()[0] == 9

    # linhagem: toda celula aponta a recebida que a originou
    cursor.execute("SELECT COUNT(*) FROM medidas WHERE medida_recebida_id IS NULL")
    assert cursor.fetchone()[0] == 0

    # controle por arquivo
    cursor.execute(
        "SELECT filial, competencia, status, medidas_gravadas FROM processamentos_datahub"
    )
    assert cursor.fetchall() == [("016", date(2026, 7, 1), "ok", 9)]

    # cliente fora do cadastro virou pendencia com nome e raiz
    pendencias = processamento_datahub.listar_pendencias_cliente(cursor)
    assert [(p["cliente_na_fonte"], p["nome_na_fonte"]) for p in pendencias] == [
        ("99999999", "NOVO LTDA")
    ]


def test_idempotente_processar_duas_vezes(cursor, monkeypatch):
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx([_linha(peso_bruto=100.0)]))])

    processamento_datahub.processar_arquivo(cursor, "item-016")
    processamento_datahub.processar_arquivo(cursor, "item-016")

    # celulas canonicas: as MESMAS (upsert), valores inalterados
    assert _medidas(cursor, "peso_bruto_movimentado") == [("67945071", 100.0)]
    cursor.execute("SELECT COUNT(*) FROM medidas")
    assert cursor.fetchone()[0] == 3
    # auditoria acumula: 2 execucoes, 6 recebidas, 1 controle por arquivo
    cursor.execute("SELECT COUNT(*) FROM execucoes")
    assert cursor.fetchone()[0] == 2
    cursor.execute("SELECT COUNT(*) FROM medidas_recebidas")
    assert cursor.fetchone()[0] == 6
    cursor.execute("SELECT COUNT(*) FROM processamentos_datahub")
    assert cursor.fetchone()[0] == 1


def test_reprocessar_apos_cadastro_move_do_balde_sem_cliente(cursor, monkeypatch):
    """O caminho combinado com a decisao da Maria: cliente desconhecido soma no
    balde NULL; depois do cadastro, o reprocessamento move os valores pra linha
    do cliente e REMOVE a celula orfa do balde."""
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    linhas = [
        _linha(peso_bruto=100.0),
        _linha(cliente="NOVO LTDA", cnpj=_DESCONHECIDO_CNPJ, peso_bruto=7.0),
    ]
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    processamento_datahub.processar_arquivo(cursor, "item-016")
    assert _medidas(cursor, "peso_bruto_movimentado") == [
        ("67945071", 100.0), (None, 7.0),
    ]

    cursor.execute(
        "INSERT INTO clientes (nk_erp, nome, catering) VALUES ('99999999', 'Novo Ltda', false)"
    )
    relatorio = processamento_datahub.processar_arquivo(cursor, "item-016")

    assert relatorio["celulas_removidas"] == 3  # balde NULL das 3 metricas
    assert _medidas(cursor, "peso_bruto_movimentado") == [
        ("67945071", 100.0), ("99999999", 7.0),
    ]
    cursor.execute("SELECT COUNT(*) FROM medidas WHERE cliente_id IS NULL")
    assert cursor.fetchone()[0] == 0


def test_filial_sem_depara_vira_pendencia(cursor, monkeypatch):
    arquivo = _arquivo("ENTRADA_MERCADORIAS_002_2607.xlsx", "item-002")
    _preparar(monkeypatch, [(arquivo, _xlsx([_linha()]))])

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-002")

    assert relatorio["status"] == "pendencia_depara"
    assert "002" in relatorio["detalhe"]
    cursor.execute("SELECT COUNT(*) FROM medidas")
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM execucoes")
    assert cursor.fetchone()[0] == 0
    assert [p["filial_na_fonte"] for p in processamento_datahub.listar_pendencias_filial(cursor)] == ["002"]
    cursor.execute("SELECT status FROM processamentos_datahub")
    assert cursor.fetchall() == [("pendencia_depara",)]


def test_conceito_sem_unidade_aprovada_bloqueia_processamento(cursor, monkeypatch):
    """Enforcement na ingestao: a unidade vem do conceito canonico; sem conceito
    aprovado com unidade, nada e gravado -- erro de configuracao, nunca palpite."""
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx([_linha()]))])
    cursor.execute(
        "UPDATE conceitos_canonicos SET status = 'rascunho' WHERE chave = 'peso_bruto_movimentado'"
    )

    with pytest.raises(
        processamento_datahub.ProcessamentoDatahubError, match="peso_bruto_movimentado"
    ):
        processamento_datahub.processar_arquivo(cursor, "item-016")
    cursor.execute("SELECT COUNT(*) FROM medidas")
    assert cursor.fetchone()[0] == 0


def test_metrica_fora_do_catalogo_e_erro_de_configuracao(cursor, monkeypatch):
    """Metrica sumindo do catalogo (seed nao rodado/edicao manual) e erro de
    configuracao com mensagem clara (vira 400 no endpoint), nunca 500 -- e
    nada e gravado (a resolucao acontece antes de qualquer escrita)."""
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx([_linha()]))])
    cursor.execute("DELETE FROM metricas WHERE nome = 'registros_movimentacao'")

    with pytest.raises(
        processamento_datahub.ProcessamentoDatahubError, match="registros_movimentacao"
    ):
        processamento_datahub.processar_arquivo(cursor, "item-016")
    cursor.execute("SELECT COUNT(*) FROM medidas")
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM execucoes")
    assert cursor.fetchone()[0] == 0


def test_reprocessar_arquivo_que_ficou_sem_linhas_validas_espelha_vazio(cursor, monkeypatch):
    """Arquivo republicado onde TODAS as linhas viraram invalidas (lidas > 0,
    validas = 0): o espelho fiel apaga as celulas anteriores daquela filial x
    competencia -- comportamento intencional (a serie reflete o ultimo estado
    do arquivo), registrado como decisao, nao acidente."""
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx([_linha()]))])
    processamento_datahub.processar_arquivo(cursor, "item-016")
    cursor.execute("SELECT COUNT(*) FROM medidas")
    assert cursor.fetchone()[0] == 3

    linha_invalida = _linha()
    linha_invalida[13] = "abc"  # Peso Bruto nao numerico -> linha descartada
    _preparar(monkeypatch, [(arquivo, _xlsx([linha_invalida]))])
    relatorio = processamento_datahub.processar_arquivo(cursor, "item-016")

    assert relatorio["status"] == "ok"
    assert relatorio["medidas_gravadas"] == 0
    assert relatorio["celulas_removidas"] == 3
    cursor.execute("SELECT COUNT(*) FROM medidas")
    assert cursor.fetchone()[0] == 0


# --- processar_todos (historico) -------------------------------------------------


def test_processar_todos_processa_novos_e_pula_inalterados(cursor, monkeypatch):
    a16 = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    a01 = _arquivo("ENTRADA_MERCADORIAS_001_2606.xlsx", "item-001")
    _preparar(monkeypatch, [(a16, _xlsx([_linha()])), (a01, _xlsx([_linha()]))])

    primeira = processamento_datahub.processar_todos(cursor)
    assert primeira["total_familia"] == 2
    assert len(primeira["processados"]) == 2
    assert primeira["pulados"] == 0

    segunda = processamento_datahub.processar_todos(cursor)
    assert len(segunda["processados"]) == 0
    assert segunda["pulados"] == 2

    # arquivo alterado no SharePoint (modificado_em novo) e reprocessado
    a16["modificado_em"] = "2026-07-20T00:00:00Z"
    terceira = processamento_datahub.processar_todos(cursor)
    assert [p["arquivo"] for p in terceira["processados"]] == [a16["nome"]]
    assert terceira["pulados"] == 1

    quarta = processamento_datahub.processar_todos(cursor, forcar=True)
    assert len(quarta["processados"]) == 2
    assert quarta["pulados"] == 0


def test_processar_todos_erro_num_arquivo_nao_derruba_o_lote(cursor, monkeypatch):
    bom = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    ruim = _arquivo("ENTRADA_MERCADORIAS_001_2607.xlsx", "item-001")
    _preparar(
        monkeypatch,
        [(bom, _xlsx([_linha()])), (ruim, _xlsx([_linha()], aba="Sheet1"))],
    )

    relatorio = processamento_datahub.processar_todos(cursor)

    assert [p["arquivo"] for p in relatorio["processados"]] == [bom["nome"]]
    assert [e["arquivo"] for e in relatorio["erros"]] == [ruim["nome"]]
    assert "SLIN" in relatorio["erros"][0]["erro"]
    cursor.execute(
        "SELECT status, detalhe FROM processamentos_datahub WHERE arquivo = %s",
        (ruim["nome"],),
    )
    status, detalhe = cursor.fetchone()
    assert status == "erro"
    assert "SLIN" in detalhe


def test_processar_todos_sem_sincronizacao_falha(cursor):
    with pytest.raises(processamento_datahub.ProcessamentoDatahubError, match="Sincronizar agora"):
        processamento_datahub.processar_todos(cursor)


def test_processar_todos_ignora_outras_familias(cursor, monkeypatch):
    familia = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    outra = _arquivo("GUIAS_ENTRADA_016_2607.xlsx", "item-guias")
    _preparar(monkeypatch, [(familia, _xlsx([_linha()])), (outra, b"nao importa")])

    relatorio = processamento_datahub.processar_todos(cursor)
    assert relatorio["total_familia"] == 1
    assert [p["arquivo"] for p in relatorio["processados"]] == [familia["nome"]]
