"""Verificacao somente leitura da cobertura do DataHub em producao (lote V2.1,
estendida no V2.2 e no V2.3 -- saida).

Complementa o scripts/verificar_v1.py, que cobre a superficie HTTP (health,
gate de login, paginas fechadas). Este cobre o ESTADO DOS DADOS depois do
deploy: schema na revisao certa, de-para qualificado pela unidade, pendencias
visiveis, processamentos por unidade, os indices de `medidas` e, desde o
V2.3, o par entrada/saida de metricas e o recorte de escopo da saida (D3).

**Nao grava nada.** Os checks de banco sao SELECT; os de HTTP sao GET (mais o
POST de login e o de logout).

So stdlib (http.client + subprocess) de proposito, pela licao do verificar_v1:
o Python do HOST que roda o docker compose nao tem as dependencias do projeto
(nem psycopg2 nem alembic) -- `scripts/` nao e copiado pro container. Os checks
de banco vao pelo psql do proprio container do Postgres, que e como o runbook
(docs/DEPLOY.md) ja consulta o banco na VM.

Uso:
    ADMIN_PASSWORD=... python3 scripts/verificar_v2.py [URL_BASE]

URL_BASE default: http://localhost:8002. Saida: OK/FALHA/AVISO por item; codigo
de saida 0 se nada falhou, 1 se algo falhou. AVISO nao reprova -- e usado pra
estado que depende de acao humana (pendencia de de-para conhecida, arquivo ainda
nao processado), que nao e defeito de deploy.
"""

import http.client
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit

RAIZ = Path(__file__).resolve().parent.parent
SERVICO_DB = os.environ.get("SERVICO_DB", "nuvem-db")
USUARIO_DB = os.environ.get("POSTGRES_USER", "nuvem")
NOME_DB = os.environ.get("POSTGRES_DB", "nuvem")

# Origens que seguem SEM de-para por decisao, nao por esquecimento.
#
# `RMSPII/002` NAO entra: o de-para dela segue pendente por decisao da Maria, mas
# o codigo 002 so aparece em DADOS_GERAIS e OCORRENCIAS_ENTREGAS, que nao sao
# familias integradas -- nao existe arquivo de ENTRADA_MERCADORIAS da 002, entao
# ela nunca pode virar pendencia de PROCESSAMENTO. Estava na lista e o script
# avisava "pendencia esperada ausente" pra sempre, pedindo uma coisa impossivel
# (achado da primeira rodada real na VM, 06/ago/2026). Aviso que nunca sai treina
# quem le a ignorar a saida inteira.
#
# `RJ/004-003` SAIU desta lista no V2.3 (migration 0016_depara_rj): a RJ ganhou
# de-para junto do leitor da variante de 18 colunas. Se voltar a aparecer como
# pendencia, e regressao -- nao pendencia esperada.
PENDENCIAS_ESPERADAS: set[str] = set()

# De-para do conector sharepoint_datahub depois do V2.3
DEPARA_ESPERADO = {
    "RMSPII/001": "RMSPII",
    "RMSPII/015": "RMSPIII",
    "RMSPII/016": "RMSPIV",
    "CWB3/001": "CWBIII",
    "SANCA/025": "RMSPV",
    "RJ/004-003": "RMRJ",
}

INDICES_ESPERADOS = {"ix_medidas_metrica_competencia", "ix_medidas_metrica_cliente_competencia"}

# Metricas do DataHub apos o V2.3 (par de entrada + par de saida -- nao existe
# valor_mercadoria_saida, a fonte nao tem coluna de valor). Resolvidas contra
# o catalogo na hora, nunca assumidas -- ver o comentario no check que usa isto.
_METRICAS_DATAHUB = (
    "peso_bruto_entrada", "valor_mercadoria_entrada", "registros_entrada",
    "peso_bruto_saida", "registros_saida",
)
_METRICAS_DATAHUB_SQL = "(" + ", ".join(f"'{m}'" for m in _METRICAS_DATAHUB) + ")"

