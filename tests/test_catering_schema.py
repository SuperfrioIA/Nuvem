"""V3.0 -- o schema do catering (migration 0019) contra Postgres real.

Confere o que a migration promete e que quebraria em silencio:
  1. o schema criado casa com `catering/contrato.py` (medido no dado) nos dois
     sentidos -- nenhuma coluna do contrato falta, nenhuma coluna sobra --
     inclusive tipo e nulabilidade;
  2. identificador com zero a esquerda e TEXT, a chave natural e UNIQUE de
     verdade, e ha um unico indice explicito por fato;
  3. a V2 nao foi tocada;
  4. os CHECK recusam valor desconhecido e o fato exige carga;
  5. `downgrade` desfaz tudo, sem sobrar tabela `cat_`.

Postgres real, nunca mock -- decisao de principio do projeto.

**Poucos testes de banco, de proposito.** A fixture `banco_migrado` zera o
schema e roda as 19 migrations mais os seeds a cada teste; quebrar isto em
dezesseis testes parametrizados custaria dezesseis migrations completas para
checar um schema que e estatico. As asserts carregam mensagem propria, entao a
falha continua dizendo qual coluna quebrou.
"""

import os

import psycopg2
import pytest
from alembic import command
from alembic.script import ScriptDirectory

from backend import migracao
from catering import contrato
from catering.dominio import tipo_estoque
from tests.conftest import consultar

REVISAO = "0019_catering_fato_dw"
ANTERIOR = "0018_corrige_sigla_rmspii"

TABELAS_NOVAS = {
    "cat_unidades", "cat_clientes", "cat_tipos_estoque", "cat_cargas",
    "cat_fato_recebimento", "cat_fato_expedicao",
}

FATO = {"rec": "cat_fato_recebimento", "exp": "cat_fato_expedicao"}

# Como o contrato declara o tipo -> como o Postgres o devolve no catalogo.
TIPO_ESPERADO = {
    "INTEGER": "integer",
    "SMALLINT": "smallint",
    "TEXT": "text",
    "DATE": "date",
    "TIMESTAMP": "timestamp without time zone",
    "NUMERIC(18,3)": "numeric",
}


def _colunas(tabela):
    """{nome: (tipo, aceita_nulo)} do catalogo do Postgres."""
    linhas = consultar(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (tabela,),
    )
    return {n: (t, s == "YES") for n, t, s in linhas}


