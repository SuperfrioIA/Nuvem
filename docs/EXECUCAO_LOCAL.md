# Execução local — Nuvem IA

Método real de subir, testar, validar e encerrar o projeto nesta máquina
(Windows, Maria). Ler antes de iniciar processos, rodar testes ou validar
qualquer tela localmente.

Base: inspeção direta do código do repositório (`docker-compose.yml`,
`Dockerfile`, `backend/`, `tests/conftest.py`, `docs/DEPLOY.md`) em
19/ago/2026. Os fatos de topologia WSL/Docker (distro, containers já
existentes) vêm de uma investigação ao vivo feita na mesma data e não foram
reexecutados aqui — rodar `docker ps` de novo teria o mesmo efeito colateral
descrito na nota abaixo, e este documento é só consolidação, não diagnóstico.

> **Achado que motiva a regra da seção 4**: em 19/ago/2026, um `docker ps`
> de diagnóstico acordou o WSL e o Docker Desktop recriou sozinho um
> container do `docker-compose.yml` que tinha `restart: unless-stopped` —
> sem nenhum `docker compose up` explícito. Container derrubado de novo
> (volume preservado), com autorização da Maria. Ver seção 4.

---

## 1. Ambiente

- **Host**: Windows (`C:\Users\maria.watanabe\Documents\nuvem-ia`).
- **Docker**: existe **só dentro do WSL**, não no PATH do PowerShell/Git Bash
  do Windows. Docker Desktop usa backend WSL2, distro **Ubuntu-24.04**; todo
  comando de container precisa ser prefixado por
  `wsl -d Ubuntu-24.04 -e ...`.
- **Python**: **sem venv** — o Python global do Windows é o ambiente do
  projeto (`requirements.txt`/`requirements-dev.txt` instalados nele
  diretamente; confirmado — não há `.venv/` no repositório, embora esteja no
  `.gitignore` caso passe a existir). `pytest` não está no PATH — sempre
  `python -m pytest`.
- **Frontend**: sem processo/build próprio. HTML + JS vanilla
  (`frontend/*.html`, `comum.js`), sem `package.json`. O próprio FastAPI
  (`backend/main.py`) serve as rotas de página (`/admin`, `/nuvem`,
  `/laboratorio`, `/cockpit`, `/linhagem`, confirmadas no código) e os
  estáticos via `StaticFiles` em `/frontend` — que **recusa servir `.html`
  cru** (classe `_FrontendEstatico`, decisão deliberada: cada página só é
  servida pela sua rota autenticada). Subir "frontend" e "backend" é a
  mesma coisa.

### Duas formas de subir

**A) Stack completo via `docker-compose.yml`** — mesma imagem/arquitetura da
VM de produção (porta 8002, Postgres 16 dedicado sem porta publicada,
healthcheck, Alembic no startup — confirmado no `docker-compose.yml` e no
`Dockerfile`). É o que `scripts/verificar_v1.py` e `scripts/verificar_v2.py`
esperam por padrão em `localhost:8002` (confirmado no cabeçalho de
`verificar_v2.py`). Mais fiel a produção, mais lento de iterar: o
`Dockerfile` faz `COPY` de `backend/`/`frontend/`, não monta volume — mudança
de código só entra com rebuild.

```
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/c/Users/maria.watanabe/Documents/nuvem-ia && docker compose up -d --build"
```

Sobe `nuvem-ia-nuvem-app-1` (porta host **8002** → 8000 no container) e
`nuvem-ia-nuvem-db-1` (Postgres, sem porta publicada — só alcançável de
dentro da rede Docker do projeto). Usa o `.env` da raiz automaticamente
(Compose lê `.env` do mesmo diretório); o `.env` local tem valores de
**teste**, nunca produção (seção 5).

URL: `http://localhost:8002/admin`.

**B) `uvicorn` direto no host (bare), contra um Postgres de teste leve** —
caminho mais rápido para iterar backend e para validação manual de tela (foi
o usado na validação do V2.5, ver `memory/validar-tela-no-navegador.md`).
Sem rebuild: editar um `.py` e reiniciar o processo reflete a mudança;
estáticos são lidos do disco a cada request.

Pré-requisito: Postgres de teste de pé no WSL, mapeado em `localhost:5433`
(mesmo banco da suíte pytest — seção 2). Se não existir:

