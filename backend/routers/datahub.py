from contextlib import contextmanager

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import exigir_login
from ..config import ConfiguracaoGraphIncompletaError, obter_configuracao_graph
from ..database import get_conn
from ..services import (
    compatibilidade_medidas,
    entrada_mercadorias,
    filiais_datahub,
    graph_datahub,
    inventario_datahub,
    kpis_poc,
    nuvem_datahub,
    processamento_datahub,
    resumo_poc,
    serie_datahub,
)

router = APIRouter(prefix="/datahub", dependencies=[Depends(exigir_login)])

# Um arquivo de 400 KB tem milhares de linhas -- devolver tudo em JSON so
# infla a resposta sem servir pro P4 (que le do proprio processo). A tela
# (Lote P4/P5.5) mostra so uma previa.
_MAX_LINHAS_RESPOSTA = 100


def _pasta_configurada() -> str | None:
    try:
        return obter_configuracao_graph().pasta
    except ConfiguracaoGraphIncompletaError:
        return None


def _serializar(estado: dict) -> dict:
    sincronizado_em = estado["sincronizado_em"]
    return {
        **estado,
        "sincronizado_em": sincronizado_em.isoformat() if sincronizado_em else None,
        "pasta_configurada": _pasta_configurada(),
    }


_SEM_DADO = "arquivo sem linhas de dado (so cabecalho)"


def _recusar_se_sem_dado(resultado: dict) -> None:
    """Endpoint que exibe UM arquivo recusa competencia sem movimento.

    O leitor deixou de levantar excecao nesse caso no V2.1.1 (competencia sem
    movimento e estado legitimo da fonte, e o processamento agora grava
    `sem_dado`). Mas a tela executiva mostra UM arquivo como se fosse a leitura
    da operacao: renderizar zero ali, sem declarar, e apresentar ausencia de
    medicao como medicao -- exatamente o que este projeto nao faz. Entao aqui a
    mensagem clara continua, identica a de antes.
    """
    if resultado.get("sem_dado"):
        raise HTTPException(status_code=400, detail=_SEM_DADO)


@router.get("/status")
def status():
    return _serializar(inventario_datahub.status())


@router.post("/sincronizar")
def sincronizar():
    estado = inventario_datahub.sincronizar()
    # V1.3: sincronizacao OK e persistida -- o startup reidrata o cache dela
    if estado.get("ok"):
        with get_conn() as conn:
            with conn.cursor() as cur:
                inventario_datahub.salvar_persistido(cur, estado)
    return _serializar(estado)


@contextmanager
def _erros_como_http():
    """Traduz os erros de leitura/download pra HTTPException -- reaproveitado
    por /ler e /kpis (Lote P3/P4), mesmo mapeamento nos dois."""
    try:
        yield
    except entrada_mercadorias.EntradaMercadoriasError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except graph_datahub.GraphArquivoGrandeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except graph_datahub.GraphError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/ler")
def ler(item_id: str = Body(..., embed=True)):
    """Le e valida um arquivo ENTRADA_MERCADORIAS ja sincronizado (Lote P3).

    def comum (nao async): o cliente Graph e sincrono (httpx.get/stream) --
    async def bloquearia o event loop do FastAPI durante o download, mesmo
    padrao ja adotado em /sincronizar.
    """
    with _erros_como_http():
        resultado = entrada_mercadorias.ler(item_id)
    _recusar_se_sem_dado(resultado)

    linhas = resultado.pop("linhas")
    resultado["linhas_amostra"] = linhas[:_MAX_LINHAS_RESPOSTA]
    return resultado


