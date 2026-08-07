"""Processamento persistente das familias de volumetria do DataHub: entrada
(Bloco C / V1.3, ENTRADA_MERCADORIAS) e saida (V2.3, SAIDA_MERCADORIAS).

Transforma a leitura ao vivo em serie historica: cada arquivo (ou, na saida,
cada PARTICAO -- ver secao abaixo) vira uma execucao que grava
`medidas_recebidas` (append-only, com unidade canonica e arquivo de origem --
linhagem preservada) e publica as celulas canonicas em `medidas`, no grao
competencia x filial x cliente x tipo de estoque.

Regras que sustentam a prevencao de dupla contagem:

- Uma metrica do DataHub existe num grao SO: cliente x tipo de estoque
  (cliente_id NULL = "sem cliente identificado no cadastro OU unidade sem
  coluna de cliente na fonte -- ver D5.1/serie_datahub", tipo_estoque NULL so
  em celula anterior ao V2.2; nunca "total da filial"). O total da filial e
  SEMPRE a soma das linhas -- nunca ha duas granularidades da mesma metrica
  no banco.
- Idempotencia: a mesma origem processada 2x upserta as MESMAS celulas
  (constraint medidas_celula_unica); reprocessar uma origem alterada cria
  execucao nova (auditoria acumula) e atualiza as celulas.
- Celula orfa: se um reprocessamento deixa de emitir uma celula que existia
  (ex.: cliente foi cadastrado e as linhas dele sairam do balde NULL), a
  celula antiga e REMOVIDA -- as celulas de (metrica, armazem, competencia)
  espelham exatamente o ultimo processamento daquela origem, que e a unica
  dona daquele recorte. **O escopo do prune usa so os `metrica_id` do
  PRODUTOR em questao** (entrada ou saida) -- e isso, e so isso, que garante
  que processar a saida nunca apaga celula de entrada e vice-versa: com
  metricas separadas (peso_bruto_entrada != peso_bruto_saida) os escopos nunca
  se encontram, DESDE que o codigo nunca misture os dois conjuntos de
  metrica_id numa mesma chamada do prune.

A identidade do arquivo e o `item_id` do Graph, nunca o nome (migration 0008).
A fonte tem quatro unidades desde 31/jul/2026 e as quatro publicam com a mesma
convencao: `ENTRADA_MERCADORIAS_001_2601.xlsx` existe em RMSPII e em CWB3, em
armazens diferentes. Tres consequencias sustentadas aqui:

- o de-para e consultado pelo codigo de origem QUALIFICADO pela unidade
  (`RMSPII/001`), nunca pelo codigo de filial nu;
- o de-para e resolvido ANTES do download: origem sem de-para vira pendencia
  visivel sem baixar nada;
- "uma origem por armazem x competencia" e invariante VERIFICADA: a guarda de
  colisao aborta a rodada inteira se dois arquivos apontarem pro mesmo
  recorte, antes e depois de gravar. Sem isso, um apagaria as celulas do
  outro como orfas e a linhagem em `medidas_recebidas` (append-only) ficaria
  com o armazem errado pra sempre.

## Particao (V2.3)

A saida vem partida em `_f1`/`_f2` (33 MB por filial/competencia) OU sem
sufixo nenhum (a CWB3 publica assim). A unidade de processamento da saida
deixa de ser "um arquivo" e passa a ser a PARTICAO: `(origem qualificada,
competencia)`, com 1..N partes identificadas por `indice_parte` (None = sem
sufixo, parte unica e indiferenciada). Todas as partes de uma particao sao
baixadas, agregadas e gravadas como uma unidade so -- uma execucao, uma
gravacao -- mas cada parte continua tendo sua PROPRIA linha em
`processamentos_datahub` (chaveada por item_id, como sempre), porque o
painel precisa mostrar as duas.

A guarda de colisao ganhou duas dimensoes pra sustentar isso: a FAMILIA
(entrada e saida nunca colidem entre si, mesmo apontando pro mesmo
codigo_origem+competencia -- sao produtores de metricas diferentes) e o
`indice_parte` (partes DIFERENTES da mesma particao nao colidem -- e o caso
normal; a mesma parte aparecendo duas vezes, sim). A entrada tem
`indice_parte` sempre None, entao a chave dela se reduz exatamente ao
comportamento de antes do V2.3.

Cliente e resolvido pela raiz do CNPJ (8 digitos) contra clientes.nk_erp
(NK_CLIENTE do DW). SEM auto-cadastro (decisao da Maria, 31/jul/2026):
cliente fora do cadastro vira pendencia (`cliente_pendencias`) e as linhas
dele somam no balde NULL ate o cadastro acontecer -- ai um reprocessamento
move os valores pra linha do cliente. **Origem sem coluna de cliente na
fonte** (RMRJ na entrada, layout de 18 colunas; RMSPV na saida, layout de 34
-- decisao D2 do V2.3) tambem cai no balde NULL, mas SEM pendencia: nao ha
CNPJ pra cadastrar. Isso sai de graca do proprio `raiz_cnpj`/leitor (emitem
`Cliente CNPJ: None`, e `raiz_cnpj(None)` ja e None sem passar pelo caminho
que registra pendencia) -- nenhum codigo aqui precisou saber da distincao.

A unidade gravada nas recebidas vem do CONCEITO canonico homonimo
(conceitos_canonicos, V1.1) -- e a forma de enforcement na ingestao: metrica
sem conceito aprovado com unidade definida nao processa (erro de
configuracao, nunca palpite).
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
    saida_mercadorias,
    tipo_estoque as tipo_estoque_servico,
)

_FONTE_CHAVE_ENTRADA = "datahub_entrada_mercadorias"
_FONTE_CHAVE_SAIDA = "datahub_saida_mercadorias"

# metrica persistida -> coluna somada (None = contagem de linhas). Os nomes
# sao os conceitos canonicos (renomeados pro par de entrada no V2.3, migration
# 0015). clientes_atendidos NAO entra em nenhum dos dois pares (contagem
# distinta nao e somavel -- derivada na consulta, serie_datahub); volumes por
# embalagem ficam fora da serie (decisao da Maria, 31/jul/2026).
_METRICAS_ENTRADA = (
    ("peso_bruto_entrada", "Peso Bruto"),
    ("valor_mercadoria_entrada", "Vlr. Total"),
    ("registros_entrada", None),
)

# Sem par de valor: a fonte (SAIDA_MERCADORIAS) nao tem coluna monetaria em
# nenhuma unidade -- conferido no dado em 06/ago/2026
# (docs/V2_3_PLANO_EXECUCAO.md, secao 1.1). Criar a metrica seria prometer um
# numero que o dado nao paga.
_METRICAS_SAIDA = (
    ("peso_bruto_saida", "Peso Bruto"),
    ("registros_saida", None),
)

# Decisao D3/7 do V2.3: so 2026. O historico da saida (competencias 2110..2512,
# 176 arquivos na fonte) fica DECLARADO como disponivel e deliberadamente fora
# -- nunca processado em silencio (ver nuvem_datahub._cobertura_do_arquivo e
# scripts/processar_saida.py).
COMPETENCIA_MINIMA_SAIDA = date(2026, 1, 1)


class ProcessamentoDatahubError(Exception):
    """Erro de configuracao/estado do processamento -- mensagem clara pro
    chamador (endpoint traduz pra HTTP 400)."""


def raiz_cnpj(valor) -> str | None:
    """Raiz do CNPJ (8 digitos) a partir da coluna 'Cliente CNPJ'.

    Celula numerica do Excel perde zeros a esquerda -- por isso 9..14 digitos
    sao completados a esquerda ate 14 antes de cortar a raiz. 8 digitos ja e
    uma raiz; menos que 8 (ou mais que 14) nao da pra identificar com
    seguranca -> None (balde "sem cliente identificado"), nunca chute. `None`
    de entrada (origem sem coluna de cliente na fonte, V2.3) cai direto aqui.
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


