"""Processamento persistente da familia ENTRADA_MERCADORIAS (Bloco C / V1.3).

Transforma a leitura ao vivo do P3 em serie historica: cada arquivo da familia
vira uma execucao que grava `medidas_recebidas` (append-only, com unidade
canonica e arquivo de origem -- linhagem preservada) e publica as celulas
canonicas em `medidas`, no grao competencia x filial x cliente.

Regras que sustentam a prevencao de dupla contagem:

- Uma metrica do DataHub existe num grao SO: cliente (cliente_id NULL =
  "sem cliente identificado no cadastro", nunca "total da filial"). O total da
  filial e SEMPRE a soma das linhas -- nunca ha duas granularidades da mesma
  metrica no banco.
- Idempotencia: o mesmo arquivo processado 2x upserta as MESMAS celulas
  (constraint medidas_celula_unica); reprocessar um arquivo alterado cria
  execucao nova (auditoria acumula) e atualiza as celulas.
- Celula orfa: se um reprocessamento deixa de emitir uma celula que existia
  (ex.: cliente foi cadastrado e as linhas dele sairam do balde NULL), a
  celula antiga e REMOVIDA -- as celulas de (metrica, filial, competencia)
  espelham exatamente o ultimo processamento do arquivo, que e o unico dono
  daquele recorte (um arquivo por filial x competencia, garantido pelo padrao
  de nome).

Cliente e resolvido pela raiz do CNPJ (8 digitos) contra clientes.nk_erp
(NK_CLIENTE do DW). SEM auto-cadastro (decisao da Maria, 31/jul/2026):
cliente fora do cadastro vira pendencia (`cliente_pendencias`) e as linhas
dele somam no balde NULL ate o cadastro acontecer -- ai um reprocessamento
move os valores pra linha do cliente.

A unidade gravada nas recebidas vem do CONCEITO canonico homonimo
(conceitos_canonicos, V1.1) -- e a forma de enforcement na ingestao: metrica
sem conceito aprovado com unidade definida nao processa (erro de configuracao,
nunca palpite).
"""

import re
from datetime import date

from .. import ingestao
from ..seed_datahub import TIPO_CONECTOR
from . import entrada_mercadorias, graph_datahub, inventario_datahub

_FONTE_CHAVE = "datahub_entrada_mercadorias"

# metrica persistida -> coluna somada (None = contagem de linhas). Os nomes
# sao os conceitos canonicos do V1.1; clientes_atendidos NAO entra (contagem
# distinta nao e somavel -- derivada na consulta, serie_datahub) e volumes por
# embalagem ficam fora da serie (decisao da Maria, 31/jul/2026).
_METRICAS = (
    ("peso_bruto_movimentado", "Peso Bruto"),
    ("valor_mercadoria_movimentada", "Vlr. Total"),
    ("registros_movimentacao", None),
)


class ProcessamentoDatahubError(Exception):
    """Erro de configuracao/estado do processamento -- mensagem clara pro
    chamador (endpoint traduz pra HTTP 400)."""


def raiz_cnpj(valor) -> str | None:
    """Raiz do CNPJ (8 digitos) a partir da coluna 'Cliente CNPJ'.

    Celula numerica do Excel perde zeros a esquerda -- por isso 9..14 digitos
    sao completados a esquerda ate 14 antes de cortar a raiz. 8 digitos ja e
    uma raiz; menos que 8 (ou mais que 14) nao da pra identificar com
    seguranca -> None (balde "sem cliente identificado"), nunca chute.
    """
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    digitos = re.sub(r"\D", "", str(valor))
    if len(digitos) == 8:
        return digitos
    if 9 <= len(digitos) <= 14:
        return digitos.zfill(14)[:8]
    return None


def _competencia_date(competencia: str) -> date:
    ano, mes = competencia.split("-")
    return date(int(ano), int(mes), 1)


