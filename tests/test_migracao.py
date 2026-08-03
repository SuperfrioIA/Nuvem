"""Migracao (Alembic + backend/migracao.py): banco novo, banco legado valido
(stamp), banco legado divergente (aborta SEM stamp) e equivalencia exata entre
a baseline e o schema que o init_db antigo criava."""

import os

import psycopg2
import pytest
from alembic.script import ScriptDirectory

from backend import migracao
from tests.conftest import consultar


def _head() -> str:
    """A revisao de topo do Alembic (muda a cada migration nova — R0 era a
    baseline, R1 acrescentou a 0002). Os testes de migracao comparam contra o
    head, nao contra a baseline fixa."""
    return ScriptDirectory.from_config(migracao._config()).get_current_head()

# DDL EXATO do init_db antigo (backend/database.py ate o Lote 8.5, antes do
# R0) — usado pra simular um banco legado real, como o da VM.
LEGADO_DDL = """
CREATE TABLE IF NOT EXISTS conectores (
    id SERIAL PRIMARY KEY,
    tipo TEXT NOT NULL,
    nome TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    ativo BOOLEAN NOT NULL DEFAULT true,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS armazens (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    sigla TEXT UNIQUE NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS metricas (
    id SERIAL PRIMARY KEY,
    nome TEXT UNIQUE NOT NULL,
    unidade TEXT
);
CREATE TABLE IF NOT EXISTS depara_armazem (
    id SERIAL PRIMARY KEY,
    conector_id INTEGER NOT NULL REFERENCES conectores(id),
    armazem_na_fonte TEXT NOT NULL,
    armazem_id INTEGER NOT NULL REFERENCES armazens(id),
    UNIQUE (conector_id, armazem_na_fonte)
);
CREATE TABLE IF NOT EXISTS depara_pendencias (
    id SERIAL PRIMARY KEY,
    conector_id INTEGER NOT NULL REFERENCES conectores(id),
    armazem_na_fonte TEXT NOT NULL,
    primeira_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultima_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (conector_id, armazem_na_fonte)
);
CREATE TABLE IF NOT EXISTS modelos_importacao (
    id SERIAL PRIMARY KEY,
    conector_id INTEGER NOT NULL REFERENCES conectores(id),
    nome TEXT NOT NULL,
    mapeamento JSONB NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT true,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS medidas (
    id SERIAL PRIMARY KEY,
    metrica_id INTEGER NOT NULL REFERENCES metricas(id),
    armazem_id INTEGER NOT NULL REFERENCES armazens(id),
    competencia DATE NOT NULL,
    valor NUMERIC NOT NULL,
    conector_id INTEGER REFERENCES conectores(id),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (metrica_id, armazem_id, competencia)
);
CREATE TABLE IF NOT EXISTS scores (
    id SERIAL PRIMARY KEY,
    metrica_id INTEGER NOT NULL REFERENCES metricas(id),
    armazem_id INTEGER NOT NULL REFERENCES armazens(id),
    competencia DATE NOT NULL,
    media NUMERIC,
    desvio_padrao NUMERIC,
    z_score NUMERIC,
    estado TEXT,
    calculado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (metrica_id, armazem_id, competencia)
);
CREATE TABLE IF NOT EXISTS execucoes (
    id SERIAL PRIMARY KEY,
    conector_id INTEGER REFERENCES conectores(id),
    modelo_id INTEGER REFERENCES modelos_importacao(id),
    origem TEXT NOT NULL DEFAULT 'manual',
    iniciado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalizado_em TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'em_andamento',
    linhas_lidas INTEGER,
    linhas_gravadas INTEGER,
    erro TEXT,
    arquivo_path TEXT
);
CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nk_erp TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    catering BOOLEAN NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS catalogo_fontes (
    id SERIAL PRIMARY KEY,
    chave TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    descricao TEXT NOT NULL,
    tabela_origem TEXT NOT NULL,
    tipo_origem TEXT NOT NULL,
    grao TEXT NOT NULL,
    modelo_id INTEGER REFERENCES modelos_importacao(id)
);
CREATE TABLE IF NOT EXISTS catalogo_colunas (
    id SERIAL PRIMARY KEY,
    fonte_id INTEGER NOT NULL REFERENCES catalogo_fontes(id),
    coluna TEXT NOT NULL,
    significado TEXT,
    papel TEXT
);
"""


def _executar(sql: str):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.close()