def _fonte_id(cur, chave: str):
    cur.execute("SELECT id FROM catalogo_fontes WHERE chave = %s", (chave,))
    row = cur.fetchone()
    return row[0] if row else None


def _metrica_ids(cur, metricas) -> dict[str, int]:
    """ids das metricas governadas, resolvidos ANTES de qualquer escrita --
    metrica fora do catalogo e erro de configuracao com mensagem clara (400),
    nunca um 500 no meio do lote."""
    ids = {}
    for nome, _ in metricas:
        try:
            ids[nome] = ingestao.resolver_metrica_governada(cur, nome)
        except ValueError as exc:
            raise ProcessamentoDatahubError(str(exc)) from exc
    return ids


def _unidades_dos_conceitos(cur, metricas) -> dict[str, str]:
    """unidade canonica por metrica, vinda do conceito canonico homonimo --
    enforcement da ingestao: sem conceito aprovado com unidade, nao processa."""
    nomes = [nome for nome, _ in metricas]
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


def _agregar_por_cliente_e_tipo(cur, conector_id: int, linhas, metricas) -> dict:
    """{(cliente_id, tipo_estoque): {metrica: valor}} -- cliente pela raiz do
    CNPJ (pendencia por raiz desconhecida, NUNCA quando a raiz e None -- ver
    docstring do modulo) e tipo de estoque por palavra-chave em `Nome
    Estoque` (pendencia por valor nao classificado, tipo_estoque.py) --
    cache por valor distinto nos dois, pra nao registrar a mesma pendencia N
    vezes dentro da mesma origem.

    `linhas` pode ser uma lista (entrada) ou um GERADOR (saida, V2.3 -- ver
    saida_mercadorias.ler) -- so itera uma vez, nunca materializa."""
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

        acc = agregados.setdefault((cliente_id, tipo), {nome: 0.0 for nome, _ in metricas})
        for nome, coluna in metricas:
            acc[nome] += 1 if coluna is None else linha[coluna]
    return agregados


