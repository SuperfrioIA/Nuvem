import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse

from .. import armazenamento, ingestao, motor, versoes
from ..auth import (
    autenticado,
    criar_sessao,
    encerrar_sessao,
    exigir_login,
    ip_do_cliente,
    registrar_falha_login,
    registrar_sucesso_login,
    senha_confere,
    verificar_bloqueio_login,
)
from ..conectores import upload_manual
from ..database import get_conn
from ..services import auditoria, cache_consulta

logger = logging.getLogger("nuvem.admin")

# Publicas (login precisa ser alcancavel sem sessao; /me e consultado pelo
# proprio JS de login pra saber se ja esta autenticado). Bloco G / G2:
# gate por Depends nas demais rotas, nao mais chamada imperativa em cada
# handler -- rota nova esquecida de gatear deixa de ser possivel por
# construcao.
router_publico = APIRouter()
router = APIRouter(dependencies=[Depends(exigir_login)])


async def _ler_upload(arquivo: UploadFile) -> bytes:
    """Le o arquivo do upload respeitando o limite de tamanho (Lote R0).

    Limite configuravel por UPLOAD_MAX_MB (default 50 — o maior arquivo real da
    POC, o fato de volumetria, tem ~30 MB). Lido aqui (na chamada, nao no
    import) pra ser ajustavel por ambiente e testavel."""
    limite_mb = int(os.environ.get("UPLOAD_MAX_MB", "50"))
    limite = limite_mb * 1024 * 1024
    conteudo = await arquivo.read(limite + 1)
    if len(conteudo) > limite:
        raise HTTPException(
            status_code=413,
            detail=f"arquivo maior que o limite de {limite_mb} MB (UPLOAD_MAX_MB)",
        )
    return conteudo


@router_publico.post("/login")
def login(request: Request, response: Response, senha: str = Form(...)):
    ip = ip_do_cliente(request)
    try:
        verificar_bloqueio_login(request)
    except HTTPException:
        with get_conn() as conn, conn.cursor() as cur:
            auditoria.registrar(cur, "login_bloqueado", ip=ip)
        raise
    if not senha_confere(senha):
        registrar_falha_login(request)
        with get_conn() as conn, conn.cursor() as cur:
            auditoria.registrar(cur, "login_falha", ip=ip)
        raise HTTPException(status_code=401, detail="senha incorreta")
    registrar_sucesso_login(request)
    criar_sessao(response)
    with get_conn() as conn, conn.cursor() as cur:
        auditoria.registrar(cur, "login_sucesso", ip=ip)
    return {"ok": True}


@router_publico.post("/logout")
def logout(request: Request, response: Response):
    encerrar_sessao(response)
    with get_conn() as conn, conn.cursor() as cur:
        auditoria.registrar(cur, "logout", ip=ip_do_cliente(request))
    return {"ok": True}


@router_publico.get("/me")
def me(request: Request):
    return {"autenticado": autenticado(request)}


@router.get("/conectores")
def listar_conectores():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, tipo, nome, ativo FROM conectores ORDER BY nome")
        return [{"id": r[0], "tipo": r[1], "nome": r[2], "ativo": r[3]} for r in cur.fetchall()]


@router.get("/armazens")
def listar_armazens():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, nome, sigla FROM armazens WHERE ativo ORDER BY nome")
        return [{"id": r[0], "nome": r[1], "sigla": r[2]} for r in cur.fetchall()]


@router.post("/armazens")
def criar_armazem(request: Request, nome: str = Form(...), sigla: str = Form(...)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO armazens (nome, sigla) VALUES (%s, %s) RETURNING id",
            (nome, sigla),
        )
        armazem_id = cur.fetchone()[0]
        auditoria.registrar(
            cur, "armazem_criado", detalhe={"nome": nome, "sigla": sigla}, ip=ip_do_cliente(request)
        )
        return {"id": armazem_id}


@router.get("/clientes")
def listar_clientes():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, nk_erp, nome, catering FROM clientes ORDER BY nome")
        return [{"id": r[0], "nk_erp": r[1], "nome": r[2], "catering": r[3]} for r in cur.fetchall()]


