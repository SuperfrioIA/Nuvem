"""App da V3 -- FastAPI propria, separada da aplicacao da V2.

## Por que app separado, e nao um router dentro do `backend/main.py`

Decisao da Maria em 24/ago/2026: *"V3 e um projeto totalmente diferente"*, e a
V2 esta congelada. Um router no `backend/main.py` deixaria `backend/` "intocado
exceto uma linha" -- que nao e intocado. Com app propria:

  - `backend/` fica intacto **de verdade**;
  - a V3 sobe, cai e faz rollback sem encostar no que serve a operacao hoje;
  - o desmonte do V3.6 e remover um servico do compose, nao editar codigo da V2.

O banco e o **mesmo** (as migrations continuam na mesma cadeia). O que se separa
e o processo, nao o dado -- separar o dado exigiria uma segunda instancia de
Postgres, backup proprio e uma conciliacao entre os dois, o que nao serve nada.

## Sem login neste lote

Login e papeis sao o V3.4, e o deploy e o V3.6 -- nesta ordem de proposito,
para que **nada sem autenticacao chegue a VM**. Enquanto isso este app roda
apenas local. O `/health` existe desde agora porque o compose do V3.6 vai
precisar dele.

## Valor cru na API, formatacao na tela

O endpoint devolve o numero como a fonte o tem (kg para peso, R$ para valor).
Converter para tonelada e trabalho da tela, e o download do V3.3 quer o numero
cru. Decimal vai como string no JSON, para nao perder precisao no float do
JavaScript -- peso e valor em R$ nao devem passar por binario de ponto
flutuante.
"""

import os
from decimal import Decimal
from pathlib import Path

import psycopg2
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from catering import auditoria, contrato
from catering.consulta import download, matriz, planilha, recorte

AQUI = Path(__file__).resolve().parent
WEB = AQUI / "web"

app = FastAPI(
    title="Nuvem IA -- Volumetria de catering (V3)",
    description="Filtros + Matriz sobre o dado do DW. Lote V3.2.",
)


def _conexao():
    """Conexao por request. Sem pool nesta altura de proposito: a V3.2 tem um
    endpoint de leitura e uso local. O pool entra quando houver concorrencia
    real para justificar -- adiantar isso agora seria copiar a resposta da V2
    para uma pergunta que a V3 ainda nao fez."""
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _filtros(de, ate, movimento, lente, faixa, pagina,
             unidade, cliente, tipo_estoque, operacao):
    """Monta e valida o recorte. Um lugar so para os tres endpoints -- se cada
    um montasse o seu, a tela mostraria um recorte e baixaria outro.

    Filtro invalido e **400**, nao 500: 500 esconderia erro do chamador atras de
    erro do servidor, e manda quem esta depurando olhar o lugar errado."""
    filtros = recorte.Filtros(
        de=de, ate=ate, movimento=movimento, lente=lente, faixa=faixa,
        pagina=pagina, unidades=tuple(unidade), clientes=tuple(cliente),
        tipos_estoque=tuple(tipo_estoque), operacoes=tuple(operacao),
    )
    try:
        return filtros.validar()
    except recorte.FiltroInvalido as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from None