def _remover_celulas_orfas(
    cur, metrica_ids: list[int], armazem_id: int, competencia: date, manter: set
) -> int:
    """Apaga celulas canonicas das metricas do PRODUTOR (entrada OU saida --
    nunca os dois juntos, ver docstring do modulo) que o processamento atual
    nao emitiu. `manter` e um conjunto de tuplas (cliente_id, tipo_estoque) --
    comparadas em Python porque NULL nao entra em `= ANY(...)`.

    O escopo do WHERE cobre TODO o recorte (metrica, armazem, competencia),
    **independente de tipo_estoque** -- de proposito (V2.2, risco 4 da
    proposta V3). A origem e dona do recorte inteiro, nao so das combinacoes
    (cliente, tipo) que ela emitiu desta vez.

    O escopo (metrica, armazem, competencia) so e seguro porque: o armazem ja
    distingue as unidades (de-para qualificado); a rodada aborta se dois
    arquivos disputarem o mesmo recorte; e `metrica_ids` e SEMPRE so do
    produtor que esta processando (entrada chama com os 3 ids dela, saida com
    os 2 dela -- nunca os 5 juntos). As tres coisas juntas garantem um
    produtor unico por chamada.
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


def _origem(arquivo_inventario: dict, dados_da_familia) -> dict:
    """Identificacao de origem, so com o que o inventario ja sabe -- sem
    baixar o arquivo: nome, caminho, unidade (galho de primeiro nivel), filial,
    competencia e indice_parte (todos do NOME, via `dados_da_familia` do
    modulo leitor certo) e o codigo de origem qualificado que o de-para
    consulta (`RMSPII/001`).

    `dados_da_familia` devolve 2-tupla (entrada, sem particao) ou 3-tupla
    (saida, com indice_parte) -- normalizado aqui pra sempre 3, entao o resto
    do modulo nunca precisa saber qual leitor emitiu.
    """
    nome = arquivo_inventario.get("nome") or ""
    dados = dados_da_familia(nome)
    if dados is None:
        raise ProcessamentoDatahubError(f"nome fora do padrao esperado da familia: {nome}")
    if len(dados) == 3:
        filial, competencia, indice_parte = dados
    else:
        filial, competencia = dados
        indice_parte = None
    caminho = arquivo_inventario.get("caminho")
    unidade = inventario_datahub.unidade_do_caminho(caminho)
    return {
        "item_id": arquivo_inventario.get("id"),
        "arquivo": nome,
        "caminho": caminho,
        "unidade": unidade,
        "filial": filial,
        "competencia": competencia,
        "indice_parte": indice_parte,
        "modificado_em": arquivo_inventario.get("modificado_em"),
        "codigo_origem": filiais_datahub.codigo_qualificado(unidade, filial),
    }


def _registrar_processamento(cur, origem: dict, status: str, detalhe=None,
                             execucao_id=None, linhas_validas=None,
                             medidas_gravadas=None, layout_lido=None) -> None:
    """Estado corrente do arquivo, chaveado pelo `item_id` (migration 0008).

    `arquivo`, `caminho` e `unidade` sao atributos MUTAVEIS: renomear ou mover
    o arquivo no SharePoint atualiza este registro em vez de criar outro,
    porque o item_id sobrevive as duas operacoes. Uma particao com N partes
    (V2.3) grava N linhas aqui -- uma por item_id -- todas com o mesmo
    `execucao_id`.

    `layout_lido` (V2.3, migration 0017): o layout que o leitor de fato
    detectou (20/18 colunas na entrada, 36/34 na saida). None quando o
    arquivo nunca foi lido (pendencia_depara, ou erro antes da leitura) --
    nunca inventa o valor. O `UPDATE` usa `COALESCE` pra NAO apagar um layout
    ja detectado numa rodada anterior: sem isso, um `erro` (rede, token) ou
    uma `pendencia_depara` numa rodada POSTERIOR sobrescreveria com NULL o
    layout que a rodada anterior tinha lido de verdade -- e
    `serie_datahub._armazens_sem_coluna_cliente` reclassificaria em silencio o
    balde "sem cliente identificado" daquele armazem de `sem_coluna_na_fonte`
    (nao resolvivel) pra `nao_cadastrado` (resolvivel), mandando a Maria caçar
    um cadastro que nao existe -- achado da revisao independente do V2.3.
    """
    cur.execute(
        """
        INSERT INTO processamentos_datahub
            (arquivo, item_id, caminho, unidade, filial, competencia,
             modificado_em, execucao_id, status, detalhe, linhas_validas,
             medidas_gravadas, layout_lido)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            layout_lido = COALESCE(EXCLUDED.layout_lido, processamentos_datahub.layout_lido),
            processado_em = now()
        """,
        (origem["arquivo"], origem["item_id"], origem["caminho"], origem["unidade"],
         origem["filial"], _competencia_date(origem["competencia"]),
         origem["modificado_em"], execucao_id, status, detalhe, linhas_validas,
         medidas_gravadas, layout_lido),
    )


# Status em que o arquivo NAO precisa ser reprocessado enquanto o `modificado_em`
# nao mudar. `sem_dado` entra aqui (V2.1.1) porque competencia sem movimento e um
# desfecho terminal, nao uma falha a repetir.
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


def _abortar_se_origens_colidem(familia: str, candidatos: list[dict], dados_da_familia) -> None:
    """Aborta ANTES de baixar qualquer coisa se dois arquivos do inventario
    apontarem pra o MESMO (familia, origem qualificada, competencia, parte).

    A chave ganha `familia` (V2.3): sem ela, a entrada e a saida da mesma
    filial/competencia se acusariam de colidir, e a rodada abortaria sempre --
    sao produtores de metricas diferentes, nunca disputam o mesmo recorte.
    Ganha tambem `indice_parte`: partes DIFERENTES da mesma particao da saida
    (`_f1` e `_f2`) NAO colidem -- e o caso normal, com 1..N partes por
    competencia. A entrada tem indice_parte sempre None, entao a chave dela
    se reduz exatamente ao comportamento de antes do V2.3 (uma origem por
    competencia, sem particao).

    Complementa a guarda de tempo de execucao: esta ve todos os candidatos,
    inclusive os que a rodada vai pular por estarem inalterados; a outra ve os
    armazens de fato resolvidos, inclusive de-paras distintos apontando para o
    mesmo armazem.
    """
    vistos: dict[tuple, str] = {}
    for arquivo in candidatos:
        origem = _origem(arquivo, dados_da_familia)
        chave = (familia, origem["codigo_origem"], origem["competencia"], origem["indice_parte"])
        anterior = vistos.get(chave)
        if anterior is not None:
            parte = (
                f", parte {origem['indice_parte']}" if origem["indice_parte"] is not None else ""
            )
            raise ProcessamentoDatahubError(
                f"colisao de origem: '{origem['caminho']}' e '{anterior}' apontam "
                f"para {origem['codigo_origem']} na competencia "
                f"{origem['competencia']}{parte} -- rodada abortada sem gravar nada"
            )
        vistos[chave] = origem["caminho"]


# =============================================================================
# ENTRADA (Bloco C / V1.3) -- API publica inalterada desde antes do V2.3
# =============================================================================


def processar_arquivo(cur, item_id: str) -> dict:
    """Processa UM arquivo de ENTRADA_MERCADORIAS ja sincronizado: resolve a
    origem, le (validacao do P3 intacta), agrega por cliente e persiste.
    Devolve o relatorio do arquivo."""
    unidades = _unidades_dos_conceitos(cur, _METRICAS_ENTRADA)
    metrica_ids = _metrica_ids(cur, _METRICAS_ENTRADA)
    conector_id = _conector_id(cur)
    fonte_id = _fonte_id(cur, _FONTE_CHAVE_ENTRADA)

    origem = _origem(
        entrada_mercadorias.arquivo_do_inventario(item_id), entrada_mercadorias.dados_da_familia
    )
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
    layout_lido = resultado["layout"]

    agregados = _agregar_por_cliente_e_tipo(cur, conector_id, linhas, _METRICAS_ENTRADA)

    execucao_id = ingestao.iniciar_execucao(
        cur, conector_id, None, None, "datahub", origem["caminho"]
    )

    gravadas = 0
    for nome, _ in _METRICAS_ENTRADA:
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
        layout_lido=layout_lido,
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


def processar_todos(cur, forcar: bool = False) -> dict:
    """Processa a familia ENTRADA_MERCADORIAS inteira do inventario atual:
    arquivo novo ou alterado (modificado_em diferente) e processado,
    inalterado e pulado (a menos de forcar=True). Erro num arquivo nao
    derruba o lote -- vira status 'erro' no relatorio e no controle.

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
    _abortar_se_origens_colidem("entrada", candidatos, entrada_mercadorias.dados_da_familia)

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
            _registrar_processamento(
                cur, _origem(arquivo, entrada_mercadorias.dados_da_familia), "erro", detalhe=str(exc)
            )
            continue

        processados.append(relatorio)
        # `sem_dado` entra na guarda junto do `ok` (V2.1.1): ele nao grava celula,
        # mas PODA o escopo (armazem, competencia) -- num cenario de colisao, o
        # arquivo vazio apagaria as celulas do irmao sem a rodada abortar.
        if relatorio["status"] not in _STATUS_TERMINAIS:
            continue
        chave = ("entrada", relatorio["armazem_id"], relatorio["competencia"])
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