# Layouts sem coluna de cliente, conferidos no dado em 06/ago/2026 (V2.3):
# RMRJ na entrada (18 colunas) e RMSPV na saida (34 colunas). Usado pelo check
# de "zero celula de cliente nao nulo" abaixo.
UNIDADES_SEM_CLIENTE_ENTRADA = {"RMRJ"}
UNIDADES_SEM_CLIENTE_SAIDA = {"RMSPV"}

# Competencia minima da saida (decisao D3/07 -- so 2026)
COMPETENCIA_MINIMA_SAIDA = "2026-01-01"

TOTAL_ARQUIVOS_SAIDA_ESPERADO = 72

_FALHAS: list[str] = []


def _checar(descricao: str, ok: bool, detalhe: str = "") -> None:
    if ok:
        print(f"OK    {descricao}")
    else:
        print(f"FALHA {descricao}" + (f" -- {detalhe}" if detalhe else ""))
        _FALHAS.append(descricao)


def _avisar(descricao: str, detalhe: str = "") -> None:
    """Estado que depende de acao humana -- nao reprova o deploy."""
    print(f"AVISO {descricao}" + (f" -- {detalhe}" if detalhe else ""))


# --- banco (SELECT via psql do container) ------------------------------------


class ErroPsql(Exception):
    pass


def _sql(consulta: str) -> list[list[str]]:
    """Roda um SELECT pelo psql do container e devolve linhas de campos.

    -A (sem alinhamento) + -t (sem cabecalho) + -F '|' pra saida parseavel;
    ON_ERROR_STOP pra erro de SQL nao virar saida vazia silenciosa."""
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


def _revisao_head_dos_arquivos() -> str | None:
    """Head da cadeia de migrations lendo os arquivos: a revisao que nenhuma
    outra declara como down_revision. Sem alembic instalado no host."""
    revisoes, anteriores = set(), set()
    for arquivo in (RAIZ / "alembic" / "versions").glob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        rev = re.search(r'^revision\s*=\s*"([^"]+)"', texto, re.MULTILINE)
        down = re.search(r'^down_revision\s*=\s*"([^"]+)"', texto, re.MULTILINE)
        if rev:
            revisoes.add(rev.group(1))
        if down:
            anteriores.add(down.group(1))
    candidatos = revisoes - anteriores
    return candidatos.pop() if len(candidatos) == 1 else None