@router.get("/depara")
def listar_depara():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.armazem_na_fonte, d.armazem_id, a.nome, c.id, c.nome
            FROM depara_armazem d
            JOIN armazens a ON a.id = d.armazem_id
            JOIN conectores c ON c.id = d.conector_id
            ORDER BY c.nome, d.armazem_na_fonte
            """
        )
        return [
            {
                "id": r[0],
                "armazem_na_fonte": r[1],
                "armazem_id": r[2],
                "armazem_nome": r[3],
                "conector_id": r[4],
                "conector_nome": r[5],
            }
            for r in cur.fetchall()
        ]


@router.post("/depara")
def criar_depara(
    request: Request,
    conector_id: int = Form(...),
    armazem_na_fonte: str = Form(...),
    armazem_id: int = Form(...),
):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (conector_id, armazem_na_fonte) DO UPDATE SET armazem_id = EXCLUDED.armazem_id
            RETURNING id
            """,
            (conector_id, armazem_na_fonte, armazem_id),
        )
        novo_id = cur.fetchone()[0]
        cur.execute(
            "DELETE FROM depara_pendencias WHERE conector_id = %s AND armazem_na_fonte = %s",
            (conector_id, armazem_na_fonte),
        )
        auditoria.registrar(
            cur,
            "depara_criado",
            detalhe={
                "conector_id": conector_id,
                "armazem_na_fonte": armazem_na_fonte,
                "armazem_id": armazem_id,
            },
            ip=ip_do_cliente(request),
        )
    # V2.7: o de-para novo apaga a pendencia -- sem invalidar, o admin que
    # acabou de cadastrar continuaria vendo a pendencia no Cockpit por ate um
    # TTL e concluiria que o cadastro nao funcionou.
    cache_consulta.invalidar("de-para criado")
    return {"id": novo_id}


@router.delete("/depara/{depara_id}")
def apagar_depara(request: Request, depara_id: int):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM depara_armazem WHERE id = %s", (depara_id,))
        auditoria.registrar(cur, "depara_apagado", detalhe={"depara_id": depara_id}, ip=ip_do_cliente(request))
    cache_consulta.invalidar("de-para apagado")
    return {"ok": True}


@router.get("/pendencias")
def listar_pendencias():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.armazem_na_fonte, c.id, c.nome, p.primeira_vez_em, p.ultima_vez_em
            FROM depara_pendencias p
            JOIN conectores c ON c.id = p.conector_id
            ORDER BY p.ultima_vez_em DESC
            """
        )
        return [
            {
                "id": r[0],
                "armazem_na_fonte": r[1],
                "conector_id": r[2],
                "conector_nome": r[3],
                "primeira_vez_em": r[4].isoformat(),
                "ultima_vez_em": r[5].isoformat(),
            }
            for r in cur.fetchall()
        ]


@router.get("/modelos")
def listar_modelos(conector_id: int | None = None):
    with get_conn() as conn, conn.cursor() as cur:
        if conector_id:
            cur.execute(
                "SELECT id, nome, mapeamento, fonte_id FROM modelos_importacao WHERE ativo AND conector_id = %s ORDER BY nome",
                (conector_id,),
            )
        else:
            cur.execute("SELECT id, nome, mapeamento, fonte_id FROM modelos_importacao WHERE ativo ORDER BY nome")
        return [{"id": r[0], "nome": r[1], "mapeamento": r[2], "fonte_id": r[3]} for r in cur.fetchall()]


@router.get("/modelos/{modelo_id}/versoes")
def listar_versoes(modelo_id: int):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, versao, hash_config, ativo, padrao, criado_em
            FROM modelo_versoes WHERE modelo_id = %s ORDER BY versao DESC
            """,
            (modelo_id,),
        )
        return [
            {
                "id": r[0],
                "versao": r[1],
                "hash_config": r[2],
                "ativo": r[3],
                "padrao": r[4],
                "criado_em": r[5].isoformat() if r[5] else None,
            }
            for r in cur.fetchall()
        ]


@router.post("/modelos/{modelo_id}/versoes")
def criar_versao_modelo(modelo_id: int, mapeamento_json: str = Form(...)):
    """Editar um modelo = criar uma versao nova. A configuracao historica nunca e
    alterada; a versao nova vira a padrao (usada por uploads novos). Execucoes
    antigas seguem apontando pra versao que usaram (nao muda resultado historico)."""
    try:
        mapeamento = json.loads(mapeamento_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"mapeamento_json invalido: {e}")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM modelos_importacao WHERE id = %s", (modelo_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="modelo nao encontrado")
        versao_id, numero = versoes.criar_versao(cur, modelo_id, mapeamento, padrao=True)
    return {"versao_id": versao_id, "versao": numero}