# =============================================================================
# SAIDA (V2.3) -- particao (1..N partes), fora de escopo antes de 2026 (D3)
# =============================================================================


def _agrupar_particoes_saida(candidatos: list[dict]) -> dict[tuple, list[dict]]:
    """{(codigo_origem, competencia): [arquivo, ...]} -- so chamar DEPOIS da
    guarda de colisao (garante que nao ha indice_parte duplicado dentro do
    mesmo grupo).

    `indice_parte is None` significa "parte unica, indiferenciada"
    (`saida_mercadorias.arquivo_do_inventario`) -- semanticamente incompativel
    com ter irmas. A guarda de colisao NAO pega isso: `None` e `1` sao
    indice_parte DIFERENTES, entao nao colidem ali, mas agrupar os dois
    aqui os somaria em silencio (achado da revisao independente do V2.3) --
    se a fonte republicar num formato partido uma competencia que hoje e
    parte unica, o peso daquele mes dobraria sem erro nenhum. E erro, nao
    soma."""
    grupos: dict[tuple, list[dict]] = {}
    for arquivo in candidatos:
        origem = _origem(arquivo, saida_mercadorias.dados_da_familia)
        chave = (origem["codigo_origem"], origem["competencia"])
        grupos.setdefault(chave, []).append(arquivo)

    for chave, arquivos in grupos.items():
        codigo_origem, competencia = chave
        if len(arquivos) < 2:
            continue
        indices = [
            _origem(arquivo, saida_mercadorias.dados_da_familia)["indice_parte"]
            for arquivo in arquivos
        ]
        if any(i is None for i in indices):
            nomes = ", ".join(sorted(a["nome"] for a in arquivos))
            raise ProcessamentoDatahubError(
                f"particao mista em {codigo_origem} na competencia {competencia}: "
                f"arquivo sem sufixo de parte (_fN) junto com arquivo(s) partido(s) -- "
                f"nao da pra saber se e uma parte unica ou uma parte perdida entre as "
                f"outras. Arquivos: {nomes}"
            )
        # ordenadas pelo indice do sufixo (plano de execucao do V2.3, secao
        # 3.7) -- sem isto `arquivo_origem_nomes`/a ordem de leitura das
        # partes dependia da ordem de retorno do inventario, que pode variar
        # entre rodadas (achado da revisao independente).
        grupos[chave] = sorted(
            arquivos,
            key=lambda a: _origem(a, saida_mercadorias.dados_da_familia)["indice_parte"],
        )
    return grupos


