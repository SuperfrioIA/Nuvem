"""Prova do risco 4 (V2.2) e do rename do V2.3: o total por competencia e o
mesmo antes e depois do reprocesso/deploy, mesmo o grao ou o NOME das celulas
mudando.

Uso no runbook do lote (rename de metrica no meio, caso do V2.3):

    # antes do `git pull` -- e a versao ANTIGA deste script, com os nomes
    # antigos (peso_bruto_movimentado, ...); rode do jeito que ja estava
    python3 scripts/totais_competencia.py antes.txt
    # deploy: git pull, docker compose up -d --build (migrations no startup)
    # "Processar arquivos" com FORCAR no painel do DataHub
    # --nomes-antigos pede a versao NOVA do script pra rotular as metricas
    # renomeadas com o nome de ANTES -- sem isso o diff acusa 100% das linhas
    # como diferentes so porque o ROTULO mudou (achado da revisao
    # independente do V2.3), mesmo o total batendo exato
    python3 scripts/totais_competencia.py --nomes-antigos depois.txt
    diff antes.txt depois.txt

Quando NAO ha rename no meio (lote comum), omita `--nomes-antigos` nas duas
chamadas.

O que o diff tem que mostrar: a coluna do total IDENTICA linha a linha pras
metricas que ja existiam antes do lote, e `n_celulas` podendo aumentar (grao
novo aparecendo). Linha de metrica NOVA (sem par em `antes.txt`, caso do par
de saida no V2.3) aparece so em `depois.txt` -- esperado, nao e diferenca.
Qualquer mudanca na coluna de total de uma metrica que ja existia reprova o
lote.

`ROUND(..., 3)` nao e cosmetico: o Python pode somar o mesmo total em
acumuladores/ordens de operacao diferentes entre uma rodada e outra -- a MESMA
soma pode divergir nos ultimos bits de um float. Arredondar pra 3 casas
(precisao de kg e de R$) evita falso positivo no diff por causa disso.
`registros_entrada`/`registros_saida` sao contagem inteira e batem exato de
qualquer forma.

**Endurecimento do V2.3** (achado da propria varredura do lote): a lista de
metricas era literal (`IN ('peso_bruto_movimentado', ...)`). Renomear a
metrica no banco sem atualizar esta lista faria a consulta voltar VAZIA -- o
`antes.txt`/`depois.txt` sairiam ambos vazios, o `diff` daria zero diferencas,
e o lote seria aprovado sem nada ter sido de fato comparado. Agora a lista e
RESOLVIDA contra `metricas` na hora, e o script FALHA se nenhuma resolver --
consulta vazia deixou de significar "esta tudo certo".

So stdlib (psql do container), mesmo padrao do verificar_v2.py: o Python do
host que roda o docker compose nao tem psycopg2. Somente leitura -- e SELECT.
"""

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SERVICO_DB = os.environ.get("SERVICO_DB", "nuvem-db")
USUARIO_DB = os.environ.get("POSTGRES_USER", "nuvem")
NOME_DB = os.environ.get("POSTGRES_DB", "nuvem")

# Par de entrada (V2.1-V2.2) + par de saida (V2.3). NAO existe
# valor_mercadoria_saida -- a fonte nao tem coluna de valor (docs/V2_3_PLANO_EXECUCAO.md §1.1).
_METRICAS_DATAHUB = (
    "peso_bruto_entrada", "valor_mercadoria_entrada", "registros_entrada",
    "peso_bruto_saida", "registros_saida",
)

# nome atual -> nome de antes do rename da migration 0015 (V2.3). So usado
# com --nomes-antigos, pra comparar um antes.txt gerado pela versao ANTERIOR
# deste script (que so conhecia os nomes antigos) contra um depois.txt gerado
# por esta versao -- sem isso o diff acusa 100% das linhas renomeadas como
# diferentes so pelo rotulo, mascarando a prova real (o total).
_NOMES_ANTES_DO_RENAME_V23 = {
    "peso_bruto_entrada": "peso_bruto_movimentado",
    "valor_mercadoria_entrada": "valor_mercadoria_movimentada",
    "registros_entrada": "registros_movimentacao",
}