@router.post("/upload/preview")
async def upload_preview(arquivo: UploadFile = File(...)):
    conteudo = await _ler_upload(arquivo)
    try:
        return upload_manual.preview(conteudo, arquivo.filename)
    except Exception as e:
        logger.warning("falha ao pre-visualizar upload %s: %s", arquivo.filename, e)
        raise HTTPException(status_code=400, detail="não foi possível ler o arquivo enviado") from e


@router.post("/upload/processar")
async def upload_processar(
    arquivo: UploadFile = File(...),
    modelo_id: int | None = Form(None),
    nome_novo_modelo: str | None = Form(None),
    mapeamento_json: str | None = Form(None),
    fonte_id: int | None = Form(None),
):
    conteudo = await _ler_upload(arquivo)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM conectores WHERE tipo = 'upload_manual'")
        conector_id = cur.fetchone()[0]

        if modelo_id:
            # upload novo com modelo salvo: usa a versao ativa/padrao do modelo
            versao = versoes.resolver_versao_padrao(cur, modelo_id)
            if versao is None:
                raise HTTPException(status_code=404, detail="modelo nao encontrado ou sem versao ativa/padrao")
            modelo_versao_id, mapeamento = versao
        else:
            if not mapeamento_json or not nome_novo_modelo:
                raise HTTPException(
                    status_code=400, detail="informe modelo_id ou mapeamento_json + nome_novo_modelo"
                )
            mapeamento = json.loads(mapeamento_json)
            cur.execute(
                "INSERT INTO modelos_importacao (conector_id, nome, mapeamento, fonte_id) VALUES (%s, %s, %s, %s) RETURNING id",
                (conector_id, nome_novo_modelo, json.dumps(mapeamento), fonte_id),
            )
            modelo_id = cur.fetchone()[0]
            # modelo novo nasce com a versao 1 (ativa e padrao)
            modelo_versao_id, _ = versoes.criar_versao(cur, modelo_id, mapeamento, padrao=True)
            # se veio ligado a uma fonte logica, o catalogo passa a listar as execucoes
            if fonte_id:
                cur.execute(
                    "UPDATE catalogo_fontes SET modelo_id = %s WHERE id = %s AND modelo_id IS NULL",
                    (modelo_id, fonte_id),
                )

        arquivo_path = armazenamento.salvar_arquivo(conteudo, arquivo.filename)
        execucao_id = ingestao.iniciar_execucao(
            cur, conector_id, modelo_id, modelo_versao_id, "manual", arquivo_path
        )

    try:
        agregados, linhas_lidas = upload_manual.aplicar_modelo(conteudo, mapeamento, arquivo.filename)
    except Exception as e:
        logger.warning("falha ao processar upload %s (execucao %s): %s", arquivo.filename, execucao_id, e)
        with get_conn() as conn, conn.cursor() as cur:
            ingestao.finalizar_execucao(cur, execucao_id, "erro", erro=str(e))
        raise HTTPException(status_code=400, detail="erro ao processar arquivo") from e

    try:
        with get_conn() as conn, conn.cursor() as cur:
            linhas_gravadas = ingestao.gravar_agregados(cur, conector_id, execucao_id, agregados)
            ingestao.finalizar_execucao(cur, execucao_id, "ok", linhas_lidas, linhas_gravadas)
    except ValueError as e:
        with get_conn() as conn, conn.cursor() as cur:
            ingestao.finalizar_execucao(cur, execucao_id, "erro", erro=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    with get_conn() as conn, conn.cursor() as cur:
        motor.calcular_scores(cur)

    # V2.7 (achado da revisao independente): o upload manual grava em `medidas`
    # (ingestao.gravar_agregados), entao o Cockpit tem que ver o numero novo
    # assim que a resposta diz "linhas_gravadas: N" -- era o mesmo raciocinio do
    # de-para, e este caminho tinha ficado de fora.
    cache_consulta.invalidar("upload manual processado")
    return {
        "execucao_id": execucao_id,
        "modelo_id": modelo_id,
        "modelo_versao_id": modelo_versao_id,
        "linhas_lidas": linhas_lidas,
        "linhas_gravadas": linhas_gravadas,
        "pendencias": linhas_lidas - linhas_gravadas if linhas_lidas else 0,
    }


@router.post("/execucoes/{execucao_id}/reprocessar")
def reprocessar_execucao(execucao_id: int):
    """Reprocessa uma execucao antiga a partir do arquivo retido, usando a MESMA
    versao de modelo que ela usou originalmente — nunca a versao mais nova. Criar
    uma versao nova (v2, v3...) portanto nao muda o resultado de reprocessar uma
    execucao antiga. Gera uma execucao nova (origem 'reprocessamento') amarrada a
    versao original."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT conector_id, modelo_id, modelo_versao_id, arquivo_path FROM execucoes WHERE id = %s",
            (execucao_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="execucao nao encontrada")
        conector_id, modelo_id, modelo_versao_id, arquivo_path = row
        if modelo_versao_id is None:
            raise HTTPException(
                status_code=400,
                detail="execucao sem versao registrada (anterior ao R1) — reprocessamento exige a versao original",
            )
        if not arquivo_path:
            raise HTTPException(status_code=404, detail="execucao sem arquivo retido para reprocessar")
        mapeamento = versoes.carregar_versao(cur, modelo_versao_id)
        if mapeamento is None:
            raise HTTPException(status_code=404, detail="versao do modelo nao encontrada")
        nova_execucao_id = ingestao.iniciar_execucao(
            cur, conector_id, modelo_id, modelo_versao_id, "reprocessamento", arquivo_path
        )

    nome_arquivo = Path(arquivo_path).name
    try:
        conteudo = armazenamento.ler_arquivo(arquivo_path)
        agregados, linhas_lidas = upload_manual.aplicar_modelo(conteudo, mapeamento, nome_arquivo)
    except Exception as e:
        logger.warning("falha ao reprocessar execucao %s (arquivo %s): %s", execucao_id, nome_arquivo, e)
        with get_conn() as conn, conn.cursor() as cur:
            ingestao.finalizar_execucao(cur, nova_execucao_id, "erro", erro=str(e))
        raise HTTPException(status_code=400, detail="erro ao reprocessar arquivo") from e

    try:
        with get_conn() as conn, conn.cursor() as cur:
            linhas_gravadas = ingestao.gravar_agregados(cur, conector_id, nova_execucao_id, agregados)
            ingestao.finalizar_execucao(cur, nova_execucao_id, "ok", linhas_lidas, linhas_gravadas)
    except ValueError as e:
        with get_conn() as conn, conn.cursor() as cur:
            ingestao.finalizar_execucao(cur, nova_execucao_id, "erro", erro=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    cache_consulta.invalidar("execucao reprocessada")

    with get_conn() as conn, conn.cursor() as cur:
        motor.calcular_scores(cur)

    return {
        "execucao_id": nova_execucao_id,
        "reprocessou": execucao_id,
        "modelo_id": modelo_id,
        "modelo_versao_id": modelo_versao_id,
        "linhas_lidas": linhas_lidas,
        "linhas_gravadas": linhas_gravadas,
    }


@router.get("/execucoes")
def listar_execucoes():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id, c.nome, e.origem, e.status, e.iniciado_em, e.finalizado_em,
                   e.linhas_lidas, e.linhas_gravadas, e.erro, e.arquivo_path
            FROM execucoes e
            LEFT JOIN conectores c ON c.id = e.conector_id
            ORDER BY e.iniciado_em DESC
            LIMIT 100
            """
        )
        return [
            {
                "id": r[0],
                "conector_nome": r[1],
                "origem": r[2],
                "status": r[3],
                "iniciado_em": r[4].isoformat() if r[4] else None,
                "finalizado_em": r[5].isoformat() if r[5] else None,
                "linhas_lidas": r[6],
                "linhas_gravadas": r[7],
                "erro": r[8],
                "tem_arquivo": bool(r[9]),
            }
            for r in cur.fetchall()
        ]


