"""Processamento incremental da familia SAIDA_MERCADORIAS (lote V2.3, decisao D4).

Roda DENTRO do container do app -- e o unico script de scripts/ que precisa
disso, porque so ele chama o motor de ingestao de verdade (psycopg2,
credenciais GRAPH_*, os modulos de backend/). `verificar_v2.py` e
`totais_competencia.py` continuam no host, fazendo so SELECT via `psql` do
container do banco.

Fora do request HTTP de proposito (decisao D4): 616 MB so na competencia
minima de 2026 (72 arquivos) travaria o worker unico do uvicorn se rodasse
dentro de uma chamada sincrona do painel. O botao fica pro V2.7 ("escala e
operacao") -- construir a interface antes desta ingestao ter rodado uma vez
na vida real seria desenhar sem saber quanto demora nem onde quebra.

Uso, na VM:

    docker compose exec nuvem-app python scripts/processar_saida.py
    docker compose exec nuvem-app python scripts/processar_saida.py --forcar

Incremental por desenho (mesma regra de "Processar arquivos" da entrada):
particao inalterada e pulada; so --forcar reprocessa tudo. Competencia
anterior a 2026 fica fora de escopo (decisao D3) -- listada, nunca
processada em silencio.

**Uma particao por transacao** (D4: "uma falha isolada nao derruba as
outras"): a decisao de QUAIS particoes processar (`listar_particoes_saida`)
roda numa conexao curta, so leitura; cada particao pendente entao abre a SUA
PROPRIA conexao/transacao pra baixar, agregar e gravar. Uma falha de banco
numa particao (rara, mas psycopg2.Error nao e capturado dentro do
processamento) so aborta a transacao DAQUELA particao -- as outras, ja
commitadas, ficam de pé.
"""

import sys
from pathlib import Path

# `python scripts/processar_saida.py` (ao contrario de `python -m ...`) so
# coloca a PASTA DO SCRIPT no sys.path, nao a raiz do projeto -- sem isto o
# `from backend...` abaixo falharia com ModuleNotFoundError, dependendo de
# como o comando for digitado no runbook.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import get_conn  # noqa: E402
from backend.services import inventario_datahub, processamento_datahub  # noqa: E402


def _sincronizar() -> bool:
    print("Sincronizando inventario do DataHub...")
    estado = inventario_datahub.sincronizar()
    if not estado.get("ok"):
        print(f"FALHA na sincronizacao: {estado.get('mensagem_erro')}", file=sys.stderr)
        return False
    with get_conn() as conn:
        with conn.cursor() as cur:
            inventario_datahub.salvar_persistido(cur, estado)
    print(f"  {estado['resumo']['total_arquivos']} arquivos na fonte")
    return True


def _relatar_particao(relatorio: dict) -> None:
    """`pendencia_depara` tem uma FORMA DIFERENTE do relatorio de sucesso
    (`processamento_datahub.processar_particao_saida`, ramo de origem sem
    de-para): nao tem `medidas_gravadas`/`clientes`/`sem_cliente`/`tipos`/
    `competencia`, porque nada foi lido nem gravado. Ler esses campos direto
    (como a versao anterior fazia) estourava KeyError e derrubava a rodada
    inteira no meio -- achado da revisao independente do V2.3. Pendencia e
    estado esperado (mesma familia de D2), nunca deve competir com erro real."""
    arquivos = ", ".join(relatorio["arquivos"])
    if relatorio["status"] == "pendencia_depara":
        print(
            f"    pendencia  {relatorio['unidade']}/{relatorio['filial']}: "
            f"{relatorio['detalhe']}  [{arquivos}]"
        )
        return
    print(
        f"    {relatorio['status']}  {relatorio['unidade']}/{relatorio['filial']} {relatorio['competencia']}: "
        f"{relatorio['medidas_gravadas']} medida(s), "
        f"{relatorio['clientes']} cliente(s), {relatorio['sem_cliente']} sem-cliente, "
        f"{relatorio['tipos']} tipo(s) de estoque  [{arquivos}]"
    )


def main() -> int:
    forcar = "--forcar" in sys.argv[1:]

    if not _sincronizar():
        return 1

    print(f"\nDeterminando particoes pendentes de SAIDA_MERCADORIAS{' (FORCAR)' if forcar else ''}...")
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                plano = processamento_datahub.listar_particoes_saida(cur, forcar=forcar)
    except processamento_datahub.ProcessamentoDatahubError as exc:
        print(f"\nFALHA: {exc}", file=sys.stderr)
        return 1

    total_particoes = len(plano["particoes_pendentes"])
    print(f"  {plano['total_familia']} arquivo(s) na familia (dentro do escopo 2026+)")
    print(
        f"  {len(plano['arquivos_fora_de_escopo'])} arquivo(s) fora de escopo "
        "(antes de 2026, decisao D3) -- nao processados"
    )
    print(f"  {plano['pulados']} arquivo(s) pulado(s) (particao inalterada)")
    print(f"  {total_particoes} particao(oes) a processar\n")

    processadas, pendencias, erros = [], [], []
    for indice, partes in enumerate(plano["particoes_pendentes"], start=1):
        nomes = ", ".join(p["nome"] for p in partes)
        print(f"  [{indice}/{total_particoes}] {nomes}")
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    relatorio = processamento_datahub.processar_particao_saida(
                        cur, [p["id"] for p in partes]
                    )
        except Exception as exc:  # noqa: BLE001 -- fronteira de isolamento por particao (D4)
            # psycopg2.Error, erro do leitor ou de configuracao -- qualquer um
            # cai aqui. A transacao DESTA particao ja foi revertida pelo
            # get_conn (rollback antes de devolver a conexao ao pool); as
            # particoes anteriores, ja commitadas, ficam de pe.
            print(f"    ERRO: {exc}", file=sys.stderr)
            erros.append({"arquivos": nomes, "erro": str(exc)})
            continue

        _relatar_particao(relatorio)
        # pendencia_depara e estado esperado (a origem ficou registrada, sem
        # armazem pra gravar) -- nao e sucesso nem erro; contar como "ok" no
        # resumo escondia a pendencia atras de um numero que parece bom.
        (pendencias if relatorio["status"] == "pendencia_depara" else processadas).append(relatorio)

    print(
        f"\nResumo: {len(processadas)} particao(oes) ok, "
        f"{len(pendencias)} pendencia(s) de de-para, {len(erros)} erro(s)."
    )
    if pendencias:
        print(f"\n  pendencia de de-para (origem sem armazem pra gravar), {len(pendencias)} particao(oes):")
        for p in pendencias:
            print(f"    {p['unidade']}/{p['filial']}: {', '.join(p['arquivos'])}")
    if plano["arquivos_fora_de_escopo"]:
        print(
            f"\n  fora de escopo (nao processados, decisao D3 -- so 2026), "
            f"{len(plano['arquivos_fora_de_escopo'])} arquivo(s):"
        )
        for nome in sorted(plano["arquivos_fora_de_escopo"])[:10]:
            print(f"    {nome}")
        restantes = len(plano["arquivos_fora_de_escopo"]) - 10
        if restantes > 0:
            print(f"    ... e mais {restantes}")

    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