def verificar_banco() -> None:
    head = _revisao_head_dos_arquivos()
    atual = _sql("SELECT version_num FROM alembic_version")
    versao = atual[0][0] if atual else None
    _checar(
        f"alembic na revisao head ({head})",
        head is not None and versao == head,
        f"banco em {versao}",
    )

    unique = _sql(
        "SELECT conname FROM pg_constraint WHERE conrelid = 'processamentos_datahub'::regclass "
        "AND contype = 'u'"
    )
    nomes = {linha[0] for linha in unique}
    colunas = _sql(
        """
        SELECT a.attname FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.conrelid = 'processamentos_datahub'::regclass AND c.contype = 'u'
        """
    )
    _checar(
        "identidade do arquivo e o item_id (UNIQUE em processamentos_datahub)",
        {linha[0] for linha in colunas} == {"item_id"},
        f"constraints {nomes}, colunas {[l[0] for l in colunas]}",
    )

    depara = dict(
        (linha[0], linha[1])
        for linha in _sql(
            """
            SELECT d.armazem_na_fonte, a.sigla
            FROM depara_armazem d
            JOIN armazens a ON a.id = d.armazem_id
            JOIN conectores c ON c.id = d.conector_id
            WHERE c.tipo = 'sharepoint_datahub'
            """
        )
    )
    _checar(
        "de-para do DataHub completo e correto",
        depara == DEPARA_ESPERADO,
        f"encontrado {depara}",
    )
    nus = [origem for origem in depara if "/" not in origem]
    _checar(
        "nenhum de-para com codigo de filial nu (sem unidade)",
        not nus,
        f"codigos nus: {nus}",
    )

    indices = {
        linha[0] for linha in _sql("SELECT indexname FROM pg_indexes WHERE tablename = 'medidas'")
    }
    _checar(
        "indices de consulta em medidas criados",
        INDICES_ESPERADOS <= indices,
        f"faltando {sorted(INDICES_ESPERADOS - indices)}",
    )
    _checar(
        "indice redundante com a UNIQUE nao foi criado",
        "ix_medidas_metrica_armazem_competencia" not in indices,
        "o prefixo da UNIQUE medidas_celula_unica ja atende esse acesso",
    )

    # V2.2: tipo de estoque como dimensao --------------------------------------

    colunas_medidas = {
        linha[0] for linha in
        _sql("SELECT column_name FROM information_schema.columns WHERE table_name = 'medidas'")
    }
    _checar("coluna tipo_estoque existe em medidas", "tipo_estoque" in colunas_medidas)

    colunas_recebidas = {
        linha[0] for linha in _sql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'medidas_recebidas'"
        )
    }
    _checar(
        "coluna tipo_estoque existe em medidas_recebidas",
        "tipo_estoque" in colunas_recebidas,
    )

    colunas_unique_medidas = {
        linha[0] for linha in _sql(
            """
            SELECT a.attname FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
            WHERE c.conrelid = 'medidas'::regclass AND c.conname = 'medidas_celula_unica'
            """
        )
    }
    _checar(
        "UNIQUE de medidas cobre as 5 colunas (com tipo_estoque)",
        colunas_unique_medidas
        == {"metrica_id", "armazem_id", "competencia", "cliente_id", "tipo_estoque"},
        f"encontrado {sorted(colunas_unique_medidas)}",
    )

    # o guarda central do risco 4 (prune de orfas): se o escopo do prune tivesse
    # ficado estreito por tipo_estoque, celula de grao antigo (NULL) sobreviveria
    # ao lado da nova apos o primeiro reprocesso -- e o total dobraria em
    # silencio. Este check pega isso -- mas so como AVISO, nao FALHA: a propria
    # migration 0014 documenta que, entre o deploy (upgrade da migration) e o
    # "Processar arquivos" com FORCAR (dois passos manuais separados do
    # runbook), toda celula das metricas do DataHub fica com tipo_estoque NULL
    # por desenho -- "total certo, dimensao ausente", nao um defeito. Reprovar
    # o deploy por rodar o script antes do reprocesso confundiria rotina com erro.
    #
    # A lista e RESOLVIDA contra `metricas` (V2.3): antes era literal, e um
    # rename sem atualizar aqui fazia a consulta voltar VAZIA -- o `if
    # grao_misto` caia no ramo de sucesso e o check PASSAVA POR VACUIDADE,
    # aprovando um banco inteiro no grao antigo. Agora o script FALHA se a
    # lista nao resolver nenhuma metrica.
    metricas_datahub = [
        linha[0] for linha in _sql(f"SELECT nome FROM metricas WHERE nome IN {_METRICAS_DATAHUB_SQL}")
    ]
    if not metricas_datahub:
        _checar(
            "metricas do DataHub existem no catalogo (V2.3)",
            False,
            f"nenhuma de {_METRICAS_DATAHUB} encontrada -- rename sem seed/migration aplicada?",
        )
    else:
        lista_encontradas = "(" + ", ".join(f"'{m}'" for m in metricas_datahub) + ")"
        grao_misto = _sql(
            f"""
            SELECT mt.nome, COUNT(*) FROM medidas m
            JOIN metricas mt ON mt.id = m.metrica_id
            WHERE mt.nome IN {lista_encontradas}
              AND m.tipo_estoque IS NULL
            GROUP BY 1
            """
        )
        if grao_misto:
            _avisar(
                "celulas do DataHub ainda no grao antigo (tipo_estoque NULL)",
                f"{grao_misto} -- normal ate rodar 'Processar arquivos' com FORCAR; "
                "so e defeito se persistir depois do reprocesso",
            )
        else:
            _checar("nenhuma celula das metricas do DataHub com tipo_estoque NULL (grao misto)", True)

        distribuicao = _sql(
            f"""
            SELECT mt.nome, COALESCE(m.tipo_estoque, '(nulo)'), COUNT(*), ROUND(SUM(m.valor), 3)
            FROM medidas m
            JOIN metricas mt ON mt.id = m.metrica_id
            WHERE mt.nome IN {lista_encontradas}
            GROUP BY 1, 2 ORDER BY 1, 2
            """
        )
        print("\n      distribuicao por tipo de estoque:")
        for metrica, tipo, qtd, soma in distribuicao:
            print(f"        {metrica:<32} {tipo:<18} {qtd:>6} celula(s)   soma {soma}")
        print()

    # unidade NULL so e legitima em arquivo solto na raiz (sem galho de unidade)
    sem_unidade = _sql(
        "SELECT arquivo, caminho FROM processamentos_datahub "
        "WHERE unidade IS NULL AND caminho LIKE '%/%'"
    )
    _checar(
        "nenhum processamento com unidade NULL fora da raiz da pasta",
        not sem_unidade,
        f"{len(sem_unidade)} registro(s): {[l[0] for l in sem_unidade][:5]}",
    )

    por_unidade = _sql(
        "SELECT COALESCE(unidade, '(raiz)'), status, COUNT(*) "
        "FROM processamentos_datahub GROUP BY 1, 2 ORDER BY 1, 2"
    )
    erros = [(u, q) for u, s, q in por_unidade if s == "erro"]
    print("\n      processamentos por unidade e status:")
    for unidade, status, quantos in por_unidade:
        print(f"        {unidade:<8} {status:<18} {quantos}")
    # `sem_dado` conta como processado: competencia sem movimento e desfecho
    # terminal esperado (SANCA 2601-2605), nao pendencia de acao
    _checar(
        "nenhum arquivo com status erro",
        not erros,
        f"{erros} -- ver o detalhe no painel do DataHub",
    )
    unidades_ok = {u for u, s, _ in por_unidade if s in ("ok", "sem_dado")}
    for esperada in ("RMSPII", "CWB3", "SANCA"):
        if esperada in unidades_ok:
            _checar(f"{esperada} tem arquivo processado com status ok", True)
        else:
            _avisar(
                f"{esperada} sem arquivo processado com status ok",
                "rodar 'Processar arquivos' no painel do DataHub",
            )
    print()

    pendencias = {
        linha[0]
        for linha in _sql(
            "SELECT p.armazem_na_fonte FROM depara_pendencias p "
            "JOIN conectores c ON c.id = p.conector_id "
            "WHERE c.tipo = 'sharepoint_datahub'"
        )
    }
    inesperadas = pendencias - PENDENCIAS_ESPERADAS
    _checar(
        "nenhuma pendencia de de-para inesperada",
        not inesperadas,
        f"origens novas sem de-para: {sorted(inesperadas)}",
    )
    for esperada in sorted(PENDENCIAS_ESPERADAS & pendencias):
        _avisar(f"pendencia conhecida de de-para: {esperada}", "decisao humana, nao defeito")
    resolvidas = PENDENCIAS_ESPERADAS - pendencias
    if resolvidas:
        _avisar(
            f"pendencia esperada ausente: {sorted(resolvidas)}",
            "os arquivos dessa origem ainda nao foram processados, ou ela ganhou de-para",
        )

    pendencias_tipo_estoque = _sql(
        "SELECT tp.valor_na_fonte FROM tipo_estoque_pendencias tp "
        "JOIN conectores c ON c.id = tp.conector_id "
        "WHERE c.tipo = 'sharepoint_datahub'"
    )
    for (valor,) in pendencias_tipo_estoque:
        _avisar(
            f"valor de 'Nome Estoque' nao classificado: {valor}",
            "decisao humana (revisar palavra-chave em tipo_estoque.py), nao defeito",
        )