```
wsl -d Ubuntu-24.04 -e docker run -d --name nuvem-teste-db --restart unless-stopped \
  -p 5433:5432 -e POSTGRES_USER=nuvem -e POSTGRES_PASSWORD=teste -e POSTGRES_DB=nuvem_teste \
  postgres:16
```

Depois, no PowerShell (Python global, raiz do projeto) — confirmado em
`backend/database.py`: `DATABASE_URL` é lido direto de `os.environ`, sem
default, então sem essa variável o app nem sobe:

```
$env:DATABASE_URL = "postgresql://nuvem:teste@localhost:5433/nuvem_teste"
$env:ADMIN_PASSWORD = "senha-teste"
$env:SECRET_KEY = "chave-de-teste-nao-usar-em-prod"
python -m uvicorn backend.main:app --port 8003
```

`8003` não é porta fixada em nenhum lugar do projeto — é só a porta livre
usada da última vez (V2.5). Qualquer porta livre serve; o que importa é
**anunciar qual foi escolhida**.

URL: `http://localhost:8003/admin`.

**C) O app da V3 (`catering/`), `uvicorn` bare na porta 8003** — a V3 é uma
FastAPI **própria** (`catering/app.py`), separada da V2 congelada. Não há
serviço no `docker-compose.yml` para ela ainda (isso é o V3.6), então local é
sempre bare.

Mesmo pré-requisito do caminho B: `nuvem-teste-db` de pé em `localhost:5433`.
As migrations da V3 estão na **mesma cadeia** do Alembic, e o app da V3 **não**
as roda no startup — quem migra é o pytest ou um `alembic upgrade head` à mão.

```
$env:DATABASE_URL = "postgresql://nuvem:teste@localhost:5433/nuvem_teste"
$env:CAT_SECRET_KEY = "chave-v3-de-teste-nao-usar-em-prod"
$env:CAT_ADMIN_LOGIN = "maria.watanabe"
$env:CAT_ADMIN_SENHA = "<escolher na hora, não versionar>"
python -m uvicorn catering.app:app --host 127.0.0.1 --port 8003
```

URL: `http://localhost:8003/` — cai em `/login`, porque a partir do V3.4 tudo
exige sessão (só `/health`, `/logo.png` e `/login` ficam abertos).

> **Armadilha: o `.env` NÃO é lido aqui.** O projeto não usa `python-dotenv`
> (confirmado — nenhum `load_dotenv` no código); quem lê o `.env` da raiz é o
> **docker-compose**. Colocar `CAT_SECRET_KEY` no `.env` resolve o caminho A e o
> V3.6, e não resolve o caminho C: no `uvicorn` bare a variável tem que estar
> exportada na sessão do shell. Para não duplicar o valor, carregue o `.env` na
> sessão (não imprime nada):
>
> ```
> Get-Content .env | Where-Object { $_ -match '^\s*[A-Z_]' } | ForEach-Object { $n,$v = $_ -split '=',2; Set-Item "env:$n" $v }
> ```

Sobre as variáveis (detalhe e motivo em `docs/V3_PLANO.md`, lote V3.4):

- **`CAT_SECRET_KEY` é obrigatória** e é **própria da V3** — não é a
  `SECRET_KEY` da V2. Sem ela o app sobe e o `/health` responde, mas login e
  sessão levantam erro nomeando a variável.
- `CAT_ADMIN_LOGIN`/`CAT_ADMIN_SENHA` criam o **primeiro** admin, e só quando a
  `cat_usuarios` está vazia. Depois disso são inertes — não recriam nem trocam
  senha de quem existe. **Senha não vai para o chat nem para commit.**
- `CAT_COOKIE_SECURE` fica desligada local (não há HTTPS).
- **`CAT_FUSO_EXIBICAO`** (padrão `America/Sao_Paulo`) é o fuso em que data e
  hora **aparecem** na tela — o rodapé "De quando é o dado" e a coluna "quando"
  da auditoria. O dado é gravado em UTC (`timestamptz`), que é o certo; esta
  variável só governa a leitura. Sem ela o `to_char` renderizava no fuso da
  sessão do Postgres (`Etc/UTC` no container) e uma carga das 09h45 aparecia
  como **12h45** — medido em 26/ago/2026. Fuso desconhecido
  (`America/SaoPaulo`, sem o `_`) falha nomeando a variável. **Não é o mesmo
  fuso do crontab**, que é UTC de propósito (`docs/DEPLOY.md`).

