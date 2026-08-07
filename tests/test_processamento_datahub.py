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


def _linha(cliente="SAPORE", cnpj=_SAPORE_CNPJ, peso_bruto=100.0, vlr_total=50.0,
           nome_estoque="ESTOQUE 1"):
    return [
        cliente, cnpj, "GEM1", "N", "SOL1", "NF001", "COD1", "DESC",
        10, "CX", 1, "CX", 90.0, peso_bruto, 5.0, vlr_total, 3,
        "EST1", nome_estoque, "ENTRADA",
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


def _arquivo(nome, id_, modificado_em="2026-07-13T00:00:00Z", unidade="RMSPII"):
    """Item do inventario. `unidade` e o galho de primeiro nivel do caminho --
    e ela que qualifica o codigo de filial no de-para (`RMSPII/016`)."""
    return {
        "nome": nome,
        "caminho": f"{unidade}/ENTRADA/ENTRADA MERCADORIAS/{nome}",
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
    assert _medidas(cursor, "peso_bruto_entrada") == [
        ("02905110", 50.0), ("67945071", 300.0), (None, 7.0),
    ]
    assert _medidas(cursor, "valor_mercadoria_entrada") == [
        ("02905110", 5.0), ("67945071", 30.0), (None, 3.0),
    ]
    assert _medidas(cursor, "registros_entrada") == [
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
        ("peso_bruto_entrada", "kg", arquivo["nome"]),
        ("registros_entrada", "un", arquivo["nome"]),
        ("valor_mercadoria_entrada", "brl", arquivo["nome"]),
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
    assert _medidas(cursor, "peso_bruto_entrada") == [("67945071", 100.0)]
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
    assert _medidas(cursor, "peso_bruto_entrada") == [
        ("67945071", 100.0), (None, 7.0),
    ]

    cursor.execute(
        "INSERT INTO clientes (nk_erp, nome, catering) VALUES ('99999999', 'Novo Ltda', false)"
    )
    relatorio = processamento_datahub.processar_arquivo(cursor, "item-016")

    assert relatorio["celulas_removidas"] == 3  # balde NULL das 3 metricas
    assert _medidas(cursor, "peso_bruto_entrada") == [
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
    # a pendencia sai QUALIFICADA pela unidade: e a origem, nao o codigo nu,
    # que precisa de decisao humana pra virar de-para
    assert [
        p["origem_na_fonte"] for p in processamento_datahub.listar_pendencias_filial(cursor)
    ] == ["RMSPII/002"]
    cursor.execute("SELECT status FROM processamentos_datahub")
    assert cursor.fetchall() == [("pendencia_depara",)]


def test_conceito_sem_unidade_aprovada_bloqueia_processamento(cursor, monkeypatch):
    """Enforcement na ingestao: a unidade vem do conceito canonico; sem conceito
    aprovado com unidade, nada e gravado -- erro de configuracao, nunca palpite."""
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx([_linha()]))])
    cursor.execute(
        "UPDATE conceitos_canonicos SET status = 'rascunho' WHERE chave = 'peso_bruto_entrada'"
    )

    with pytest.raises(
        processamento_datahub.ProcessamentoDatahubError, match="peso_bruto_entrada"
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
    cursor.execute("DELETE FROM metricas WHERE nome = 'registros_entrada'")

    with pytest.raises(
        processamento_datahub.ProcessamentoDatahubError, match="registros_entrada"
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


# --- identidade do arquivo e unidade da fonte (lote de correcao) ----------------
#
# A fonte foi reestruturada em 31/jul/2026 e passou a ter quatro unidades
# publicando com a mesma convencao de nome. O que estes testes fixam: o nome
# nao identifica mais o arquivo (item_id identifica), o codigo de filial nao
# identifica mais o armazem (unidade + codigo identificam), nada some em
# silencio e colisao aborta a rodada.


def _depara_extra(cur, codigo_origem: str, sigla: str) -> int:
    """Garante que uma origem qualificada aponte pra um armazem do cadastro, no
    conector do DataHub. Devolve o armazem_id.

    `DO UPDATE` e nao `DO NOTHING`: desde o V2.1 origens como `CWB3/001` ja vem
    semeadas, e um teste precisa apontar essa origem pro armazem ERRADO de
    proposito (pra acionar a guarda de colisao). Com DO NOTHING o de-para
    semeado venceria em silencio e o teste passaria por engano."""
    cur.execute("SELECT id FROM conectores WHERE tipo = 'sharepoint_datahub'")
    conector_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM armazens WHERE sigla = %s", (sigla,))
    armazem_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT (conector_id, armazem_na_fonte) DO UPDATE SET armazem_id = EXCLUDED.armazem_id",
        (conector_id, codigo_origem, armazem_id),
    )
    return armazem_id


def _medidas_por_armazem(cur, metrica: str):
    """[(sigla do armazem, valor)] das celulas da metrica."""
    cur.execute(
        """
        SELECT a.sigla, m.valor::float
        FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        JOIN armazens a ON a.id = m.armazem_id
        WHERE mt.nome = %s
        ORDER BY a.sigla
        """,
        (metrica,),
    )
    return cur.fetchall()


def test_homonimos_de_unidades_diferentes_tem_registros_distintos(cursor, monkeypatch):
    """O caso real: ENTRADA_MERCADORIAS_001_2601.xlsx existe em RMSPII e em
    CWB3. Com a chave antiga (nome) os dois disputavam o mesmo registro; agora
    cada item_id tem o seu.

    Desde o V2.1 a CWB3 tem de-para, entao os dois homonimos processam -- que e
    o caso mais exigente pro registro por item_id, porque os dois escrevem. O
    lado "homonimo sem de-para para na pendencia" continua coberto pelos testes
    de pendencia (RJ e RMSPII/002 abaixo), que e o mesmo mecanismo: o de-para e
    resolvido por arquivo, antes de qualquer gravacao."""
    rmspii = _arquivo("ENTRADA_MERCADORIAS_001_2601.xlsx", "item-rmspii")
    cwb3 = _arquivo("ENTRADA_MERCADORIAS_001_2601.xlsx", "item-cwb3", unidade="CWB3")
    _preparar(monkeypatch, [(rmspii, _xlsx([_linha()])), (cwb3, _xlsx([_linha()]))])

    relatorio = processamento_datahub.processar_todos(cursor)

    assert relatorio["total_familia"] == 2
    assert {p["status"] for p in relatorio["processados"]} == {"ok"}

    cursor.execute(
        "SELECT item_id, unidade, status FROM processamentos_datahub ORDER BY item_id"
    )
    assert cursor.fetchall() == [
        ("item-cwb3", "CWB3", "ok"),
        ("item-rmspii", "RMSPII", "ok"),
    ]
    # cada unidade na sua celula, e a CWB3 deixou de ser pendencia (V2.1)
    assert _medidas_por_armazem(cursor, "peso_bruto_entrada") == [
        ("CWBIII", 100.0), ("RMSPII", 100.0),
    ]
    assert processamento_datahub.listar_pendencias_filial(cursor) == []


def test_pula_inalterado_mesmo_com_homonimo_de_outra_unidade(cursor, monkeypatch):
    """Era o flip-flop: como os dois homonimos escreviam no mesmo registro com
    modificado_em diferente, NENHUM era reconhecido como inalterado e os dois
    reprocessavam a cada rodada."""
    rmspii = _arquivo("ENTRADA_MERCADORIAS_001_2601.xlsx", "item-rmspii")
    cwb3 = _arquivo(
        "ENTRADA_MERCADORIAS_001_2601.xlsx", "item-cwb3", unidade="CWB3",
        modificado_em="2026-07-20T00:00:00Z",
    )
    _depara_extra(cursor, "CWB3/001", "CWBIII")
    _preparar(monkeypatch, [(rmspii, _xlsx([_linha()])), (cwb3, _xlsx([_linha()]))])

    processamento_datahub.processar_todos(cursor)
    segunda = processamento_datahub.processar_todos(cursor)

    assert segunda["pulados"] == 2
    assert segunda["processados"] == []


def test_renomear_no_sharepoint_nao_cria_entidade_nova(cursor, monkeypatch):
    """item_id sobrevive a rename/move -- o registro e ATUALIZADO, nao
    duplicado, e o nome novo aparece no painel."""
    antes = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(antes, _xlsx([_linha()]))])
    processamento_datahub.processar_todos(cursor)

    depois = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    depois["nome"] = "ENTRADA_MERCADORIAS_016_2607.xlsx"
    depois["caminho"] = "RMSPII/ENTRADA/2026/ENTRADA_MERCADORIAS_016_2607.xlsx"
    depois["modificado_em"] = "2026-08-01T00:00:00Z"
    _preparar(monkeypatch, [(depois, _xlsx([_linha()]))])
    processamento_datahub.processar_todos(cursor)

    cursor.execute("SELECT item_id, caminho FROM processamentos_datahub")
    assert cursor.fetchall() == [("item-016", depois["caminho"])]