def _particao_ja_processada(cur, partes: list[dict]) -> bool:
    """Toda parte tem que estar processada e inalterada -- uma parte nova ou
    modificada reprocessa a PARTICAO inteira (senao metade da competencia
    ficaria com dado velho)."""
    return all(_ja_processado(cur, p["id"], p.get("modificado_em")) for p in partes)


def _dentro_do_escopo_saida(competencia: str) -> bool:
    return _competencia_date(competencia) >= COMPETENCIA_MINIMA_SAIDA


def processar_particao_saida(cur, item_ids: list[str]) -> dict:
    """Processa UMA particao de SAIDA_MERCADORIAS (1..N partes da mesma
    origem x competencia) como uma unidade so: baixa e agrega TODAS as partes
    ANTES de gravar (uma execucao, uma gravacao), mas registra cada parte na
    sua PROPRIA linha de `processamentos_datahub`.

    Memoria (risco 3 do V2.3): as partes sao lidas uma POR VEZ -- o generator
    de `saida_mercadorias.ler()` e consumido e descartado antes de baixar a
    proxima, nunca duas partes inteiras em memoria ao mesmo tempo.
    """
    unidades = _unidades_dos_conceitos(cur, _METRICAS_SAIDA)
    metrica_ids = _metrica_ids(cur, _METRICAS_SAIDA)
    conector_id = _conector_id(cur)
    fonte_id = _fonte_id(cur, _FONTE_CHAVE_SAIDA)

    origens = [
        _origem(saida_mercadorias.arquivo_do_inventario(item_id), saida_mercadorias.dados_da_familia)
        for item_id in item_ids
    ]
    origem_ref = origens[0]
    competencia = _competencia_date(origem_ref["competencia"])

    armazem_id = ingestao.resolver_armazem(cur, conector_id, origem_ref["codigo_origem"])
    if armazem_id is None:
        ingestao.registrar_pendencia(cur, conector_id, origem_ref["codigo_origem"])
        detalhe = (
            f"origem {origem_ref['codigo_origem']} sem de-para no conector "
            "sharepoint_datahub"
        )
        for origem in origens:
            _registrar_processamento(cur, origem, "pendencia_depara", detalhe)
        return {
            "arquivos": [o["arquivo"] for o in origens],
            "status": "pendencia_depara",
            "unidade": origem_ref["unidade"],
            "filial": origem_ref["filial"],
            "competencia": origem_ref["competencia"],
            "detalhe": detalhe,
        }

    agregados: dict[tuple, dict[str, float]] = {}
    layout_lido = None
    contadores_por_item: dict[str, dict] = {}
    nomes_arquivos = []
    for item_id in item_ids:
        resultado = saida_mercadorias.ler(item_id)
        layout_lido = resultado["layout"]  # todas as partes de uma origem tem o mesmo layout
        nomes_arquivos.append(resultado["arquivo"])
        parciais = _agregar_por_cliente_e_tipo(
            cur, conector_id, resultado["linhas"], _METRICAS_SAIDA
        )
        for chave, valores in parciais.items():
            acc = agregados.setdefault(chave, {nome: 0.0 for nome, _ in _METRICAS_SAIDA})
            for nome, _ in _METRICAS_SAIDA:
                acc[nome] += valores[nome]
        contadores_por_item[item_id] = dict(resultado["contadores"])

    linhas_lidas_total = sum(c["lidas"] for c in contadores_por_item.values())
    arquivo_origem_nomes = ", ".join(nomes_arquivos)

    execucao_id = ingestao.iniciar_execucao(
        cur, conector_id, None, None, "datahub", origem_ref["caminho"]
    )

    gravadas = 0
    for nome, _ in _METRICAS_SAIDA:
        metrica_id = metrica_ids[nome]
        for (cliente_id, tipo), valores in agregados.items():
            recebida_id = ingestao.registrar_recebida_datahub(
                cur, execucao_id, fonte_id, armazem_id, cliente_id,
                metrica_id, competencia, valores[nome],
                unidades[nome], arquivo_origem_nomes, tipo_estoque=tipo,
            )
            ingestao.upsert_medida(
                cur, metrica_id, armazem_id, competencia, valores[nome],
                conector_id, recebida_id, cliente_id, tipo_estoque=tipo,
            )
            gravadas += 1

    # mesma decisao (a) de 06/ago/2026: particao republicada sem linha de
    # dado apaga o que havia gravado -- espelho fiel do ultimo estado da fonte
    removidas = _remover_celulas_orfas(
        cur, list(metrica_ids.values()), armazem_id, competencia, set(agregados)
    )

    status = "sem_dado" if linhas_lidas_total == 0 else "ok"
    detalhe = "competencia sem movimento (arquivo so com cabecalho)" if status == "sem_dado" else None

    ingestao.finalizar_execucao(
        cur, execucao_id, "ok", linhas_lidas=linhas_lidas_total, linhas_gravadas=gravadas,
    )
    # `gravadas` e o total da PARTICAO (todas as partes agregadas antes de
    # gravar uma vez so) -- gravar o mesmo numero em CADA linha de parte fazia
    # `cockpit.qualidade()` (SUM(medidas_gravadas) agrupado por status) contar
    # em dobro (ou N vezes) uma particao de N partes. So a primeira parte
    # carrega o total; as demais ficam com 0 -- achado da revisao
    # independente do V2.3.
    for indice, (item_id, origem) in enumerate(zip(item_ids, origens)):
        _registrar_processamento(
            cur, origem, status, detalhe=detalhe, execucao_id=execucao_id,
            linhas_validas=contadores_por_item[item_id]["validas"],
            medidas_gravadas=gravadas if indice == 0 else 0,
            layout_lido=layout_lido,
        )

    clientes_da_particao = {cliente_id for cliente_id, _ in agregados}
    return {
        "arquivos": nomes_arquivos,
        "status": status,
        "unidade": origem_ref["unidade"],
        "filial": origem_ref["filial"],
        "competencia": origem_ref["competencia"],
        "armazem_id": armazem_id,
        "clientes": sum(1 for c in clientes_da_particao if c is not None),
        "sem_cliente": 1 if None in clientes_da_particao else 0,
        "tipos": len({tipo for _, tipo in agregados}),
        "medidas_gravadas": gravadas,
        "celulas_removidas": removidas,
    }