def _conector_id(cur) -> int:
    cur.execute("SELECT id FROM conectores WHERE tipo = %s", (TIPO_CONECTOR,))
    row = cur.fetchone()
    if row is None:
        raise ProcessamentoDatahubError(
            "conector sharepoint_datahub nao cadastrado -- rodar os seeds (init_db)"
        )
    return row[0]


def _fonte_id(cur):
    cur.execute("SELECT id FROM catalogo_fontes WHERE chave = %s", (_FONTE_CHAVE,))
    row = cur.fetchone()
    return row[0] if row else None


def _metrica_ids(cur) -> dict[str, int]:
    """ids das metricas governadas, resolvidos ANTES de qualquer escrita --
    metrica fora do catalogo e erro de configuracao com mensagem clara (400),
    nunca um 500 no meio do lote."""
    ids = {}
    for nome, _ in _METRICAS:
        try:
            ids[nome] = ingestao.resolver_metrica_governada(cur, nome)
        except ValueError as exc:
            raise ProcessamentoDatahubError(str(exc)) from exc
    return ids


def _unidades_dos_conceitos(cur) -> dict[str, str]:
    """unidade canonica por metrica, vinda do conceito canonico homonimo --
    enforcement da ingestao: sem conceito aprovado com unidade, nao processa."""
    nomes = [nome for nome, _ in _METRICAS]
    cur.execute(
        """
        SELECT chave, unidade_canonica FROM conceitos_canonicos
        WHERE chave = ANY(%s) AND status = 'aprovado'
        """,
        (nomes,),
    )
    unidades = {chave: unidade for chave, unidade in cur.fetchall()}
    faltando = sorted(n for n in nomes if not unidades.get(n))
    if faltando:
        raise ProcessamentoDatahubError(
            "conceito canonico aprovado com unidade definida nao encontrado para: "
            + ", ".join(faltando)
        )
    return unidades


def _agregar_por_cliente(cur, conector_id: int, linhas: list[dict]) -> dict:
    """{cliente_id (int|None): {metrica: valor}} -- resolucao de cliente pela
    raiz do CNPJ, com pendencia registrada uma vez por raiz desconhecida."""
    resolvidos: dict[str, int | None] = {}
    agregados: dict[int | None, dict[str, float]] = {}
    for linha in linhas:
        raiz = raiz_cnpj(linha.get("Cliente CNPJ"))
        if raiz is None:
            cliente_id = None
        elif raiz in resolvidos:
            cliente_id = resolvidos[raiz]
        else:
            cliente_id = ingestao.resolver_cliente(cur, raiz)
            if cliente_id is None:
                nome = str(linha.get("Cliente") or "").strip() or None
                ingestao.registrar_cliente_pendencia(cur, conector_id, raiz, nome)
            resolvidos[raiz] = cliente_id

        acc = agregados.setdefault(
            cliente_id, {nome: 0.0 for nome, _ in _METRICAS}
        )
        for nome, coluna in _METRICAS:
            acc[nome] += 1 if coluna is None else linha[coluna]
    return agregados


def _remover_celulas_orfas(
    cur, metrica_ids: list[int], armazem_id: int, competencia: date, manter: set
) -> int:
    """Apaga celulas canonicas das metricas do DataHub que o processamento
    atual nao emitiu (ver docstring do modulo). Compara cliente_id em Python
    porque NULL nao entra em `= ANY(...)`."""
    cur.execute(
        """
        SELECT id, cliente_id FROM medidas
        WHERE metrica_id = ANY(%s) AND armazem_id = %s AND competencia = %s
        """,
        (metrica_ids, armazem_id, competencia),
    )
    orfas = [mid for mid, cliente_id in cur.fetchall() if cliente_id not in manter]
    if orfas:
        cur.execute("DELETE FROM medida_linhagem WHERE medida_id = ANY(%s)", (orfas,))
        cur.execute("DELETE FROM medidas WHERE id = ANY(%s)", (orfas,))
    return len(orfas)


