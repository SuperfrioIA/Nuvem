"""Processamento persistente da familia ENTRADA_MERCADORIAS (Bloco C / V1.3).

Transforma a leitura ao vivo do P3 em serie historica: cada arquivo da familia
vira uma execucao que grava `medidas_recebidas` (append-only, com unidade
canonica e arquivo de origem -- linhagem preservada) e publica as celulas
canonicas em `medidas`, no grao competencia x filial x cliente.

Regras que sustentam a prevencao de dupla contagem:

- Uma metrica do DataHub existe num grao SO: cliente x tipo de estoque
  (cliente_id NULL = "sem cliente identificado no cadastro", tipo_estoque NULL
  so em celula anterior ao V2.2; nunca "total da filial"). O total da filial e
  SEMPRE a soma das linhas -- nunca ha duas granularidades da mesma metrica no
  banco.
- Idempotencia: o mesmo arquivo processado 2x upserta as MESMAS celulas
  (constraint medidas_celula_unica); reprocessar um arquivo alterado cria
  execucao nova (auditoria acumula) e atualiza as celulas.
- Celula orfa: se um reprocessamento deixa de emitir uma celula que existia
  (ex.: cliente foi cadastrado e as linhas dele sairam do balde NULL), a
  celula antiga e REMOVIDA -- as celulas de (metrica, armazem, competencia)
  espelham exatamente o ultimo processamento do arquivo, que e o unico dono
  daquele recorte.

A identidade do arquivo e o `item_id` do Graph, nunca o nome (migration 0008).
A fonte tem quatro unidades desde 31/jul/2026 e as quatro publicam com a mesma
convencao: `ENTRADA_MERCADORIAS_001_2601.xlsx` existe em RMSPII e em CWB3, em
armazens diferentes. Tres consequencias sustentadas aqui:

- o de-para e consultado pelo codigo de origem QUALIFICADO pela unidade
  (`RMSPII/001`), nunca pelo codigo de filial nu;
- o de-para e resolvido ANTES do download: origem sem de-para vira pendencia
  visivel sem baixar nada (a RJ, por exemplo, tem layout proprio de 18 colunas
  -- baixar so pra falhar na leitura trocaria uma pendencia clara por um erro);
- "um arquivo por armazem x competencia" deixou de ser premissa e virou
  invariante VERIFICADA: `processar_todos` aborta a rodada inteira se dois
  arquivos apontarem para o mesmo recorte, antes e depois de gravar. Sem isso,
  um apagaria as celulas do outro como orfas e a linhagem em
  `medidas_recebidas` (append-only) ficaria com o armazem errado pra sempre.

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
from . import (
    entrada_mercadorias,
    filiais_datahub,
    graph_datahub,
    inventario_datahub,
    tipo_estoque as tipo_estoque_servico,
)

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


def _agregar_por_cliente_e_tipo(cur, conector_id: int, linhas: list[dict]) -> dict:
    """{(cliente_id, tipo_estoque): {metrica: valor}} (V2.2) -- cliente pela
    raiz do CNPJ (pendencia por raiz desconhecida) e tipo de estoque por
    palavra-chave em `Nome Estoque` (pendencia por valor nao classificado,
    tipo_estoque.py) -- cache por valor distinto nos dois, pra nao registrar a
    mesma pendencia N vezes dentro de um arquivo so."""
    resolvidos: dict[str, int | None] = {}
    tipos_pendentes_registrados: set[str] = set()
    agregados: dict[tuple, dict[str, float]] = {}
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

        valor_bruto = linha.get("Nome Estoque")
        tipo = tipo_estoque_servico.classificar(valor_bruto)
        if tipo == tipo_estoque_servico.NAO_CLASSIFICADO:
            valor_pendencia = (
                str(valor_bruto).strip() if valor_bruto not in (None, "") else "(sem valor)"
            )
            if valor_pendencia not in tipos_pendentes_registrados:
                ingestao.registrar_tipo_estoque_pendencia(cur, conector_id, valor_pendencia)
                tipos_pendentes_registrados.add(valor_pendencia)

        acc = agregados.setdefault(
            (cliente_id, tipo), {nome: 0.0 for nome, _ in _METRICAS}
        )
        for nome, coluna in _METRICAS:
            acc[nome] += 1 if coluna is None else linha[coluna]
    return agregados


def _remover_celulas_orfas(
    cur, metrica_ids: list[int], armazem_id: int, competencia: date, manter: set
) -> int:
    """Apaga celulas canonicas das metricas do DataHub que o processamento
    atual nao emitiu (ver docstring do modulo). `manter` e um conjunto de
    tuplas (cliente_id, tipo_estoque) -- comparadas em Python porque NULL nao
    entra em `= ANY(...)`.

    O escopo do WHERE cobre TODO o recorte (metrica, armazem, competencia),
    **independente de tipo_estoque** -- de proposito (V2.2, risco 4 da proposta
    V3). O arquivo e dono do recorte inteiro, nao so das combinacoes
    (cliente, tipo) que ele emitiu desta vez. Se o WHERE filtrasse por
    tipo_estoque, uma celula de grao antigo (tipo_estoque IS NULL, gravada
    antes deste lote) sobreviveria ao lado da nova no primeiro reprocesso, e o
    total da competencia dobraria -- exatamente o que este escopo largo evita.
    E varrendo o recorte inteiro que o prune tambem limpa, de graca, a celula
    de grao antigo assim que o arquivo reprocessa.

    O escopo (metrica, armazem, competencia) so e seguro porque o armazem ja
    distingue as unidades (de-para qualificado) e porque a rodada aborta se
    dois arquivos disputarem o mesmo recorte -- juntas, as duas coisas garantem
    um produtor unico. Uma segunda familia emitindo estas mesmas metricas
    quebraria isso: ai o escopo precisa ganhar a dimensao do produtor antes.
    """
    cur.execute(
        """
        SELECT id, cliente_id, tipo_estoque FROM medidas
        WHERE metrica_id = ANY(%s) AND armazem_id = %s AND competencia = %s
        """,
        (metrica_ids, armazem_id, competencia),
    )
    orfas = [
        mid for mid, cliente_id, tipo in cur.fetchall()
        if (cliente_id, tipo) not in manter
    ]
    if orfas:
        cur.execute("DELETE FROM medida_linhagem WHERE medida_id = ANY(%s)", (orfas,))
        cur.execute("DELETE FROM medidas WHERE id = ANY(%s)", (orfas,))
    return len(orfas)


def _origem(arquivo_inventario: dict) -> dict:
    """Identificacao de origem, so com o que o inventario ja sabe -- sem baixar
    o arquivo: nome, caminho, unidade (galho de primeiro nivel), filial e
    competencia (do nome) e o codigo de origem qualificado que o de-para
    consulta (`RMSPII/001`)."""
    nome = arquivo_inventario.get("nome") or ""
    dados = entrada_mercadorias.dados_da_familia(nome)
    if dados is None:
        raise ProcessamentoDatahubError(
            f"nome fora do padrao da familia ENTRADA_MERCADORIAS: {nome}"
        )
    filial, competencia = dados
    caminho = arquivo_inventario.get("caminho")
    unidade = inventario_datahub.unidade_do_caminho(caminho)
    return {
        "item_id": arquivo_inventario.get("id"),
        "arquivo": nome,
        "caminho": caminho,
        "unidade": unidade,
        "filial": filial,
        "competencia": competencia,
        "modificado_em": arquivo_inventario.get("modificado_em"),
        "codigo_origem": filiais_datahub.codigo_qualificado(unidade, filial),
    }


def _registrar_processamento(cur, origem: dict, status: str, detalhe=None,
                             execucao_id=None, linhas_validas=None,
                             medidas_gravadas=None) -> None:
    """Estado corrente do arquivo, chaveado pelo `item_id` (migration 0008).

    `arquivo`, `caminho` e `unidade` sao atributos MUTAVEIS: renomear ou mover
    o arquivo no SharePoint atualiza este registro em vez de criar outro,
    porque o item_id sobrevive as duas operacoes.
    """
    cur.execute(
        """
        INSERT INTO processamentos_datahub
            (arquivo, item_id, caminho, unidade, filial, competencia,
             modificado_em, execucao_id, status, detalhe, linhas_validas,
             medidas_gravadas)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (item_id) DO UPDATE SET
            arquivo = EXCLUDED.arquivo,
            caminho = EXCLUDED.caminho,
            unidade = EXCLUDED.unidade,
            filial = EXCLUDED.filial,
            competencia = EXCLUDED.competencia,
            modificado_em = EXCLUDED.modificado_em,
            execucao_id = EXCLUDED.execucao_id,
            status = EXCLUDED.status,
            detalhe = EXCLUDED.detalhe,
            linhas_validas = EXCLUDED.linhas_validas,
            medidas_gravadas = EXCLUDED.medidas_gravadas,
            processado_em = now()
        """,
        (origem["arquivo"], origem["item_id"], origem["caminho"], origem["unidade"],
         origem["filial"], _competencia_date(origem["competencia"]),
         origem["modificado_em"], execucao_id, status, detalhe, linhas_validas,
         medidas_gravadas),
    )


def processar_arquivo(cur, item_id: str) -> dict:
    """Processa UM arquivo ja sincronizado: resolve a origem, le (validacao do
    P3 intacta), agrega por cliente e persiste. Devolve o relatorio do arquivo."""
    unidades = _unidades_dos_conceitos(cur)
    metrica_ids = _metrica_ids(cur)
    conector_id = _conector_id(cur)
    fonte_id = _fonte_id(cur)

    origem = _origem(entrada_mercadorias.arquivo_do_inventario(item_id))
    competencia = _competencia_date(origem["competencia"])

    # de-para ANTES do download: origem sem de-para nao gasta um download pra
    # falhar depois na leitura (ver docstring do modulo)
    armazem_id = ingestao.resolver_armazem(cur, conector_id, origem["codigo_origem"])
    if armazem_id is None:
        ingestao.registrar_pendencia(cur, conector_id, origem["codigo_origem"])
        detalhe = (
            f"origem {origem['codigo_origem']} sem de-para no conector "
            "sharepoint_datahub"
        )
        _registrar_processamento(cur, origem, "pendencia_depara", detalhe)
        return {
            "arquivo": origem["arquivo"],
            "status": "pendencia_depara",
            "unidade": origem["unidade"],
            "filial": origem["filial"],
            "detalhe": detalhe,
        }

    resultado = entrada_mercadorias.ler(item_id)
    linhas = resultado.pop("linhas")

    agregados = _agregar_por_cliente_e_tipo(cur, conector_id, linhas)

    execucao_id = ingestao.iniciar_execucao(
        cur, conector_id, None, None, "datahub", origem["caminho"]
    )

    gravadas = 0
    for nome, _ in _METRICAS:
        metrica_id = metrica_ids[nome]
        for (cliente_id, tipo), valores in agregados.items():
            recebida_id = ingestao.registrar_recebida_datahub(
                cur, execucao_id, fonte_id, armazem_id, cliente_id,
                metrica_id, competencia, valores[nome],
                unidades[nome], resultado["arquivo"], tipo_estoque=tipo,
            )
            ingestao.upsert_medida(
                cur, metrica_id, armazem_id, competencia, valores[nome],
                conector_id, recebida_id, cliente_id, tipo_estoque=tipo,
            )
            gravadas += 1

    # Decisao da Maria em 06/ago/2026, opcao (a): arquivo republicado vazio APAGA
    # as celulas que ele gravou antes -- a serie e espelho fiel do ultimo estado
    # da fonte, coerente com o que a V1 ja faz quando todas as linhas sao
    # invalidas. Sai de graca: com `agregados` vazio, o prune remove todas as
    # celulas daquele (metrica, armazem, competencia).
    removidas = _remover_celulas_orfas(
        cur, list(metrica_ids.values()), armazem_id, competencia, set(agregados)
    )

    # `sem_dado`: cabecalho valido e zero linha. Status TERMINAL, nao erro -- ver
    # migration 0013 e o comentario de `sem_dado` em entrada_mercadorias.ler.
    status = "sem_dado" if resultado["sem_dado"] else "ok"
    detalhe = "competencia sem movimento (arquivo so com cabecalho)" if resultado["sem_dado"] else None

    ingestao.finalizar_execucao(
        cur, execucao_id, "ok",
        linhas_lidas=resultado["linhas_lidas"], linhas_gravadas=gravadas,
    )
    _registrar_processamento(
        cur, origem, status, detalhe=detalhe, execucao_id=execucao_id,
        linhas_validas=resultado["linhas_validas"], medidas_gravadas=gravadas,
    )
    clientes_do_arquivo = {cliente_id for cliente_id, _ in agregados}
    return {
        "arquivo": origem["arquivo"],
        "status": status,
        "unidade": origem["unidade"],
        "filial": origem["filial"],
        "competencia": origem["competencia"],
        # id interno: alimenta a guarda de colisao de processar_todos
        "armazem_id": armazem_id,
        "clientes": sum(1 for c in clientes_do_arquivo if c is not None),
        "sem_cliente": 1 if None in clientes_do_arquivo else 0,
        # tipos de estoque distintos gravados (V2.2) -- explica o salto no
        # numero de medidas_gravadas em relacao a antes do lote
        "tipos": len({tipo for _, tipo in agregados}),
        "medidas_gravadas": gravadas,
        "celulas_removidas": removidas,
    }


# Status em que o arquivo NAO precisa ser reprocessado enquanto o `modificado_em`
# nao mudar. `sem_dado` entra aqui (V2.1.1) porque competencia sem movimento e um
# desfecho terminal, nao uma falha a repetir: sem isto os 5 arquivos vazios da
# SANCA eram baixados de novo em toda rodada, pra sempre.
_STATUS_TERMINAIS = ("ok", "sem_dado")


def _ja_processado(cur, item_id: str, modificado_em) -> bool:
    """Arquivo ja processado com sucesso e inalterado desde entao.

    Chaveado por item_id (migration 0008): com a chave antiga -- o nome --
    dois homonimos de unidades diferentes disputavam o mesmo registro e
    NENHUM dos dois era reconhecido como inalterado, entao os dois
    reprocessavam a cada rodada.
    """
    cur.execute(
        "SELECT modificado_em, status FROM processamentos_datahub WHERE item_id = %s",
        (item_id,),
    )
    row = cur.fetchone()
    return row is not None and row[1] in _STATUS_TERMINAIS and row[0] == modificado_em


def _abortar_se_origens_colidem(candidatos: list[dict]) -> None:
    """Aborta ANTES de baixar qualquer coisa se dois arquivos do inventario
    apontarem para a mesma (origem qualificada, competencia).

    Complementa a guarda de tempo de execucao: esta ve todos os candidatos,
    inclusive os que a rodada vai pular por estarem inalterados; a outra ve os
    armazens de fato resolvidos, inclusive de-paras distintos apontando para o
    mesmo armazem.
    """
    vistos: dict[tuple, str] = {}
    for arquivo in candidatos:
        origem = _origem(arquivo)
        chave = (origem["codigo_origem"], origem["competencia"])
        anterior = vistos.get(chave)
        if anterior is not None:
            raise ProcessamentoDatahubError(
                f"colisao de origem: '{origem['caminho']}' e '{anterior}' apontam "
                f"para {origem['codigo_origem']} na competencia "
                f"{origem['competencia']} -- rodada abortada sem gravar nada"
            )
        vistos[chave] = origem["caminho"]


def processar_todos(cur, forcar: bool = False) -> dict:
    """Processa a familia inteira do inventario atual: arquivo novo ou alterado
    (modificado_em diferente) e processado; inalterado e pulado (a menos de
    forcar=True). Erro num arquivo nao derruba o lote -- vira status 'erro' no
    relatorio e no controle.

    Colisao, ao contrario de erro, DERRUBA a rodada: dois arquivos no mesmo
    recorte fariam um apagar as celulas do outro como orfas e a linhagem ficar
    com o armazem errado de forma permanente. Como o endpoint roda tudo numa
    transacao, abortar reverte a rodada inteira -- nada e gravado pela metade.
    """
    resumo = inventario_datahub.status().get("resumo")
    if not resumo:
        raise ProcessamentoDatahubError(
            "nenhuma sincronizacao do DataHub ainda -- clique em 'Sincronizar agora' primeiro"
        )

    candidatos = [
        a for a in resumo.get("arquivos", [])
        if entrada_mercadorias.dados_da_familia(a.get("nome", "")) is not None
    ]
    _abortar_se_origens_colidem(candidatos)

    processados, pulados, erros = [], 0, []
    emitidos: dict[tuple, str] = {}
    for arquivo in candidatos:
        if not forcar and _ja_processado(cur, arquivo["id"], arquivo.get("modificado_em")):
            pulados += 1
            continue
        try:
            relatorio = processar_arquivo(cur, arquivo["id"])
        except (
            entrada_mercadorias.EntradaMercadoriasError,
            graph_datahub.GraphError,
            ProcessamentoDatahubError,
        ) as exc:
            erros.append({"arquivo": arquivo["nome"], "erro": str(exc)})
            # nome ja casou com o padrao da familia (filtro dos candidatos)
            _registrar_processamento(cur, _origem(arquivo), "erro", detalhe=str(exc))
            continue

        processados.append(relatorio)
        # `sem_dado` entra na guarda junto do `ok` (V2.1.1): ele nao grava celula,
        # mas PODA o escopo (armazem, competencia) -- num cenario de colisao, o
        # arquivo vazio apagaria as celulas do irmao sem a rodada abortar.
        if relatorio["status"] not in _STATUS_TERMINAIS:
            continue
        chave = (relatorio["armazem_id"], relatorio["competencia"])
        anterior = emitidos.get(chave)
        if anterior is not None:
            raise ProcessamentoDatahubError(
                f"colisao de armazem: '{relatorio['arquivo']}' e '{anterior}' gravaram "
                f"no mesmo armazem na competencia {relatorio['competencia']} -- rodada "
                "abortada e revertida; conferir o de-para do conector sharepoint_datahub"
            )
        emitidos[chave] = relatorio["arquivo"]

    return {
        "total_familia": len(candidatos),
        "processados": processados,
        "pulados": pulados,
        "erros": erros,
    }


def listar_processamentos(cur) -> list[dict]:
    """Estado corrente por arquivo, pro painel do admin.

    A unidade e o caminho vem junto porque o nome do arquivo deixou de ser
    unico na fonte: sem eles, dois homonimos de unidades diferentes ficam
    indistinguiveis na tela.
    """
    cur.execute(
        """
        SELECT arquivo, unidade, caminho, filial, competencia, status, detalhe,
               linhas_validas, medidas_gravadas, processado_em
        FROM processamentos_datahub
        ORDER BY competencia DESC, unidade NULLS FIRST, filial, arquivo
        """
    )
    return [
        {
            "arquivo": r[0],
            "unidade": r[1],
            "caminho": r[2],
            "filial": r[3],
            "competencia": r[4].isoformat() if r[4] else None,
            "status": r[5],
            "detalhe": r[6],
            "linhas_validas": r[7],
            "medidas_gravadas": r[8],
            "processado_em": r[9].isoformat() if r[9] else None,
        }
        for r in cur.fetchall()
    ]


def listar_pendencias_filial(cur) -> list[dict]:
    """Pendencias de de-para do conector do DataHub, pro painel do admin --
    mesma tabela usada pelo upload manual.

    O que aparece aqui e o codigo de origem QUALIFICADO (`RMSPII/002`,
    `CWB3/001`, `SANCA/025`, `RJ/004-003`), nao o codigo de filial nu: e ele
    que precisa de decisao humana pra virar de-para.
    """
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
            "origem_na_fonte": r[0],
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


def listar_pendencias_tipo_estoque(cur) -> list[dict]:
    """Valores de `Nome Estoque` que nao casaram com nenhuma palavra-chave
    (backend/services/tipo_estoque.py), pro painel do admin -- mesmo padrao
    das pendencias de filial e de cliente (V2.2)."""
    cur.execute(
        """
        SELECT tp.valor_na_fonte, tp.primeira_vez_em, tp.ultima_vez_em
        FROM tipo_estoque_pendencias tp
        JOIN conectores c ON c.id = tp.conector_id
        WHERE c.tipo = %s
        ORDER BY tp.ultima_vez_em DESC
        """,
        (TIPO_CONECTOR,),
    )
    return [
        {
            "valor_na_fonte": r[0],
            "primeira_vez_em": r[1].isoformat() if r[1] else None,
            "ultima_vez_em": r[2].isoformat() if r[2] else None,
        }
        for r in cur.fetchall()
    ]