Usuário depois do primeiro: `python -m catering.seguranca criar --login ...`
(a senha é pedida por `getpass`, nunca por argumento de linha de comando).

> **Porta:** 8002 é a V2 no compose, **8003 é o app da V3**. Uma execução bare da
> V2 (caminho B) usou 8003 no V2.5 — hoje ela deve escolher outra (8004, por
> exemplo) para não colidir com a V3. Qualquer porta livre serve; o que importa é
> **anunciar qual foi escolhida**.

### O que precisa estar rodando antes

| Caminho | Precisa antes |
|---|---|
| A (compose completo) | WSL com integração Docker Desktop ligada; `.env` na raiz; o `nuvem-app` já espera o `nuvem-db` ficar `healthy` (`depends_on: condition: service_healthy`, confirmado no compose) |
| B (uvicorn bare, V2) | WSL com Docker; container `nuvem-teste-db` de pé em `localhost:5433`; `DATABASE_URL`/`ADMIN_PASSWORD`/`SECRET_KEY` exportadas na mesma sessão de shell que roda o `uvicorn` |
| C (uvicorn bare, V3) | o mesmo container `nuvem-teste-db`; schema já migrado (pytest ou `alembic upgrade head`); `DATABASE_URL` e `CAT_SECRET_KEY` exportadas; um usuário em `cat_usuarios` (via `CAT_ADMIN_*` ou o CLI) — sem usuário não há como entrar |

### Dev vs. teste automatizado vs. validação manual

- **Desenvolvimento** (mexendo em código, rodando à mão): caminho B — mais
  rápido, banco isolado, sem rebuild.
- **Teste automatizado** (pytest): usa o **mesmo** Postgres de teste do
  caminho B (`localhost:5433`), mas não sobe `uvicorn` — o `TestClient` do
  FastAPI (confirmado em `tests/conftest.py`, fixture `cliente`) chama a
  aplicação em processo, sem servidor HTTP real. Ver seção 2.
- **Validação manual/visual** (navegador, Playwright): caminho B na prática
  (mais rápido de religar); caminho A quando o objetivo for validar
  especificamente o comportamento "igual produção" (Dockerfile, variáveis
  via compose, `--no-access-log`) — por exemplo antes de um deploy.

---

## 2. Como testar

### Testes automatizados

- **Comando**: `python -m pytest -q` (não `pytest` sozinho — não está no
  PATH desta máquina).
- **Ao fechar um lote da V3**, a suíte do lote basta:
  `python -m pytest tests/test_catering_*.py tests/test_migracao.py`
  (188 testes, ~4min30 em 25/ago/2026, contra ~13min29 da suíte inteira). O
  motivo e o que o `test_migracao.py` faz ali estão em `docs/V3_PLANO.md`,
  seção "Qual suíte roda ao fechar um lote da V3". A suíte **completa** volta a
  ser obrigatória antes de um deploy.
- **A suíte inteira tem 2 `xfail` esperados** (`test_volumetria.py` e
  `test_volumetria_router.py`, V2 congelada) — verde com `xfailed`, e não
  vermelho. Ver `docs/V3_PLANO.md`.
- **Ambiente**: Python global do Windows, sem venv.
- **Dependências**: `pip install -r requirements-dev.txt` (já puxa
  `requirements.txt`). **Atenção**: `alembic` é dependência de runtime
  (confirmado em `requirements.txt`, `alembic==1.14.1`), não só de teste —
  se faltar, o erro é enganoso (`cannot import name 'command' from
  'alembic'`, porque a pasta `alembic/` do próprio repo vira namespace
  package). Já causou confusão real, registrada em
  `memory/suite-testes-local.md`.
- **Banco**: Postgres real, **nunca mock** (decisão de princípio do
  projeto). Container `nuvem-teste-db`, banco `nuvem_teste`, usuário
  `nuvem`. As fixtures em `tests/conftest.py` fazem `DROP SCHEMA public
  CASCADE` + `CREATE SCHEMA` e rodam `alembic upgrade head` + seeds antes de
  cada teste que precisa de banco (fixture `banco_migrado`). Pode ser
  trocado por `TEST_DATABASE_URL`, mas **nunca apontar para um banco com
  dado real** — o dado é destruído a cada teste.