def test_origem_sem_depara_nao_baixa_o_arquivo(cursor, monkeypatch):
    """`RMSPII/002` segue sem de-para (decisao humana pendente da Maria desde
    02/ago/2026 -- ver [[filiais-catering-poc]]): baixar so pra falhar na
    leitura trocaria uma pendencia clara por um erro. O de-para e resolvido
    antes. (Ate o V2.3 este teste usava a RJ como exemplo -- a migration 0016
    do proprio lote deu de-para a ela, RMRJ, entao deixou de servir.)"""
    baixados = []
    filial_002 = _arquivo("ENTRADA_MERCADORIAS_002_2601.xlsx", "item-002")
    _preparar(monkeypatch, [(filial_002, _xlsx([_linha()]))])
    monkeypatch.setattr(
        graph_datahub, "baixar_item",
        lambda item_id, limite_bytes: baixados.append(item_id) or b"",
    )

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-002")

    assert relatorio["status"] == "pendencia_depara"
    assert baixados == []


def test_filial_com_hifen_da_rj_vira_pendencia_visivel(cursor, monkeypatch):
    """Antes o padrao de nome exigia so digitos: os arquivos da RJ nao casavam
    e sumiam do processamento sem virar nem pendencia -- "nao casou no regex"
    virava "nao existe". O regex com hifen e o que este teste prova (a RJ
    entra na lista de candidatos); a pendencia em si e provada com
    `RMSPII/002` e `RMSPII/003` (nenhuma tem de-para) -- a RJ GANHOU de-para
    na migration 0016 deste mesmo lote (RMRJ), entao deixou de servir como
    exemplo de pendencia."""
    rj = _arquivo("ENTRADA_MERCADORIAS_004-003_2601.xlsx", "item-rj", unidade="RJ")
    filial_002 = _arquivo("ENTRADA_MERCADORIAS_002_2601.xlsx", "item-002")
    filial_003 = _arquivo("ENTRADA_MERCADORIAS_003_2601.xlsx", "item-003")
    _preparar(
        monkeypatch,
        [(rj, _xlsx([_linha()])), (filial_002, _xlsx([_linha()])), (filial_003, _xlsx([_linha()]))],
    )

    relatorio = processamento_datahub.processar_todos(cursor)

    assert relatorio["total_familia"] == 3
    # a RJ tem de-para agora (RMRJ) -- processa "ok"; as outras duas seguem pendentes
    assert {p["status"] for p in relatorio["processados"]} == {"ok", "pendencia_depara"}
    assert sorted(
        p["origem_na_fonte"] for p in processamento_datahub.listar_pendencias_filial(cursor)
    ) == ["RMSPII/002", "RMSPII/003"]