def _lista_sql(nomes) -> str:
    """`('a', 'b')` a partir de uma lista de nomes -- sao constantes fixas do
    proprio script, nunca entrada externa."""
    return "(" + ", ".join(f"'{n}'" for n in nomes) + ")"


class ErroPsql(Exception):
    pass


def _sql(consulta: str) -> list[list[str]]:
    comando = [
        "docker", "compose", "exec", "-T", SERVICO_DB,
        "psql", "-U", USUARIO_DB, "-d", NOME_DB,
        "-v", "ON_ERROR_STOP=1", "-A", "-t", "-F", "|", "-c", consulta,
    ]
    try:
        resultado = subprocess.run(
            comando, cwd=RAIZ, capture_output=True, text=True, timeout=60
        )
    except FileNotFoundError as exc:
        raise ErroPsql("docker nao encontrado no PATH deste host") from exc
    except subprocess.TimeoutExpired as exc:
        raise ErroPsql("psql nao respondeu em 60s") from exc
    if resultado.returncode != 0:
        raise ErroPsql((resultado.stderr or resultado.stdout).strip()[:300])
    return [
        linha.split("|")
        for linha in resultado.stdout.strip().splitlines()
        if linha.strip()
    ]


def _metricas_existentes() -> list[str]:
    """Resolve `_METRICAS_DATAHUB` contra o catalogo -- nunca confia que o
    nome ainda existe. Sem isto, um rename (como o do V2.3) faz a consulta
    principal voltar vazia em silencio (ver docstring do modulo)."""
    linhas = _sql(f"SELECT nome FROM metricas WHERE nome IN {_lista_sql(_METRICAS_DATAHUB)}")
    encontradas = [linha[0] for linha in linhas]
    if not encontradas:
        raise ErroPsql(
            "nenhuma das metricas esperadas existe no catalogo "
            f"({', '.join(_METRICAS_DATAHUB)}) -- a lista deste script esta "
            "desatualizada (rename sem atualizar aqui?) ou o banco nao tem seed"
        )
    faltando = sorted(set(_METRICAS_DATAHUB) - set(encontradas))
    if faltando:
        print(f"AVISO: metrica(s) esperada(s) ausente(s): {faltando}", file=sys.stderr)
    return encontradas


def gerar_relatorio(nomes_antigos: bool = False) -> str:
    metricas = _metricas_existentes()
    consulta = f"""
        SELECT mt.nome, m.competencia, a.sigla, ROUND(SUM(m.valor), 3), COUNT(*)
        FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        JOIN armazens a ON a.id = m.armazem_id
        WHERE mt.nome IN {_lista_sql(metricas)}
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
    """
    linhas = _sql(consulta)
    cabecalho = f"{'metrica':<32} {'competencia':<12} {'filial':<8} {'total':>18} {'n_celulas':>10}"
    corpo = [cabecalho, "-" * len(cabecalho)]
    for metrica, competencia, filial, total, n_celulas in linhas:
        if nomes_antigos:
            metrica = _NOMES_ANTES_DO_RENAME_V23.get(metrica, metrica)
        corpo.append(f"{metrica:<32} {competencia:<12} {filial:<8} {total:>18} {n_celulas:>10}")
    # ORDER BY do SQL usa o nome ATUAL -- reordena pelo rotulo exibido pra
    # nao embaralhar a ordenacao quando --nomes-antigos troca o rotulo.
    if nomes_antigos:
        corpo = corpo[:2] + sorted(corpo[2:])
    return "\n".join(corpo) + "\n"


def main() -> int:
    argumentos = sys.argv[1:]
    nomes_antigos = "--nomes-antigos" in argumentos
    posicionais = [a for a in argumentos if not a.startswith("--")]

    try:
        relatorio = gerar_relatorio(nomes_antigos=nomes_antigos)
    except ErroPsql as exc:
        print(f"FALHA ao consultar o banco: {exc}", file=sys.stderr)
        return 1

    print(relatorio)
    if posicionais:
        destino = Path(posicionais[0])
        destino.write_text(relatorio, encoding="utf-8")
        print(f"(gravado em {destino})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
