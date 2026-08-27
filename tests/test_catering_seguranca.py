"""V3.4 -- login, papeis e auditoria de acesso.

Estes testes existem separados de `test_catering_app.py` de proposito: se a
autenticacao quebrar, o sinal tem que chegar como falha de seguranca, e nao como
catorze falhas de Matriz mandando olhar o lugar errado.

## O que aqui e afirmacao de contrato, e nao detalhe

Tres propriedades do V3.4 nao sao "comportamento observado", sao promessa:

  1. **`test_usuario_sem_senha_local_tem_papel_mas_nao_entra`** -- a costura do
     AD. Se alguem tornar `senha_hash` obrigatoria, este teste quebra, e "o AD
     entra depois sem reescrita" deixa de ser verdade em silencio.
  2. **`test_papel_vem_do_banco_e_nao_do_cookie`** -- rebaixar alguem vale no
     request seguinte. Se o papel migrar para dentro do cookie (o atalho que
     economiza uma consulta), revogar acesso passaria a levar ate 12 horas.
  3. **`test_recusa_nao_distingue_login_inexistente_de_senha_errada`** -- a
     mensagem e o codigo sao os mesmos nos dois casos. Diferenciar entregaria
     quem tem conta a quem esta adivinhando.
"""

import time

import psycopg2
import pytest
from fastapi.testclient import TestClient

from catering.app import app
from catering.seguranca import identidade, senha as mod_senha, sessao, usuarios
from tests.conftest import consultar

SENHA = "senha-boa-de-teste"
OUTRA = "outra-senha-de-teste"


@pytest.fixture(autouse=True)
def freio_limpo():
    """O freio de tentativas vive em memoria de modulo -- ver `identidade.py`.

    Sem esta limpeza, as falhas de login de um teste contariam no balde por IP
    do teste seguinte (o `TestClient` usa sempre a mesma origem), e um 429
    inesperado apareceria vinte testes depois da causa."""
    identidade.zerar_freio()
    yield
    identidade.zerar_freio()


@pytest.fixture
def cliente(banco_migrado):
    """Cliente **sem** sessao. Cada teste abre a sua, se precisar."""
    with TestClient(app) as c:
        yield c


def entra(cliente, login, credencial=SENHA):
    return cliente.post("/login", data={"login": login, "senha": credencial})


# =========================================================== senha (scrypt)
def test_mesma_senha_gera_hashes_diferentes():
    """Sal por senha. Dois hashes iguais denunciariam "estas duas pessoas usam a
    mesma senha", e uma tabela pre-computada serviria para todo mundo de uma
    vez."""
    a = mod_senha.gerar(SENHA)
    b = mod_senha.gerar(SENHA)
    assert a != b
    assert mod_senha.confere(SENHA, a)
    assert mod_senha.confere(SENHA, b)
    assert not mod_senha.confere(OUTRA, a)


def test_o_hash_guarda_os_parametros_de_custo():
    """Sem os parametros dentro do valor guardado, subir o custo no futuro
    invalidaria toda senha ja cadastrada -- a verificacao usaria um custo
    diferente do da gravacao e ninguem entraria."""
    guardado = mod_senha.gerar(SENHA)
    algoritmo, n, r, p, sal, chave = guardado.split("$")
    assert algoritmo == "scrypt"
    assert (int(n), int(r), int(p)) == (mod_senha.N, mod_senha.R, mod_senha.P)
    assert sal and chave

    # hash gravado com custo MENOR continua conferindo, porque o custo vem da
    # linha e nao da constante do modulo
    barato = mod_senha._derivar(SENHA, b"sal-fixo-16-byt", 2**12, 8, 1)
    import base64
    antigo = f"scrypt$4096$8$1${base64.b64encode(b'sal-fixo-16-byt').decode()}$" \
             f"{base64.b64encode(barato).decode()}"
    assert mod_senha.confere(SENHA, antigo)


@pytest.mark.parametrize(
    "guardado",
    [None, "", "   ", "sha256$abc", "scrypt$nao-numero$8$1$aa$bb", "texto solto"],
)
def test_hash_ausente_ou_estranho_devolve_falso_sem_explodir(guardado):
    """Linha corrompida em `cat_usuarios` nao pode derrubar o login de todo
    mundo -- e senha local ausente e o usuario de AD, que e estado legitimo."""
    assert mod_senha.confere(SENHA, guardado) is False


