"""As variaveis de ambiente que a V3 exige, e o que dizer quando faltam.

## Por que este modulo existe

O CLI de usuarios (V3.4) resolveu isto uma vez: sem `DATABASE_URL`, ele morria
com `KeyError: 'DATABASE_URL'` e quinze linhas de traceback apontando para o
`psycopg2`. A correcao foi uma mensagem que diz o que fazer.

O carregador **nao** herdou essa correcao, e cobrou o preco: no fechamento do
V3.5 (26/ago/2026) a mesma falta produziu `carga falhou: 'DATABASE_URL'` --
duas vezes, na mesma sessao, com a pessoa certa lendo. A mensagem nao mentia,
so nao ajudava.

Duplicar o texto nos dois `__main__` seria a saida curta e errada: duas copias
de uma instrucao operacional envelhecem em ritmos diferentes, e a que envelhece
e sempre a que alguem le no pior momento. Entao o texto mora aqui, e os CLIs
importam.

## Por que a checagem e explicita, e nao um `try` em volta do `connect`

Porque o momento importa. A falta de variavel e conhecida **antes** de qualquer
trabalho: da para recusar na entrada, com a orientacao completa, em vez de
descobrir no meio de uma carga que ja abriu sessao no DW. Um `except KeyError`
generico em volta da conexao tambem pegaria um `KeyError` de outra origem e
diria a coisa errada com confianca.

## Por que depois do parse de argumento

`--help` e argumento errado nao dependem de banco. Exigir a variavel para ler a
ajuda seria hostil justamente com quem ainda esta descobrindo o comando.
"""

import os

# A armadilha e concreta e apareceu no uso real, duas vezes: as variaveis valem
# por sessao de shell, entao um SEGUNDO terminal aberto na mesma pasta nao tem
# nada exportado -- e o `.env` da raiz nao cobre o buraco, porque quem o le e o
# docker-compose, nao o Python.
FALTA_BANCO = """falta a variavel DATABASE_URL nesta sessao do terminal.

Variavel de ambiente vale por terminal -- se voce exportou noutra janela, esta
nao herda. O `.env` da raiz nao serve aqui: ele e lido pelo docker-compose, nao
pelo Python (ver docs/EXECUCAO_LOCAL.md).

No PowerShell, na raiz do repositorio:

    $env:DATABASE_URL = "postgresql://nuvem:teste@localhost:5433/nuvem_teste"

Ou, para carregar o .env inteiro nesta sessao:

    Get-Content .env | Where-Object { $_ -match '^\\s*[A-Z_]' } | ForEach-Object { $n,$v = $_ -split '=',2; Set-Item "env:$n" $v }
"""

# A mesma coisa para a credencial do DW. A `FonteOracle` ja recusa sem ela
# (`CredencialAusente`), e essa recusa acontece DEPOIS de o carregador abrir a
# conexao com o Postgres e registrar a rodada -- entao a linha em `cat_cargas`
# fica com `status='erro'` por um motivo que a pessoa poderia ter sabido antes
# de comecar. Isto e a mesma checagem, mais cedo.
#
# **Sem `.format` de proposito.** O corpo carrega um comando PowerShell com
# `ForEach-Object { ... }`, e `str.format` le essas chaves como campo de
# formatacao -- `KeyError: " $_ -match ..."`. Uma mensagem de erro que estoura
# ao ser montada e o pior lugar possivel para esse defeito, porque ela so e
# montada quando algo ja deu errado. A primeira linha e concatenada.
FALTA_DW = """Elas vivem no `.env` da raiz, que o Python NAO le sozinho. No PowerShell, na
raiz do repositorio:

    Get-Content .env | Where-Object { $_ -match '^\\s*[A-Z_]' } | ForEach-Object { $n,$v = $_ -split '=',2; Set-Item "env:$n" $v }

Nao passe a senha como argumento de linha de comando -- argumento aparece em
`ps`, no historico do shell e no log de quem estiver olhando.
"""

VARIAVEIS_DO_DW = ("DW_USER", "DW_SENHA")


def _vazia(nome: str) -> bool:
    return not (os.environ.get(nome) or "").strip()


def exigir_banco() -> None:
    """Recusa com orientacao se `DATABASE_URL` nao estiver na sessao."""
    if _vazia("DATABASE_URL"):
        raise SystemExit(FALTA_BANCO)


def exigir_credencial_do_dw() -> None:
    """Recusa com orientacao se faltar `DW_USER` ou `DW_SENHA`.

    Nomeia **quais** faltam: "faltam as credenciais" com as duas listadas manda
    conferir as duas; dizer que falta so a senha e o que faz a pessoa olhar no
    lugar certo."""
    faltando = [nome for nome in VARIAVEIS_DO_DW if _vazia(nome)]
    if faltando:
        raise SystemExit(
            "faltam as credenciais do DW nesta sessao do terminal: "
            + " e ".join(faltando) + ".\n\n" + FALTA_DW
        )
