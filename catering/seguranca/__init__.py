"""Login e papeis da V3 (lote V3.4).

Tres responsabilidades, separadas de proposito:

  - `identidade.py` -- **quem** a pessoa e. O modulo que o AD vai substituir.
  - `usuarios.py`   -- a tabela `cat_usuarios`: papel, `ativo`, senha guardada.
  - `sessao.py`     -- o cookie assinado, e o papel lido do banco por request.

`senha.py` guarda so a primitiva de hash (scrypt da stdlib), separada da politica
de autenticacao para ser testavel sozinha.

## O primeiro admin

Sistema com login precisa de uma forma de o primeiro acesso existir. As duas
saidas ruins sao: usuario fixo no codigo (que vai para o Git e para producao) e
endpoint publico de cadastro (que qualquer um usa antes de voce).

A saida daqui: `garantir_primeiro_admin()` roda no startup e cria o admin **so
se a tabela estiver vazia**, lendo `CAT_ADMIN_LOGIN` e `CAT_ADMIN_SENHA` do
ambiente. Com um usuario cadastrado, a funcao nao faz nada -- entao a variavel
esquecida no `.env` nao recria nem sobrescreve ninguem, e trocar o valor dela
depois nao muda a senha de quem existe.

A senha vai para o hash e **nunca** para log, auditoria ou resposta HTTP.
"""

import logging
import os

import psycopg2

from catering.seguranca import identidade, senha, sessao, usuarios

logger = logging.getLogger(__name__)

__all__ = ["identidade", "senha", "sessao", "usuarios", "garantir_primeiro_admin"]


def garantir_primeiro_admin():
    """Cria o primeiro admin a partir do ambiente, se nao houver usuario nenhum.

    Devolve o login criado, ou `None` se nao havia o que fazer. Nao levanta erro
    por banco ausente ou tabela inexistente: startup de app nao deve morrer por
    causa do bootstrap -- o `/health` e o lugar de reportar banco fora."""
    login = (os.environ.get("CAT_ADMIN_LOGIN") or "").strip()
    segredo = os.environ.get("CAT_ADMIN_SENHA") or ""
    if not login or not segredo:
        return None
    try:
        if usuarios.contar() > 0:
            return None
        criado = usuarios.criar(
            login=login,
            nome=os.environ.get("CAT_ADMIN_NOME") or login,
            papel="admin",
            senha=segredo,
        )
    except psycopg2.errors.UndefinedTable:
        logger.warning(
            "cat_usuarios nao existe ainda -- rode as migrations antes do login"
        )
        return None
    except psycopg2.OperationalError as erro:
        logger.warning("banco inalcancavel no bootstrap do admin: %s", erro)
        return None
    except usuarios.UsuarioInvalido as erro:
        logger.error("CAT_ADMIN_LOGIN invalido: %s", erro)
        return None
    logger.info("primeiro admin criado a partir do ambiente: %s", criado.login)
    return criado.login
