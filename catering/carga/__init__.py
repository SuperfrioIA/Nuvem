"""Carregador do catering: le a fonte, tipa, grava idempotente.

## A costura, que e o ponto do V3.1

    extrair(movimento, desde)   -> fonte_csv.py / fonte_oracle.py  (os UNICOS
                                   que conhecem a fonte)
    transformar(linha)          -> transformacao.py (nao sabe de onde veio)
    gravar(cur, lote)           -> destino.py       (nao sabe de onde veio)

O V3.1 previu que o V3.5 trocaria **uma** classe, e foi o que aconteceu:
`fonte_oracle.FonteOracle` tem o mesmo `extrair(movimento, desde)`, e este
arquivo ganhou uma guarda nova (a de carga vazia, abaixo) e nada mais. O
`desde` estar na assinatura desde o V3.1 e o que evitou que a troca mexesse na
assinatura de todo mundo.

## Idempotencia

Identidade e a chave natural do contrato, nao a `PK_FATO_VOL_*_CAT` (que vem
1..N e nao sobrevive a uma reconstrucao da tabela no DW). Rodar duas vezes
sobre a mesma fonte deixa o banco identico: a segunda rodada reporta
**0 inserida, 0 atualizada** e nem toca em `carga_id`, porque o `DO UPDATE`
tem `WHERE ... IS DISTINCT FROM`. Isso e testado.

## Falha derruba a rodada inteira

Decisao da Maria, 24/ago/2026. Linha malformada -> rollback do lote,
`cat_cargas.status = 'erro'` com a mensagem nomeando linha e coluna, e a
excecao sobe (processo agendado que falha em silencio e o pior desfecho).

Por que rollback e barato aqui: o upsert nao apaga nada, entao o dado da
rodada anterior continua no banco e na tela. O custo maximo de uma falha e
perder o frescor de meio dia (a carga roda 07h05 e 15h05). O custo de uma
carga PARCIAL seria um furo silencioso permanente -- a Matriz mostraria um
numero quase certo, e ninguem saberia quais linhas faltam.

**Fora de escopo nao e malformado.** Instancia nao-SLIN e outro negocio: e
pulada, contada e logada, sem derrubar nada. Medido nos CSVs de 21/ago: zero
linha nessa situacao, entao a guarda e tripwire.

## Carga COMPLETA que le zero linha e erro (V3.5)

`sem_dado` e o desfecho normal do **incremental**: nada mudou no DW desde a
marca d'agua. Numa carga **completa** ele nao e desfecho normal nenhum -- e a
fonte inteira vindo vazia, e nesse caso a tela continua mostrando o dado da
rodada anterior sem ninguem ser avisado. A A-7 do `V3_PLANO.md` pede
literalmente que a carga nunca reporte ok com zero linha, e isto e a
implementacao dela.

Tabela ausente ja derruba sozinha (`ORA-00942`). O que esta guarda cobre e o
caso pior, que a sondagem de 25/ago tornou concreto: a tabela **existe** e vem
vazia, porque o processo do DW versiona e reconstroi objeto. Custa nada --
rollback de rodada vazia nao desfaz nada, e o upsert nunca apaga -- e troca um
silencio por um alarme.

## Ordem

`carregar_tudo()` faz recebimento, expedicao e **depois** as dimensoes -- uma
vez, nao por movimento, porque a canonizacao do cliente soma peso sobre o
historico inteiro (ver `dimensoes.py`). Se um dos fatos falha, a rodada para
ali: mudanca de contrato costuma atingir os dois, e seguir depois de uma falha
produziria um relatorio que mistura o que deu certo com o que nao rodou.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from catering import contrato
from catering.carga import destino, dimensoes, transformacao

logger = logging.getLogger(__name__)

MOVIMENTOS = contrato.MOVIMENTOS


class CargaVazia(Exception):
    """Carga completa que nao trouxe nenhuma linha carregavel. Ver docstring."""


@dataclass
class Resultado:
    """O que uma rodada de um movimento fez.

    `linhas_fonte` e o que a fonte entregou; `linhas_carregadas` e o que
    estava dentro do escopo e entrou na carga. `iguais` e a fonte
    reapresentando linha sem mudanca -- o caso normal do dia a dia."""

    movimento: str
    carga_id: int
    status: str
    linhas_fonte: int = 0
    linhas_carregadas: int = 0
    inseridas: int = 0
    atualizadas: int = 0
    fora_escopo: int = 0
    max_dw_data_alteracao: datetime | None = None
    erro: str | None = None

    @property
    def iguais(self) -> int:
        return self.linhas_carregadas - self.inseridas - self.atualizadas

    def resumo(self) -> str:
        return (
            f"{self.movimento}: {self.status} -- {self.linhas_carregadas} lida(s), "
            f"{self.inseridas} inserida(s), {self.atualizadas} atualizada(s), "
            f"{self.iguais} igual(is), {self.fora_escopo} fora de escopo"
        )


def _chave_crua(linha, movimento) -> str:
    """A chave natural lida do dict CRU, para a mensagem de erro poder dizer
    qual linha quebrou mesmo quando a tipagem dela falhou."""
    return "/".join(
        str(linha.get(contrato.coluna_dw(coluna, movimento), ""))
        for coluna in contrato.CHAVE_NATURAL
    )


def carregar_movimento(fonte, movimento, desde=None) -> Resultado:
    """Carrega um movimento inteiro. Uma transacao para o fato, conexao
    separada para `cat_cargas` (ver `destino.py`)."""
    if movimento not in MOVIMENTOS:
        raise KeyError(movimento)

    logger.info(
        "carga %s iniciando -- fonte: %s%s",
        movimento,
        fonte.descrever(movimento),
        f", incremental desde {desde}" if desde else ", completa",
    )
    carga_id = destino.abrir_carga(movimento, fonte.nome)
    resultado = Resultado(movimento=movimento, carga_id=carga_id, status="rodando")

    conn = destino.conexao()
    try:
        with conn.cursor() as cur:
            lote = []
            for numero_linha, crua in enumerate(fonte.extrair(movimento, desde), start=1):
                resultado.linhas_fonte += 1

                if not transformacao.dentro_do_escopo(crua):
                    resultado.fora_escopo += 1
                    continue

                try:
                    linha = transformacao.transformar(crua, movimento)
                except transformacao.LinhaInvalida as erro:
                    raise transformacao.LinhaInvalida(
                        f"linha {numero_linha} da fonte "
                        f"({_chave_crua(crua, movimento)}): {erro}"
                    ) from None

                alterada_em = linha["dw_data_alteracao"]
                if (
                    resultado.max_dw_data_alteracao is None
                    or alterada_em > resultado.max_dw_data_alteracao
                ):
                    resultado.max_dw_data_alteracao = alterada_em

                lote.append(linha)
                resultado.linhas_carregadas += 1
                if len(lote) >= destino.PAGINA:
                    inseridas, atualizadas = destino.gravar(cur, movimento, carga_id, lote)
                    resultado.inseridas += inseridas
                    resultado.atualizadas += atualizadas
                    lote = []

            inseridas, atualizadas = destino.gravar(cur, movimento, carga_id, lote)
            resultado.inseridas += inseridas
            resultado.atualizadas += atualizadas

            # Antes do commit de proposito: a rodada vazia tem que sair pelo
            # mesmo caminho de falha das outras, com rollback e registro.
            if desde is None and resultado.linhas_carregadas == 0:
                raise CargaVazia(
                    f"carga completa de {movimento} nao trouxe nenhuma linha "
                    + (
                        f"carregavel: as {resultado.fora_escopo} linha(s) da fonte "
                        "estao todas fora do escopo do catering"
                        if resultado.fora_escopo
                        else "-- a fonte nao devolveu linha nenhuma"
                    )
                )

        conn.commit()
    except Exception as erro:
        conn.rollback()
        resultado.status = "erro"
        resultado.erro = str(erro)
        destino.finalizar_carga(carga_id, "erro", erro=erro)
        logger.error("carga %s falhou: %s", movimento, erro)
        raise
    finally:
        conn.close()

    # `sem_dado` e o caso normal do incremental do V3.5: nada mudou no DW
    # desde a marca d'agua. Nao e falha, e o status ja existe no CHECK da 0019.
    resultado.status = "sem_dado" if resultado.linhas_carregadas == 0 else "ok"
    destino.finalizar_carga(
        carga_id,
        resultado.status,
        linhas_lidas=resultado.linhas_carregadas,
        linhas_inseridas=resultado.inseridas,
        linhas_atualizadas=resultado.atualizadas,
        max_dw_data_alteracao=resultado.max_dw_data_alteracao,
    )
    if resultado.fora_escopo:
        logger.warning(
            "carga %s: %d linha(s) fora do escopo do catering (instancia nao %s)",
            movimento, resultado.fora_escopo, contrato.PREFIXO_INSTANCIA,
        )
    logger.info(resultado.resumo())
    return resultado


def carregar_tudo(fonte, incremental=False) -> dict:
    """Os dois fatos e depois as dimensoes, uma vez.

    `incremental=True` retoma cada movimento da marca d'agua da ultima rodada
    `ok` dele -- a forma que o V3.5 vai usar contra o Oracle, exercitavel hoje
    contra o CSV."""
    resultados = {}
    for movimento in MOVIMENTOS:
        desde = destino.marca_dagua(movimento) if incremental else None
        resultados[movimento] = carregar_movimento(fonte, movimento, desde=desde)
    resultados["dimensoes"] = dimensoes.atualizar()
    return resultados
