"""Ambiente do Alembic: conecta pelo DATABASE_URL (mesma variavel do app).

Sem target_metadata (nao ha models SQLAlchemy no projeto — o backend usa
psycopg2 puro): as migrations sao SQL escrito a mao, sem autogenerate.
Sem fileConfig: o logging fica com quem chamou (uvicorn no startup, pytest
nos testes) — configurar logging aqui silenciaria os loggers do app.
"""

import os

from alembic import context
from sqlalchemy import create_engine, pool


def _url() -> str:
    return os.environ["DATABASE_URL"]


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