def listar_particoes_saida(cur, forcar: bool = False) -> dict:
    """Determina o trabalho da rodada de saida SEM gravar nada: quais
    particoes precisam ser processadas (ja filtradas por escopo D3 e por "ja
    processada"/`forcar`), quais arquivos ficam fora de escopo, e roda a
    guarda de colisao (pode levantar `ProcessamentoDatahubError` -- colisao
    aborta ANTES de decidir qualquer coisa).

    Pensado pra abrir uma conexao/transacao CURTA, so leitura, antes de um
    laço que processa cada particao na sua PROPRIA transacao
    (`scripts/processar_saida.py`, decisao D4: uma competencia por transacao,
    uma falha isolada nao derruba as outras). `processar_todos_saida` usa
    isto internamente quando o chamador prefere UMA transacao so (mais
    simples pra teste, mas sem o isolamento por particao)."""
    resumo = inventario_datahub.status().get("resumo")
    if not resumo:
        raise ProcessamentoDatahubError(
            "nenhuma sincronizacao do DataHub ainda -- clique em 'Sincronizar agora' primeiro"
        )

    candidatos_todos = [
        a for a in resumo.get("arquivos", [])
        if saida_mercadorias.dados_da_familia(a.get("nome", "")) is not None
    ]
    _abortar_se_origens_colidem("saida", candidatos_todos, saida_mercadorias.dados_da_familia)

    fora_de_escopo = []
    candidatos = []
    for arquivo in candidatos_todos:
        _, competencia, _ = saida_mercadorias.dados_da_familia(arquivo["nome"])
        if _dentro_do_escopo_saida(competencia):
            candidatos.append(arquivo)
        else:
            fora_de_escopo.append(arquivo["nome"])

    particoes = _agrupar_particoes_saida(candidatos)
    pendentes, pulados = [], 0
    for partes in particoes.values():
        if not forcar and _particao_ja_processada(cur, partes):
            pulados += len(partes)
        else:
            pendentes.append(partes)

    return {
        "total_familia": len(candidatos_todos),
        "arquivos_fora_de_escopo": fora_de_escopo,
        "particoes_pendentes": pendentes,
        "pulados": pulados,
    }


