"""V3.6 -- o que a imagem e o compose precisam ter para a V3 subir na VM.

## Por que testar arquivo de infraestrutura

Porque o modo de falhar dele e o pior que existe: **silencioso e com cara de
sucesso**. Foi o que aconteceu ao levantar este lote -- `CAT_SECRET_KEY` nao
estava no `.env.example`, e o `.env` local da Maria tinha a variavel desde o
V3.4, entao `docker compose config` validou sem reclamar. Quem montasse o `.env`
da VM a partir do exemplo subiria um app cujo `/health` responde **200** e cujo
**login estoura**. Healthcheck verde, aplicacao inutil.

Nada aqui sobe container nem fala com Docker. Sao asserts sobre o texto dos
arquivos -- baratos, e cobrem exatamente a classe de erro que so aparece no
deploy, quando o custo de descobrir e mais alto.

## O que estes testes NAO provam

Que a imagem constroi, que o servico sobe, que a VM alcanca o DW. Isso e o
procedimento de `docs/DEPLOY.md`, executado pela Maria. Aqui se prova que os
arquivos declaram o que precisam declarar.
"""

import pathlib
import re

import pytest
import yaml

RAIZ = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))
DOCKERFILE = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
ENV_EXEMPLO = (RAIZ / ".env.example").read_text(encoding="utf-8")

SERVICO = "nuvem-cat"


def test_a_imagem_contem_o_codigo_da_v3():
    """Sem `COPY catering/`, o servico sobe e o uvicorn nao acha o modulo. E o
    `carga_catering.sh` roda `docker compose run` DESTA imagem -- sem ele na
    imagem, a carga agendada falha todo dia as 07h05."""
    assert re.search(r"^COPY catering/ catering/", DOCKERFILE, re.M), \
        "o Dockerfile nao copia catering/ -- a V3 nao existe dentro da imagem"
    assert "COPY scripts/carga_catering.sh" in DOCKERFILE, \
        "o script da carga agendada nao entra na imagem"


def test_o_servico_da_v3_existe_com_o_nome_que_o_script_espera():
    """`scripts/carga_catering.sh` usa `SERVICO_CATERING`, padrao `nuvem-cat`.
    Nome diferente aqui = carga agendada falhando com o compose reclamando de
    servico inexistente."""
    assert SERVICO in COMPOSE["services"], \
        f"o compose nao tem o servico {SERVICO!r}"
    cat = COMPOSE["services"][SERVICO]
    assert "catering.app:app" in " ".join(cat["command"]), \
        "o servico nao serve o app da V3"
    assert cat["ports"] == ["8003:8000"], \
        "porta 8003 no host: 80 e o Conciliador, 8001 o Hub, 8002 era a V2"


@pytest.mark.parametrize("variavel", [
    "DATABASE_URL", "CAT_SECRET_KEY", "DW_USER", "DW_SENHA",
])
def test_o_servico_recebe_as_variaveis_sem_as_quais_ele_nao_serve(variavel):
    """As quatro que nao tem padrao no codigo. `CAT_SECRET_KEY` e a mais
    traicoeira: sem ela o app sobe, o /health responde 200 e o login estoura."""
    assert variavel in COMPOSE["services"][SERVICO]["environment"], \
        f"{variavel} nao chega no container"


@pytest.mark.parametrize("variavel", [
    "CAT_FUSO_EXIBICAO", "CAT_ABERTURA_DE", "DW_ANO_MINIMO",
])
def test_variavel_de_configuracao_e_declarada_no_compose(variavel):
    """As que TEM padrao no codigo tambem precisam estar declaradas aqui.

    O compose nao repassa o `.env` inteiro para dentro do container -- ele
    repassa o que o servico declara. Variavel de configuracao ausente daqui
    funciona no host (pytest, CLI) e e **silenciosamente ignorada** na VM: quem
    escrever `CAT_ABERTURA_DE=2026-01-01` no `.env` de producao veria a tela
    continuar abrindo no padrao, sem erro nenhum para investigar."""
    assert variavel in COMPOSE["services"][SERVICO]["environment"], \
        f"{variavel} nao chega no container -- ajustar no .env da VM nao teria efeito"


