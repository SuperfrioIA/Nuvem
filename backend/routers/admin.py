import json
import os

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse

from .. import armazenamento, ingestao, motor
from ..auth import autenticado, criar_sessao, encerrar_sessao, exigir_login, senha_confere
from ..conectores import upload_manual
from ..database import get_conn

router = APIRouter()


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


@router.post("/login")
def login(response: Response, senha: str = Form(...)):
    if not senha_confere(senha):
        raise HTTPException(status_code=401, detail="senha incorreta")
    criar_sessao(response)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    encerrar_sessao(response)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    return {"autenticado": autenticado(request)}


@router.get("/conectores")
def listar_conectores(request: Request):
    exigir_login(request)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, tipo, nome, ativo FROM conectores ORDER BY nome")
        return [{"id": r[0], "tipo": r[1], "nome": r[2], "ativo": r[3]} for r in cur.fetchall()]


@router.get("/armazens")
def listar_armazens(request: Request):
    exigir_login(request)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, nome, sigla FROM armazens WHERE ativo ORDER BY nome")
        return [{"id": r[0], "nome": r[1], "sigla": r[2]} for r in cur.fetchall()]


@router.post("/armazens")
def criar_armazem(request: Request, nome: str = Form(...), sigla: str = Form(...)):
    exigir_login(request)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO armazens (nome, sigla) VALUES (%s, %s) RETURNING id",
            (nome, sigla),
        )
        return {"id": cur.fetchone()[0]}


@router.get("/clientes")
def listar_clientes(request: Request):
    exigir_login(request)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, nk_erp, nome, catering FROM clientes ORDER BY nome")
        return [{"id": r[0], "nk_erp": r[1], "nome": r[2], "catering": r[3]} for r in cur.fetchall()]


@router.get("/depara")
def listar_depara(request: Request):
    exigir_login(request)
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
    exigir_login(request)
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
        return {"id": novo_id}


@router.delete("/depara/{depara_id}")
def apagar_depara(request: Request, depara_id: int):
    exigir_login(request)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM depara_armazem WHERE id = %s", (depara_id,))
    return {"ok": True}


@router.get("/pendencias")
def listar_pendencias(request: Request):
    exigir_login(request)
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
def listar_modelos(request: Request, conector_id: int | None = None):
    exigir_login(request)
    with get_conn() as conn, conn.cursor() as cur:
        if conector_id:
            cur.execute(
                "SELECT id, nome, mapeamento FROM modelos_importacao WHERE ativo AND conector_id = %s ORDER BY nome",
                (conector_id,),
            )
        else:
            cur.execute("SELECT id, nome, mapeamento FROM modelos_importacao WHERE ativo ORDER BY nome")
        return [{"id": r[0], "nome": r[1], "mapeamento": r[2]} for r in cur.fetchall()]


@router.post("/upload/preview")
async def upload_preview(request: Request, arquivo: UploadFile = File(...)):
    exigir_login(request)
    conteudo = await _ler_upload(arquivo)
    try:
        return upload_manual.preview(conteudo, arquivo.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"não foi possível ler o arquivo: {e}")


@router.post("/upload/processar")
async def upload_processar(
    request: Request,
    arquivo: UploadFile = File(...),
    modelo_id: int | None = Form(None),
    nome_novo_modelo: str | None = Form(None),
    mapeamento_json: str | None = Form(None),
):
    exigir_login(request)
    conteudo = await _ler_upload(arquivo)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM conectores WHERE tipo = 'upload_manual'")
        conector_id = cur.fetchone()[0]

        if modelo_id:
            cur.execute("SELECT mapeamento FROM modelos_importacao WHERE id = %s", (modelo_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="modelo não encontrado")
            mapeamento = row[0]
        else:
            if not mapeamento_json or not nome_novo_modelo:
                raise HTTPException(
                    status_code=400, detail="informe modelo_id ou mapeamento_json + nome_novo_modelo"
                )
            mapeamento = json.loads(mapeamento_json)
            cur.execute(
                "INSERT INTO modelos_importacao (conector_id, nome, mapeamento) VALUES (%s, %s, %s) RETURNING id",
                (conector_id, nome_novo_modelo, json.dumps(mapeamento)),
            )
            modelo_id = cur.fetchone()[0]

        arquivo_path = armazenamento.salvar_arquivo(conteudo, arquivo.filename)
        execucao_id = ingestao.iniciar_execucao(cur, conector_id, modelo_id, "manual", arquivo_path)

    try:
        agregados, linhas_lidas = upload_manual.aplicar_modelo(conteudo, mapeamento, arquivo.filename)
    except Exception as e:
        with get_conn() as conn, conn.cursor() as cur:
            ingestao.finalizar_execucao(cur, execucao_id, "erro", erro=str(e))
        raise HTTPException(status_code=400, detail=f"erro ao processar arquivo: {e}")

    with get_conn() as conn, conn.cursor() as cur:
        linhas_gravadas = ingestao.gravar_agregados(cur, conector_id, agregados)
        ingestao.finalizar_execucao(cur, execucao_id, "ok", linhas_lidas, linhas_gravadas)

    with get_conn() as conn, conn.cursor() as cur:
        motor.calcular_scores(cur)

    return {
        "execucao_id": execucao_id,
        "modelo_id": modelo_id,
        "linhas_lidas": linhas_lidas,
        "linhas_gravadas": linhas_gravadas,
        "pendencias": linhas_lidas - linhas_gravadas if linhas_lidas else 0,
    }


@router.get("/execucoes")
def listar_execucoes(request: Request):
    exigir_login(request)
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
def recalcular_scores(request: Request):
    exigir_login(request)
    with get_conn() as conn, conn.cursor() as cur:
        gravados = motor.calcular_scores(cur)
    return {"scores_gravados": gravados}


@router.get("/scores")
def listar_scores(request: Request):
    exigir_login(request)
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


@router.get("/catalogo")
def listar_catalogo(request: Request):
    exigir_login(request)
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
def detalhe_catalogo(request: Request, fonte_id: int):
    exigir_login(request)
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
    exigir_login(request)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT arquivo_path FROM execucoes WHERE id = %s", (execucao_id,))
        row = cur.fetchone()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="arquivo não encontrado")
    return FileResponse(row[0], filename=f"execucao_{execucao_id}.xlsx")
