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

## Login (V3.4): pagina redireciona, API responde 401

Tudo exige sessao, com tres excecoes declaradas: `/health` (o compose do V3.6
depende dele, e ele nao expoe dado), `/logo.png` (a propria tela de login usa) e
`/login`.

A recusa tem **duas formas**, porque quem recebe e diferente:

  - rota de **pagina** (`/`, `/administracao`) sem sessao -> **303 para `/login`**.
    Responder 401 numa navegacao mostraria `{"detail": "..."}` cru no navegador,
    que e o servidor falando com uma pessoa em formato de maquina;
  - rota de **API** sem sessao -> **401**, que e o que o `fetch` da tela sabe
    tratar (ele redireciona para `/login`).

Login e papeis vieram antes do deploy (V3.6) de proposito: **nada sem
autenticacao chega a VM**.

## Valor cru na API, formatacao na tela

O endpoint devolve o numero como a fonte o tem (kg para peso, R$ para valor).
Converter para tonelada e trabalho da tela, e o download do V3.3 quer o numero
cru. Decimal vai como string no JSON, para nao perder precisao no float do
JavaScript -- peso e valor em R$ nao devem passar por binario de ponto
flutuante.
"""

import os
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import psycopg2
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, Response
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)

from catering import auditoria, contrato, seguranca
from catering.consulta import download, matriz, planilha, recorte
from catering.seguranca import identidade, sessao, usuarios

AQUI = Path(__file__).resolve().parent
WEB = AQUI / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bootstrap do primeiro admin, se a tabela estiver vazia e o ambiente
    trouxer as variaveis. Idempotente -- ver `catering/seguranca/__init__.py`.

    **Nao roda migration, e o motivo mudou no V3.6.** Antes, o schema vinha do
    startup da V2 -- que subia no mesmo compose e chamava `migracao.migrar()`.
    A V2 saiu do ar em 26/ago/2026, e as migrations passaram a ser aplicadas
    por comando explicito no deploy:

        docker compose run --rm nuvem-cat alembic upgrade head

    Ficou melhor do que era. Migrar como efeito de subir significa que a
    migration roda quando o orquestrador decide reiniciar o container -- de
    madrugada, depois de um OOM, num `restart: unless-stopped` -- e sem ninguem
    olhando o resultado. Explicito, ela roda quando alguem escolheu, com o
    backup recem-feito e a saida na tela. Ver `docs/DEPLOY.md`, secao V3.6."""
    seguranca.garantir_primeiro_admin()
    yield


