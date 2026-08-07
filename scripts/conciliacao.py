"""Lado NUVEM da conciliacao com o Power BI (lote V2.6), somente leitura.

Produz as tabelas que `docs/CONCILIACAO_POWERBI_V2.md` pede, no recorte que o
Power BI usa, prontas para colar ao lado dos numeros do BI:

    1. total por competencia (entrada, saida, total, saldo)
    2. total por unidade fisica E o agregado que o BI chama de "RMSPII"
    3. ranking por cliente, agrupado pela RAIZ DO CNPJ

O agregado "RMSPII" e o achado central da primeira passada
(memory/conciliacao-rmspii-primeira-passada.md): **no Power BI, "Unidade:
RMSPII" soma 001+015+016** -- RMSPII+RMSPIII+RMSPIV na Nuvem. Comparar a RMSPII
da Nuvem com a RMSPII do BI da 2,68x de diferenca e manda todo mundo procurar
um defeito que nao existe. Por isso este script imprime as duas leituras, e a
agregada vem rotulada com as tres siglas no nome.

Agrupar cliente pela RAIZ DO CNPJ, nunca pelo nome: a fonte tem a mesma raiz com
grafias diferentes entre arquivos (GR SERVICOS/SERVICOS E ALIMENTACAO/ALIMENTOS,
NOVITA, PIMENTA VERDE, CONVIDA, LC ADMINISTRACAO). Somar por nome cru
fragmentaria um cliente em tres linhas e cada uma pareceria menor que o BI.

Uso (na VM, com o stack de pe):

    python3 scripts/conciliacao.py --de 2026-01 --ate 2026-07
    python3 scripts/conciliacao.py --de 2026-01 --ate 2026-07 --unidade RMSPII_AGREGADA

Peso em TONELADAS (a unidade em que o Power BI publica), 0 casas na tabela de
cliente e 1 nas de competencia -- o kg cru esta no banco e a linhagem continua
sendo a fonte pra auditar celula por celula.

So stdlib (subprocess + psql do container), mesmo padrao do verificar_v2.py e do
totais_competencia.py: o Python do host que roda o docker compose nao tem
psycopg2. **Nao grava nada** -- todas as consultas sao SELECT.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SERVICO_DB = os.environ.get("SERVICO_DB", "nuvem-db")
USUARIO_DB = os.environ.get("POSTGRES_USER", "nuvem")
NOME_DB = os.environ.get("POSTGRES_DB", "nuvem")

# O que o Power BI chama de "RMSPII" (achado de 06/ago/2026, conferido batendo o
# total). Lista explicita e nomeada, nao derivada: se o BI mudar o agrupamento,
# a correcao e aqui, num lugar so, com o motivo escrito ao lado.
RMSPII_DO_POWER_BI = ("RMSPII", "RMSPIII", "RMSPIV")

METRICAS = {
    "entrada": "peso_bruto_entrada",
    "saida": "peso_bruto_saida",
}


class ErroPsql(RuntimeError):
    pass


def _sql(consulta: str) -> list[list[str]]:
    comando = [
        "docker", "compose", "exec", "-T", SERVICO_DB,
        "psql", "-U", USUARIO_DB, "-d", NOME_DB,
        "-v", "ON_ERROR_STOP=1", "-A", "-t", "-F", "|", "-c", consulta,
    ]
    try:
        resultado = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, timeout=120)
    except FileNotFoundError as exc:
        raise ErroPsql("docker nao encontrado no PATH deste host") from exc
    except subprocess.TimeoutExpired as exc:
        raise ErroPsql("psql nao respondeu em 120s") from exc
    if resultado.returncode != 0:
        raise ErroPsql((resultado.stderr or resultado.stdout).strip()[:400])
    return [linha.split("|") for linha in resultado.stdout.strip().splitlines() if linha.strip()]


def _literal(valor: str) -> str:
    """Aspas simples duplicadas -- os valores aqui vem de --de/--ate/--unidade,
    que sao validados antes, mas escapar e barato e a consulta e montada por
    concatenacao (o psql -c nao aceita parametro ligado)."""
    return "'" + str(valor).replace("'", "''") + "'"


def _periodo_sql(coluna: str, de: str | None, ate: str | None) -> str:
    partes = []
    if de:
        partes.append(f"{coluna} >= {_literal(de + '-01')}::date")
    if ate:
        partes.append(f"{coluna} <= {_literal(ate + '-01')}::date")
    return (" AND " + " AND ".join(partes)) if partes else ""


def _validar_competencia(valor: str | None, campo: str) -> str | None:
    if valor is None:
        return None
    partes = valor.split("-")
    if len(partes) != 2 or len(partes[0]) != 4 or not partes[0].isdigit() or not partes[1].isdigit():
        sys.exit(f"{campo} invalida (esperado AAAA-MM): {valor!r}")
    if not 1 <= int(partes[1]) <= 12:
        sys.exit(f"{campo} invalida (mes fora de 1..12): {valor!r}")
    return valor


def _filtro_unidade(unidade: str | None) -> tuple[str, str]:
    """(SQL, rotulo). `RMSPII_AGREGADA` e a leitura do Power BI."""
    if not unidade:
        return "", "todas as unidades"
    if unidade == "RMSPII_AGREGADA":
        siglas = ", ".join(_literal(s) for s in RMSPII_DO_POWER_BI)
        return (
            f" AND a.sigla IN ({siglas})",
            f"\"RMSPII\" do Power BI = {' + '.join(RMSPII_DO_POWER_BI)}",
        )
    return f" AND a.sigla = {_literal(unidade)}", f"unidade {unidade}"


def _toneladas(kg: str) -> float:
    return float(kg) / 1000.0


def _cabecalho(titulo: str) -> None:
    print()
    print(titulo)
    print("-" * len(titulo))


def por_competencia(de, ate, filtro_unidade) -> None:
    _cabecalho("1. Peso por competencia (toneladas)")
    print("competencia | entrada | saida | total | saldo")
    linhas = _sql(
        f"""
        SELECT to_char(m.competencia, 'YYYY-MM'),
               COALESCE(SUM(m.valor) FILTER (WHERE mt.nome = {_literal(METRICAS['entrada'])}), 0),
               COALESCE(SUM(m.valor) FILTER (WHERE mt.nome = {_literal(METRICAS['saida'])}), 0)
        FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        JOIN armazens a ON a.id = m.armazem_id
        WHERE mt.nome IN ({_literal(METRICAS['entrada'])}, {_literal(METRICAS['saida'])})
          {filtro_unidade}{_periodo_sql('m.competencia', de, ate)}
        GROUP BY 1 ORDER BY 1
        """
    )
    total_e = total_s = 0.0
    for competencia, entrada_kg, saida_kg in linhas:
        entrada, saida = _toneladas(entrada_kg), _toneladas(saida_kg)
        total_e += entrada
        total_s += saida
        print(f"{competencia} | {entrada:>12,.1f} | {saida:>12,.1f} | "
              f"{entrada + saida:>12,.1f} | {entrada - saida:>12,.1f}")
    print(f"TOTAL      | {total_e:>12,.1f} | {total_s:>12,.1f} | "
          f"{total_e + total_s:>12,.1f} | {total_e - total_s:>12,.1f}")
    print("\nComparar com o Power BI: o acumulado do grafico mensal de Recebimento.")


def por_unidade(de, ate, tem_filtro_unidade) -> None:
    """Decomposicao por unidade. O `--unidade` NAO se aplica aqui de proposito
    (esta tabela existe pra mostrar a decomposicao inteira), e por isso ela
    DECLARA isso quando o filtro foi passado -- achado da revisao independente:
    o cabecalho do relatorio anuncia "unidade RMSPIV" e esta secao listava todas,
    entao quem colasse ao lado de um print do BI filtrado compararia coisas
    diferentes."""
    _cabecalho("2. Peso de entrada por unidade fisica (toneladas)")
    if tem_filtro_unidade:
        print("(o filtro --unidade NAO se aplica a esta tabela: ela e a decomposicao")
        print(" por unidade, e existe justamente pra mostrar o agregado do Power BI)")
    linhas = _sql(
        f"""
        SELECT a.sigla, COALESCE(SUM(m.valor), 0)
        FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        JOIN armazens a ON a.id = m.armazem_id
        WHERE mt.nome = {_literal(METRICAS['entrada'])}{_periodo_sql('m.competencia', de, ate)}
        GROUP BY 1 ORDER BY 2 DESC
        """
    )
    agregado = 0.0
    for sigla, kg in linhas:
        toneladas = _toneladas(kg)
        marca = " (entra no 'RMSPII' do BI)" if sigla in RMSPII_DO_POWER_BI else ""
        if sigla in RMSPII_DO_POWER_BI:
            agregado += toneladas
        print(f"{sigla:<10} | {toneladas:>12,.1f}{marca}")
    print(f"\n{'+'.join(RMSPII_DO_POWER_BI)} = {agregado:,.1f} t  <-- e ISTO que o "
          f"filtro 'Unidade: RMSPII' do Power BI mostra")


def por_cliente(de, ate, filtro_unidade, rotulo_unidade) -> None:
    _cabecalho(f"3. Peso de entrada por cliente, raiz do CNPJ ({rotulo_unidade}, toneladas)")
    linhas = _sql(
        f"""
        SELECT COALESCE(c.nk_erp, 'SEM_CNPJ'),
               COALESCE(c.nome, 'Sem cliente identificado'),
               COALESCE(SUM(m.valor), 0)
        FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        JOIN armazens a ON a.id = m.armazem_id
        LEFT JOIN clientes c ON c.id = m.cliente_id
        WHERE mt.nome = {_literal(METRICAS['entrada'])}
          {filtro_unidade}{_periodo_sql('m.competencia', de, ate)}
        GROUP BY c.id, c.nk_erp, c.nome ORDER BY 3 DESC
        """
    )
    total = 0.0
    print("raiz CNPJ  | cliente                                   | toneladas")
    for nk_erp, nome, kg in linhas:
        toneladas = _toneladas(kg)
        total += toneladas
        # reticencia no truncamento (mesmo defeito que a validacao em navegador
        # corrigiu no eixo do grafico: nome cortado e OUTRO nome) e 1 casa
        # decimal (com 0 casas, cliente abaixo de 500 kg saia como "0")
        rotulo = nome if len(nome) <= 41 else nome[:40] + "…"
        print(f"{nk_erp:<10} | {rotulo:<41} | {toneladas:>11,.1f}")
    print(f"{'TOTAL':<10} | {'':<41} | {total:>11,.1f}")
    print(
        "\nAtencao ao comparar com o Power BI:\n"
        "  - WYDA (Power BI) e CUCINARE PRO ALIMENTACAO (Nuvem) sao o MESMO cliente\n"
        "    (nome comercial x razao social, confirmado pela Maria em 06/ago/2026);\n"
        "  - a linha 'Sem cliente identificado' nao tem correspondente no BI: la o\n"
        "    valor esta dentro do cliente, aqui esta separado por falta de cadastro\n"
        "    (ou por a unidade nao ter coluna de cliente na fonte -- RMRJ)."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Lado Nuvem da conciliacao com o Power BI (V2.6)")
    parser.add_argument("--de", help="competencia inicial (AAAA-MM)")
    parser.add_argument("--ate", help="competencia final (AAAA-MM)")
    parser.add_argument(
        "--unidade",
        help="sigla (RMSPIV), ou RMSPII_AGREGADA para a leitura do Power BI "
             f"({'+'.join(RMSPII_DO_POWER_BI)})",
    )
    args = parser.parse_args()

    de = _validar_competencia(args.de, "--de")
    ate = _validar_competencia(args.ate, "--ate")
    if de and ate and de > ate:
        sys.exit(f"intervalo invalido: --de ({de}) maior que --ate ({ate})")

    filtro_unidade, rotulo_unidade = _filtro_unidade(args.unidade)

    print("Conciliacao Nuvem x Power BI -- lado NUVEM (somente leitura)")
    print(f"Recorte: {de or 'inicio'} a {ate or 'fim'} | {rotulo_unidade}")

    try:
        por_competencia(de, ate, filtro_unidade)
        por_unidade(de, ate, bool(args.unidade))
        por_cliente(de, ate, filtro_unidade, rotulo_unidade)
    except ErroPsql as exc:
        print(f"\nFALHA ao consultar o banco: {exc}", file=sys.stderr)
        return 1

    print(
        "\nO numero da Nuvem NAO precisa bater com o do BI -- precisa ser "
        "RASTREAVEL.\nDiferenca sem explicacao vira pendencia registrada em "
        "docs/CONCILIACAO_POWERBI_V2.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