def _assinatura():
    """Assinatura do schema: colunas (nome, tipo, nulo, default de serial) e
    constraints (definicao normalizada, independente de nome)."""
    colunas = set(
        consultar(
            """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name <> 'alembic_version'
            """
        )
    )
    constraints = set(
        consultar(
            """
            SELECT rel.relname, con.contype, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = rel.relnamespace
            WHERE ns.nspname = 'public' AND rel.relname <> 'alembic_version'
            """
        )
    )
    return colunas, constraints


def _versao_alembic():
    linhas = consultar(
        "SELECT to_regclass('public.alembic_version') IS NOT NULL"
    )
    if not linhas[0][0]:
        return None
    versao = consultar("SELECT version_num FROM alembic_version")
    return versao[0][0] if versao else None


def test_banco_novo_cria_pela_baseline(banco_vazio):
    """Banco novo sobe pela cadeia de migrations ate o head (baseline + R1).
    As tabelas da baseline seguem todas presentes; o head so acrescenta."""
    migracao.migrar()
    assert _versao_alembic() == _head()
    tabelas = {t for t, *_ in _assinatura()[0]}
    assert set(migracao.SCHEMA_ESPERADO) <= tabelas
    assert "modelo_versoes" in tabelas  # tabela nova do R1


def test_migrar_e_idempotente(banco_vazio):
    migracao.migrar()
    antes = _assinatura()
    migracao.migrar()  # banco ja gerenciado: upgrade head sem pendencia = no-op
    assert _assinatura() == antes