app = FastAPI(
    title="Nuvem IA -- Volumetria de catering (V3)",
    description="Filtros + Matriz sobre o dado do DW, com login. Lote V3.4.",
    lifespan=lifespan,
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


def _ip(request: Request):
    """IP do cliente, ou `None`. **Nao** viramos ausencia em `"desconhecido"`:
    o freio de tentativas juntaria origens diferentes num mesmo balde, e a
    auditoria passaria a ter um IP que nunca existiu."""
    return request.client.host if request.client else None


# ---------------------------------------------------------------- login (V3.4)
@app.post("/login")
def entrar(
    request: Request,
    response: Response,
    login: str = Form(...),
    senha: str = Form(...),
):
    """Autentica e abre a sessao.

    A recusa e **sempre a mesma mensagem**, com o mesmo 401: "login ou senha
    invalidos". Dizer "esse usuario nao existe" entregaria quem tem conta a quem
    esta adivinhando. O motivo real vai para o log e para a auditoria, que sao
    nossos.

    Sucesso e falha, os dois, viram linha em `cat_auditoria` -- inclusive a
    tentativa barrada pelo freio, que e justamente a que interessa ver."""
    ip = _ip(request)
    tentado = usuarios.normalizar(login)

    try:
        identidade.verificar_freio(login, ip)
    except identidade.MuitasTentativas as erro:
        auditoria.registrar_login(tentado, ip=ip, ok=False, motivo="freio de tentativas")
        raise HTTPException(status_code=429, detail=str(erro)) from None

    usuario = identidade.autenticar(login, senha)
    if usuario is None:
        identidade.registrar_falha(login, ip)
        auditoria.registrar_login(
            tentado, ip=ip, ok=False, motivo="credencial invalida"
        )
        raise HTTPException(status_code=401, detail="login ou senha invalidos")

    identidade.registrar_sucesso(login, ip)
    auditoria.registrar_login(usuario.login, ip=ip, ok=True)
    sessao.criar(response, usuario)
    return {"ok": True, "usuario": usuario.como_dict()}


@app.post("/logout")
def sair(response: Response):
    """Apaga o cookie. **Nao exige sessao**: sair sem estar dentro nao e erro, e
    exigir login para sair prenderia quem tem cookie invalido numa recusa."""
    sessao.encerrar(response)
    return {"ok": True}


@app.get("/api/eu")
def eu(usuario=Depends(sessao.exigir_login)):
    """Quem esta logado, para o cabecalho da tela. O papel sai do banco, como em
    todo request -- ver `seguranca/sessao.py`."""
    return usuario.como_dict()


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
    return {"ok": True, "banco": "ok", "lote": "V3.4"}


@app.get("/api/opcoes")
def opcoes(usuario=Depends(sessao.exigir_login)):
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

            # procedencia: de quando e o dado que a tela esta mostrando.
            # `AT TIME ZONE` porque `terminada_em` e `timestamptz` e o `to_char`
            # renderiza no fuso da sessao -- sem isto uma carga das 09h45
            # aparece como 12h45 (ver `contrato.fuso_exibicao`). O fuso entra
            # por BIND: ele vem de variavel de ambiente, e variavel de ambiente
            # concatenada em SQL e injecao esperando a vez, mesmo validada.
            cur.execute(
                """
                SELECT tabela_origem, fonte,
                       to_char(terminada_em AT TIME ZONE %s, 'DD/MM/YYYY HH24:MI'),
                       linhas_lidas
                FROM cat_cargas WHERE status = 'ok'
                ORDER BY id DESC LIMIT 2
                """,
                (contrato.fuso_exibicao(),),
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
    usuario=Depends(sessao.exigir_login),
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
    usuario=Depends(sessao.exigir_login),
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
    usuario=Depends(sessao.exigir_login),
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

    # V3.4: `usuario` deixa de ser nulo. O resto do registro nao mudou de forma,
    # como o V3.3 previu -- e uma linha, e nao um retrabalho.
    registro = auditoria.abrir(
        "download", recorte=filtros.como_dict(), formato=formato,
        ip=_ip(request), usuario=usuario.login,
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


# ------------------------------------------------- administracao (so admin)
@app.get("/api/usuarios")
def api_usuarios(admin=Depends(sessao.exigir_admin)):
    """Quem existe, com papel e se tem senha local. **Sem hash** -- o objeto
    `Usuario` nao carrega o hash, exatamente para nao poder sair por aqui."""
    return [u.como_dict() for u in usuarios.listar()]


@app.post("/api/usuarios")
def api_criar_usuario(
    login: str = Form(...),
    nome: str = Form(...),
    papel: str = Form(...),
    senha: str = Form(""),
    admin=Depends(sessao.exigir_admin),
):
    """Cria usuario. Senha vazia cria **sem credencial local** -- o caso do AD,
    que tem papel e entra pelo diretorio (ver a migration 0022)."""
    try:
        usuario = usuarios.criar(login, nome, papel, senha or None)
    except usuarios.UsuarioJaExiste as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from None
    except usuarios.UsuarioInvalido as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from None
    return usuario.como_dict()


@app.patch("/api/usuarios/{login}")
def api_alterar_usuario(
    login: str,
    papel: str = Form(None),
    senha: str = Form(None),
    ativo: bool = Form(None),
    admin=Depends(sessao.exigir_admin),
):
    """Troca papel, senha ou `ativo`. Papel e `ativo` valem **no request
    seguinte**, porque nenhum dos dois mora no cookie.

    `409` quando a mudanca deixaria o sistema sem admin ativo nenhum -- ver
    `usuarios.UltimoAdmin`."""
    if papel is None and senha is None and ativo is None:
        raise HTTPException(status_code=400, detail="nada a alterar")
    if usuarios.buscar(login) is None:
        raise HTTPException(status_code=404, detail=f"login: {login}")
    try:
        if papel is not None:
            usuarios.definir_papel(login, papel)
        if ativo is not None:
            usuarios.definir_ativo(login, ativo)
        if senha is not None:
            usuarios.definir_senha(login, senha or None)
    except usuarios.UltimoAdmin as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from None
    except usuarios.UsuarioInvalido as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from None
    return usuarios.buscar(login).como_dict()


@app.get("/api/auditoria")
def api_auditoria(
    limite: int = Query(100, ge=1, le=1000),
    evento: str = Query(None),
    admin=Depends(sessao.exigir_admin),
):
    """As ultimas linhas de `cat_auditoria`. Restrita a admin: a tabela diz quem
    baixou o que e quem tentou entrar, e isso nao e leitura de todo mundo."""
    if evento is not None and evento not in auditoria.EVENTOS:
        raise HTTPException(status_code=400, detail=f"evento: {evento!r}")
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id,
                       to_char(criado_em AT TIME ZONE %s, 'DD/MM/YYYY HH24:MI:SS'),
                       evento,
                       usuario, formato, linhas, ip, status, erro, recorte
                FROM cat_auditoria
                WHERE (%s IS NULL OR evento = %s)
                ORDER BY id DESC LIMIT %s
                """,
                # O fuso vem PRIMEIRO: ele aparece antes na string, e a ordem
                # dos binds e posicional. Auditoria com hora errada e problema
                # de rastreabilidade, nao de estetica.
                (contrato.fuso_exibicao(), evento, evento, limite),
            )
            colunas = ("id", "quando", "evento", "usuario", "formato", "linhas",
                       "ip", "status", "erro", "recorte")
            return [dict(zip(colunas, linha)) for linha in cur.fetchall()]
    finally:
        conn.close()


# ------------------------------------------------------------------- paginas
def _pagina(arquivo):
    """HTML de pagina protegida, com `Cache-Control: no-store`.

    Sem isso o navegador serve a pagina do **cache** e a autorizacao nao e
    reavaliada -- achado na validacao do V3.4: depois de sair de um admin e
    entrar como visualizador, o `GET /administracao` nao chegou ao servidor, o
    Chrome devolveu o HTML guardado, e o desvio para a Matriz nunca teve chance
    de acontecer. Nao houve vazamento de dado (as APIs responderam 403 e as
    tabelas ficaram vazias), mas a tela errada abrir e defeito por si.

    `FileResponse` manda `ETag`/`Last-Modified` por padrao, o que e certo para o
    logo e errado para pagina atras de sessao. O `/logo.png` continua
    cacheavel de proposito: e estatico e publico.
    """
    return FileResponse(WEB / arquivo, headers={"Cache-Control": "no-store"})


@app.get("/login")
def pagina_login(request: Request):
    """Aberta, por definicao. Quem ja esta logado nao precisa dela -- vai para a
    Matriz, em vez de ver um formulario que nao serve mais."""
    if sessao.usuario_atual(request) is not None:
        return RedirectResponse("/", status_code=303)
    return _pagina("login.html")


@app.get("/")
def pagina(request: Request):
    """Pagina, e nao API: sem sessao **redireciona**, e nao devolve 401. Ver a
    docstring do modulo."""
    if sessao.usuario_atual(request) is None:
        return RedirectResponse("/login", status_code=303)
    return _pagina("matriz.html")


@app.get("/administracao")
def pagina_admin(request: Request):
    """Usuarios e auditoria. Visualizador vai para a Matriz em vez de levar 403
    numa navegacao: 403 e resposta para `fetch`, nao para uma pessoa que clicou
    num link."""
    usuario = sessao.usuario_atual(request)
    if usuario is None:
        return RedirectResponse("/login", status_code=303)
    if not usuario.admin:
        return RedirectResponse("/", status_code=303)
    return _pagina("administracao.html")


@app.get("/logo.png")
def logo():
    """O logo servido como arquivo, nao embutido em base64: o PNG da marca tem
    147 KB, e inline ele entraria em toda resposta da pagina."""
    return FileResponse(WEB / "logo.png", media_type="image/png")