def _json(valor):
    """Decimal -> string; o resto passa. A tela formata."""
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, dict):
        return {k: _json(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_json(v) for v in valor]
    return valor


@app.get("/health")
def health():
    """Vivo e com banco alcancavel. O compose do V3.6 depende disto."""
    try:
        conn = _conexao()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        finally:
            conn.close()
    except Exception as erro:
        return JSONResponse(
            {"ok": False, "banco": f"{type(erro).__name__}"}, status_code=503
        )
    return {"ok": True, "banco": "ok", "lote": "V3.2"}


@app.get("/api/opcoes")
def opcoes():
    """O que existe para filtrar -- lido do dado, nao de lista fixa.

    Unidade nova, cliente novo ou operacao nova aparecem no filtro sozinhos.
    Lista fixa aqui viraria a mesma armadilha do de-para da V2: a fonte anda e
    a tela nao."""
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT COALESCE(u.sigla, f.nk_wms_filial)
                FROM (SELECT nk_wms_filial FROM cat_fato_recebimento
                      UNION SELECT nk_wms_filial FROM cat_fato_expedicao) f
                LEFT JOIN cat_unidades u ON u.sigla_fonte = f.nk_wms_filial
                ORDER BY 1
                """
            )
            unidades = [linha[0] for linha in cur.fetchall()]

            cur.execute(
                """
                SELECT f.nk_cliente, COALESCE(c.razao_social, f.nk_cliente)
                FROM (SELECT DISTINCT nk_cliente FROM cat_fato_recebimento
                      UNION SELECT DISTINCT nk_cliente FROM cat_fato_expedicao) f
                LEFT JOIN cat_clientes c ON c.raiz_cnpj = f.nk_cliente
                ORDER BY 2
                """
            )
            clientes = [{"chave": k, "rotulo": r} for k, r in cur.fetchall()]

            cur.execute(
                """
                SELECT DISTINCT descr_oper_wms, movimento FROM (
                    SELECT descr_oper_wms, 'rec' AS movimento FROM cat_fato_recebimento
                    UNION SELECT descr_oper_wms, 'exp' FROM cat_fato_expedicao
                ) t ORDER BY 1
                """
            )
            operacoes = {"rec": [], "exp": []}
            for nome, movimento in cur.fetchall():
                operacoes[movimento].append(nome)

            cur.execute("SELECT DISTINCT tipo FROM cat_tipos_estoque ORDER BY 1")
            tipos = [linha[0] for linha in cur.fetchall()]

            # o periodo que existe no dado -- a tela abre nele em vez de chutar
            cur.execute(
                """
                SELECT to_char(min(nk_calendario), 'YYYY-MM'),
                       to_char(max(nk_calendario), 'YYYY-MM')
                FROM (SELECT nk_calendario FROM cat_fato_recebimento
                      UNION ALL SELECT nk_calendario FROM cat_fato_expedicao) t
                """
            )
            periodo = cur.fetchone()

            # procedencia: de quando e o dado que a tela esta mostrando
            cur.execute(
                """
                SELECT tabela_origem, fonte, to_char(terminada_em, 'DD/MM/YYYY HH24:MI'),
                       linhas_lidas
                FROM cat_cargas WHERE status = 'ok'
                ORDER BY id DESC LIMIT 2
                """
            )
            cargas = [
                {"tabela": t, "fonte": f, "quando": q, "linhas": n}
                for t, f, q, n in cur.fetchall()
            ]
    finally:
        conn.close()

    return {
        "unidades": unidades,
        "clientes": clientes,
        "operacoes": operacoes,
        "tipos_estoque": tipos,
        "periodo": {"de": periodo[0], "ate": periodo[1]},
        "lentes": [
            {"chave": c, "nome": d["nome"], "unidade": d["unidade"],
             "so_entrada": d["exp"] is None}
            for c, d in contrato.LENTES.items()
        ],
        "faixas": [
            {"chave": f, "rotulo": matriz._rotulo_faixa(f)} for f in contrato.FAIXAS
        ],
        "cargas": cargas,
    }


@app.get("/api/matriz")
def api_matriz(
    de: str = Query(..., description="mes inicial, AAAA-MM"),
    ate: str = Query(..., description="mes final, AAAA-MM"),
    movimento: str = Query("rec"),
    lente: str = Query("liq"),
    faixa: str = Query("solicitado"),
    pagina: int = Query(1, ge=1),
    unidade: list[str] = Query(default=[]),
    cliente: list[str] = Query(default=[]),
    tipo_estoque: list[str] = Query(default=[]),
    operacao: list[str] = Query(default=[]),
):
    """A Matriz do recorte."""
    filtros = _filtros(de, ate, movimento, lente, faixa, pagina,
                       unidade, cliente, tipo_estoque, operacao)
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            resultado = matriz.matriz(cur, filtros)
    finally:
        conn.close()
    return _json(resultado)


@app.get("/api/planilha")
def api_planilha(
    de: str = Query(..., description="mes inicial, AAAA-MM"),
    ate: str = Query(..., description="mes final, AAAA-MM"),
    movimento: str = Query("rec"),
    lente: str = Query("liq"),
    faixa: str = Query("solicitado"),
    pagina: int = Query(1, ge=1),
    unidade: list[str] = Query(default=[]),
    cliente: list[str] = Query(default=[]),
    tipo_estoque: list[str] = Query(default=[]),
    operacao: list[str] = Query(default=[]),
):
    """Linhas cruas do recorte, 100 por pagina, paginadas no servidor."""
    filtros = _filtros(de, ate, movimento, lente, faixa, pagina,
                       unidade, cliente, tipo_estoque, operacao)
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            return _json(planilha.planilha(cur, filtros))
    finally:
        conn.close()


@app.get("/api/download")
def api_download(
    request: Request,
    de: str = Query(..., description="mes inicial, AAAA-MM"),
    ate: str = Query(..., description="mes final, AAAA-MM"),
    formato: str = Query("csv"),
    movimento: str = Query("rec"),
    lente: str = Query("liq"),
    faixa: str = Query("solicitado"),
    unidade: list[str] = Query(default=[]),
    cliente: list[str] = Query(default=[]),
    tipo_estoque: list[str] = Query(default=[]),
    operacao: list[str] = Query(default=[]),
):
    """O recorte inteiro, em CSV (streaming) ou xlsx (sob teto).

    **Sempre no recorte dos filtros da tela** (contrato): os mesmos parametros
    da Matriz e da planilha, e a auditoria registra exatamente qual recorte
    saiu. `pagina` nao entra de proposito -- download de uma pagina so nao e
    download do recorte.
    """
    if formato not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail=f"formato: {formato!r}")
    filtros = _filtros(de, ate, movimento, lente, faixa, 1,
                       unidade, cliente, tipo_estoque, operacao)

    ip = request.client.host if request.client else None
    # `usuario` fica nulo: login e o V3.4. Ver catering/auditoria.py.
    registro = auditoria.abrir(
        "download", recorte=filtros.como_dict(), formato=formato, ip=ip
    )

    nome = download.nome_do_arquivo(filtros, formato)
    cabecalhos = {"Content-Disposition": f'attachment; filename="{nome}"'}

    if formato == "csv":
        # o gerador e dono da conexao: o corpo dele roda DEPOIS de a resposta
        # comecar, quando um `with` daqui ja teria fechado tudo
        return StreamingResponse(
            download.gerar_csv(filtros, registro),
            media_type="text/csv; charset=utf-8",
            headers=cabecalhos,
        )

    try:
        conteudo = download.gerar_xlsx(filtros, registro)
    except download.DownloadGrandeDemais as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from None
    return Response(
        content=conteudo,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers=cabecalhos,
    )


@app.get("/")
def pagina():
    return FileResponse(WEB / "matriz.html")


@app.get("/logo.png")
def logo():
    """O logo servido como arquivo, nao embutido em base64: o PNG da marca tem
    147 KB, e inline ele entraria em toda resposta da pagina."""
    return FileResponse(WEB / "logo.png", media_type="image/png")
