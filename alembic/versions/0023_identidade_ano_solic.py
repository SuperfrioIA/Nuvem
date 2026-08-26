"""A identidade do fato ganha `ano_solic`: o num_gem se recicla por ano.

## O que a primeira carga real descobriu (25/ago/2026)

A chave natural da 0019 -- `(nk_instancia, nk_wms_filial, num_gem, nome_estoque,
descr_oper_wms, nk_cliente)` -- foi medida unica em 36.300/36.300 e 42.468/42.468
linhas. Essas medicoes foram feitas nos CSVs de 21/ago, que tinham **um ano
so** (2026). No dia 25/ago o DW reconstruiu as duas tabelas com 3,6 anos de
historico (2023-2026, 201.848 e 231.886 linhas), e a chave deixou de ser unica:
repete em 27.834 linhas no recebimento e 44.187 na expedicao.

O upsert recusou, como devia: `ON CONFLICT DO UPDATE command cannot affect row
a second time`. Generalizar unicidade de uma amostra de um ano para a serie
inteira foi a falha -- de raciocinio, nao de codigo.

A causa: **`num_gem` se recicla por ano**. As colisoes aparecem 4x (2023, 2024,
2025, 2026) e em datas proximas dentro do ano -- gem `0000000020` em 03/jan/2023
e 05/jan/2026.

## Por que `ano_solic`, e nao uma das duas datas

Quatro candidatos ficaram unicos na medicao: `ano_solic`, `ano de data_solic`,
`data_solic` e `nk_calendario`. Tres coisas escolheram entre eles:

1. **O espaco de numeracao e o ano do PEDIDO, nao o do movimento.** `+ ano de
   nk_calendario` NAO fica unico (repete em 12 linhas no recebimento e 79 na
   expedicao) -- sao as viradas de ano, guia pedida em dezembro e movimentada em
   janeiro, que pertence a sequencia do ano anterior.

2. **A chave certa e a mais GROSSA que ainda seja unica.** Identidade fina
   significa que correcao na coluna extra deixa de ser update e passa a ser
   INSERT, com a linha antiga sobrevivendo ao lado: numero dobrado, sem alarme.
   `ano_solic` (SMALLINT) e a mais grossa das quatro.

3. **`data_solic` tem lixo, e `ano_solic` nao.** Nas 16 linhas da expedicao em
   que as duas discordam, `data_solic` traz **2105-04-29**, `2002-04-29` e
   `2005-05-07`, com `nk_calendario` sao em 2024/2025 -- ou seja, e a data que
   esta errada, e o ano que esta certo. Isso deixa de ser preferencia e vira
   decisao: existe defeito visivel na fonte que alguem vai corrigir um dia, e
   com `data_solic` na chave essa correcao (2105 -> 2025) mudaria a identidade
   da linha e duplicaria em silencio. Com `ano_solic` na chave, a mesma
   correcao e um UPDATE, porque `data_solic` e coluna comum.

## O nome da restricao

A 0019 criou o UNIQUE **sem nome**, e o Postgres gerou um nome truncado em 63
caracteres -- que ficou **diferente** nas duas tabelas
(`..._num_gem_nome__key` numa, `..._num_gem_nom_key` na outra), porque a
truncagem depende do tamanho do nome da tabela. Por isso esta migration
**descobre** o nome no catalogo em vez de escreve-lo, e nomeia a restricao nova
(`uq_cat_fato_<rec|exp>_identidade`) para a proxima nao ter esse trabalho.

## Recarga

Esta migration nao mexe em dado. A recarga vem de graca: nenhuma rodada contra
o Oracle chegou a concluir (todas ficaram em `erro`), entao nao ha marca d'agua
e a proxima carga e completa.

Revision ID: 0023_identidade_ano_solic
Revises: 0022_cat_usuarios
"""

from alembic import op

revision = "0023_identidade_ano_solic"
down_revision = "0022_cat_usuarios"
branch_labels = None
depends_on = None

FATOS = (("cat_fato_recebimento", "rec"), ("cat_fato_expedicao", "exp"))

# `ano_solic` entra logo depois do `num_gem`: ele qualifica o numero da guia --
# "o GEM e unico dentro do ano do pedido" -- e a chave se le nessa ordem.
IDENTIDADE_NOVA = (
    "nk_instancia, nk_wms_filial, num_gem, ano_solic, nome_estoque, "
    "descr_oper_wms, nk_cliente"
)
IDENTIDADE_ANTIGA = (
    "nk_instancia, nk_wms_filial, num_gem, nome_estoque, descr_oper_wms, "
    "nk_cliente"
)


def _trocar(tabela, apelido, colunas_novas, nome_novo):
    """Derruba o UNIQUE que existir na tabela e cria o novo, nomeado.

    Procura pelo catalogo porque a 0019 nao nomeou o dela. Falha alto se nao
    achar exatamente uma restricao unica: migration que nao encontra o que
    esperava tem que parar, nao seguir e deixar a tabela com duas identidades
    (ou nenhuma)."""
    op.execute(
        f"""
        DO $$
        DECLARE
            antigo text;
            quantas int;
        BEGIN
            SELECT count(*) INTO quantas FROM pg_constraint
             WHERE conrelid = '{tabela}'::regclass AND contype = 'u';
            IF quantas <> 1 THEN
                RAISE EXCEPTION
                  '{tabela}: esperava 1 restricao unica, achei %', quantas;
            END IF;

            SELECT conname INTO antigo FROM pg_constraint
             WHERE conrelid = '{tabela}'::regclass AND contype = 'u';
            EXECUTE format('ALTER TABLE {tabela} DROP CONSTRAINT %I', antigo);
        END $$
        """
    )
    op.execute(
        f"ALTER TABLE {tabela} ADD CONSTRAINT {nome_novo} "
        f"UNIQUE ({colunas_novas})"
    )


def upgrade() -> None:
    for tabela, apelido in FATOS:
        _trocar(tabela, apelido, IDENTIDADE_NOVA,
                f"uq_cat_fato_{apelido}_identidade")


def downgrade() -> None:
    """Volta a chave de seis colunas.

    **Isto falha de proposito** se o banco ja tiver mais de um ano de historico:
    a chave antiga nao e unica nesse dado, e o Postgres recusa criar a restricao.
    Falhar e o comportamento certo -- a alternativa seria apagar linha para o
    passado caber, e migration nao apaga dado do usuario para conseguir
    descer."""
    for tabela, apelido in FATOS:
        _trocar(tabela, apelido, IDENTIDADE_ANTIGA,
                f"uq_cat_fato_{apelido}_identidade_antiga")