@router.post("/scores/recalcular")
def recalcular_scores():
    with get_conn() as conn, conn.cursor() as cur:
        gravados = motor.calcular_scores(cur)
    return {"scores_gravados": gravados}


@router.get("/scores")
def listar_scores():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.competencia, m.nome, a.nome, a.sigla,
                   s.media, s.desvio_padrao, s.z_score, s.estado, s.calculado_em
            FROM scores s
            JOIN metricas m ON m.id = s.metrica_id
            JOIN armazens a ON a.id = s.armazem_id
            ORDER BY s.competencia DESC, m.nome, a.nome
            """
        )
        return [
            {
                "competencia": r[0].isoformat(),
                "metrica": r[1],
                "armazem": r[2],
                "armazem_sigla": r[3],
                "media": float(r[4]) if r[4] is not None else None,
                "desvio_padrao": float(r[5]) if r[5] is not None else None,
                "z_score": float(r[6]) if r[6] is not None else None,
                "estado": r[7],
                "calculado_em": r[8].isoformat(),
            }
            for r in cur.fetchall()
        ]


@router.get("/metricas")
def listar_metricas():
    """Catalogo semantico das metricas (Lote R3) — read-only."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, nome, nome_executivo, unidade, dominio, descricao,
                   granularidade_esperada, periodicidade, tipo, direcao_risco,
                   agregacao_padrao, comparabilidade, ativo
            FROM metricas
            ORDER BY dominio NULLS LAST, nome
            """
        )
        return [
            {
                "id": r[0],
                "nome": r[1],
                "nome_executivo": r[2],
                "unidade": r[3],
                "dominio": r[4],
                "descricao": r[5],
                "granularidade_esperada": r[6],
                "periodicidade": r[7],
                "tipo": r[8],
                "direcao_risco": r[9],
                "agregacao_padrao": r[10],
                "comparabilidade": r[11],
                "ativo": r[12],
            }
            for r in cur.fetchall()
        ]


@router.get("/catalogo")
def listar_catalogo():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, chave, nome, descricao, tabela_origem, tipo_origem, grao, modelo_id
            FROM catalogo_fontes
            ORDER BY nome
            """
        )
        return [
            {
                "id": r[0],
                "chave": r[1],
                "nome": r[2],
                "descricao": r[3],
                "tabela_origem": r[4],
                "tipo_origem": r[5],
                "grao": r[6],
                "modelo_id": r[7],
            }
            for r in cur.fetchall()
        ]