- **Porta**: 5433 (host) → 5432 (container).
- **Falha de ambiente vs. regressão real**: uma suíte inteira estourando
  `OperationalError`/`connection refused` em dezenas de arquivos não
  relacionados é quase sempre o container do banco fora do ar (o Docker
  Desktop já derrubou esse container sozinho por inatividade — achado
  registrado em `memory/suite-testes-local.md`) — **não** é regressão de
  código. Regressão real aparece isolada, com mensagem de asserção do
  próprio teste. Antes de reportar falha: confirmar
  `wsl -d Ubuntu-24.04 -e docker ps --filter name=nuvem-teste-db` mostra
  `Up`/`healthy`.
- **Em execuções longas**, o Docker Desktop já derrubou o container de
  teste *no meio* da suíte (achado registrado em
  `memory/suite-testes-local.md`, com uma rodada que gastou minutos em
  timeout de conexão antes de perceberem que era o container, não o
  código). Em suítes longas, vale checar o container periodicamente
  durante a execução, não só antes.

### Carga da volumetria de catering (V3.5)

O carregador é um comando à parte — não sobe processo nenhum, não abre porta, e
termina sozinho. Duas fontes, a mesma interface:

```
# CSV (as extrações de 21/ago em docs/Analise) — continua valendo igual
python -m catering.carga --de docs/Analise
python -m catering.carga --de docs/Analise --incremental

# DW Oracle
python -m catering.carga --fonte oracle --sondar        # SÓ lê o DW
python -m catering.carga --fonte oracle                 # carga completa
python -m catering.carga --fonte oracle --incremental
python -m catering.carga --fonte oracle --movimento rec
```

Variáveis, e o que cada uma exige:

| comando | precisa de |
|---|---|
| `--fonte csv` | `DATABASE_URL` |
| `--fonte oracle --sondar` | `DW_USER` e `DW_SENHA` — **e mais nada**. Não toca no Postgres |
| `--fonte oracle` (carga) | `DATABASE_URL` + `DW_USER` + `DW_SENHA` |

Faltando qualquer uma delas, o comando **recusa na entrada** com a orientação de
como exportar — e não com `KeyError: 'DATABASE_URL'` no meio da rodada, que foi
o que aconteceu duas vezes em 26/ago/2026. `--sondar` não paga o pedágio do
`DATABASE_URL`, porque não toca no Postgres.

`DW_HOST`, `DW_PORTA` e `DW_BANCO` têm padrão no código
(`oracleprd-aws.superfrio.com.br:1521/pdwgener`, Oracle 12.2 em modo thin, sem
Instant Client). `DW_TABELA_REC`/`DW_TABELA_EXP` também têm padrão — só existem
para trocar de versão do objeto sem commit.

**`DW_ANO_MINIMO` (padrão 2026)** é o primeiro ano que a carga lê, por
`nk_calendario`. A V3 lê de 2026 para frente (decisão da Maria, 25/ago/2026);
para comparar 2025 com 2026, `$env:DW_ANO_MINIMO = "2025"` na mesma sessão e
rodar a carga de novo — ela traz o passado sem tocar em código. **Subir o piso
de volta não apaga o que já entrou:** a carga só insere e atualiza, então
desfazer exige `DELETE` à mão. Ano inválido (`26`, `20226`) falha nomeando a
variável, em vez de carregar tudo ou nada em silêncio.

> **A mesma armadilha do `.env` do caminho C vale aqui**: o projeto não usa
> `python-dotenv`, então num `python` bare a credencial tem que estar exportada
> na sessão do shell. Carregue o `.env` na sessão (não imprime nada):
>
> ```
> Get-Content .env | Where-Object { $_ -match '^\s*[A-Z_]' } | ForEach-Object { $n,$v = $_ -split '=',2; Set-Item "env:$n" $v }
> $env:DATABASE_URL = "postgresql://nuvem:teste@localhost:5433/nuvem_teste"
> ```

Três coisas que vale saber antes de rodar a carga contra o DW nesta máquina:

