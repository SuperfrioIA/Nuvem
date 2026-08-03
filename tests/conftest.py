"""Fixtures da suite (Lote R0). Postgres REAL — nada de mock de banco.

Banco de teste esperado em localhost:5433 (sobe uma vez e fica):

    docker run -d --name nuvem-teste-db -p 5433:5432 \
      -e POSTGRES_USER=nuvem -e POSTGRES_PASSWORD=teste \
      -e POSTGRES_DB=nuvem_teste postgres:16

Outra URL: exportar TEST_DATABASE_URL antes do pytest. Cada teste que usa
banco recomeca do zero (DROP SCHEMA public CASCADE) — nunca aponte pra um
banco com dados de verdade.
"""

import os
import tempfile

# ambiente ANTES de qualquer import do backend (DATABASE_URL, ADMIN_PASSWORD e
# SECRET_KEY sao lidos no import dos modulos)
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://nuvem:teste@localhost:5433/nuvem_teste"
)
os.environ.setdefault("ADMIN_PASSWORD", "senha-teste")
os.environ.setdefault("SECRET_KEY", "chave-de-teste-nao-usar-em-prod")
os.environ.setdefault("UPLOADS_DIR", tempfile.mkdtemp(prefix="nuvem_uploads_"))
# Bloco E (V1.5): so pra obter_configuracao_ia() nao levantar "faltam as
# variaveis" -- os testes mockam ia_client.enviar_mensagem, entao esta chave
# nunca chega a sair pra rede de verdade.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-teste-nao-usar-em-prod")

import psycopg2
import pytest

from backend import migracao
from backend.database import init_db


@pytest.fixture
def banco_vazio():
    """Schema public zerado (drop cascade + create)."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE")
        cur.execute("CREATE SCHEMA public")
    conn.close()


@pytest.fixture
def banco_migrado(banco_vazio):
    """Banco novo criado pelo caminho real: Alembic (upgrade head) + seeds."""
    migracao.migrar()
    init_db()


@pytest.fixture
def cursor(banco_migrado):
    """Cursor com commit no fim (mesmo padrao do get_conn do app)."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def cliente(banco_migrado):
    """TestClient autenticado no admin (o startup roda migrar+seeds de novo —
    precisa ser idempotente, e isso e parte do que os testes provam)."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        resposta = c.post("/api/admin/login", data={"senha": os.environ["ADMIN_PASSWORD"]})
        assert resposta.status_code == 200
        yield c


def consultar(sql: str, params=None) -> list[tuple]:
    """Consulta avulsa no banco de teste (pra asserts)."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()