def _registrar_processamento(cur, resultado: dict, item_id: str, status: str,
                             detalhe=None, execucao_id=None, medidas_gravadas=None) -> None:
    cur.execute(
        """
        INSERT INTO processamentos_datahub
            (arquivo, item_id, filial, competencia, modificado_em, execucao_id,
             status, detalhe, linhas_validas, medidas_gravadas)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (arquivo) DO UPDATE SET
            item_id = EXCLUDED.item_id,
            modificado_em = EXCLUDED.modificado_em,
            execucao_id = EXCLUDED.execucao_id,
            status = EXCLUDED.status,
            detalhe = EXCLUDED.detalhe,
            linhas_validas = EXCLUDED.linhas_validas,
            medidas_gravadas = EXCLUDED.medidas_gravadas,
            processado_em = now()
        """,
        (resultado["arquivo"], item_id, resultado["filial"],
         _competencia_date(resultado["competencia"]), resultado.get("modificado_em"),
         execucao_id, status, detalhe, resultado.get("linhas_validas"), medidas_gravadas),
    )


def processar_arquivo(cur, item_id: str) -> dict:
    """Processa UM arquivo ja sincronizado: le (validacao do P3 intacta),
    agrega por cliente e persiste. Devolve o relatorio do arquivo."""
    unidades = _unidades_dos_conceitos(cur)
    metrica_ids = _metrica_ids(cur)
    conector_id = _conector_id(cur)
    fonte_id = _fonte_id(cur)

    resultado = entrada_mercadorias.ler(item_id)
    linhas = resultado.pop("linhas")
    filial = resultado["filial"]
    competencia = _competencia_date(resultado["competencia"])

    armazem_id = ingestao.resolver_armazem(cur, conector_id, filial)
    if armazem_id is None:
        ingestao.registrar_pendencia(cur, conector_id, filial)
        detalhe = f"filial {filial} sem de-para no conector sharepoint_datahub"
        _registrar_processamento(cur, resultado, item_id, "pendencia_depara", detalhe)
        return {"arquivo": resultado["arquivo"], "status": "pendencia_depara", "detalhe": detalhe}

    agregados = _agregar_por_cliente(cur, conector_id, linhas)

    execucao_id = ingestao.iniciar_execucao(
        cur, conector_id, None, None, "datahub", resultado.get("caminho")
    )

    gravadas = 0
    for nome, _ in _METRICAS:
        metrica_id = metrica_ids[nome]
        for cliente_id, valores in agregados.items():
            recebida_id = ingestao.registrar_recebida_datahub(
                cur, execucao_id, fonte_id, armazem_id, cliente_id,
                metrica_id, competencia, valores[nome],
                unidades[nome], resultado["arquivo"],
            )
            ingestao.upsert_medida(
                cur, metrica_id, armazem_id, competencia, valores[nome],
                conector_id, recebida_id, cliente_id,
            )
            gravadas += 1

    removidas = _remover_celulas_orfas(
        cur, list(metrica_ids.values()), armazem_id, competencia, set(agregados)
    )

    ingestao.finalizar_execucao(
        cur, execucao_id, "ok",
        linhas_lidas=resultado["linhas_lidas"], linhas_gravadas=gravadas,
    )
    _registrar_processamento(
        cur, resultado, item_id, "ok",
        execucao_id=execucao_id, medidas_gravadas=gravadas,
    )
    return {
        "arquivo": resultado["arquivo"],
        "status": "ok",
        "filial": filial,
        "competencia": resultado["competencia"],
        "clientes": sum(1 for c in agregados if c is not None),
        "sem_cliente": 1 if None in agregados else 0,
        "medidas_gravadas": gravadas,
        "celulas_removidas": removidas,
    }


def _ja_processado(cur, arquivo: str, modificado_em) -> bool:
    cur.execute(
        "SELECT modificado_em, status FROM processamentos_datahub WHERE arquivo = %s",
        (arquivo,),
    )
    row = cur.fetchone()
    return row is not None and row[1] == "ok" and row[0] == modificado_em