1. **O DW é produção, e a leitura é somente leitura por construção.** O módulo
   só emite `SELECT`, com guarda estática e de runtime na suíte
   (`tests/test_catering_oracle.py`). Mesmo assim, quem roda a carga contra o DW
   é a Maria — a IA não conecta nele.
2. **O banco de destino local é o `nuvem_teste`, que o pytest zera.** Carregar
   78 mil linhas do DW e depois rodar a suíte apaga o que foi carregado. Isso é
   esperado, não defeito: o schema é recriado a cada teste.
3. **A primeira rodada contra o Oracle é completa, mesmo com `--incremental`.**
   O V3.5 passou a gravar o nome qualificado em `cat_cargas.tabela_origem`, que
   é a chave da marca d'água — então não existe marca d'água anterior com esse
   nome. Foi decidido assim (ver `docs/V3_PLANO.md`, A-7).

Depois da carga, para ver o dado real na tela: caminho C acima, e o bloco
"De quando é o dado" no rodapé passa a dizer `oracle` em vez de `csv`.

**Encerramento:** nada a encerrar — o comando é síncrono e sai com código 0 ou 1.
Rodada que falha fica registrada em `cat_cargas` com `status='erro'` e a
mensagem; `SELECT * FROM cat_cargas ORDER BY id DESC LIMIT 5` conta a história.

### Validação da aplicação

- **Como subir**: caminho B da seção 1 (uvicorn bare, porta livre
  anunciada), banco de teste semeado com dado plausível (múltiplas
  unidades, competências, clientes e um "balde sem cliente") — banco vazio
  não mostra nada para validar.
- **Login primeiro**: `/cockpit`, `/nuvem`, `/laboratorio` e `/linhagem`
  redirecionam para `/admin` se não autenticado (cookie `nuvem_sessao`,
  HMAC-assinado, **12h de validade** — confirmado em `backend/auth.py`,
  `SESSAO_DURACAO_SEGUNDOS = 12 * 3600`). Logar em `/admin` com a
  `ADMIN_PASSWORD` usada na subida antes de navegar pelas outras rotas.
- **O que validar** (lição registrada em
  `memory/validar-tela-no-navegador.md`: revisão de código sozinha **não**
  pega isso): layout renderizado de fato, ausência de erro no console JS,
  rótulos que dependem de dado real (RMSPII, RMSPIII e RMSPV compartilham o
  mesmo nome cadastral "Barueri/SP" — já causou confusão real), truncamento
  de texto em gráfico, tema escuro, filtros mexendo o DOM de verdade e —
  quando o fluxo gera arquivo para download — interceptar
  `URL.createObjectURL` em vez de tentar salvar o arquivo.
- **Playwright/browser**: MCP do Playwright disponível nesta sessão
  (`browser_navigate`, `browser_snapshot`, `browser_take_screenshot`,
  `browser_evaluate`, `browser_console_messages`) — mecanismo já usado e
  validado no V2.5.

---

## 3. Como parar tudo

Princípio: **toda execução iniciada por uma IA tem que ter um encerramento
explícito anunciado junto do início** — nenhum `uvicorn`, container ou
watcher fica rodando "por conta própria" depois que a tarefa termina, a
menos que a Maria peça explicitamente para manter (e mesmo assim, com o
comando de encerramento relembrado na resposta).

| O que foi iniciado | Como encerrar | Como confirmar que parou |
|---|---|---|
| `uvicorn` bare no host (caminho B) | Primeiro plano: `Ctrl+C`. Background: `Stop-Process -Id <PID>` (PID anotado no início) | `Get-NetTCPConnection -LocalPort <porta> -ErrorAction SilentlyContinue` vazio; ou `curl` na URL falha |
| Stack `docker compose` (caminho A) | `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/c/Users/maria.watanabe/Documents/nuvem-ia && docker compose down"` (mantém o volume do banco) | `wsl -d Ubuntu-24.04 -e docker ps --filter name=nuvem-ia` deve vir vazio |
| Container standalone `nuvem-teste-db` (criado com `docker run`, não gerenciado por `docker compose down`) | `wsl -d Ubuntu-24.04 -e docker stop nuvem-teste-db` (`docker rm` depois, se for descartar de vez) | `wsl -d Ubuntu-24.04 -e docker ps --filter name=nuvem-teste-db` sem `Up` |
| WSL em si (opcional, mais agressivo) | `wsl --shutdown` — derruba **todo** o Docker Desktop, inclusive containers de **outros** projetos na mesma máquina (Conciliador, Hub) | `wsl -l -v` mostra `Stopped` |