@router.get("/kpis")
def kpis():
    """KPIs auditaveis do arquivo ENTRADA_MERCADORIAS mais recente (Lote P4).

    Sem cache proprio -- cada chamada baixa e recalcula na hora (o botao
    "Atualizar" da tela e so uma nova chamada a este endpoint). O arquivo usado
    e sempre o mais recente sincronizado, sem escolha (ver
    entrada_mercadorias.item_mais_recente).
    """
    with _erros_como_http():
        item_id = entrada_mercadorias.item_mais_recente()
        resultado = entrada_mercadorias.ler(item_id)
    _recusar_se_sem_dado(resultado)

    linhas = resultado.pop("linhas")
    fonte = f"{resultado['arquivo']} (filial {resultado['filial']}, competência {resultado['competencia']})"
    # sigla de exibicao (V1.0) -- entra nos metadados antes do resumo pra o
    # texto executivo poder nomear a filial (ex.: "016 (RMSPIV)"). Resolvida
    # pela origem qualificada (unidade + codigo): o codigo sozinho nao
    # identifica armazem desde a reestruturacao da fonte.
    resultado["filial_sigla"] = filiais_datahub.sigla(
        resultado["unidade"], resultado["filial"]
    )
    # catalogo de unidades (V1.2) -- alimenta o motor de compatibilidade que
    # separa os volumes por embalagem em vez de consolidar unidades mistas
    with get_conn() as conn:
        with conn.cursor() as cur:
            tabela_unidades = compatibilidade_medidas.carregar_tabela(cur)
    calculado = kpis_poc.calcular(linhas, fonte, tabela_unidades)
    resumo = resumo_poc.gerar(resultado, calculado["kpis"], calculado["por_cliente"])

    return {
        "arquivo": resultado["arquivo"],
        "caminho": resultado["caminho"],
        "unidade": resultado["unidade"],
        "filial": resultado["filial"],
        "filial_sigla": resultado["filial_sigla"],
        "competencia": resultado["competencia"],
        "modificado_em": resultado["modificado_em"],
        "qualidade_pct": resultado["qualidade_pct"],
        "linhas_lidas": resultado["linhas_lidas"],
        "linhas_validas": resultado["linhas_validas"],
        "linhas_descartadas": resultado["linhas_descartadas"],
        "kpis": calculado["kpis"],
        "volumes": calculado["volumes"],
        "por_cliente": calculado["por_cliente"],
        "resumo": resumo,
        # previa pra Nuvem do DataHub (Lote P5.5) -- reaproveita a leitura que
        # este endpoint ja faz, sem baixar o arquivo de novo.
        "linhas_amostra": linhas[:_MAX_LINHAS_RESPOSTA],
    }


@router.post("/processar")
def processar(forcar: bool = Body(False, embed=True)):
    """Processa a familia ENTRADA_MERCADORIAS inteira pro banco (V1.3): arquivo
    novo/alterado e processado, inalterado e pulado (forcar=true reprocessa
    tudo). Erro em um arquivo nao derruba o lote -- vem no relatorio."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return processamento_datahub.processar_todos(cur, forcar=forcar)
    except processamento_datahub.ProcessamentoDatahubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/processamentos")
def processamentos():
    """Estado corrente por arquivo + pendencias de de-para (filial, cliente e
    tipo de estoque) do conector do DataHub, pro painel do admin."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            return {
                "processamentos": processamento_datahub.listar_processamentos(cur),
                "pendencias_filial": processamento_datahub.listar_pendencias_filial(cur),
                "pendencias_cliente": processamento_datahub.listar_pendencias_cliente(cur),
                "pendencias_tipo_estoque": processamento_datahub.listar_pendencias_tipo_estoque(cur),
            }


@router.get("/serie")
def serie(
    metrica: str,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
    tipo_estoque: str | None = None,
):
    """Serie historica persistida (V1.3): mensal + consolidacao anual +
    acumulado, do que esta em `medidas` -- nunca recalcula do arquivo.
    tipo_estoque (V2.2) e filtro de dimensao, igual filial/cliente -- ranking e
    distribuicao por tipo continuam fora desta consulta (V2.4)."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return serie_datahub.serie(
                    cur, metrica, de=de, ate=ate, filial=filial, cliente=cliente,
                    tipo_estoque=tipo_estoque,
                )
    except serie_datahub.SerieDatahubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/nuvem")
def nuvem():
    """Bolinhas por familia do DataHub, agrupadas por area (Lote P5.5).

    Usa so o inventario ja em cache (P2) -- nenhuma chamada nova ao Graph.
    """
    resumo = inventario_datahub.status().get("resumo")
    if not resumo:
        raise HTTPException(
            status_code=400,
            detail="nenhuma sincronizacao do DataHub ainda -- clique em 'Sincronizar agora' primeiro",
        )
    return {"bolinhas": nuvem_datahub.montar_bolinhas(resumo)}