# ================================================== usuarios (cat_usuarios)
def test_login_e_normalizado_na_escrita_e_na_leitura(banco_migrado):
    """`Maria.Watanabe` e `maria.watanabe` sao a MESMA conta. Duas contas com
    papeis diferentes so apareceriam no dia em que uma delas nao conseguisse
    baixar nada."""
    usuarios.criar("  Maria.Watanabe ", "Maria", "admin", SENHA)
    assert usuarios.buscar("maria.watanabe") is not None
    assert usuarios.buscar("MARIA.WATANABE") is not None
    assert usuarios.buscar(" maria.watanabe ").papel == "admin"


def test_o_banco_tambem_recusa_login_nao_normalizado(cursor):
    """A guarda esta no CHECK, e nao so no Python: o CLI, um `INSERT` manual e
    uma futura sincronizacao de AD entram por baixo do app."""
    with pytest.raises(psycopg2.errors.CheckViolation):
        cursor.execute(
            "INSERT INTO cat_usuarios (login, nome, papel) VALUES (%s, %s, %s)",
            ("Maria.Watanabe", "Maria", "admin"),
        )


def test_o_banco_tambem_recusa_papel_fora_do_contrato(cursor):
    """Mesmo argumento do login normalizado: a guarda vale para quem entra por
    baixo do app. `gerente` nao existe, e um `INSERT` manual nao pode inventar
    um papel que nenhum `Depends` sabe interpretar."""
    with pytest.raises(psycopg2.errors.CheckViolation):
        cursor.execute(
            "INSERT INTO cat_usuarios (login, nome, papel) VALUES (%s, %s, %s)",
            ("gerente.novo", "Gerente", "gerente"),
        )


def test_usuario_nao_carrega_o_hash_da_senha(banco_migrado):
    """Se o hash viajasse no objeto, um dia sairia num JSON, num log ou num
    traceback -- e nenhum dos tres e uma decisao."""
    import dataclasses

    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    usuario = usuarios.buscar("joao")

    campos = {campo.name for campo in dataclasses.fields(usuario)}
    assert "senha_hash" not in campos
    assert not hasattr(usuario, "senha_hash")
    assert "senha_hash" not in usuario.como_dict()

    # o que sai e o FATO de ter senha, nunca o valor
    assert usuario.tem_senha_local is True
    serializado = str(usuario) + str(usuario.como_dict())
    assert SENHA not in serializado
    assert "scrypt" not in serializado

    # e a porta por onde o hash sai e uma, com nome que diz para que serve
    _usuario, guardado = usuarios.buscar_para_autenticar("joao")
    assert guardado.startswith("scrypt$")


def test_papel_fora_do_contrato_e_recusado(banco_migrado):
    with pytest.raises(usuarios.UsuarioInvalido):
        usuarios.criar("x", "X", "gerente", SENHA)
    with pytest.raises(usuarios.UsuarioInvalido):
        usuarios.criar("", "X", "admin", SENHA)


def test_login_duplicado_e_recusado(banco_migrado):
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    with pytest.raises(usuarios.UsuarioJaExiste):
        usuarios.criar("JOAO", "Outro Joao", "admin", OUTRA)


def test_o_unico_admin_ativo_nao_consegue_se_rebaixar_nem_se_desativar(banco_migrado):
    """O modo de falha que isso impede e definitivo: o unico admin se desativa
    por engano e ninguem mais cadastra usuario nem le auditoria."""
    usuarios.criar("chefe", "Chefe", "admin", SENHA)
    usuarios.criar("joao", "Joao", "visualizador", SENHA)

    with pytest.raises(usuarios.UltimoAdmin):
        usuarios.definir_papel("chefe", "visualizador")
    with pytest.raises(usuarios.UltimoAdmin):
        usuarios.definir_ativo("chefe", False)

    # tirar a SENHA do unico admin tranca do mesmo jeito, enquanto nao ha AD:
    # ele mantem o papel e deixa de ter qualquer forma de entrar
    with pytest.raises(usuarios.UltimoAdmin):
        usuarios.definir_senha("chefe", None)

    # com um segundo admin, a saida existe -- a guarda nao fecha a porta
    usuarios.criar("segunda", "Segunda", "admin", SENHA)
    assert usuarios.definir_papel("chefe", "visualizador") is True
    assert usuarios.buscar("chefe").papel == "visualizador"
    # e trocar a senha (em vez de remover) nunca foi barrado
    assert usuarios.definir_senha("segunda", OUTRA) is True
    assert identidade.autenticar("segunda", OUTRA) is not None