def test_baseline_identica_ao_init_db_antigo(banco_vazio):
    """A prova de que a baseline reproduz exatamente o schema legado: mesmo
    conjunto de colunas (nome/tipo/nulidade) e mesmas constraints. Compara so
    ate a BASELINE (nao o head) — o head diverge de proposito a partir do R1."""
    from alembic import command

    _executar(LEGADO_DDL)
    assinatura_legado = _assinatura()

    _executar("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    command.upgrade(migracao._config(), migracao.BASELINE)
    assinatura_baseline = _assinatura()

    assert assinatura_baseline == assinatura_legado


def test_legado_valido_recebe_stamp_sem_tocar_dados(banco_vazio):
    _executar(LEGADO_DDL)
    _executar("INSERT INTO armazens (nome, sigla) VALUES ('Teste', 'TST')")

    migracao.migrar()

    # legado valido: stamp da baseline + upgrade ate o head (0002/R1)
    assert _versao_alembic() == _head()
    assert consultar("SELECT nome FROM armazens WHERE sigla = 'TST'") == [("Teste",)]
    # a migration R1 rodou por cima do legado sem perder o dado existente
    assert consultar("SELECT to_regclass('public.modelo_versoes') IS NOT NULL")[0][0] is True


def test_legado_com_coluna_faltando_aborta_sem_stamp(banco_vazio):
    _executar(LEGADO_DDL)
    _executar("ALTER TABLE medidas DROP COLUMN conector_id")

    with pytest.raises(RuntimeError, match="medidas.*conector_id"):
        migracao.migrar()

    assert _versao_alembic() is None  # nada de stamp automatico


def test_legado_com_tabela_faltando_aborta_sem_stamp(banco_vazio):
    """Simula a VM que nunca rodou o codigo dos Lotes 7.1/8.5 (sem as 3
    tabelas novas): validacao lista as ausentes e nao stampa."""
    _executar(LEGADO_DDL)
    _executar("DROP TABLE catalogo_colunas; DROP TABLE catalogo_fontes; DROP TABLE clientes")

    with pytest.raises(RuntimeError, match="tabela ausente: catalogo_colunas"):
        migracao.migrar()

    assert _versao_alembic() is None


def test_banco_novo_inclui_r2(banco_vazio):
    """Banco novo sobe pela cadeia completa (baseline + R1 + R2)."""
    migracao.migrar()
    assert _versao_alembic() == _head()
    tabelas = {t for t, *_ in _assinatura()[0]}
    assert {"medidas_recebidas", "medida_linhagem"} <= tabelas


def test_migrar_para_r2_preserva_medidas_como_legado(banco_vazio):
    """Banco parado na 0002 (pre-R2) com uma medida real: a migration 0003 nao
    pode perder a linha nem inventar vinculo com execucao que nao existe."""
    from alembic import command

    command.upgrade(migracao._config(), "0002_versionamento_modelos")
    _executar(
        """
        INSERT INTO conectores (tipo, nome) VALUES ('upload_manual', 'Upload manual');
        INSERT INTO armazens (nome, sigla) VALUES ('Teste', 'TST');
        INSERT INTO metricas (nome, unidade) VALUES ('metrica_teste', 'un');
        """
    )
    conector_id, armazem_id, metrica_id = (
        consultar("SELECT id FROM conectores")[0][0],
        consultar("SELECT id FROM armazens")[0][0],
        consultar("SELECT id FROM metricas")[0][0],
    )
    _executar(
        f"INSERT INTO medidas (metrica_id, armazem_id, competencia, valor, conector_id) "
        f"VALUES ({metrica_id}, {armazem_id}, '2026-01-01', 42, {conector_id})"
    )

    migracao.migrar()  # banco ja gerenciado (alembic_version na 0002) -> upgrade head

    assert _versao_alembic() == _head()
    assert consultar("SELECT valor, origem_tipo, medida_recebida_id FROM medidas") == [
        (42, "legado", None)
    ]


def test_migracao_0006_ciclo_completo_preserva_grao_filial(banco_vazio):
    """Bloco C: upgrade -> downgrade -> upgrade da 0006. O downgrade restaura a
    constraint antiga e descarta SO as linhas no grao cliente (nao
    representaveis nela); a linha sem cliente sobrevive ao ciclo inteiro."""
    from alembic import command

    migracao.migrar()
    _executar(
        """
        INSERT INTO conectores (tipo, nome) VALUES ('upload_manual', 'Upload manual');
        INSERT INTO armazens (nome, sigla) VALUES ('Teste', 'TST');
        INSERT INTO metricas (nome, unidade) VALUES ('metrica_teste', 'un');
        INSERT INTO clientes (nk_erp, nome) VALUES ('11111111', 'Cliente Teste');
        """
    )
    armazem_id = consultar("SELECT id FROM armazens")[0][0]
    metrica_id = consultar("SELECT id FROM metricas")[0][0]
    cliente_id = consultar("SELECT id FROM clientes")[0][0]
    _executar(
        f"INSERT INTO medidas (metrica_id, armazem_id, competencia, valor) "
        f"VALUES ({metrica_id}, {armazem_id}, '2026-07-01', 10)"
    )
    _executar(
        f"INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
        f"VALUES ({metrica_id}, {armazem_id}, '2026-07-01', {cliente_id}, 7)"
    )

    command.downgrade(migracao._config(), "0005_catalogo_semantico")

    for tabela in ("sincronizacoes_datahub", "processamentos_datahub", "cliente_pendencias"):
        assert consultar(f"SELECT to_regclass('public.{tabela}') IS NULL")[0][0] is True
    # a linha do grao cliente foi descartada; a do grao filial sobreviveu
    assert consultar("SELECT valor FROM medidas") == [(10,)]
    # a constraint antiga (3 colunas) voltou a valer
    constraint = consultar(
        """
        SELECT pg_get_constraintdef(con.oid)
        FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid
        WHERE rel.relname = 'medidas' AND con.contype = 'u'
        """
    )
    assert constraint == [("UNIQUE (metrica_id, armazem_id, competencia)",)]

    command.upgrade(migracao._config(), "head")

    assert _versao_alembic() == _head()
    assert consultar("SELECT valor, cliente_id FROM medidas") == [(10, None)]
    constraint = consultar(
        """
        SELECT pg_get_constraintdef(con.oid)
        FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid
        WHERE rel.relname = 'medidas' AND con.contype = 'u'
        """
    )
    assert constraint == [
        ("UNIQUE NULLS NOT DISTINCT (metrica_id, armazem_id, competencia, cliente_id)",)
    ]


def test_constraint_nova_deduplica_cliente_null(banco_vazio):
    """A celula sem cliente tem identidade (NULLS NOT DISTINCT): inserir a
    mesma celula NULL duas vezes viola a constraint -- e o que garante o
    upsert idempotente do caminho do upload E do DataHub."""
    migracao.migrar()
    _executar(
        """
        INSERT INTO armazens (nome, sigla) VALUES ('Teste', 'TST');
        INSERT INTO metricas (nome, unidade) VALUES ('metrica_teste', 'un');
        """
    )
    armazem_id = consultar("SELECT id FROM armazens")[0][0]
    metrica_id = consultar("SELECT id FROM metricas")[0][0]
    _executar(
        f"INSERT INTO medidas (metrica_id, armazem_id, competencia, valor) "
        f"VALUES ({metrica_id}, {armazem_id}, '2026-07-01', 10)"
    )
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _executar(
            f"INSERT INTO medidas (metrica_id, armazem_id, competencia, valor) "
            f"VALUES ({metrica_id}, {armazem_id}, '2026-07-01', 20)"
        )


def _preparar_datahub_sem_qualificacao():
    """Estado de um banco na 0007: conector do DataHub, um de-para de filial
    com codigo NU e uma pendencia idem -- exatamente o que o seed do Bloco C
    escrevia antes da 0008."""
    _executar(
        """
        INSERT INTO conectores (tipo, nome) VALUES ('sharepoint_datahub', 'SharePoint DataHub');
        INSERT INTO armazens (nome, sigla) VALUES ('Barueri/SP', 'RMSPII');
        """
    )
    conector_id = consultar(
        "SELECT id FROM conectores WHERE tipo = 'sharepoint_datahub'"
    )[0][0]
    armazem_id = consultar("SELECT id FROM armazens WHERE sigla = 'RMSPII'")[0][0]
    _executar(
        "INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id) "
        f"VALUES ({conector_id}, '001', {armazem_id})"
    )
    _executar(
        "INSERT INTO depara_pendencias (conector_id, armazem_na_fonte) "
        f"VALUES ({conector_id}, '002')"
    )
    return conector_id, armazem_id


def test_migracao_0008_qualifica_o_depara_preservando_o_armazem(banco_vazio):
    """Lote de correcao: o de-para do DataHub passa a ser qualificado pela
    unidade. O UPDATE preserva o armazem_id de cada linha (nao e delete +
    reseed, senao um ajuste manual de de-para se perderia), e a pendencia de
    codigo nu e descartada -- nao da pra afirmar a unidade dela."""
    from alembic import command

    migracao.migrar()
    command.downgrade(migracao._config(), "0007_laboratorio_sessoes")
    _, armazem_id = _preparar_datahub_sem_qualificacao()

    command.upgrade(migracao._config(), "head")

    assert consultar("SELECT armazem_na_fonte, armazem_id FROM depara_armazem") == [
        ("RMSPII/001", armazem_id)
    ]
    assert consultar("SELECT COUNT(*) FROM depara_pendencias")[0][0] == 0

    # e volta: o downgrade desfaz a qualificacao sem perder o vinculo
    command.downgrade(migracao._config(), "0007_laboratorio_sessoes")
    assert consultar("SELECT armazem_na_fonte, armazem_id FROM depara_armazem") == [
        ("001", armazem_id)
    ]


def test_migracao_0008_chave_do_processamento_vira_item_id(banco_vazio):
    """A identidade do arquivo deixa de ser o nome: dois homonimos de unidades
    diferentes passam a conviver, e o mesmo item_id nao entra duas vezes. O
    downgrade descarta o homonimo excedente (politica declarada na 0006)."""
    from alembic import command

    migracao.migrar()

    for item_id, unidade in (("item-rmspii", "RMSPII"), ("item-cwb3", "CWB3")):
        _executar(
            f"""
            INSERT INTO processamentos_datahub
                (arquivo, item_id, caminho, unidade, filial, competencia, status)
            VALUES ('ENTRADA_MERCADORIAS_001_2601.xlsx', '{item_id}',
                    '{unidade}/ENTRADA/ENTRADA_MERCADORIAS_001_2601.xlsx',
                    '{unidade}', '001', '2026-01-01', 'ok')
            """
        )
    assert consultar("SELECT COUNT(*) FROM processamentos_datahub")[0][0] == 2

    with pytest.raises(psycopg2.errors.UniqueViolation):
        _executar(
            """
            INSERT INTO processamentos_datahub
                (arquivo, item_id, filial, competencia, status)
            VALUES ('outro_nome.xlsx', 'item-cwb3', '001', '2026-01-01', 'ok')
            """
        )

    command.downgrade(migracao._config(), "0007_laboratorio_sessoes")

    assert consultar("SELECT item_id FROM processamentos_datahub") == [("item-cwb3",)]
    constraint = consultar(
        """
        SELECT pg_get_constraintdef(con.oid)
        FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid
        WHERE rel.relname = 'processamentos_datahub' AND con.contype = 'u'
        """
    )
    assert constraint == [("UNIQUE (arquivo)",)]

    command.upgrade(migracao._config(), "head")
    assert _versao_alembic() == _head()
    constraint = consultar(
        """
        SELECT pg_get_constraintdef(con.oid)
        FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid
        WHERE rel.relname = 'processamentos_datahub' AND con.contype = 'u'
        """
    )
    assert constraint == [("UNIQUE (item_id)",)]


def test_migracao_0009_corrige_cadastro_de_banco_existente(banco_vazio):
    """A 0009 e migration de DADO, e existe justamente pra alcancar banco que ja
    tem as linhas: o seed e insert-only, entao corrigir o seed nao mexeria neles.
    Simula o estado antigo (CWBI ativa com o apelido `001995`; RPIII ativa, com
    nome placeholder e sem CNPJ) e prova que o upgrade corrige os dois -- e que
    o downgrade os devolve."""
    from alembic import command

    migracao.migrar()
    command.downgrade(migracao._config(), "0008_identidade_datahub")

    _executar(
        """
        INSERT INTO conectores (tipo, nome) VALUES ('upload_manual', 'Upload manual');
        INSERT INTO armazens (nome, sigla, ativo) VALUES ('CWBI', 'CWBI', true);
        INSERT INTO armazens (nome, sigla, ativo) VALUES ('RPIII', 'RPIII', true);
        """
    )
    conector_id = consultar("SELECT id FROM conectores")[0][0]
    armazem_id = consultar("SELECT id FROM armazens WHERE sigla = 'CWBI'")[0][0]
    _executar(
        "INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id) "
        f"VALUES ({conector_id}, '001995', {armazem_id})"
    )

    command.upgrade(migracao._config(), "head")

    assert consultar(
        "SELECT ativo FROM armazens WHERE sigla IN ('CWBI','RPIII') ORDER BY sigla"
    ) == [(False,), (False,)]
    assert consultar(
        "SELECT count(*) FROM depara_armazem WHERE armazem_na_fonte = '001995'"
    ) == [(0,)]
    # RPIII ganhou o CNPJ como apelido e perdeu o nome placeholder
    assert consultar("SELECT nome FROM armazens WHERE sigla = 'RPIII'") == [
        ("Ribeirão Preto/SP",)
    ]
    assert consultar(
        "SELECT count(*) FROM depara_armazem WHERE armazem_na_fonte = '02060862000640'"
    ) == [(1,)]

    command.downgrade(migracao._config(), "0008_identidade_datahub")

    assert consultar(
        "SELECT ativo FROM armazens WHERE sigla IN ('CWBI','RPIII') ORDER BY sigla"
    ) == [(True,), (True,)]
    assert consultar(
        "SELECT count(*) FROM depara_armazem WHERE armazem_na_fonte = '001995'"
    ) == [(1,)]
    assert consultar("SELECT nome FROM armazens WHERE sigla = 'RPIII'") == [("RPIII",)]
    assert consultar(
        "SELECT count(*) FROM depara_armazem WHERE armazem_na_fonte = '02060862000640'"
    ) == [(0,)]


def test_migracao_0009_nao_toca_depara_de_outro_armazem(banco_vazio):
    """Escopo estreito: um de-para de `001995` apontando pra OUTRO armazem seria
    cadastro de alguem, nao o residuo do Lote 7 -- a migration nao apaga."""
    from alembic import command

    migracao.migrar()
    command.downgrade(migracao._config(), "0008_identidade_datahub")

    _executar(
        """
        INSERT INTO conectores (tipo, nome) VALUES ('upload_manual', 'Upload manual');
        INSERT INTO armazens (nome, sigla, ativo) VALUES ('Outro', 'OUT', true);
        """
    )
    conector_id = consultar("SELECT id FROM conectores")[0][0]
    armazem_id = consultar("SELECT id FROM armazens WHERE sigla = 'OUT'")[0][0]
    _executar(
        "INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id) "
        f"VALUES ({conector_id}, '001995', {armazem_id})"
    )

    command.upgrade(migracao._config(), "head")

    assert consultar(
        "SELECT count(*) FROM depara_armazem WHERE armazem_na_fonte = '001995'"
    ) == [(1,)]


def test_schema_esperado_bate_com_a_baseline(banco_vazio):
    """Guarda de consistencia interna: toda tabela/coluna que a validacao de
    legado exige precisa existir na baseline (senao a validacao mentiria)."""
    migracao.migrar()
    colunas, _ = _assinatura()
    existentes: dict[str, set] = {}
    for tabela, coluna, _tipo, _nulo in colunas:
        existentes.setdefault(tabela, set()).add(coluna)
    assert migracao.validar_schema_legado(existentes) == []