def test_arquivo_na_raiz_sem_unidade_cai_como_pendencia_nao_qualificada(cursor, monkeypatch):
    """Arquivo solto na raiz da pasta configurada nao tem unidade: o codigo
    fica sem prefixo, nao casa com de-para nenhum e vira pendencia visivel --
    melhor que atribuir uma unidade por palpite."""
    solto = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-solto")
    solto["caminho"] = "ENTRADA_MERCADORIAS_016_2607.xlsx"
    _preparar(monkeypatch, [(solto, _xlsx([_linha()]))])

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-solto")

    assert relatorio["status"] == "pendencia_depara"
    assert relatorio["unidade"] is None
    assert [
        p["origem_na_fonte"] for p in processamento_datahub.listar_pendencias_filial(cursor)
    ] == ["016"]


def test_processamento_nao_apaga_celula_de_outra_unidade(cursor, monkeypatch):
    """Criterio central do lote: com o de-para qualificado, cada unidade grava
    no seu armazem e a remocao de orfas (metrica, armazem, competencia) nao
    alcanca a outra. Antes, os dois caiam no armazem da RMSPII e cada
    processamento apagava as celulas do outro."""
    _depara_extra(cursor, "CWB3/001", "CWBIII")
    rmspii = _arquivo("ENTRADA_MERCADORIAS_001_2601.xlsx", "item-rmspii")
    cwb3 = _arquivo("ENTRADA_MERCADORIAS_001_2601.xlsx", "item-cwb3", unidade="CWB3")
    _preparar(
        monkeypatch,
        [(rmspii, _xlsx([_linha(peso_bruto=100.0)])),
         (cwb3, _xlsx([_linha(peso_bruto=70.0)]))],
    )

    processamento_datahub.processar_todos(cursor)

    assert _medidas_por_armazem(cursor, "peso_bruto_entrada") == [
        ("CWBIII", 70.0), ("RMSPII", 100.0),
    ]
    # e a linhagem aponta pro armazem certo em cada recebida
    cursor.execute(
        """
        SELECT a.sigla, mr.arquivo_origem, e.arquivo_path
        FROM medidas_recebidas mr
        JOIN armazens a ON a.id = mr.armazem_id
        JOIN execucoes e ON e.id = mr.execucao_id
        JOIN metricas mt ON mt.id = mr.metrica_id
        WHERE mt.nome = 'peso_bruto_entrada'
        ORDER BY a.sigla
        """
    )
    assert cursor.fetchall() == [
        ("CWBIII", cwb3["nome"], cwb3["caminho"]),
        ("RMSPII", rmspii["nome"], rmspii["caminho"]),
    ]


