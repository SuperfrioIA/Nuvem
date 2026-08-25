"""V3.4 -- `cat_usuarios`: identidade e papel.

## A coluna nulavel e a costura do AD

O contrato do V3.4 pede "desenhado para o AD entrar depois sem reescrita
(**papel separado de identidade**)". Isso nao e organizacao de codigo, e o
schema:

    identidade -> QUEM voce e.     Hoje: senha local. Depois: AD.
    papel      -> O QUE voce pode. Sempre nosso, sempre neste banco.

Por isso `senha_hash` e **NULAVEL**. Um usuario do AD tem linha aqui -- com
papel, nome e `ativo` -- e **nenhuma senha local**. No dia do AD, a autenticacao
troca de modulo e a autorizacao nao muda uma linha, porque nunca dependeu de a
senha existir.

Se a coluna fosse `NOT NULL`, "AD depois" exigiria migration + senha falsa para
cada pessoa, e alguem acabaria guardando um hash inutil so para satisfazer a
restricao. O teste `test_usuario_sem_senha_local_tem_papel_mas_nao_entra` fixa
isso: se alguem tornar a coluna obrigatoria, o teste quebra.

## Login normalizado no banco, nao so no codigo

`CHECK (login = lower(btrim(login)))` existe porque a alternativa e ter
`Maria.Watanabe` e `maria.watanabe` como duas contas, com papeis diferentes,
descobertas no dia em que uma delas nao consegue baixar nada. Normalizar so no
Python protege o caminho do app e deixa o CLI, um `INSERT` manual e uma futura
sincronizacao de AD entrarem por baixo. A restricao no banco vale para todos.

O teto de 120 caracteres e para `login` nao virar campo livre de tamanho
arbitrario -- e-mail corporativo cabe com folga.

## Papeis: dois, e checados no banco

`admin` e `visualizador` (contrato). CHECK em vez de tabela de dominio: sao dois
valores fechados, e uma tabela de dominio com dois registros custaria join em
toda leitura de papel para descrever o que o CHECK ja descreve. Se um terceiro
papel aparecer, muda o CHECK -- que e uma migration honesta, e nao um dado novo
solto numa tabela.

## `ativo`, e nao apagar

Desativar preserva o rastro: a `cat_auditoria` guarda o login de quem baixou, e
apagar a pessoa transformaria auditoria antiga em referencia orfa. Nao ha FK
entre `cat_auditoria.usuario` e este `login` de proposito -- auditoria tem que
sobreviver a exclusao, inclusive de um login que nunca existiu nesta tabela (uma
tentativa de login com usuario inventado, que e exatamente o que se quer ver).

Revision ID: 0022_cat_usuarios
Revises: 0021_cat_auditoria
"""

from alembic import op

revision = "0022_cat_usuarios"
down_revision = "0021_cat_auditoria"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE cat_usuarios (
            login         TEXT PRIMARY KEY,
            nome          TEXT NOT NULL,
            papel         TEXT NOT NULL,
            -- NULAVEL de proposito: usuario de AD tem papel e nao tem senha
            -- local. Ver docstring -- e a costura do V3.5+, nao um esquecimento.
            senha_hash    TEXT,
            ativo         BOOLEAN NOT NULL DEFAULT true,
            criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
            ultimo_acesso TIMESTAMPTZ,
            CONSTRAINT ck_cat_usuarios_papel CHECK (papel IN
                ('admin', 'visualizador')),
            CONSTRAINT ck_cat_usuarios_login CHECK (
                login = lower(btrim(login))
                AND login <> ''
                AND length(login) <= 120),
            CONSTRAINT ck_cat_usuarios_nome CHECK (btrim(nome) <> '')
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE cat_usuarios")