def _tabelas():
    return {
        r[0] for r in consultar(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
    }


def _unique(tabela):
    """Lista de conjuntos de colunas de cada constraint UNIQUE da tabela."""
    linhas = consultar(
        """
        SELECT array_agg(a.attname::text)
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.conrelid = %s::regclass AND c.contype = 'u'
        GROUP BY c.oid
        """,
        (tabela,),
    )
    return [set(x[0]) for x in linhas]


def _indices(tabela):
    nomes = {
        r[0] for r in consultar(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename = %s",
            (tabela,),
        )
    }
    return {n for n in nomes if n.startswith("ix_")}


def _recusa(sql, params=None):
    """Executa numa conexao propria e exige que o banco recuse. Conexao a
    parte de proposito: insert que falha aborta a transacao, e nao quero
    deixar a conexao dos outros asserts num estado herdado."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.Error):
                cur.execute(sql, params)
    finally:
        conn.rollback()
        conn.close()


def _aceita(sql, params=None):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------- cadeia
def test_0019_esta_na_cadeia_depois_da_0018():
    """Confere o elo, nao que a 0019 seja o topo -- afirmar que ela e o head
    viraria falha legitima na primeira migration da V3.1. Nao toca banco."""
    script = ScriptDirectory.from_config(migracao._config())
    revisao = script.get_revision(REVISAO)
    assert revisao is not None
    assert revisao.down_revision == ANTERIOR
    head = script.get_current_head()
    caminho = {r.revision for r in script.walk_revisions("base", head)}
    assert REVISAO in caminho, "a 0019 ficou num galho fora do caminho do head"


# ------------------------------------------------------------- o schema
def test_schema_do_catering(banco_migrado):
    """As seis tabelas, o contrato nos dois sentidos, tipos de identificador,
    chave natural, indice, e a V2 intacta."""
    tabelas = _tabelas()
    assert TABELAS_NOVAS <= tabelas, "faltou tabela do catering"

    # a V2 continua rodando em producao enquanto a V3 e construida
    for antiga in ("medidas", "medidas_recebidas", "armazens", "clientes",
                   "conectores", "processamentos_datahub"):
        assert antiga in tabelas, f"a 0019 mexeu na V2: {antiga} desapareceu"

    for movimento, tabela in FATO.items():
        reais = _colunas(tabela)

        # 1. nenhuma coluna do contrato falta, e tipo e nulabilidade casam
        for nome, tipo, aceita_nulo in contrato.colunas(movimento):
            assert nome in reais, f"{tabela}: falta {nome}"
            tipo_real, nulo_real = reais[nome]
            assert tipo_real == TIPO_ESPERADO[tipo], \
                f"{tabela}.{nome}: banco diz {tipo_real}, contrato diz {tipo}"
            assert nulo_real is aceita_nulo, \
                f"{tabela}.{nome}: nulabilidade divergente do contrato"

        # 2. nenhuma coluna sobra -- coluna que o contrato nao declara e
        #    coluna que o carregador nao preenche
        declaradas = {n for n, _t, _nl in contrato.colunas(movimento)}
        declaradas |= {"id", "carga_id"}          # nossas, nao vem do DW
        assert set(reais) == declaradas, \
            f"{tabela}: colunas fora do contrato: {sorted(set(reais) - declaradas)}"

        # 3. identificador com zero a esquerda e TEXT. Como inteiro, num_gem
        #    '0000000001' deixa de casar com a fonte -- quebra o de-para.
        for nome in contrato.IDENTIFICADORES_TEXTO:
            assert reais[nome][0] == "text", f"{tabela}.{nome} deveria ser TEXT"

        # 4. a identidade da linha, e o alarme contra duplicata silenciosa
        assert _unique(tabela) == [set(contrato.CHAVE_NATURAL)], \
            f"{tabela}: UNIQUE nao e a chave natural do contrato"

        # 5. um indice explicito, e so. Indice que nao serve consulta nenhuma
        #    custa escrita e engana quem le o schema (disciplina do V2.1).
        assert _indices(tabela) == {f"ix_cat_fato_{movimento}_periodo"}, \
            f"{tabela}: indices explicitos inesperados"


# ------------------------------------------------------------- guardas
def test_guardas_do_schema(banco_migrado):
    """Os CHECK e a FK: status de carga, tipo de estoque, e fato sem carga."""
    _aceita("INSERT INTO cat_cargas (tabela_origem, status) VALUES (%s, 'ok')",
            (contrato.TABELA_REC,))
    _recusa("INSERT INTO cat_cargas (tabela_origem, status) VALUES (%s, 'xpto')",
            (contrato.TABELA_REC,))

    for tipo in sorted(tipo_estoque.TIPOS_VALIDOS):
        _aceita("INSERT INTO cat_tipos_estoque (nome_estoque, tipo) VALUES (%s, %s)",
                (f"NOME {tipo}", tipo))
    _recusa("INSERT INTO cat_tipos_estoque (nome_estoque, tipo) VALUES (%s, %s)",
            ("NOME X", "GELADINHO"))

    # linha de fato sem rodada de carga nao tem procedencia -- e a tela nao
    # poderia dizer de quando o dado e
    colunas = (
        "carga_id, pk_dw, dw_processo, dw_data_inclusao, dw_data_alteracao,"
        " sk_calendario, sk_instancia, sk_empresa, sk_filial, sk_cliente,"
        " nk_calendario, nk_instancia, nk_empresa, nk_filial, nk_wms_filial,"
        " nk_qls_filial, nk_slin_empresa, nk_slin_filial, nk_cliente,"
        " nk_wms_cliente, data_solic, ano_solic, nome_und, num_gem,"
        " cnpj_cpf_cli, raz_social, descr_oper_wms, nome_estoque,"
        " status_processo, flg_interface"
    )
    valores = (
        "999999, 1, 'p', now(), now(), 1, 1, 1, 1, 1, '2026-01-02',"
        " 'SLIN_RMSPII_PRD', 'SF', '02060862000569', 'RMSPII', 'RMSPII',"
        " '001', '001', '01838723', 'X', '2026-01-02', 2026, 'BARUERI',"
        " '0000000001', '01838723041311', 'ALFA', 'ENTRADA', 'SECO',"
        " 'Concluido', 'D'"
    )
    _recusa(f"INSERT INTO cat_fato_recebimento ({colunas}) VALUES ({valores})")


# ------------------------------------------------------------ downgrade
def test_downgrade_nao_deixa_sobra(banco_migrado):
    """Migration que nao volta e migration que nao pode ser corrigida."""
    assert TABELAS_NOVAS <= _tabelas()
    command.downgrade(migracao._config(), ANTERIOR)
    assert {t for t in _tabelas() if t.startswith("cat_")} == set()
    command.upgrade(migracao._config(), "head")
    assert TABELAS_NOVAS <= _tabelas()