# ==================================================== identidade (login)
def test_usuario_sem_senha_local_tem_papel_mas_nao_entra(banco_migrado):
    """**A costura do AD.** Papel sem senha local e estado legitimo: e assim que
    uma pessoa do diretorio vai existir aqui.

    Se `senha_hash` virar `NOT NULL`, ou se `criar()` passar a exigir senha, este
    teste quebra -- e e por isso que ele existe."""
    usuarios.criar("do.ad", "Pessoa do AD", "admin", senha=None)

    usuario = usuarios.buscar("do.ad")
    assert usuario.papel == "admin"          # tem autorizacao
    assert usuario.tem_senha_local is False  # e nao tem credencial local

    assert identidade.autenticar("do.ad", "") is None
    assert identidade.autenticar("do.ad", SENHA) is None


def test_credencial_certa_entra_e_marca_o_ultimo_acesso(banco_migrado):
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    assert consultar("SELECT ultimo_acesso FROM cat_usuarios")[0][0] is None

    usuario = identidade.autenticar("JOAO ", SENHA)
    assert usuario is not None
    assert usuario.login == "joao"
    assert usuario.papel == "visualizador"
    assert consultar("SELECT ultimo_acesso FROM cat_usuarios")[0][0] is not None


def test_senha_errada_login_inexistente_e_inativo_nao_entram(banco_migrado):
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    usuarios.criar("saiu", "Quem saiu", "visualizador", SENHA)
    usuarios.definir_ativo("saiu", False)

    assert identidade.autenticar("joao", OUTRA) is None
    assert identidade.autenticar("ninguem", SENHA) is None
    assert identidade.autenticar("saiu", SENHA) is None


def test_freio_trava_o_login_que_errou_e_nao_o_do_colega(banco_migrado):
    """A V2 freava por IP e travava o CSC inteiro atras do mesmo IP. Com
    identidade por pessoa, quem erra trava a si mesmo."""
    for _ in range(identidade.FALHAS_POR_LOGIN):
        identidade.registrar_falha("joao", "10.0.0.7")

    with pytest.raises(identidade.MuitasTentativas):
        identidade.verificar_freio("joao", "10.0.0.7")

    # o colega, no MESMO IP, continua podendo tentar
    identidade.verificar_freio("maria", "10.0.0.7")


def test_freio_por_ip_pega_varredura_de_logins_diferentes(banco_migrado):
    """O caso que o freio por login nao pega: um login novo a cada tentativa."""
    for i in range(identidade.FALHAS_POR_IP):
        identidade.registrar_falha(f"chute{i}", "10.0.0.9")

    with pytest.raises(identidade.MuitasTentativas):
        identidade.verificar_freio("mais.um.chute", "10.0.0.9")
    # outra origem nao foi afetada
    identidade.verificar_freio("mais.um.chute", "10.0.0.10")


def test_sucesso_limpa_o_freio_do_login_mas_nao_o_do_ip(banco_migrado):
    """Varredura que acerta uma conta no meio nao deve limpar o rastro das
    outras tentativas."""
    for i in range(identidade.FALHAS_POR_IP):
        identidade.registrar_falha(f"chute{i}", "10.0.0.9")
    identidade.registrar_falha("joao", "10.0.0.9")

    identidade.registrar_sucesso("joao", "10.0.0.9")
    identidade.verificar_freio("joao", None)  # o login foi liberado
    with pytest.raises(identidade.MuitasTentativas):
        identidade.verificar_freio("joao", "10.0.0.9")  # o IP, nao


# ========================================================= sessao (cookie)
def _cookie_de(cliente):
    return cliente.cookies.get(sessao.COOKIE)


def test_cookie_adulterado_e_recusado(cliente):
    """Trocar o login dentro do payload invalida a assinatura -- e a assinatura,
    e nao o conteudo, e o que impede forjar sessao."""
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    usuarios.criar("chefe", "Chefe", "admin", SENHA)
    assert entra(cliente, "joao").status_code == 200

    bom = _cookie_de(cliente)
    payload, assinatura = bom.rsplit(".", 1)
    expira, _, _login = payload.partition(":")

    for forjado in (
        f"{expira}:chefe.{assinatura}",              # trocou de quem e
        f"{int(expira) + 999999}:joao.{assinatura}",  # esticou a validade
        f"{payload}.{'0' * len(assinatura)}",         # assinatura inventada
        "nao-e-cookie",
    ):
        cliente.cookies.set(sessao.COOKIE, forjado)
        assert cliente.get("/api/eu").status_code == 401, forjado