def processar_todos_saida(cur, forcar: bool = False) -> dict:
    """Processa a familia SAIDA_MERCADORIAS inteira do inventario atual, por
    PARTICAO (1..N partes cada), numa transacao SO (o cursor do chamador).
    Competencia anterior a `COMPETENCIA_MINIMA_SAIDA` (decisao D3 -- so 2026)
    fica FORA DE ESCOPO -- declarada no relatorio, nunca processada em
    silencio nem tratada como erro/pendencia.

    Uma transacao so e adequado pra teste e pra uso ocasional; a rodada real
    na VM (`scripts/processar_saida.py`, decisao D4) usa
    `listar_particoes_saida` + uma transacao POR particao, pra uma falha
    isolada nao derrubar as outras. Nao ha endpoint HTTP pra isto neste lote.
    """
    plano = listar_particoes_saida(cur, forcar=forcar)

    processados, erros = [], []
    emitidos: dict[tuple, str] = {}
    for partes in plano["particoes_pendentes"]:
        try:
            relatorio = processar_particao_saida(cur, [p["id"] for p in partes])
        except (
            saida_mercadorias.SaidaMercadoriasError,
            graph_datahub.GraphError,
            ProcessamentoDatahubError,
        ) as exc:
            erros.append({"arquivo": ", ".join(p["nome"] for p in partes), "erro": str(exc)})
            for arquivo in partes:
                _registrar_processamento(
                    cur, _origem(arquivo, saida_mercadorias.dados_da_familia),
                    "erro", detalhe=str(exc),
                )
            continue

        processados.append(relatorio)
        if relatorio["status"] not in _STATUS_TERMINAIS:
            continue
        chave = ("saida", relatorio["armazem_id"], relatorio["competencia"])
        anterior = emitidos.get(chave)
        if anterior is not None:
            raise ProcessamentoDatahubError(
                f"colisao de armazem: particao atual e '{anterior}' gravaram no mesmo "
                f"armazem na competencia {relatorio['competencia']} -- rodada abortada e "
                "revertida; conferir o de-para do conector sharepoint_datahub"
            )
        emitidos[chave] = ", ".join(relatorio["arquivos"])

    return {
        "total_familia": plano["total_familia"],
        "total_fora_de_escopo": len(plano["arquivos_fora_de_escopo"]),
        "arquivos_fora_de_escopo": plano["arquivos_fora_de_escopo"],
        "processados": processados,
        "pulados": plano["pulados"],
        "erros": erros,
    }


