"""A tabela `cat_usuarios`: identidade e papel.

## O hash nao sai daqui

`Usuario` **nao tem** o campo do hash. Ele existe apenas dentro deste modulo, e
sai por uma unica funcao (`buscar_para_autenticar`), usada so pela
`identidade.py`. O motivo e concreto: se o hash viajasse no objeto, um dia ele
apareceria num `JSONResponse(usuario)`, num `logger.info("%s", usuario)` ou num
traceback -- e nenhum desses tres lugares e uma decisao, e um acidente.

## Conexao propria, sem pool

Mesma escolha da `auditoria.py` e do `app.py` da V3.2: conexao por chamada,
enquanto nao houver concorrencia que justifique um pool. O custo real disso e
uma conexao curta a mais por request autenticado (o papel e lido do banco a cada
request -- ver `sessao.py`). Numa ferramenta interna de CSC isso e barato;
quando deixar de ser, entra pool -- e entra para os dois, nao so aqui.

## `login` normalizado antes de tocar o banco

`normalizar()` aplica `strip().lower()`. A migration 0022 tem o mesmo CHECK, de
proposito redundante: aqui protege o app, la protege o CLI, o `INSERT` manual e
a futura sincronizacao de AD.
"""

import logging
import os
from dataclasses import dataclass

import psycopg2

from catering.seguranca import senha as mod_senha

logger = logging.getLogger(__name__)

PAPEIS = ("admin", "visualizador")


class UsuarioInvalido(ValueError):
    """Dado de usuario que o banco recusaria -- erro do chamador."""


class UsuarioJaExiste(UsuarioInvalido):
    """Login ja cadastrado."""


class UltimoAdmin(UsuarioInvalido):
    """A alteracao deixaria o sistema sem nenhum admin ativo.

    O modo de falha que isto impede e simples e definitivo: o unico admin se
    desativa (ou se rebaixa) por engano, e ninguem mais consegue cadastrar
    usuario nem ler auditoria -- so o CLI na maquina resolve.

    A guarda fica **aqui**, e nao no `app.py`, para valer tambem para o CLI. Isso
    nao fecha a saida de recuperacao: criar outro admin primeiro e depois
    rebaixar o antigo continua funcionando, porque nesse instante ja existem
    dois."""


@dataclass(frozen=True)
class Usuario:
    """Quem a pessoa e e o que ela pode. **Sem o hash da senha** -- ver docstring
    do modulo."""

    login: str
    nome: str
    papel: str
    ativo: bool
    tem_senha_local: bool = False

    @property
    def admin(self) -> bool:
        return self.papel == "admin"

    def como_dict(self) -> dict:
        return {
            "login": self.login,
            "nome": self.nome,
            "papel": self.papel,
            "ativo": self.ativo,
            "tem_senha_local": self.tem_senha_local,
        }


def _conexao():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def normalizar(login) -> str:
    return (login or "").strip().lower()


def _validar_papel(papel) -> str:
    if papel not in PAPEIS:
        raise UsuarioInvalido(f"papel: {papel!r} -- esperado um de {PAPEIS}")
    return papel


def _montar(linha) -> Usuario:
    login, nome, papel, ativo, tem_senha = linha
    return Usuario(
        login=login, nome=nome, papel=papel, ativo=ativo,
        tem_senha_local=bool(tem_senha),
    )


_SELECAO = (
    "SELECT login, nome, papel, ativo, (senha_hash IS NOT NULL) FROM cat_usuarios"
)


def buscar(login) -> Usuario | None:
    """O usuario, ou `None`. Sem o hash."""
    login = normalizar(login)
    if not login:
        return None
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(f"{_SELECAO} WHERE login = %s", (login,))
            linha = cur.fetchone()
    finally:
        conn.close()
    return _montar(linha) if linha else None


def buscar_para_autenticar(login):
    """`(Usuario, hash)` -- a **unica** porta por onde o hash sai deste modulo.

    Usada so pela `identidade.py`. Devolve `(None, None)` se nao existir."""
    login = normalizar(login)
    if not login:
        return None, None
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT login, nome, papel, ativo, (senha_hash IS NOT NULL),"
                " senha_hash FROM cat_usuarios WHERE login = %s",
                (login,),
            )
            linha = cur.fetchone()
    finally:
        conn.close()
    if not linha:
        return None, None
    return _montar(linha[:5]), linha[5]


def listar(incluir_inativos=True) -> list[Usuario]:
    condicao = "" if incluir_inativos else " WHERE ativo"
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(f"{_SELECAO}{condicao} ORDER BY papel, login")
            return [_montar(linha) for linha in cur.fetchall()]
    finally:
        conn.close()