def processar_todos(cur, forcar: bool = False) -> dict:
    """Processa a familia inteira do inventario atual: arquivo novo ou alterado
    (modificado_em diferente) e processado; inalterado e pulado (a menos de
    forcar=True). Erro num arquivo nao derruba o lote -- vira status 'erro' no
    relatorio e no controle."""
    resumo = inventario_datahub.status().get("resumo")
    if not resumo:
        raise ProcessamentoDatahubError(
            "nenhuma sincronizacao do DataHub ainda -- clique em 'Sincronizar agora' primeiro"
        )

    candidatos = [
        a for a in resumo.get("arquivos", [])
        if entrada_mercadorias.dados_da_familia(a.get("nome", "")) is not None
    ]

    processados, pulados, erros = [], 0, []
    for arquivo in candidatos:
        if not forcar and _ja_processado(cur, arquivo["nome"], arquivo.get("modificado_em")):
            pulados += 1
            continue
        try:
            processados.append(processar_arquivo(cur, arquivo["id"]))
        except (
            entrada_mercadorias.EntradaMercadoriasError,
            graph_datahub.GraphError,
            ProcessamentoDatahubError,
        ) as exc:
            # nome ja casou com o padrao da familia (filtro dos candidatos)
            filial, competencia = entrada_mercadorias.dados_da_familia(arquivo["nome"])
            erros.append({"arquivo": arquivo["nome"], "erro": str(exc)})
            _registrar_processamento(
                cur,
                {
                    "arquivo": arquivo["nome"], "filial": filial,
                    "competencia": competencia,
                    "modificado_em": arquivo.get("modificado_em"),
                },
                arquivo["id"], "erro", detalhe=str(exc),
            )

    return {
        "total_familia": len(candidatos),
        "processados": processados,
        "pulados": pulados,
        "erros": erros,
    }


def listar_processamentos(cur) -> list[dict]:
    """Estado corrente por arquivo, pro painel do admin."""
    cur.execute(
        """
        SELECT arquivo, filial, competencia, status, detalhe, linhas_validas,
               medidas_gravadas, processado_em
        FROM processamentos_datahub
        ORDER BY competencia DESC, filial, arquivo
        """
    )
    return [
        {
            "arquivo": r[0],
            "filial": r[1],
            "competencia": r[2].isoformat() if r[2] else None,
            "status": r[3],
            "detalhe": r[4],
            "linhas_validas": r[5],
            "medidas_gravadas": r[6],
            "processado_em": r[7].isoformat() if r[7] else None,
        }
        for r in cur.fetchall()
    ]


def listar_pendencias_filial(cur) -> list[dict]:
    """Pendencias de de-para de filial do conector do DataHub (ex.: a 002),
    pro painel do admin -- mesma tabela usada pelo upload manual."""
    cur.execute(
        """
        SELECT dp.armazem_na_fonte, dp.primeira_vez_em, dp.ultima_vez_em
        FROM depara_pendencias dp
        JOIN conectores c ON c.id = dp.conector_id
        WHERE c.tipo = %s
        ORDER BY dp.ultima_vez_em DESC
        """,
        (TIPO_CONECTOR,),
    )
    return [
        {
            "filial_na_fonte": r[0],
            "primeira_vez_em": r[1].isoformat() if r[1] else None,
            "ultima_vez_em": r[2].isoformat() if r[2] else None,
        }
        for r in cur.fetchall()
    ]


def listar_pendencias_cliente(cur) -> list[dict]:
    cur.execute(
        """
        SELECT cp.cliente_na_fonte, cp.nome_na_fonte, cp.primeira_vez_em, cp.ultima_vez_em
        FROM cliente_pendencias cp
        JOIN conectores c ON c.id = cp.conector_id
        WHERE c.tipo = %s
        ORDER BY cp.ultima_vez_em DESC
        """,
        (TIPO_CONECTOR,),
    )
    return [
        {
            "cliente_na_fonte": r[0],
            "nome_na_fonte": r[1],
            "primeira_vez_em": r[2].isoformat() if r[2] else None,
            "ultima_vez_em": r[3].isoformat() if r[3] else None,
        }
        for r in cur.fetchall()
    ]
