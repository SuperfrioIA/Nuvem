"""Linha de comando do carregador.

    python -m catering.carga --de docs/Analise
    python -m catering.carga --de docs/Analise --incremental
    python -m catering.carga --de docs/Analise --movimento rec

Fino de proposito: so argumento, log e codigo de saida. Toda a decisao esta
nos modulos, para que a carga agendada do V3.5 possa chamar `carregar_tudo()`
direto sem passar por aqui.

Sai com codigo 1 quando a rodada falha -- agendador que nao ve falha nao serve
de agendador.
"""

import argparse
import logging
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m catering.carga",
        description="Carrega a volumetria de catering na base da V3.",
    )
    parser.add_argument(
        "--de", required=True, metavar="DIR",
        help="diretorio com as duas extracoes do DW (ex.: docs/Analise)",
    )
    parser.add_argument(
        "--movimento", choices=("rec", "exp"), default=None,
        help="carrega so um movimento (padrao: os dois, mais as dimensoes)",
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="retoma da marca d'agua da ultima rodada ok de cada movimento",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Import depois do parse de proposito: `--help` e erro de argumento nao
    # precisam pagar o import do psycopg2 nem do pacote de carga inteiro.
    from catering.carga import carregar_movimento, carregar_tudo, destino
    from catering.carga.fonte_csv import FonteCSV

    fonte = FonteCSV(args.de)
    try:
        if args.movimento:
            desde = destino.marca_dagua(args.movimento) if args.incremental else None
            resultado = carregar_movimento(fonte, args.movimento, desde=desde)
            print(resultado.resumo())
        else:
            resultados = carregar_tudo(fonte, incremental=args.incremental)
            for movimento in ("rec", "exp"):
                print(resultados[movimento].resumo())
            dim = resultados["dimensoes"]
            print(
                f"dimensoes: {dim['unidades']} unidade(s), "
                f"{dim['tipos_estoque']} nome(s) de estoque, "
                f"{dim['clientes']} cliente(s)"
            )
    except Exception as erro:
        print(f"carga falhou: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