def verificar_saida() -> None:
    """Checks especificos do V2.3 -- rename das metricas, isolamento entre
    entrada e saida, e o recorte de escopo da saida (decisao D3, so 2026).
    """
    metricas_existentes = {
        linha[0]
        for linha in _sql(f"SELECT nome FROM metricas WHERE nome IN {_METRICAS_DATAHUB_SQL}")
    }
    _checar(
        "as 5 metricas do par entrada/saida existem no catalogo",
        metricas_existentes == set(_METRICAS_DATAHUB),
        f"faltando: {sorted(set(_METRICAS_DATAHUB) - metricas_existentes)}",
    )

    sem_conceito = _sql(
        f"""
        SELECT mt.nome FROM metricas mt
        LEFT JOIN conceitos_canonicos cc ON cc.chave = mt.nome
            AND cc.status = 'aprovado' AND cc.unidade_canonica IS NOT NULL
        WHERE mt.nome IN {_METRICAS_DATAHUB_SQL} AND cc.id IS NULL
        """
    )
    _checar(
        "as 5 metricas tem conceito canonico aprovado com unidade definida",
        not sem_conceito,
        f"sem conceito aprovado com unidade: {[l[0] for l in sem_conceito]}",
    )

    # nenhuma celula de metrica de saida em armazem sem de-para: se a metrica
    # foi gravada, o armazem_id ja passou pelo de-para no momento da escrita
    # (ingestao.resolver_armazem) -- este check prova isso pelo dado, nao
    # confiando so no codigo
    orfas = _sql(
        """
        SELECT mt.nome, COUNT(*) FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        LEFT JOIN depara_armazem d ON d.armazem_id = m.armazem_id
         AND d.conector_id = (SELECT id FROM conectores WHERE tipo = 'sharepoint_datahub')
        WHERE mt.nome IN ('peso_bruto_saida', 'registros_saida') AND d.id IS NULL
        GROUP BY 1
        """
    )
    _checar(
        "nenhuma celula de saida em armazem sem de-para",
        not orfas,
        f"{orfas}",
    )

    # RMRJ (entrada) e RMSPV (saida) sao os layouts sem coluna de cliente
    # (conferido no dado, 06/ago/2026) -- se aparecer celula de cliente NAO
    # NULO nessas origens, o leitor casou o layout errado (leu Cliente/Cliente
    # CNPJ de colunas que nao existem, ou o de-para mudou sem o leitor
    # acompanhar)
    vazamento_entrada = _sql(
        """
        SELECT COUNT(*) FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        JOIN armazens a ON a.id = m.armazem_id
        WHERE mt.nome = 'peso_bruto_entrada' AND a.sigla = 'RMRJ' AND m.cliente_id IS NOT NULL
        """
    )
    _checar(
        "RMRJ (entrada, layout de 18 colunas) sem nenhuma celula com cliente identificado",
        vazamento_entrada[0][0] == "0",
        f"{vazamento_entrada[0][0]} celula(s) com cliente -- leitor pode ter casado o layout errado",
    )
    vazamento_saida = _sql(
        """
        SELECT COUNT(*) FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        JOIN armazens a ON a.id = m.armazem_id
        WHERE mt.nome = 'peso_bruto_saida' AND a.sigla = 'RMSPV' AND m.cliente_id IS NOT NULL
        """
    )
    _checar(
        "RMSPV (saida, layout de 34 colunas) sem nenhuma celula com cliente identificado",
        vazamento_saida[0][0] == "0",
        f"{vazamento_saida[0][0]} celula(s) com cliente -- leitor pode ter casado o layout errado",
    )

    # decisao D3 -- so 2026: nenhuma celula de saida em competencia anterior
    fora_de_escopo = _sql(
        f"""
        SELECT COUNT(*) FROM medidas m
        JOIN metricas mt ON mt.id = m.metrica_id
        WHERE mt.nome IN ('peso_bruto_saida', 'registros_saida')
          AND m.competencia < '{COMPETENCIA_MINIMA_SAIDA}'
        """
    )
    _checar(
        "nenhuma celula de saida em competencia anterior a 2026 (decisao D3)",
        fora_de_escopo[0][0] == "0",
        f"{fora_de_escopo[0][0]} celula(s) fora do recorte -- escopo D3 nao respeitado",
    )

    # toda particao com status terminal tem TODAS as partes terminais -- nunca
    # metade ok, metade pendencia_depara/erro (a particao e processada como
    # unidade so, ver processamento_datahub.processar_particao_saida)
    particoes_mistas = _sql(
        """
        SELECT unidade, filial, competencia, COUNT(DISTINCT status) AS estados
        FROM processamentos_datahub
        WHERE arquivo LIKE 'SAIDA_MERCADORIAS%'
        GROUP BY 1, 2, 3
        HAVING COUNT(DISTINCT status) > 1
        """
    )
    _checar(
        "nenhuma particao de saida com partes em status diferentes",
        not particoes_mistas,
        f"{particoes_mistas}",
    )

    total_saida_ok = _sql(
        """
        SELECT COUNT(*) FROM processamentos_datahub
        WHERE arquivo LIKE 'SAIDA_MERCADORIAS%' AND status IN ('ok', 'sem_dado')
        """
    )
    quantos = int(total_saida_ok[0][0])
    if quantos == 0:
        _avisar(
            "nenhum arquivo de SAIDA_MERCADORIAS processado ainda",
            "rodar 'docker compose exec nuvem-app python scripts/processar_saida.py'",
        )
    elif quantos != TOTAL_ARQUIVOS_SAIDA_ESPERADO:
        _avisar(
            f"{quantos} arquivo(s) de saida processado(s), esperado {TOTAL_ARQUIVOS_SAIDA_ESPERADO}",
            "a fonte pode ter ganho/perdido arquivo desde a conferencia de 06/ago/2026 -- "
            "conferir antes de tratar como defeito",
        )
    else:
        _checar(
            f"contagem de arquivos de saida processados bate com o esperado ({TOTAL_ARQUIVOS_SAIDA_ESPERADO})",
            True,
        )