def test_colisao_de_origem_aborta_antes_de_gravar(cursor, monkeypatch):
    """Dois arquivos na MESMA origem e competencia (ex.: uma copia numa
    subpasta da propria unidade). A rodada para antes de baixar qualquer
    coisa -- processar os dois faria um apagar as celulas do outro."""
    original = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-a")
    copia = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-b")
    copia["caminho"] = "RMSPII/ENTRADA/ENTRADA MERCADORIAS/backup/" + copia["nome"]
    _preparar(monkeypatch, [(original, _xlsx([_linha()])), (copia, _xlsx([_linha()]))])

    with pytest.raises(processamento_datahub.ProcessamentoDatahubError, match="colisao de origem"):
        processamento_datahub.processar_todos(cursor)

    cursor.execute("SELECT COUNT(*) FROM medidas")
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM processamentos_datahub")
    assert cursor.fetchone()[0] == 0


def test_colisao_de_armazem_aborta_a_rodada(cursor, monkeypatch):
    """Origens distintas apontando pro MESMO armazem (de-para mal configurado)
    passam pela pre-checagem, entao a guarda de tempo de execucao pega. Quem
    reverte o que ja foi gravado e a transacao do endpoint -- por isso a
    excecao sobe em vez de virar erro de arquivo."""
    _depara_extra(cursor, "CWB3/001", "RMSPII")  # errado de proposito
    rmspii = _arquivo("ENTRADA_MERCADORIAS_001_2601.xlsx", "item-rmspii")
    cwb3 = _arquivo("ENTRADA_MERCADORIAS_001_2601.xlsx", "item-cwb3", unidade="CWB3")
    _preparar(monkeypatch, [(rmspii, _xlsx([_linha()])), (cwb3, _xlsx([_linha()]))])

    with pytest.raises(processamento_datahub.ProcessamentoDatahubError, match="colisao de armazem"):
        processamento_datahub.processar_todos(cursor)


# --- V2.1.1: competencia sem movimento e status terminal, nao erro ------------
#
# Achado na primeira rodada real de processamento na VM (06/ago/2026): os
# arquivos 2601-2605 da SANCA tem cabecalho valido e zero linha (a unidade
# comecou a operar em 2606). O leitor levantava excecao e virava `erro`.