### Processo órfão (uvicorn/Python)

```
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Select-Object ProcessId, CommandLine
```

Procurar `CommandLine` contendo `uvicorn` e `backend.main:app`. `taskkill
/PID` ou `Stop-Process -Id` nesse PID.

### Portas que continuaram ocupadas

```
Get-NetTCPConnection -LocalPort 8002,8003,5433 -ErrorAction SilentlyContinue |
  Select-Object LocalPort, OwningProcess
```

Cruzar `OwningProcess` com `Get-Process -Id <n>` (pode ser
`com.docker.backend.exe` no caso de porta publicada por container, não
necessariamente um processo Python).

### Containers que ficaram rodando

```
wsl -d Ubuntu-24.04 -e docker ps
```

Qualquer coisa em `Up` que não devia estar. **`docker ps -a` sem filtro**
numa máquina que também roda outros projetos (Conciliador/Hub) lista
containers deles também — não confundir escopo. Pastas de trabalho antigas
podem deixar containers/volumes órfãos com nomes parecidos — antes de
presumir ambiente limpo, listar por nome do projeto atual, não assumir pelo
que "esta sessão iniciou".

---

## 4. "O que está de pé" prevalece sobre "o que eu iniciei"

Achado real (19/ago/2026, ver nota no topo do documento): `restart:
unless-stopped` (presente nos dois serviços do `docker-compose.yml`) só
evita reinício automático se o container foi parado *deliberadamente*
(`docker stop`/`docker compose down`). Se ele estava rodando quando o
Docker Desktop/WSL caiu (fechamento do Windows, `wsl --shutdown`, crash), o
daemon o recria sozinho na próxima vez que o Docker Desktop subir — mesmo
dias depois, disparado por qualquer comando, inclusive um `docker ps` de
diagnóstico.

Consequência prática: nunca concluir que o projeto está "limpo" só porque
nenhum comando de start foi dado na sessão atual — checar `docker ps`
(o que está de pé agora), não confiar em "nada foi iniciado aqui". E
`docker stop` isolado não é garantia permanente contra esse comportamento;
a forma correta de desligar de vez o stack do compose é `docker compose
down`, não só `stop` de cada serviço.

## 5. Ao subir localmente a pedido da Maria

1. **Anunciar antes de rodar**: qual caminho (A ou B), qual porta, qual URL
   e — se container — qual nome. Vale mesmo em background.
2. **Preferir primeiro plano** quando fizer sentido para a sessão (ela olha
   na hora, `Ctrl+C` encerra sozinho). Background só quando ela precisar
   continuar pedindo outras coisas em paralelo.
3. **Se rodar em background, devolver na resposta** (não só na chamada de
   ferramenta): comando exato, PID ou nome do container, porta, URL, e o
   comando de encerramento pronto para copiar.