# --- HTTP (GET nas telas e endpoints de leitura) ------------------------------


def _requisitar(hostname, porta, https, metodo, caminho, corpo=None, cookie=None):
    classe = http.client.HTTPSConnection if https else http.client.HTTPConnection
    conn = classe(hostname, porta, timeout=15)
    try:
        cabecalhos = {}
        if cookie:
            cabecalhos["Cookie"] = cookie
        if corpo is not None:
            cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
        conn.request(metodo, caminho, body=corpo, headers=cabecalhos)
        resposta = conn.getresponse()
        corpo_resposta = resposta.read()
        return (
            resposta.status,
            {c.lower(): v for c, v in resposta.getheaders()},
            corpo_resposta,
        )
    finally:
        conn.close()


def verificar_http(url_base: str, senha: str) -> None:
    partes = urlsplit(url_base)
    https = partes.scheme == "https"
    hostname, porta = partes.hostname, partes.port

    status, cabecalhos, _ = _requisitar(
        hostname, porta, https, "POST", "/api/admin/login", corpo=urlencode({"senha": senha})
    )
    cookie = cabecalhos.get("set-cookie", "").split(";", 1)[0] or None
    if status != 200 or cookie is None:
        _checar("login do admin", False, f"status {status}")
        return
    _checar("login do admin", True)

    for caminho in (
        "/api/admin/datahub/processamentos",
        "/api/admin/datahub/nuvem",
        "/api/admin/cockpit/qualidade",
    ):
        status, _, corpo = _requisitar(hostname, porta, https, "GET", caminho, cookie=cookie)
        _checar(f"GET {caminho} responde 200", status == 200, f"status {status}")

    _requisitar(hostname, porta, https, "POST", "/api/admin/logout", corpo="", cookie=cookie)


def main() -> int:
    url_base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
    senha = os.environ.get("ADMIN_PASSWORD")

    print(f"Verificando a cobertura do DataHub em {url_base} (somente leitura)\n")

    print("-- banco --")
    try:
        verificar_banco()
    except ErroPsql as exc:
        _checar("consultar o banco pelo psql do container", False, str(exc))

    print("\n-- saida (V2.3) --")
    try:
        verificar_saida()
    except ErroPsql as exc:
        _checar("consultar o banco pelo psql do container (saida)", False, str(exc))

    print("\n-- HTTP --")
    if not senha:
        _avisar("ADMIN_PASSWORD nao definida", "checks de HTTP pulados")
    else:
        try:
            verificar_http(url_base, senha)
        except (OSError, http.client.HTTPException) as exc:
            # HTTPException (resposta malformada, BadStatusLine) NAO e OSError --
            # sem ele um servidor respondendo lixo dava traceback em vez de FALHA
            _checar(f"falar com {url_base}", False, f"{type(exc).__name__}: {exc}")

    print()
    if _FALHAS:
        print(f"{len(_FALHAS)} item(ns) com FALHA:")
        for item in _FALHAS:
            print(f"  - {item}")
        return 1
    print("Nenhuma falha.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