def test_arquivo_so_com_cabecalho_vira_sem_dado_e_nao_erro(cursor, monkeypatch):
    vazio = _arquivo("ENTRADA_MERCADORIAS_016_2601.xlsx", "item-vazio")
    _preparar(monkeypatch, [(vazio, _xlsx([]))])

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-vazio")

    assert relatorio["status"] == "sem_dado"
    cursor.execute("SELECT status, detalhe FROM processamentos_datahub WHERE item_id = 'item-vazio'")
    status, detalhe = cursor.fetchone()
    assert status == "sem_dado"
    assert "sem movimento" in detalhe
    # nenhuma celula inventada
    cursor.execute("SELECT COUNT(*) FROM medidas")
    assert cursor.fetchone()[0] == 0


def test_sem_dado_nao_e_baixado_de_novo_na_rodada_seguinte(cursor, monkeypatch):
    """O motivo pratico do lote: com status `erro`, o "pula inalterado" (que
    exige status terminal) nunca pulava -- os 5 arquivos vazios da SANCA eram
    baixados de novo em TODA rodada, pra sempre."""
    vazio = _arquivo("ENTRADA_MERCADORIAS_016_2601.xlsx", "item-vazio")
    _preparar(monkeypatch, [(vazio, _xlsx([]))])
    processamento_datahub.processar_todos(cursor)

    baixados = []
    monkeypatch.setattr(
        graph_datahub, "baixar_item",
        lambda item_id, limite_bytes: baixados.append(item_id) or _xlsx([]),
    )
    segunda = processamento_datahub.processar_todos(cursor)

    assert segunda["pulados"] == 1
    assert baixados == [], "arquivo sem movimento foi baixado de novo"


def test_arquivo_republicado_vazio_apaga_as_celulas_que_tinha_gravado(cursor, monkeypatch):
    """Decisao da Maria em 06/ago/2026, opcao (a): a serie e espelho fiel do
    ultimo estado da fonte -- coerente com o que a V1 ja faz quando todas as
    linhas de um arquivo republicado sao invalidas."""
    com_dado = _arquivo("ENTRADA_MERCADORIAS_016_2601.xlsx", "item-016")
    _preparar(monkeypatch, [(com_dado, _xlsx([_linha()]))])
    processamento_datahub.processar_todos(cursor)
    assert _medidas_por_armazem(cursor, "peso_bruto_entrada") == [("RMSPIV", 100.0)]

    republicado = _arquivo(
        "ENTRADA_MERCADORIAS_016_2601.xlsx", "item-016",
        modificado_em="2026-08-06T00:00:00Z",
    )
    _preparar(monkeypatch, [(republicado, _xlsx([]))])
    processamento_datahub.processar_todos(cursor)

    assert _medidas_por_armazem(cursor, "peso_bruto_entrada") == []
    cursor.execute("SELECT status FROM processamentos_datahub WHERE item_id = 'item-016'")
    assert cursor.fetchone()[0] == "sem_dado"


def test_arquivo_com_linhas_todas_invalidas_continua_erro_e_nao_sem_dado(cursor, monkeypatch):
    """`sem_dado` e ZERO linha. Arquivo COM linha que nao passa na validacao e
    outra coisa -- ali ha dado, e ele esta ruim; misturar os dois esconderia
    export quebrado atras de "sem movimento"."""
    linha_ruim = _linha()
    linha_ruim[13] = "nao e numero"  # Peso Bruto
    ruim = _arquivo("ENTRADA_MERCADORIAS_016_2601.xlsx", "item-ruim")
    _preparar(monkeypatch, [(ruim, _xlsx([linha_ruim]))])

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-ruim")

    assert relatorio["status"] == "ok"
    cursor.execute("SELECT linhas_validas FROM processamentos_datahub WHERE item_id = 'item-ruim'")
    assert cursor.fetchone()[0] == 0


# --- V2.2: tipo de estoque como dimensao ---------------------------------------
#
# A celula muda de grao: (metrica, armazem, competencia, cliente) vira
# (metrica, armazem, competencia, cliente, tipo_estoque). tipo_estoque vem de
# `Nome Estoque` por palavra-chave (backend/services/tipo_estoque.py), com
# pendencia visivel pro que nao casar -- mesmo padrao do de-para de filial e da
# pendencia de cliente.


