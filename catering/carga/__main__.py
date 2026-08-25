"""Linha de comando do carregador.

    python -m catering.carga --de docs/Analise                 # CSV (padrao)
    python -m catering.carga --fonte oracle --sondar           # SO le o DW
    python -m catering.carga --fonte oracle                    # carga completa
    python -m catering.carga --fonte oracle --incremental      # o que o cron roda
    python -m catering.carga --fonte oracle --movimento rec

Fino de proposito: so argumento, log e codigo de saida. Toda a decisao esta
nos modulos, para que a carga agendada possa chamar `carregar_tudo()` direto
sem passar por aqui.

Sai com codigo 1 quando a rodada falha -- agendador que nao ve falha nao serve
de agendador.

## `--fonte` tem padrao `csv`

Nao por gosto, e para que todo comando ja documentado no `V3_PLANO.md` e no
`EXECUCAO_LOCAL.md` continue valendo exatamente como esta escrito. `--de` e
`--fonte oracle` sao mutuamente exclusivos: um diretorio de CSV nao tem sentido
lendo do banco, e aceitar em silencio o argumento que nao se usa e como se
comeca a duvidar do que uma rodada realmente leu.

## `--sondar` nao escreve em lugar nenhum

Nem no DW, nem no Postgres -- entao ele nao precisa de `DATABASE_URL`, e serve
como primeira prova de acesso numa maquina onde o banco local ainda nao existe.
E o comando do aceite do V3.5.
"""

import argparse
import logging
import sys


def _sondagem(fonte, movimentos) -> int:
    """Imprime a evidencia de leitura do DW. Nada aqui toca no Postgres."""
    for movimento in movimentos:
        resumo = fonte.sondar(movimento)
        cal_de, cal_ate = resumo["nk_calendario"]
        alt_de, alt_ate = resumo["dw_data_alteracao"]
        print(f"\n{resumo['tabela']}  ({resumo['dsn']})")
        print(f"  contrato          : {resumo['colunas_no_contrato']} coluna(s), "
              "conferidas contra o que o cursor descreve -- sem divergencia")
        print(f"  linhas            : {resumo['linhas']:,}".replace(",", "."))
        print(f"  nk_calendario     : {cal_de} a {cal_ate}")
        print(f"  dw_data_alteracao : {alt_de} a {alt_ate}   <- o `desde` do incremental")
        ident = resumo.get("identidade") or {}
        if ident:
            total = ident["total"]
            print("  identidade -- a chave certa e a PRIMEIRA que fica unica:")
            for rotulo, valor in ident["candidatos"]:
                falta = total - valor
                veredito = "UNICA" if falta == 0 else f"repete em {falta} linha(s)"
                print(f"    {rotulo:<24} {valor} de {total}  -> {veredito}")
            discordam = ident["ano_solic_discorda_de_data_solic"]
            print(f"    ano_solic discorda do ano de data_solic em {discordam} linha(s)")
            for ano, solic_de, solic_ate, cal, quantas in resumo.get("ano_discordante") or ():
                print(f"      ano_solic={ano}: data_solic de {solic_de} a {solic_ate}, "
                      f"nk_calendario desde {cal}, {quantas} linha(s)")
        for gem, filial, quantas, de, ate in resumo.get("colisoes") or ():
            mesma_data = de == ate
            print(f"    colisao: gem {gem} / {filial} aparece {quantas}x, "
                  f"de {de} a {ate}"
                  f"{'  <- MESMO dia: linha repetida de verdade' if mesma_data else '  <- datas diferentes: falta data na identidade'}")
        if resumo["amostra"]:
            print("  primeira linha (tipo que o driver entrega -> valor que o banco recebe):")
            for coluna, (tipo, bruto, tipado) in resumo["amostra"].items():
                print(f"    {coluna:<22} {tipo:<9} {bruto}  ->  {tipado}")
    print("\nfim da sondagem -- nada foi escrito, nem no DW nem no Postgres")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m catering.carga",
        description="Carrega a volumetria de catering na base da V3.",
    )
    parser.add_argument(
        "--fonte", choices=("csv", "oracle"), default="csv",
        help="de onde ler (padrao: csv, que e como o carregador foi construido)",
    )
    parser.add_argument(
        "--de", metavar="DIR",
        help="diretorio com as duas extracoes do DW (ex.: docs/Analise). "
             "Obrigatorio com --fonte csv, proibido com --fonte oracle",
    )
    parser.add_argument(
        "--movimento", choices=("rec", "exp"), default=None,
        help="carrega so um movimento (padrao: os dois, mais as dimensoes)",
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="retoma da marca d'agua da ultima rodada ok de cada movimento",
    )
    parser.add_argument(
        "--sondar", action="store_true",
        help="so le o DW e mostra contrato, volume e marca d'agua; nao escreve "
             "em lugar nenhum (exige --fonte oracle)",
    )
    args = parser.parse_args(argv)

    if args.fonte == "csv":
        if not args.de:
            parser.error("--de e obrigatorio com --fonte csv")
        if args.sondar:
            parser.error("--sondar existe so para --fonte oracle")
    elif args.de:
        parser.error("--de nao se aplica a --fonte oracle (a fonte e o banco)")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Import depois do parse de proposito: `--help` e erro de argumento nao
    # precisam pagar o import do psycopg2, do oracledb nem do pacote de carga.
    from catering.carga import carregar_movimento, carregar_tudo, destino

    if args.fonte == "oracle":
        from catering.carga.fonte_oracle import FonteOracle

        fonte = FonteOracle()
    else:
        from catering.carga.fonte_csv import FonteCSV

        fonte = FonteCSV(args.de)

    try:
        if args.sondar:
            return _sondagem(fonte, (args.movimento,) if args.movimento else ("rec", "exp"))
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
