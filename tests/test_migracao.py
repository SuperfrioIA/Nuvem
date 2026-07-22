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


def test_schema_esperado_bate_com_a_baseline(banco_vazio):
    """Guarda de consistencia interna: toda tabela/coluna que a validacao de
    legado exige precisa existir na baseline (senao a validacao mentiria)."""
    migracao.migrar()
    colunas, _ = _assinatura()
    existentes: dict[str, set] = {}
    for tabela, coluna, _tipo, _nulo in colunas:
        existentes.setdefault(tabela, set()).add(coluna)
    assert migracao.validar_schema_legado(existentes) == []