def test_quatro_tipos_conhecidos_classificam_corretamente(cursor, monkeypatch):
    linhas = [
        _linha(peso_bruto=10.0, nome_estoque="SECO_RMSPII"),
        _linha(peso_bruto=20.0, nome_estoque="HORT-FRUTTI"),
        _linha(peso_bruto=30.0, nome_estoque="CONGELADO"),
        _linha(peso_bruto=40.0, nome_estoque="LC UTENSILIOS - GRUPO GR - RMSPII"),
    ]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-016")

    assert relatorio["tipos"] == 4
    cursor.execute(
        """
        SELECT tipo_estoque, valor::float FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        WHERE mt.nome = 'peso_bruto_entrada' ORDER BY tipo_estoque
        """
    )
    assert cursor.fetchall() == [
        ("CONGELADO", 30.0), ("HORTIFRUTI", 20.0), ("SECO", 10.0), ("UTENSILIOS", 40.0),
    ]
    assert processamento_datahub.listar_pendencias_tipo_estoque(cursor) == []


def test_relatorio_conta_clientes_distintos_mesmo_com_varios_tipos(cursor, monkeypatch):
    """clientes/sem_cliente contam por cliente distinto, nao por bucket
    (cliente, tipo) -- um cliente com movimentacao em 2 tipos continua
    contando como 1 cliente."""
    linhas = [
        _linha(peso_bruto=100.0, nome_estoque="SECO"),
        _linha(peso_bruto=50.0, nome_estoque="CONGELADO"),
        _linha(cliente="NOVO LTDA", cnpj=_DESCONHECIDO_CNPJ, peso_bruto=7.0, nome_estoque="SECO"),
    ]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-016")

    assert relatorio["clientes"] == 1  # sapore em 2 tipos conta uma vez
    assert relatorio["sem_cliente"] == 1
    assert relatorio["tipos"] == 2
    # 3 baldes (sapore/SECO, sapore/CONGELADO, None/SECO) x 3 metricas
    assert relatorio["medidas_gravadas"] == 9


def test_valor_nao_classificado_de_nome_estoque_vira_pendencia_visivel(cursor, monkeypatch):
    linhas = [_linha(peso_bruto=100.0, nome_estoque="ARMAZEM MISTO XYZ")]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-016")

    assert relatorio["status"] == "ok"
    pendencias = processamento_datahub.listar_pendencias_tipo_estoque(cursor)
    assert [p["valor_na_fonte"] for p in pendencias] == ["ARMAZEM MISTO XYZ"]
    # a linha nao some -- vira celula NAO_CLASSIFICADO, visivel na consulta
    cursor.execute(
        """
        SELECT tipo_estoque, valor::float FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        WHERE mt.nome = 'peso_bruto_entrada'
        """
    )
    assert cursor.fetchall() == [("NAO_CLASSIFICADO", 100.0)]


def test_nome_estoque_vazio_vira_pendencia_com_marcador_sem_valor(cursor, monkeypatch):
    linhas = [_linha(peso_bruto=100.0, nome_estoque=None)]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    processamento_datahub.processar_arquivo(cursor, "item-016")

    pendencias = processamento_datahub.listar_pendencias_tipo_estoque(cursor)
    assert [p["valor_na_fonte"] for p in pendencias] == ["(sem valor)"]