# =============================================================================
# Consultas pro painel do admin (comuns as duas familias)
# =============================================================================


def listar_processamentos(cur) -> list[dict]:
    """Estado corrente por arquivo, pro painel do admin.

    A unidade e o caminho vem junto porque o nome do arquivo deixou de ser
    unico na fonte: sem eles, dois homonimos de unidades diferentes ficam
    indistinguiveis na tela.
    """
    cur.execute(
        """
        SELECT arquivo, unidade, caminho, filial, competencia, status, detalhe,
               linhas_validas, medidas_gravadas, processado_em, layout_lido
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
            "layout_lido": r[10],
        }
        for r in cur.fetchall()
    ]


def listar_pendencias_filial(cur) -> list[dict]:
    """Pendencias de de-para do conector do DataHub, pro painel do admin --
    mesma tabela usada pelo upload manual.

    O que aparece aqui e o codigo de origem QUALIFICADO (`RMSPII/002`,
    `CWB3/001`, `SANCA/025`), nao o codigo de filial nu: e ele que precisa de
    decisao humana pra virar de-para.
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
    """Valores de `Nome Estoque`/`Estoque` que nao casaram com nenhuma
    palavra-chave (backend/services/tipo_estoque.py), pro painel do admin --
    mesmo padrao das pendencias de filial e de cliente (V2.2)."""
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
