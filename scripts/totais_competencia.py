"""Prova do risco 4 (V2.2): o total por competencia e o mesmo antes e depois
do reprocesso com `forcar=True`, mesmo o grao das celulas mudando.

Uso no runbook do lote:

    python3 scripts/totais_competencia.py antes.txt      # antes do deploy
    # deploy: git pull, docker compose up -d --build (migration 0014 no startup)
    # "Processar arquivos" com FORCAR no painel do DataHub
    python3 scripts/totais_competencia.py depois.txt     # depois do reprocesso
    diff antes.txt depois.txt

O que o diff tem que mostrar: a coluna do total IDENTICA linha a linha, e
`n_celulas` aumentando -- o aumento e o grao novo aparecendo (uma linha por
tipo de estoque em vez de uma so por cliente). Qualquer mudanca na coluna de
total reprova o lote.

`ROUND(..., 3)` nao e cosmetico: antes do lote, o Python soma todas as linhas
de um cliente num acumulador so; depois passa a somar em ate 4 acumuladores
(um por tipo de estoque). A MESMA soma em ordem de operacoes diferente pode
divergir nos ultimos bits de um float -- arredondar pra 3 casas (precisao de
kg e de R$) evita falso positivo no diff por causa disso.
`registros_movimentacao` e contagem inteira e bate exato de qualquer forma.

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

_METRICAS_DATAHUB = (
    "peso_bruto_movimentado", "valor_mercadoria_movimentada", "registros_movimentacao",
)

_CONSULTA = """
SELECT mt.nome, m.competencia, a.sigla, ROUND(SUM(m.valor), 3), COUNT(*)
FROM medidas m
JOIN metricas mt ON mt.id = m.metrica_id
JOIN armazens a ON a.id = m.armazem_id
WHERE mt.nome IN ('peso_bruto_movimentado', 'valor_mercadoria_movimentada', 'registros_movimentacao')
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3
"""


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


def gerar_relatorio() -> str:
    linhas = _sql(_CONSULTA)
    cabecalho = f"{'metrica':<32} {'competencia':<12} {'filial':<8} {'total':>18} {'n_celulas':>10}"
    corpo = [cabecalho, "-" * len(cabecalho)]
    for metrica, competencia, filial, total, n_celulas in linhas:
        corpo.append(f"{metrica:<32} {competencia:<12} {filial:<8} {total:>18} {n_celulas:>10}")
    return "\n".join(corpo) + "\n"


def main() -> int:
    try:
        relatorio = gerar_relatorio()
    except ErroPsql as exc:
        print(f"FALHA ao consultar o banco: {exc}", file=sys.stderr)
        return 1

    print(relatorio)
    if len(sys.argv) > 1:
        destino = Path(sys.argv[1])
        destino.write_text(relatorio, encoding="utf-8")
        print(f"(gravado em {destino})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