def test_cookie_expirado_e_recusado(cliente, monkeypatch):
    """A validade e conferida no servidor, dentro do payload assinado. O
    `max_age` do cookie e uma instrucao ao navegador -- um cliente que guarde o
    cookie por mais tempo continuaria entrando."""
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    assert entra(cliente, "joao").status_code == 200
    assert cliente.get("/api/eu").status_code == 200

    velho = sessao._assinar(f"{int(time.time()) - 1}:joao")
    cliente.cookies.set(sessao.COOKIE, velho)
    assert cliente.get("/api/eu").status_code == 401


def test_cookie_assinado_com_outra_chave_e_recusado(cliente, monkeypatch):
    """Trocar `CAT_SECRET_KEY` invalida as sessoes abertas -- que e o que se
    quer de uma rotacao de chave."""
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    assert entra(cliente, "joao").status_code == 200
    assert cliente.get("/api/eu").status_code == 200

    monkeypatch.setenv("CAT_SECRET_KEY", "outra-chave-completamente-diferente")
    assert cliente.get("/api/eu").status_code == 401


def test_sem_chave_o_health_continua_de_pe(cliente, monkeypatch):
    """A chave e lida no USO, nao no import. Se fosse no import, o app nao
    subiria e o sintoma chegaria como "container nao fica de pe", sem dizer qual
    variavel falta."""
    monkeypatch.delenv("CAT_SECRET_KEY", raising=False)
    assert cliente.get("/health").status_code == 200
    with pytest.raises(RuntimeError, match="CAT_SECRET_KEY"):
        sessao._chave()


def test_papel_vem_do_banco_e_nao_do_cookie(cliente):
    """**Rebaixar alguem vale no request seguinte.** Com o papel dentro do
    cookie -- o atalho que economiza uma consulta -- revogar acesso levaria ate
    12 horas, e o crachá continuaria valendo depois do desligamento."""
    usuarios.criar("chefe", "Chefe", "admin", SENHA)
    usuarios.criar("segunda", "Segunda", "admin", SENHA)  # para a guarda do ultimo admin
    assert entra(cliente, "chefe").status_code == 200
    assert cliente.get("/api/usuarios").status_code == 200

    usuarios.definir_papel("chefe", "visualizador")

    # MESMO cookie, request seguinte
    assert cliente.get("/api/usuarios").status_code == 403
    assert cliente.get("/api/eu").json()["papel"] == "visualizador"


def test_desativar_corta_o_acesso_no_request_seguinte(cliente):
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    assert entra(cliente, "joao").status_code == 200
    assert cliente.get("/api/eu").status_code == 200

    usuarios.definir_ativo("joao", False)
    assert cliente.get("/api/eu").status_code == 401


# ============================================================== HTTP / app
ROTAS_DE_DADO = (
    "/api/eu",
    "/api/opcoes",
    "/api/matriz?de=2026-01&ate=2026-01",
    "/api/planilha?de=2026-01&ate=2026-01",
    "/api/download?de=2026-01&ate=2026-01",
    "/api/usuarios",
    "/api/auditoria",
)


@pytest.mark.parametrize("rota", ROTAS_DE_DADO)
def test_toda_rota_de_dado_exige_sessao(cliente, rota):
    """A lista e explicita de proposito: rota nova sem sessao nao passa por aqui
    despercebida -- ela precisa ser adicionada a lista, e isso e a hora de
    perguntar se ela devia mesmo ser aberta."""
    assert cliente.get(rota).status_code == 401


def test_health_logo_e_login_ficam_abertos(cliente):
    """As tres excecoes declaradas: o healthcheck do compose, o logo da propria
    tela de login, e a tela de login."""
    assert cliente.get("/health").status_code == 200
    assert cliente.get("/logo.png").status_code == 200
    assert cliente.get("/login").status_code == 200


def test_pagina_sem_sessao_redireciona_em_vez_de_devolver_401(cliente):
    """Pagina e para pessoa: 401 numa navegacao mostraria `{"detail": ...}` cru
    no navegador."""
    for rota in ("/", "/administracao"):
        resposta = cliente.get(rota, follow_redirects=False)
        assert resposta.status_code == 303, rota
        assert resposta.headers["location"] == "/login"