4. **Nunca subir um segundo processo fazendo o mesmo papel** sem avisar que
   já existe um — checar `docker ps`/portas ocupadas antes (seção 4: "nada
   iniciado nesta sessão" não significa "nada rodando").
5. **Ao final da tarefa** (ou quando ela disser "pode parar"), encerrar
   proativamente e confirmar.
6. **Se ela pedir para deixar rodando**, tudo bem — mas repetir nessa
   mesma resposta o comando de encerramento.

---

## 6. Segurança — separação DEV/TEST de produção

**O que já existe estruturalmente (não depende de disciplina)**:

- Produção roda numa VM Linux à parte (IP interno documentado em
  `memory/vm-nuvem-ia.md` — não repetido aqui), acessível só por SSH com
  deploy key específica do repo, **somente leitura de git**
  (`docs/DEPLOY.md`, Passo 2 — "Allow write access" desmarcado). Não existe
  esse SSH configurado nesta máquina de desenvolvimento.
- O Postgres de produção, como o de dev/teste, **não publica porta nenhuma
  no host** — no `docker-compose.yml` só `nuvem-app` tem `ports:`
  (confirmado). Um `DATABASE_URL` mal configurado localmente não teria como
  alcançar o banco de produção pela rede.
- O `.env` local (raiz, não versionado — está no `.gitignore`, confirmado)
  só tem valores de teste. O `.env` de produção só é criado **na própria
  VM**, na hora do deploy (`docs/DEPLOY.md`, Passo 4), com segredos gerados
  ali — nunca existiu cópia dele neste repositório local.
- As credenciais `GRAPH_*` no `.env` local são reais, mas com concessão
  **somente leitura** no Azure (`Sites.Selected` + `read`, confirmado em
  `.env.example`) — o próprio Graph recusa escrita, e a suíte
  (`tests/test_graph_datahub.py`) tem uma guarda estática e uma de runtime
  que reprovam qualquer `put`/`patch`/`delete` no cliente (confirmado no
  código do teste).

**O que depende de disciplina (risco real, não coberto por código)**:

- Nada no código impede colar o `DATABASE_URL` ou o IP da VM de produção
  num terminal local por hábito (confundir uma sessão "testar local" com
  uma sessão de deploy).
- Nada impede, hoje, copiar um `.env` de produção para esta máquina
  manualmente (fora do fluxo documentado).

**Proposta ainda não implementada** (registrada aqui como hipótese, não
como trava ativa): tratar como bandeira vermelha qualquer `.env` cujo
conteúdo não pareça claramente de teste, e recusar compor comandos
(`ssh`/`docker compose`/consulta direta) cujo alvo bata com o host de
produção — exigindo confirmação humana redobrada. Isso depende de uma
decisão de política mais ampla (ver `POLITICA_GLOBAL_IA.md`, seção 6); não
é algo que este documento, sozinho, ative.

---

## 7. Tabela final

| Operação | Ambiente | Comando | Porta | Como confirmar | Como encerrar |
|---|---|---|---|---|---|
| Subir aplicação (stack completo, modo "igual produção") | WSL (Ubuntu-24.04) + Docker Desktop | `wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/c/Users/maria.watanabe/Documents/nuvem-ia && docker compose up -d --build"` | 8002 (app); banco sem porta publicada | `docker compose ps` (ambos `healthy`) ou `curl localhost:8002/health` | `docker compose down` (mantém volume) / `down -v` (apaga banco — não usar sem confirmar) |
| Subir aplicação (dev rápido, bare) | Windows host, Python global (sem venv) | `$env:DATABASE_URL=...; $env:ADMIN_PASSWORD=...; $env:SECRET_KEY=...; python -m uvicorn backend.main:app --port 8003` | 8003 (qualquer porta livre, anunciada) | `curl localhost:8003/health` | `Ctrl+C`, ou `Stop-Process -Id <PID>` se em background |
| Testes automatizados | Windows host, Python global; banco no WSL | `python -m pytest -q` | usa o banco em 5433 (não abre porta própria) | saída `N passed` do próprio pytest | não sobe processo persistente — nada a encerrar além do banco de teste, se for descartá-lo |
| Banco de teste (pytest / validação manual) | WSL (Ubuntu-24.04) Docker | `wsl -d Ubuntu-24.04 -e docker run -d --name nuvem-teste-db --restart unless-stopped -p 5433:5432 -e POSTGRES_USER=nuvem -e POSTGRES_PASSWORD=teste -e POSTGRES_DB=nuvem_teste postgres:16` | 5433 | `wsl -d Ubuntu-24.04 -e docker ps --filter name=nuvem-teste-db` | `wsl -d Ubuntu-24.04 -e docker stop nuvem-teste-db` (+ `docker rm` se for descartar) |
| Frontend | Sem processo próprio — servido pelo mesmo backend | (nenhum comando extra) | mesma porta do backend escolhido acima | abrir `/admin` no navegador, checar console sem erro | encerra junto com o backend |

---

## O que fica como hipótese (não implementado)

- A denylist técnica de host/IP de produção e a checagem automática de
  `working_dir` antes de `docker compose up` (seção 6) são propostas, não
  travas ativas.
- Detalhes de topologia WSL/Docker (containers específicos hoje de pé, além
  de `nuvem-teste-db`) não foram reconferidos na escrita deste documento —
  vêm da investigação de 19/ago/2026 citada no topo. Antes de agir sobre
  "o que está rodando agora", reconferir com `docker ps` (seção 4), não
  presumir a partir deste texto.