def test_toda_variavel_obrigatoria_do_compose_esta_no_env_exemplo():
    """**O teste que existe por causa de um bug real deste lote.**

    Regra: variavel referenciada no compose SEM valor padrao (`${X}` e nao
    `${X:-algo}`) e obrigatoria, e quem monta o `.env` da VM le o
    `.env.example`. Se ela nao estiver documentada la, o deploy descobre no
    pior momento -- e, no caso da chave de sessao, descobre com healthcheck
    verde."""
    bruto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    # so as linhas ativas: o bloco da V2 esta comentado de proposito
    ativo = "\n".join(l for l in bruto.split("\n") if not l.lstrip().startswith("#"))
    obrigatorias = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)\}", ativo))
    assert obrigatorias, "nenhuma variavel encontrada -- o regex parou de casar"

    documentadas = set(re.findall(r"^#?\s*([A-Z_][A-Z0-9_]*)=", ENV_EXEMPLO, re.M))
    faltando = obrigatorias - documentadas
    assert not faltando, (
        f"variavel obrigatoria fora do .env.example: {sorted(faltando)} -- "
        "quem montar o .env da VM a partir do exemplo sobe um app quebrado"
    )


def test_a_v2_saiu_de_servico_mas_nao_do_arquivo():
    """Decisao da Maria em 26/ago/2026: nenhuma tela da V2 era usada.

    O bloco fica **comentado**, e nao deletado, porque a propria decisao previu
    a volta (*"futuramente talvez a gente volte a usar o laboratorio"*) --
    reativar deve ser descomentar, nao arqueologia no git.

    Se algum dia a V2 voltar de verdade, este teste quebra. Quebrar e o
    comportamento certo: reativar servico em producao e decisao, nao detalhe."""
    assert "nuvem-app" not in COMPOSE["services"], \
        "a V2 voltou a ser servico ativo -- se foi de proposito, ajuste este teste"
    bruto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    assert "#  nuvem-app:" in bruto, \
        "o bloco da V2 foi DELETADO em vez de comentado -- reativar virou arqueologia"


def test_o_volume_do_banco_continua_declarado():
    """O mesmo Postgres serve a V2 congelada e a V3. Volume que desaparece do
    compose e banco recriado vazio no proximo `up` -- e o dado da V1/V2
    continua la dentro, entao a perda seria silenciosa e total."""
    assert "nuvem_db_data" in (COMPOSE.get("volumes") or {}), \
        "o volume do Postgres saiu do compose"
    db = COMPOSE["services"]["nuvem-db"]
    assert any("nuvem_db_data" in v for v in db["volumes"]), \
        "o banco deixou de montar o volume -- dado vira efemero"


def test_a_v3_nao_migra_no_startup():
    """As migrations entram por comando explicito no deploy
    (`run --rm nuvem-cat alembic upgrade head`), e nao como efeito de subir.

    Enquanto a V2 subia, elas entravam de carona no startup dela -- e uma
    migration da V3 com defeito derrubava a **V2**. Se alguem puser `migrar()`
    no `catering/app.py`, o acoplamento volta pela outra ponta.

    A guarda le a arvore sintatica, e nao o texto: a primeira versao deste teste
    procurava a substring `alembic` e reprovou um **comentario** que explicava
    justamente que a V3 nao migra. Guarda que proibe falar do assunto empurra a
    explicacao para fora do codigo, que e o contrario do que se quer."""
    import ast

    arvore = ast.parse((RAIZ / "catering" / "app.py").read_text(encoding="utf-8"))
    importados = {
        alias.name.split(".")[0]
        for no in ast.walk(arvore)
        if isinstance(no, ast.Import) for alias in no.names
    } | {
        (no.module or "").split(".")[0]
        for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom)
    } | {
        alias.name
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom) for alias in no.names
    }
    for proibido in ("alembic", "migracao"):
        assert proibido not in importados, (
            f"catering/app.py importa {proibido!r} -- a V3 nao migra no startup, "
            "por decisao do V3.6 (as migrations sao comando explicito no deploy)"
        )

    chamadas = {
        no.func.attr for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
    }
    for proibida in ("migrar", "upgrade", "stamp"):
        assert proibida not in chamadas, (
            f"catering/app.py chama {proibida}() -- migration nao e efeito de subir"
        )