def test_pagina_atras_de_sessao_nao_pode_ficar_no_cache(cliente):
    """Achado na validacao do V3.4, no navegador: depois de sair de um admin e
    entrar como visualizador, o `GET /administracao` **nao chegou ao servidor**
    -- o Chrome devolveu o HTML guardado (o `FileResponse` manda `ETag`), e o
    desvio para a Matriz nunca teve chance de rodar.

    Nao houve vazamento de dado (as APIs responderam 403 e as tabelas ficaram
    vazias), mas a tela errada abrir e defeito por si -- e num computador
    compartilhado a pagina do colega voltaria pelo botao de voltar."""
    usuarios.criar("chefe", "Chefe", "admin", SENHA)
    entra(cliente, "chefe")

    for rota in ("/", "/administracao", "/login"):
        resposta = cliente.get(rota, follow_redirects=True)
        assert "no-store" in resposta.headers.get("cache-control", ""), rota

    # o logo continua cacheavel: e estatico, publico, e 147 KB em toda navegacao
    assert "no-store" not in cliente.get("/logo.png").headers.get("cache-control", "")


def test_quem_ja_esta_logado_nao_fica_na_tela_de_login(cliente):
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    entra(cliente, "joao")
    resposta = cliente.get("/login", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_visualizador_e_devolvido_para_a_matriz_e_nao_leva_403_na_pagina(cliente):
    """403 e resposta para `fetch`, nao para quem clicou num link."""
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    entra(cliente, "joao")
    resposta = cliente.get("/administracao", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_login_pelo_http_abre_sessao_e_audita_o_sucesso(cliente):
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    resposta = entra(cliente, "joao")

    assert resposta.status_code == 200
    assert resposta.json()["usuario"]["papel"] == "visualizador"
    assert _cookie_de(cliente)

    linhas = consultar(
        "SELECT evento, usuario, status, linhas, formato FROM cat_auditoria"
    )
    assert linhas == [("login", "joao", "ok", None, None)]


def test_login_recusado_tambem_vira_linha_de_auditoria(cliente):
    """"Quem tentou entrar e nao conseguiu" e o que uma auditoria de acesso serve
    para responder."""
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    assert entra(cliente, "joao", OUTRA).status_code == 401
    assert entra(cliente, "nem.existe", OUTRA).status_code == 401

    linhas = consultar(
        "SELECT usuario, status, erro FROM cat_auditoria ORDER BY id"
    )
    assert linhas == [
        ("joao", "erro", "credencial invalida"),
        ("nem.existe", "erro", "credencial invalida"),
    ]


def test_a_senha_nunca_chega_a_auditoria(cliente):
    """O que se guarda e o login tentado e o motivo. A senha -- certa ou errada
    -- nao entra em nenhuma coluna."""
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    entra(cliente, "joao", SENHA)
    entra(cliente, "joao", "senha-secreta-que-nao-pode-vazar")

    despejo = str(consultar("SELECT * FROM cat_auditoria"))
    assert SENHA not in despejo
    assert "senha-secreta-que-nao-pode-vazar" not in despejo


def test_recusa_nao_distingue_login_inexistente_de_senha_errada(cliente):
    """Mensagem e codigo iguais nos dois casos. Diferenciar entregaria **quem tem
    conta** a quem esta adivinhando, sem acertar senha nenhuma."""
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    errada = entra(cliente, "joao", OUTRA)
    inexistente = entra(cliente, "nem.existe", OUTRA)

    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json()


def test_freio_devolve_429_e_registra_a_tentativa_barrada(cliente):
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    for _ in range(identidade.FALHAS_POR_LOGIN):
        assert entra(cliente, "joao", OUTRA).status_code == 401

    barrado = entra(cliente, "joao", SENHA)  # senha CERTA, e mesmo assim barra
    assert barrado.status_code == 429
    assert "tente novamente" in barrado.json()["detail"]

    motivos = consultar(
        "SELECT erro FROM cat_auditoria ORDER BY id DESC LIMIT 1"
    )
    assert motivos == [("freio de tentativas",)]


def test_logout_apaga_o_cookie(cliente):
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    entra(cliente, "joao")
    assert cliente.get("/api/eu").status_code == 200

    assert cliente.post("/logout").status_code == 200
    assert cliente.get("/api/eu").status_code == 401
    # sair sem estar dentro nao e erro
    assert cliente.post("/logout").status_code == 200


def test_download_registra_quem_baixou(cliente):
    """A coluna `usuario` da `cat_auditoria` sai de nula -- era o que o V3.3
    tinha previsto, e custou uma linha."""
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    entra(cliente, "joao")

    resposta = cliente.get("/api/download", params={"de": "2026-01-01", "ate": "2026-01-31"})
    assert resposta.status_code == 200

    linhas = consultar(
        "SELECT usuario, status FROM cat_auditoria WHERE evento = 'download'"
    )
    assert linhas == [("joao", "ok")]


# ------------------------------------------------------- so admin (papeis)
def test_visualizador_leva_403_no_que_e_de_admin(cliente):
    """403 e nao 401: responder 401 mandaria o visualizador para a tela de login,
    onde ele entraria de novo, para ser recusado de novo."""
    usuarios.criar("joao", "Joao", "visualizador", SENHA)
    entra(cliente, "joao")

    assert cliente.get("/api/usuarios").status_code == 403
    assert cliente.get("/api/auditoria").status_code == 403
    assert cliente.post("/api/usuarios", data={
        "login": "novo", "nome": "Novo", "papel": "admin", "senha": SENHA,
    }).status_code == 403
    assert cliente.patch(
        "/api/usuarios/joao", data={"papel": "admin"}
    ).status_code == 403
    # e o que e de todo mundo continua sendo dele
    assert cliente.get("/api/opcoes").status_code == 200


def test_admin_cadastra_troca_papel_e_desativa(cliente):
    usuarios.criar("chefe", "Chefe", "admin", SENHA)
    entra(cliente, "chefe")

    criado = cliente.post("/api/usuarios", data={
        "login": " Joao.Silva ", "nome": "Joao Silva",
        "papel": "visualizador", "senha": SENHA,
    })
    assert criado.status_code == 200
    assert criado.json()["login"] == "joao.silva"
    assert criado.json()["tem_senha_local"] is True

    duplicado = cliente.post("/api/usuarios", data={
        "login": "joao.silva", "nome": "Outro", "papel": "admin", "senha": SENHA,
    })
    assert duplicado.status_code == 409

    virou = cliente.patch("/api/usuarios/joao.silva", data={"papel": "admin"})
    assert virou.status_code == 200 and virou.json()["papel"] == "admin"

    assert cliente.patch(
        "/api/usuarios/joao.silva", data={"ativo": "false"}
    ).json()["ativo"] is False

    assert cliente.patch("/api/usuarios/ninguem", data={"papel": "admin"}).status_code == 404
    assert cliente.patch("/api/usuarios/joao.silva", data={}).status_code == 400


def test_admin_nao_consegue_ficar_sem_admin_nenhum_pela_api(cliente):
    usuarios.criar("chefe", "Chefe", "admin", SENHA)
    entra(cliente, "chefe")

    recusa = cliente.patch("/api/usuarios/chefe", data={"papel": "visualizador"})
    assert recusa.status_code == 409
    assert "unico admin ativo" in recusa.json()["detail"]

    assert cliente.patch(
        "/api/usuarios/chefe", data={"ativo": "false"}
    ).status_code == 409


def test_admin_cria_usuario_sem_senha_local_pela_api(cliente):
    """O formato do AD, pela tela: papel sim, credencial local nao."""
    usuarios.criar("chefe", "Chefe", "admin", SENHA)
    entra(cliente, "chefe")

    criado = cliente.post("/api/usuarios", data={
        "login": "do.ad", "nome": "Pessoa do AD", "papel": "visualizador",
        "senha": "",
    })
    assert criado.status_code == 200
    assert criado.json()["tem_senha_local"] is False
    assert entra(cliente, "do.ad", "").status_code in (401, 422)


def test_auditoria_pela_api_filtra_por_evento(cliente):
    usuarios.criar("chefe", "Chefe", "admin", SENHA)
    entra(cliente, "chefe")
    cliente.get("/api/download", params={"de": "2026-01-01", "ate": "2026-01-31"})

    tudo = cliente.get("/api/auditoria").json()
    assert {linha["evento"] for linha in tudo} == {"login", "download"}

    logins = cliente.get("/api/auditoria", params={"evento": "login"}).json()
    assert [linha["usuario"] for linha in logins] == ["chefe"]

    assert cliente.get("/api/auditoria", params={"evento": "consulta"}).status_code == 400


# ------------------------------------------------------------------- CLI
def test_cli_sem_database_url_diz_o_que_falta(monkeypatch):
    """Apareceu no uso real (25/ago/2026): a Maria abriu um SEGUNDO terminal e o
    CLI morreu com `KeyError: 'DATABASE_URL'` e quinze linhas de traceback do
    psycopg2.

    Ferramenta de recuperacao e usada justamente quando algo esta errado -- nessa
    hora, traceback manda olhar o lugar errado. A mensagem tem que dizer o que
    falta e como resolver."""
    from catering.seguranca import __main__ as cli

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as saida:
        cli.main(["listar"])
    mensagem = str(saida.value)
    assert "DATABASE_URL" in mensagem
    assert "terminal" in mensagem  # explica por que a outra janela nao vale
    assert "Traceback" not in mensagem


def test_cli_cria_lista_troca_papel_e_desativa(banco_migrado, capsys):
    """O CLI nao tinha teste nenhum, e ele e o caminho de recuperacao: caminho de
    recuperacao quebrado se descobre exatamente na hora em que se precisa dele."""
    from catering.seguranca import __main__ as cli

    assert cli.main(["criar", "--login", "Chefe", "--nome", "Chefe",
                     "--papel", "admin", "--sem-senha"]) == 0
    assert "criado: chefe (admin)" in capsys.readouterr().out

    assert cli.main(["listar"]) == 0
    saida = capsys.readouterr().out
    assert "chefe" in saida and "nao (AD)" in saida

    assert cli.main(["criar", "--login", "joao", "--nome", "Joao",
                     "--papel", "visualizador", "--sem-senha"]) == 0
    capsys.readouterr()

    assert cli.main(["papel", "--login", "JOAO", "--papel", "admin"]) == 0
    assert usuarios.buscar("joao").papel == "admin"

    assert cli.main(["desativar", "--login", "joao"]) == 0
    assert usuarios.buscar("joao").ativo is False

    # login que nao existe: mensagem, e nao traceback
    with pytest.raises(SystemExit, match="nao encontrado"):
        cli.main(["papel", "--login", "ninguem", "--papel", "admin"])


def test_cli_recusa_deixar_o_sistema_sem_admin_com_mensagem(banco_migrado):
    """Mesmo defeito do `KeyError`, em outro lugar: `UltimoAdmin` subia crua e
    virava traceback nos comandos `papel`, `desativar` e `senha`."""
    from catering.seguranca import __main__ as cli

    usuarios.criar("chefe", "Chefe", "admin", SENHA)
    for argumentos in (
        ["papel", "--login", "chefe", "--papel", "visualizador"],
        ["desativar", "--login", "chefe"],
    ):
        with pytest.raises(SystemExit, match="unico admin ativo"):
            cli.main(argumentos)


# ------------------------------------------------ bootstrap do 1o admin
def test_bootstrap_cria_o_primeiro_admin_e_nao_mexe_em_quem_existe(
    banco_migrado, monkeypatch
):
    """Sistema com login precisa de uma forma de o primeiro acesso existir. As
    duas saidas ruins seriam usuario fixo no codigo (que vai para o Git) e
    endpoint publico de cadastro (que qualquer um usa antes de voce)."""
    from catering import seguranca

    monkeypatch.setenv("CAT_ADMIN_LOGIN", "primeira")
    monkeypatch.setenv("CAT_ADMIN_SENHA", SENHA)
    monkeypatch.setenv("CAT_ADMIN_NOME", "Primeira Admin")

    assert seguranca.garantir_primeiro_admin() == "primeira"
    assert usuarios.buscar("primeira").papel == "admin"
    assert identidade.autenticar("primeira", SENHA) is not None

    # idempotente: rodar de novo nao recria nem troca a senha de quem existe
    monkeypatch.setenv("CAT_ADMIN_SENHA", "senha-nova-que-nao-deve-valer")
    assert seguranca.garantir_primeiro_admin() is None
    assert usuarios.contar() == 1
    assert identidade.autenticar("primeira", SENHA) is not None


def test_bootstrap_nao_faz_nada_sem_as_variaveis(banco_migrado, monkeypatch):
    from catering import seguranca

    monkeypatch.delenv("CAT_ADMIN_LOGIN", raising=False)
    monkeypatch.delenv("CAT_ADMIN_SENHA", raising=False)
    assert seguranca.garantir_primeiro_admin() is None
    assert usuarios.contar() == 0