def test_prune_remove_celula_de_grao_antigo_apos_reprocesso_v22(cursor, monkeypatch):
    """Risco 4 da proposta V3: o grao da celula muda (V2.2 acrescenta
    tipo_estoque). Uma celula gravada ANTES do lote (tipo_estoque NULL)
    precisa ser removida pelo prune quando o arquivo reprocessa no grao novo --
    se o escopo do prune tivesse ficado estreito por tipo, ela sobreviveria ao
    lado das novas e o total da competencia dobraria."""
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    linhas = [
        _linha(peso_bruto=100.0, nome_estoque="SECO"),
        _linha(peso_bruto=50.0, nome_estoque="CONGELADO"),
    ]
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    # simula o estado ANTES do lote: celula no grao antigo (sem tipo_estoque)
    # pro mesmo armazem/competencia/cliente
    cursor.execute("SELECT id FROM metricas WHERE nome = 'peso_bruto_entrada'")
    metrica_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    armazem_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM clientes WHERE nk_erp = '67945071'")
    cliente_id = cursor.fetchone()[0]
    cursor.execute(
        """
        INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor, origem_tipo)
        VALUES (%s, %s, '2026-07-01', %s, 999, 'recebida')
        """,
        (metrica_id, armazem_id, cliente_id),
    )

    relatorio = processamento_datahub.processar_arquivo(cursor, "item-016")

    assert relatorio["status"] == "ok"
    assert relatorio["tipos"] == 2
    # a celula de grao antigo (tipo_estoque NULL) foi removida como orfa --
    # nao sobrevive ao lado das novas
    cursor.execute(
        "SELECT COUNT(*) FROM medidas WHERE metrica_id = %s AND cliente_id = %s "
        "AND tipo_estoque IS NULL",
        (metrica_id, cliente_id),
    )
    assert cursor.fetchone()[0] == 0
    # o total da competencia bate com o arquivo -- nao com 999 + 150
    cursor.execute(
        "SELECT SUM(valor)::float FROM medidas WHERE metrica_id = %s AND cliente_id = %s",
        (metrica_id, cliente_id),
    )
    assert cursor.fetchone()[0] == 150.0


def test_reprocesso_forcado_preserva_total_por_competencia(cursor, monkeypatch):
    """Prova que o total (SUM por competencia) e identico antes e depois do
    reprocesso com forcar=True -- so o grao (numero de celulas) muda."""
    linhas = [
        _linha(peso_bruto=100.0, nome_estoque="SECO"),
        _linha(peso_bruto=50.0, nome_estoque="CONGELADO"),
        _linha(cliente="GR SA", cnpj=_GR_CNPJ, peso_bruto=30.0, nome_estoque="HORTIFRUTI"),
    ]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    processamento_datahub.processar_todos(cursor)
    cursor.execute(
        "SELECT SUM(valor)::float, COUNT(*) FROM medidas m "
        "JOIN metricas mt ON mt.id = m.metrica_id WHERE mt.nome = 'peso_bruto_entrada'"
    )
    total_antes, celulas_antes = cursor.fetchone()

    processamento_datahub.processar_todos(cursor, forcar=True)
    cursor.execute(
        "SELECT SUM(valor)::float, COUNT(*) FROM medidas m "
        "JOIN metricas mt ON mt.id = m.metrica_id WHERE mt.nome = 'peso_bruto_entrada'"
    )
    total_depois, celulas_depois = cursor.fetchone()

    assert total_depois == total_antes == 180.0
    assert celulas_depois == celulas_antes  # mesmo arquivo, mesmo grao nas duas rodadas


def test_arquivo_republicado_vazio_apaga_todos_os_tipos(cursor, monkeypatch):
    """A decisao (a) de 06/ago (arquivo republicado vazio apaga as celulas que
    tinha gravado) continua valendo com o grao novo: todos os tipos, nao so
    um."""
    com_dado = _arquivo("ENTRADA_MERCADORIAS_016_2601.xlsx", "item-016")
    linhas = [
        _linha(peso_bruto=100.0, nome_estoque="SECO"),
        _linha(peso_bruto=50.0, nome_estoque="CONGELADO"),
    ]
    _preparar(monkeypatch, [(com_dado, _xlsx(linhas))])
    processamento_datahub.processar_todos(cursor)
    cursor.execute(
        "SELECT COUNT(*) FROM medidas m JOIN metricas mt ON mt.id = m.metrica_id "
        "WHERE mt.nome = 'peso_bruto_entrada'"
    )
    assert cursor.fetchone()[0] == 2  # SECO e CONGELADO

    republicado = _arquivo(
        "ENTRADA_MERCADORIAS_016_2601.xlsx", "item-016",
        modificado_em="2026-08-06T00:00:00Z",
    )
    _preparar(monkeypatch, [(republicado, _xlsx([]))])
    processamento_datahub.processar_todos(cursor)

    cursor.execute(
        "SELECT COUNT(*) FROM medidas m JOIN metricas mt ON mt.id = m.metrica_id "
        "WHERE mt.nome = 'peso_bruto_entrada'"
    )
    assert cursor.fetchone()[0] == 0