def contar() -> int:
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM cat_usuarios")
            return cur.fetchone()[0]
    finally:
        conn.close()


def criar(login, nome, papel, senha=None) -> Usuario:
    """Cria o usuario. `senha=None` cria **sem senha local** -- o caso do AD.

    Ver a migration 0022: papel sem senha e um estado legitimo, nao um
    rascunho."""
    login = normalizar(login)
    if not login:
        raise UsuarioInvalido("login vazio")
    if len(login) > 120:
        raise UsuarioInvalido("login acima de 120 caracteres")
    nome = (nome or "").strip()
    if not nome:
        raise UsuarioInvalido("nome vazio")
    _validar_papel(papel)
    hash_senha = mod_senha.gerar(senha) if senha else None

    conn = _conexao()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO cat_usuarios (login, nome, papel, senha_hash)"
                    " VALUES (%s, %s, %s, %s)",
                    (login, nome, papel, hash_senha),
                )
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                raise UsuarioJaExiste(f"login ja cadastrado: {login}") from None
        conn.commit()
    finally:
        conn.close()
    logger.info("usuario criado: %s (%s)", login, papel)
    return Usuario(login=login, nome=nome, papel=papel, ativo=True,
                   tem_senha_local=hash_senha is not None)


def _atualizar(login, coluna, valor) -> bool:
    """`coluna` entra por f-string, e por isso e **privada**: ela so recebe nome
    literal escrito aqui dentro (`papel`, `senha_hash`, `ativo`). O valor vai
    parametrizado, como todo o resto. Se um dia alguem precisar atualizar uma
    coluna vinda de fora, o certo e mapear entrada -> nome permitido, e nao abrir
    esta funcao."""
    login = normalizar(login)
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE cat_usuarios SET {coluna} = %s WHERE login = %s",
                (valor, login),
            )
            mudou = cur.rowcount == 1
        conn.commit()
    finally:
        conn.close()
    return mudou


def admins_ativos() -> list[str]:
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT login FROM cat_usuarios WHERE papel = 'admin' AND ativo"
            )
            return [linha[0] for linha in cur.fetchall()]
    finally:
        conn.close()


def _guardar_ultimo_admin(login) -> None:
    """Recusa a alteracao se `login` for o unico admin ativo. Ver `UltimoAdmin`."""
    ativos = admins_ativos()
    if ativos == [normalizar(login)]:
        raise UltimoAdmin(
            f"{normalizar(login)} e o unico admin ativo -- cadastre outro admin "
            "antes de rebaixar, desativar ou tirar a senha local deste"
        )


def definir_papel(login, papel) -> bool:
    """Troca o papel. **Vale no request seguinte** -- o papel nao mora no cookie
    (ver `sessao.py`)."""
    _validar_papel(papel)
    if papel != "admin":
        _guardar_ultimo_admin(login)
    mudou = _atualizar(login, "papel", papel)
    if mudou:
        logger.info("papel de %s alterado para %s", normalizar(login), papel)
    return mudou


def definir_senha(login, senha) -> bool:
    """Grava (ou remove, com `senha=None`) a senha local.

    Remover e o caminho de migracao para o AD: a pessoa mantem papel e historico
    e deixa de ter credencial local.

    A guarda do ultimo admin vale aqui tambem: **enquanto nao existe AD**, tirar
    a senha local do unico admin ativo tranca o sistema exatamente como
    desativa-lo -- ele passa a nao ter forma nenhuma de entrar."""
    valor = mod_senha.gerar(senha) if senha else None
    if valor is None:
        _guardar_ultimo_admin(login)
    mudou = _atualizar(login, "senha_hash", valor)
    if mudou:
        logger.info(
            "senha local de %s %s", normalizar(login),
            "definida" if valor else "removida",
        )
    return mudou


def definir_ativo(login, ativo) -> bool:
    """Ativa/desativa. Desativar corta o acesso **no request seguinte**, sem
    esperar o cookie expirar, e sem apagar o rastro na auditoria."""
    if not ativo:
        _guardar_ultimo_admin(login)
    mudou = _atualizar(login, "ativo", bool(ativo))
    if mudou:
        logger.info(
            "usuario %s %s", normalizar(login),
            "ativado" if ativo else "desativado",
        )
    return mudou


def marcar_acesso(login) -> None:
    """`ultimo_acesso = now()`. Chamado no login, nao a cada request: a pergunta
    que essa coluna responde e "quem ainda usa isto", e para ela um carimbo por
    sessao basta -- um por request seria uma escrita em toda leitura."""
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE cat_usuarios SET ultimo_acesso = now() WHERE login = %s",
                (normalizar(login),),
            )
        conn.commit()
    finally:
        conn.close()
