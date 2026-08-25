"""CLI de usuarios: `python -m catering.seguranca <comando>`.

O dia a dia tem tela (a `/administracao`, restrita a admin). Este CLI existe para
o que a tela nao alcanca: criar o primeiro admin sem depender do `.env`, e
recuperar acesso quando ninguem consegue entrar.

## A senha e pedida, nao passada como argumento

`--senha minha-senha` iria para o historico do shell, para o `ps` de quem
estiver na maquina e para o log de qualquer terminal gravado. Por isso a senha
vem por `getpass`, que nao ecoa. Nao ha flag para passar senha na linha de
comando -- de proposito.

Exemplos:

    python -m catering.seguranca listar
    python -m catering.seguranca criar --login maria.watanabe --nome "Maria" --papel admin
    python -m catering.seguranca criar --login joao.silva --nome "Joao" --papel visualizador --sem-senha
    python -m catering.seguranca senha --login maria.watanabe
    python -m catering.seguranca papel --login joao.silva --papel admin
    python -m catering.seguranca desativar --login joao.silva
"""

import argparse
import getpass
import os
import sys

from catering.seguranca import usuarios

# Mensagem no lugar do KeyError (25/ago/2026): sem `DATABASE_URL`, o CLI morria
# com `KeyError: 'DATABASE_URL'` e quinze linhas de traceback apontando para o
# `psycopg2`. Isso e defeito de ferramenta de recuperacao: ela e usada justamente
# quando algo esta errado, e nessa hora o traceback manda olhar o lugar errado.
#
# A armadilha e concreta e apareceu no uso real: as variaveis valem por sessao de
# shell, entao um SEGUNDO terminal aberto na mesma pasta nao tem nada exportado.
FALTA_BANCO = """falta a variavel DATABASE_URL nesta sessao do terminal.

Variavel de ambiente vale por terminal -- se voce exportou noutra janela, esta
nao herda. O `.env` da raiz nao serve aqui: ele e lido pelo docker-compose, nao
pelo Python (ver docs/EXECUCAO_LOCAL.md).

No PowerShell, na raiz do repositorio:

    $env:DATABASE_URL = "postgresql://nuvem:teste@localhost:5433/nuvem_teste"

Ou, para carregar o .env inteiro nesta sessao:

    Get-Content .env | Where-Object { $_ -match '^\\s*[A-Z_]' } | ForEach-Object { $n,$v = $_ -split '=',2; Set-Item "env:$n" $v }
"""


def _pedir_senha() -> str:
    primeira = getpass.getpass("senha: ")
    segunda = getpass.getpass("repita: ")
    if primeira != segunda:
        raise SystemExit("as senhas nao conferem")
    if len(primeira.strip()) < 8:
        raise SystemExit("senha curta -- minimo de 8 caracteres")
    return primeira


def _listar(_args) -> int:
    linhas = usuarios.listar()
    if not linhas:
        print("nenhum usuario cadastrado")
        return 0
    print(f"{'login':<32} {'papel':<14} {'ativo':<6} senha local")
    for u in linhas:
        print(
            f"{u.login:<32} {u.papel:<14} "
            f"{'sim' if u.ativo else 'NAO':<6} "
            f"{'sim' if u.tem_senha_local else 'nao (AD)'}"
        )
    return 0


def _criar(args) -> int:
    segredo = None if args.sem_senha else _pedir_senha()
    try:
        usuario = usuarios.criar(
            login=args.login, nome=args.nome, papel=args.papel, senha=segredo
        )
    except usuarios.UsuarioInvalido as erro:
        raise SystemExit(str(erro)) from None
    print(
        f"criado: {usuario.login} ({usuario.papel}), "
        f"senha local: {'sim' if usuario.tem_senha_local else 'nao'}"
    )
    return 0


def _senha(args) -> int:
    try:
        mudou = usuarios.definir_senha(args.login, _pedir_senha())
    except usuarios.UsuarioInvalido as erro:
        raise SystemExit(str(erro)) from None
    if not mudou:
        raise SystemExit(f"login nao encontrado: {args.login}")
    print(f"senha de {usuarios.normalizar(args.login)} atualizada")
    return 0


def _papel(args) -> int:
    # `UltimoAdmin` sobe daqui quando a troca deixaria o sistema sem admin ativo.
    # Sem este `except` ela virava traceback -- e numa ferramenta de recuperacao
    # o traceback esconde justamente a instrucao de como sair do problema.
    try:
        mudou = usuarios.definir_papel(args.login, args.papel)
    except usuarios.UsuarioInvalido as erro:
        raise SystemExit(str(erro)) from None
    if not mudou:
        raise SystemExit(f"login nao encontrado: {args.login}")
    print(f"papel de {usuarios.normalizar(args.login)}: {args.papel}")
    return 0


def _ativo(args, ativo) -> int:
    try:
        mudou = usuarios.definir_ativo(args.login, ativo)
    except usuarios.UsuarioInvalido as erro:
        raise SystemExit(str(erro)) from None
    if not mudou:
        raise SystemExit(f"login nao encontrado: {args.login}")
    print(
        f"{usuarios.normalizar(args.login)}: "
        f"{'ativo' if ativo else 'desativado'}"
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m catering.seguranca",
        description="usuarios e papeis da V3 (cat_usuarios)",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("listar", help="lista os usuarios").set_defaults(func=_listar)

    p = sub.add_parser("criar", help="cria um usuario")
    p.add_argument("--login", required=True)
    p.add_argument("--nome", required=True)
    p.add_argument("--papel", required=True, choices=usuarios.PAPEIS)
    p.add_argument(
        "--sem-senha", action="store_true",
        help="cria com papel e sem credencial local (o caso do AD)",
    )
    p.set_defaults(func=_criar)

    p = sub.add_parser("senha", help="define a senha local")
    p.add_argument("--login", required=True)
    p.set_defaults(func=_senha)

    p = sub.add_parser("papel", help="troca o papel")
    p.add_argument("--login", required=True)
    p.add_argument("--papel", required=True, choices=usuarios.PAPEIS)
    p.set_defaults(func=_papel)

    p = sub.add_parser("desativar", help="corta o acesso, preservando o rastro")
    p.add_argument("--login", required=True)
    p.set_defaults(func=lambda args: _ativo(args, False))

    p = sub.add_parser("ativar", help="devolve o acesso")
    p.add_argument("--login", required=True)
    p.set_defaults(func=lambda args: _ativo(args, True))

    args = parser.parse_args(argv)
    # depois do parse, de proposito: `--help` e argumento errado nao dependem de
    # banco, e exigir a variavel para ler a ajuda seria hostil
    if not (os.environ.get("DATABASE_URL") or "").strip():
        raise SystemExit(FALTA_BANCO)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