@router.get("/catalogo/{fonte_id}")
def detalhe_catalogo(fonte_id: int):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, chave, nome, descricao, tabela_origem, tipo_origem, grao, modelo_id
            FROM catalogo_fontes
            WHERE id = %s
            """,
            (fonte_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="fonte não encontrada")
        fonte = {
            "id": row[0],
            "chave": row[1],
            "nome": row[2],
            "descricao": row[3],
            "tabela_origem": row[4],
            "tipo_origem": row[5],
            "grao": row[6],
            "modelo_id": row[7],
        }

        cur.execute(
            "SELECT id, coluna, significado, papel FROM catalogo_colunas WHERE fonte_id = %s ORDER BY id",
            (fonte_id,),
        )
        fonte["colunas"] = [
            {"id": r[0], "coluna": r[1], "significado": r[2], "papel": r[3]} for r in cur.fetchall()
        ]

        if fonte["modelo_id"]:
            cur.execute(
                """
                SELECT id, origem, status, iniciado_em, finalizado_em,
                       linhas_lidas, linhas_gravadas, erro, arquivo_path
                FROM execucoes
                WHERE modelo_id = %s
                ORDER BY iniciado_em DESC
                """,
                (fonte["modelo_id"],),
            )
            fonte["execucoes"] = [
                {
                    "id": r[0],
                    "origem": r[1],
                    "status": r[2],
                    "iniciado_em": r[3].isoformat() if r[3] else None,
                    "finalizado_em": r[4].isoformat() if r[4] else None,
                    "linhas_lidas": r[5],
                    "linhas_gravadas": r[6],
                    "erro": r[7],
                    "tem_arquivo": bool(r[8]),
                }
                for r in cur.fetchall()
            ]
        else:
            fonte["execucoes"] = []

        return fonte


@router.get("/execucoes/{execucao_id}/arquivo")
def baixar_arquivo_execucao(request: Request, execucao_id: int):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT arquivo_path FROM execucoes WHERE id = %s", (execucao_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="arquivo não encontrado")
        auditoria.registrar(
            cur, "download_arquivo_execucao", detalhe={"execucao_id": execucao_id}, ip=ip_do_cliente(request)
        )
    return FileResponse(row[0], filename=f"execucao_{execucao_id}.xlsx")
